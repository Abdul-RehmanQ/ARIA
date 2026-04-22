# ARIA (Adaptive Real-time Intelligence Assistant)

This README reflects the current codebase and runtime behavior in this repository.

---

## 1) Current Architecture

ARIA has two active entry points:

- **`main.py`**: Local desktop assistant (push-to-talk + spoken replies).
- **`discord_aria.py`**: Remote Discord assistant (text + audio attachment support).

Core modules:

- **`brain/llm_router.py`**: Central router for chat history, tool schemas, model failover, and tool execution orchestration.
- **`actions/system_ops.py`**: OS/API action layer ("tools" that the model can call).
- **`audio/stt.py`**: Speech-to-text using Groq Whisper (`whisper-large-v3-turbo`), including:
  - `listen_and_transcribe()` for live microphone push-to-talk
  - `transcribe_audio_file()` for Discord voice/audio files
- **`audio/tts.py`**: Azure Speech TTS with locked, synchronous playback through PyAudio to prevent overlapping voice output.

Utility scripts:

- **`api_validation.py`**: Validates API authentication for Gemini, Cohere, Groq, OpenRouter, and Azure Speech.
- **`check_models.py`**: Quick Groq models listing check.
- **`audio_check.py`**: Local microphone/speaker diagnostic script.

---

## 2) LLM Router (`brain/llm_router.py`)

Current behavior:

- Maintains rolling chat history with a strict system prompt optimized for TTS output.
- Uses **tool calling** with JSON schemas mapped to Python functions in `actions/system_ops.py`.
- Enables **parallel tool calls** when tool invocation is requested.
- Supports model failover via `safe_chat_completion()` across this ordered list:
  1. `llama-3.3-70b-versatile`
  2. `meta-llama/llama-4-scout-17b-16e-instruct`
  3. `llama-3.1-8b-instant`
  4. `mixtral-8x7b-32768`
  5. `gemma2-9b-it`
- Handles duplicate tool-invocation suppression for identical repeated calls in a single turn.
- Accepts an optional `update_callback` (used by Discord integration to stream status updates like `Executing: <tool>...`).

---

## 3) Active Tool Catalog (`actions/system_ops.py`)

### Information
- `get_current_time()`
- `get_weather(city_name)`

### Windows/App Control
- `take_screenshot()`
- `open_application(app_name)`
- `close_application(app_name)`
- `change_system_volume(volume_percent)`

### Spotify Control
- `play_spotify_media(query, media_type="track")` (`track`, `album`, `playlist`, `liked_songs`)
- `control_spotify(command, volume_percent=None)`

### File System
- `list_directory(path)`
- `read_file(path)` (text-only, truncates long files)
- `create_file(path, content)`

---

## 4) Discord Integration (`discord_aria.py`)

The Discord bot currently includes:

- Authorized-user gate (`AUTHORIZED_USER_ID`) so only one user can trigger ARIA.
- Owner-ID fallback when `AUTHORIZED_USER_ID` is missing/invalid.
- Support for:
  - direct text messages
  - audio attachments (`.ogg`, `.wav`, `.mp3`, `.m4a`, `.webm`, `.flac`, `.aac`)
- Per-channel request lock to avoid concurrent overlapping requests.
- Message throttling and short-window deduping for repeated status updates.
- Long-response handling:
  - chunking for messages over Discord limits
  - automatic `.txt` file upload for very long responses

---

## 5) Environment Variables (`.env`)

Required for core desktop/Discord operation:

- `GROQ_API_KEY`
- `AZURE_SPEECH_KEY`
- `AZURE_SPEECH_REGION`
- `AZURE_SPEECH_VOICE` (optional; defaults in code)
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIPY_REDIRECT_URI`
- `DISCORD_BOT_TOKEN` (for Discord mode)
- `AUTHORIZED_USER_ID` (for Discord mode)

Used by validation utilities (`api_validation.py`):

- `GEMINI_API_KEY`
- `COHERE_API_KEY`
- `OPENROUTER_API_KEY`

---

## 6) Run Modes

Install dependencies:

```bash
pip install -r requirements.txt
```

Run local desktop mode:

```bash
python main.py
```

Run Discord mode:

```bash
python discord_aria.py
```

Optional diagnostics:

```bash
python api_validation.py
python check_models.py
python audio_check.py
```
