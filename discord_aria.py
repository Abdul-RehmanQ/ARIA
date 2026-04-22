import asyncio
import os
import re
import tempfile
from pathlib import Path

import discord
from dotenv import load_dotenv

# Load environment values before importing modules that use API keys.
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from audio.stt import transcribe_audio_file
from brain.llm_router import ask_aria

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
AUTHORIZED_USER_ID_RAW = os.getenv("AUTHORIZED_USER_ID")
AUDIO_EXTENSIONS = {".ogg", ".wav", ".mp3", ".m4a", ".webm", ".flac", ".aac"}
MESSAGE_SEND_MIN_INTERVAL_SECONDS = 1.0
STATUS_DEDUP_WINDOW_SECONDS = 8.0

CHANNEL_SEND_LOCKS = {}
CHANNEL_SEND_STATE = {}
ACTIVE_CHANNEL_REQUESTS = set()


def _parse_authorized_user_id(raw_value):
    if raw_value is None:
        return None

    cleaned = str(raw_value).strip()

    # Accept common paste formats like <@123...>, bot123..., or plain digits.
    match = re.search(r"(\d{17,20})", cleaned)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None

    try:
        return int(cleaned)
    except (TypeError, ValueError):
        return None


def _first_audio_attachment(attachments):
    for attachment in attachments:
        content_type = (attachment.content_type or "").lower()
        suffix = Path(attachment.filename).suffix.lower()
        if content_type.startswith("audio/") or suffix in AUDIO_EXTENSIONS:
            return attachment
    return None


async def _send_throttled(channel, text, dedupe=False):
    channel_id = channel.id
    lock = CHANNEL_SEND_LOCKS.setdefault(channel_id, asyncio.Lock())

    async with lock:
        loop = asyncio.get_running_loop()
        state = CHANNEL_SEND_STATE.setdefault(
            channel_id,
            {"last_sent_at": 0.0, "status_times": {}}
        )

        now = loop.time()
        wait_seconds = MESSAGE_SEND_MIN_INTERVAL_SECONDS - (now - state["last_sent_at"])
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

        now = loop.time()
        if dedupe:
            status_times = state["status_times"]
            cutoff = now - STATUS_DEDUP_WINDOW_SECONDS
            for message_text, sent_at in list(status_times.items()):
                if sent_at < cutoff:
                    del status_times[message_text]

            previous_sent_at = status_times.get(text)
            if previous_sent_at and (now - previous_sent_at) < STATUS_DEDUP_WINDOW_SECONDS:
                return False

        await channel.send(text)

        sent_at = loop.time()
        state["last_sent_at"] = sent_at
        if dedupe:
            state["status_times"][text] = sent_at
        return True


def _chunk_text(text, limit=1900):
    if not text:
        return [""]

    chunks = []
    current = ""

    for line in text.splitlines(keepends=True):
        if len(current) + len(line) <= limit:
            current += line
            continue

        if current:
            chunks.append(current)
            current = ""

        while len(line) > limit:
            chunks.append(line[:limit])
            line = line[limit:]

        current = line

    if current:
        chunks.append(current)

    return chunks


async def _send_response(channel, text):
    if len(text) <= 2000:
        await _send_throttled(channel, text)
        return

    chunks = _chunk_text(text)
    if len(chunks) <= 6:
        for chunk in chunks:
            await _send_throttled(channel, chunk)
        return

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt", encoding="utf-8") as handle:
        handle.write(text)
        temp_path = handle.name

    try:
        await _send_throttled(channel, "Response was too long, sending as a text file.", dedupe=True)
        await channel.send(file=discord.File(temp_path, filename="aria_response.txt"))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


AUTHORIZED_USER_ID = _parse_authorized_user_id(AUTHORIZED_USER_ID_RAW)
EFFECTIVE_AUTHORIZED_USER_ID = AUTHORIZED_USER_ID

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)


async def _resolve_owner_user_id():
    try:
        app_info = await bot.application_info()
    except Exception as e:
        print(f"[!] Could not fetch Discord application info: {e}")
        return None

    owner = getattr(app_info, "owner", None)
    owner_id = getattr(owner, "id", None)
    return int(owner_id) if owner_id else None


