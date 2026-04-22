# Discord Integration Plan for ARIA

This document outlines the step-by-step architecture and implementation plan for transforming ARIA into a remote-accessible AI agent via Discord.

## Phase 1: Environment & Discord Setup

### 1.1 Discord Developer Portal Setup
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** and name it "ARIA".
3. Navigate to the **Bot** tab:
   - Click **Reset Token** and copy the new `DISCORD_BOT_TOKEN`.
   - Scroll down to **Privileged Gateway Intents** and enable **Message Content Intent**. This is critical for the bot to read your text messages.
4. Navigate to **OAuth2 -> URL Generator**:
   - Check `bot` under Scopes.
   - Check `Administrator` (or explicitly `Read Messages/View Channels`, `Send Messages`, `Read Message History`, `Attach Files`) under Bot Permissions.
   - Copy the generated URL, paste it into your browser, and invite the bot to your private Discord server.

### 1.2 Environment Variables
Add the following to your local `.env` file:
```env
DISCORD_BOT_TOKEN=your_copied_token_here
AUTHORIZED_USER_ID=your_discord_user_id  # Ensures only YOU can trigger ARIA
```

### 1.3 Dependencies
Install the required Discord library:
```bash
pip install discord.py aiohttp
```

---

## Phase 2: Core Architecture Modifications

### 2.1 Updating `brain/llm_router.py`
Currently, `ask_aria()` uses standard `print()` statements for tool execution logs. We need to implement an optional callback so the Discord bot can receive live status updates.

*   **Change signature:** Update the function definition to: 
   `def ask_aria(user_input, update_callback=None):`
*   **Trigger callback:** Wherever a tool is executed (around line 306), add:
    ```python
    if update_callback:
        update_callback(f"⚙️ Executing: {function_name}...")
    ```
*   **Threading Wrapper:** Because `discord.py` is asynchronous (`async`/`await`) and `ask_aria` is synchronous, we will write a small async wrapper in the bot script that uses `asyncio.to_thread()` to run the LLM logic in the background without freezing the Discord bot.

### 2.2 Updating `audio/stt.py`
Currently, `stt.py` relies on `pyaudio` and `keyboard` to capture live microphone audio. We will create a new function specifically for processing pre-recorded Discord voice notes.

*   **New Function:** `def transcribe_audio_file(file_path):`
    This function will skip the PyAudio recording phase and directly send the provided audio file (which the Discord bot downloaded) to the Groq Whisper API.

---

## Phase 3: Creating `discord_aria.py`

We will create a new main entry point specifically for remote access. You can run this instead of (or alongside) `main.py`.

### Step-by-Step Logic Flow
1. **Initialize Bot:** Create a standard Discord bot instance listening to the `on_message` event.
2. **Security Check:** If `message.author.id != AUTHORIZED_USER_ID`, ignore the message.
3. **Handle Voice Notes:** 
   - Check if `message.attachments` contains an audio file (Discord voice notes are `.ogg`).
   - If yes, use `attachment.save("temp_discord.ogg")`.
   - Pass `temp_discord.ogg` to `transcribe_audio_file()`.
   - Set `user_text = transcribed_text`.
4. **Handle Text Messages:**
   - If there are no attachments, simply use `user_text = message.content`.
5. **Execute ARIA:**
   - Define a small callback function inside the discord event loop that sends an embed or text message back to the channel: `await message.channel.send("...")`.
   - Call `ask_aria(user_text, update_callback=my_callback)` in a background thread.
6. **Return Output:**
   - Take the `final_response` from `ask_aria()` and send it as a Discord message. 
   - If the output exceeds Discord's 2000 character limit, automatically chunk it or send it as an attached `.txt` file.

---

## Phase 4: Implementation & Testing

1. Write `discord_aria.py`.
2. Apply the callback modifications to `llm_router.py`.
3. Add the file transcription function to `stt.py`.
4. Run `python discord_aria.py`.
5. Open the Discord app on your phone, navigate to your private server, and send a voice note saying "Take a screenshot and list the files on my desktop."
6. Verify that ARIA streams the intermediate steps (⚙️ Executing take_screenshot... ⚙️ Executing list_directory...) and replies with the final text output!