@bot.event
async def on_ready():
    global EFFECTIVE_AUTHORIZED_USER_ID

    print(f"[+] Discord bot connected as {bot.user}")

    if bot.user and AUTHORIZED_USER_ID == bot.user.id:
        print("[!] AUTHORIZED_USER_ID matches the bot account ID. Falling back to application owner user ID.")
        owner_user_id = await _resolve_owner_user_id()
        if owner_user_id:
            EFFECTIVE_AUTHORIZED_USER_ID = owner_user_id
            print(f"[i] Using application owner user ID: {owner_user_id}")
        else:
            EFFECTIVE_AUTHORIZED_USER_ID = None
            print("[!] Could not infer application owner user ID. Set AUTHORIZED_USER_ID manually.")
        return

    if AUTHORIZED_USER_ID is None:
        print("[!] AUTHORIZED_USER_ID is missing or invalid. Falling back to application owner user ID.")
        owner_user_id = await _resolve_owner_user_id()
        if owner_user_id:
            EFFECTIVE_AUTHORIZED_USER_ID = owner_user_id
            print(f"[i] Using application owner user ID: {owner_user_id}")
        else:
            EFFECTIVE_AUTHORIZED_USER_ID = None
            print("[!] Could not infer application owner user ID. Set AUTHORIZED_USER_ID manually.")
        return

    EFFECTIVE_AUTHORIZED_USER_ID = AUTHORIZED_USER_ID
    print(f"[i] Authorized user ID loaded: {EFFECTIVE_AUTHORIZED_USER_ID}")

    # If this stays False in your app settings, message.content may be empty in guild channels.
    print(f"[i] message_content intent in code: {bot.intents.message_content}")

    if not bot.guilds:
        print("[!] Bot is not currently in any guilds.")
    for guild in bot.guilds:
        print(f"[guild] {guild.name} ({guild.id})")
        me = guild.get_member(bot.user.id) if bot.user else None
        if me is None:
            print("[!] Could not resolve bot member object in this guild.")
            continue

        visible_text_channels = 0
        for channel in guild.text_channels:
            perms = channel.permissions_for(me)
            if perms.view_channel:
                visible_text_channels += 1
            print(
                f"  [channel] #{channel.name} ({channel.id}) "
                f"view={perms.view_channel} send={perms.send_messages} "
                f"history={perms.read_message_history} attach={perms.attach_files}"
            )

        if visible_text_channels == 0:
            print("[!] Bot cannot view any text channels in this guild.")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    print(
        "[msg] "
        f"author={message.author.id} "
        f"guild={getattr(message.guild, 'id', None)} "
        f"channel={getattr(message.channel, 'id', None)} "
        f"content_len={len(message.content or '')} "
        f"attachments={len(message.attachments)}"
    )

    normalized_text = (message.content or "").strip().lower()
    if normalized_text in {"!whoami", "whoami", "/whoami"}:
        authorized_text = (
            str(EFFECTIVE_AUTHORIZED_USER_ID)
            if EFFECTIVE_AUTHORIZED_USER_ID is not None
            else "not configured"
        )
        await _send_throttled(
            message.channel,
            f"Your Discord user ID is: {message.author.id}\n"
            f"Current authorized ID is: {authorized_text}"
        )
        return

    if EFFECTIVE_AUTHORIZED_USER_ID is None:
        print("[i] Ignoring message because EFFECTIVE_AUTHORIZED_USER_ID is not set.")
        return

    if message.author.id != EFFECTIVE_AUTHORIZED_USER_ID:
        print(
            "[i] Ignored unauthorized message: "
            f"author={message.author.id}, expected={EFFECTIVE_AUTHORIZED_USER_ID}"
        )
        return

    channel_id = message.channel.id
    if channel_id in ACTIVE_CHANNEL_REQUESTS:
        await _send_throttled(
            message.channel,
            "I am still processing your previous request. Please wait a moment.",
            dedupe=True
        )
        return

    ACTIVE_CHANNEL_REQUESTS.add(channel_id)

    try:
        user_text = message.content.strip()
        audio_attachment = _first_audio_attachment(message.attachments)

        if not user_text and not audio_attachment:
            await _send_throttled(
                message.channel,
                "I received your message but content was empty. "
                "Enable Message Content Intent in Discord Developer Portal for this bot, then restart me."
            )
            return

        if audio_attachment:
            suffix = Path(audio_attachment.filename).suffix or ".ogg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_audio_path = temp_file.name

            try:
                await audio_attachment.save(temp_audio_path)
                await _send_throttled(message.channel, "Transcribing audio note...", dedupe=True)
                transcribed_text = await asyncio.to_thread(transcribe_audio_file, temp_audio_path)
            finally:
                if os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)

            if not transcribed_text:
                await _send_throttled(message.channel, "I could not transcribe that audio file.")
                return

            user_text = transcribed_text
            await _send_throttled(message.channel, f"Transcribed: {user_text}")

        if not user_text:
            return

        loop = asyncio.get_running_loop()

        def update_callback(status_text):
            try:
                asyncio.run_coroutine_threadsafe(
                    _send_throttled(message.channel, status_text, dedupe=True),
                    loop
                )
            except RuntimeError:
                pass

        await _send_throttled(message.channel, "Processing request...", dedupe=True)
        final_response = await asyncio.to_thread(ask_aria, user_text, update_callback)
        await _send_response(message.channel, final_response)
    finally:
        ACTIVE_CHANNEL_REQUESTS.discard(channel_id)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN is missing in .env")

    bot.run(BOT_TOKEN)


if __name__ == "__main__":
    main()
