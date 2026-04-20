# ARIA (Adaptive Real-time Intelligence Assistant): System Documentation

This document serves as a complete technical reference for the ARIA AI Assistant project. It outlines the system architecture, the purpose of each module, and a detailed breakdown of every tool (function) currently available to the AI. 

You can provide this document to any LLM (like ChatGPT, Claude, or Llama) as context so it immediately understands the entire codebase and can help you make modifications or add new features safely.

---

## 1. System Architecture

The project is structured into modular Python files to separate audio processing, AI reasoning, and OS-level physical actions.

### **Core Modules**
* **`main.py`**: The entry point. It loads environment variables (`.env`), initializes the system, and runs an infinite loop. It waits for the user to hold the Spacebar, records audio, transcribes it, sends the text to the LLM router, and then speaks the LLM's text response aloud.
* **`audio/stt.py` (Speech-to-Text)**: Handles the "Push-to-Talk" logic using the `keyboard` and `pyaudio` libraries. It records microphone input only while the Spacebar is held down and sends the raw audio to the **Groq Whisper** API for lightning-fast transcription.
* **`audio/tts.py` (Text-to-Speech)**: Takes text from the LLM and converts it to highly realistic spoken audio using the **Azure Cognitive Services (Speech)** API. *Note: The TTS function is wrapped in a strict `threading.Lock()` and utilizes raw PyAudio WAV streaming to guarantee the Python thread physically blocks until the speakers finish playing. This prevents overlapping audio.*
* **`brain/llm_router.py`**: The central "Brain". It manages the conversation history, holds the JSON schemas defining what tools the AI can use, and communicates with the **Groq API** (Llama models). It parses the AI's tool requests and passes them to the physical system execution script.
* **`actions/system_ops.py`**: The "Hands". This file contains all the pure Python functions that interact with the Windows Operating System, external APIs, and the file system.

---

## 2. The LLM Router (`brain/llm_router.py`)

The Brain uses advanced Agentic AI techniques to function autonomously:
* **Hybrid Auto-Failover Engine**: The script attempts to use `llama-3.3-70b-versatile` by default. If the daily token limit is exhausted (catching a 429 Error), the `safe_chat_completion()` function automatically and silently reroutes the request to the backup `llama-4-scout-17b-16e-instruct` model, ensuring zero downtime.
* **Parallel Tool Calling**: Enabled via `parallel_tool_calls=True`. The LLM can generate multiple tool requests simultaneously (e.g., "Resume Spotify AND turn the volume up").
* **JSON Schema Constraining**: The `tools` array formally maps every Python function into a structured JSON Schema so the AI knows exactly what arguments (like `city_name` or `app_name`) to pass.
* **System Prompting**: The prompt explicitly restricts the LLM from outputting markdown symbols (like `*` or `#`) because the Azure TTS engine would read those literal symbols out loud. It allows `\n` newlines for clean terminal formatting. It also dynamically injects the user's Username and Desktop paths so the AI always knows where to save files.

---

## 3. The "Hands": Tool Catalog (`actions/system_ops.py`)

Here is every active function ARIA is capable of executing, and how it works under the hood:

### 🌍 Real-Time Information
* **`get_current_time()`**: Uses Python's native `datetime` module to return the exact current day, date, and time.
* **`get_weather(city_name)`**: Uses the free `wttr.in` JSON API (`requests.get("https://wttr.in/{city_name}?format=j1")`) to fetch real-time weather data without requiring an API key.

### 💻 OS & Hardware Control
* **`take_screenshot()`**: Uses `PIL.ImageGrab` (Pillow) to capture the main monitor and saves it as a PNG timestamped file in the root project folder.
* **`open_application(app_name)`**: Uses Windows native commands (`os.system("start app_name")`). Has hardcoded fallbacks for `chrome`, `notepad`, `calc`, and URLs like `youtube.com` or `spotify:`.
* **`close_application(app_name)`**: Uses the Windows native `taskkill` command (`os.system("taskkill /F /IM {app_name}.exe /T")`) to forcefully terminate running processes gracefully.
* **`change_system_volume(volume_percent)`**: Bypasses Windows 11 background COM security blocks completely. It uses the `keyboard` library to physically simulate rapidly pressing the `Volume Down` media key 50 times to hit 0%, then pressing `Volume Up` enough times to reach the desired percentage.

### 🎵 Advanced Spotify Media Engine
*Authentication uses `spotipy.SpotifyOAuth` with `user-modify-playback-state`, `user-read-playback-state`, and `user-library-read` scopes.*
* **`play_spotify_media(query, media_type)`**: 
  - **Tracks:** Searches the query and uses `sp.start_playback(uris=[track_uri])`.
  - **Albums/Playlists:** Searches for the context and uses `sp.start_playback(context_uri=...)`.
  - **Liked Songs:** Calls `sp.current_user_saved_tracks()`, extracts the URIs, and plays them directly.
* **`control_spotify(command, volume_percent)`**: Acts as a remote control for the currently playing active device. Maps string commands to `sp.pause_playback()`, `sp.start_playback()`, `sp.next_track()`, `sp.previous_track()`, and `sp.volume()`.

### 📂 File System Operations
*Safety Note: ARIA forces the use of Absolute Paths and has no native delete function.*
* **`list_directory(path)`**: Uses `os.listdir()` and `os.path.isdir()` to return a clean, newline-formatted list of all folders and files inside a specified Windows directory.
* **`read_file(path)`**: Uses Python's `open(path, 'r')` to read text. Includes a 5,000-character truncation limit to prevent massive files from overloading the LLM's token memory.
* **`create_file(path, content)`**: Uses `os.makedirs()` to ensure the directory exists, then `open(path, 'w')` to write or overwrite a text file anywhere on the PC.

---

## 4. Environment Variables (`.env`)
The system relies on the following API keys securely stored in a `.env` file:
- `GROQ_API_KEY`: For Whisper STT and Llama 3/4 reasoning.
- `AZURE_SPEECH_KEY` & `AZURE_REGION`: For ultra-realistic TTS.
- `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI`: For the Spotify Developer App integration.

---

## 5. Post-Mortem: Computer Vision ("The Eyes")

During development, ARIA was briefly equipped with Real-World Computer Vision. This feature allowed him to view the user's laptop camera or an external IP Mobile Camera and describe the physical environment. However, the feature was completely ripped out of the codebase. This section serves as historical context for future developers or LLMs attempting to rebuild it.

### **The Implementation**
- Two tools were created in `system_ops.py`: `look_through_camera()` (single snapshot) and `start_continuous_vision()` (a background thread updating every 7 seconds).
- **OpenCV (`cv2`)** was used to interface with the camera source.
- Images were resized to 512x512, highly compressed into JPEG `base64` strings, and sent as payloads to Groq's multimodal `meta-llama/llama-4-scout-17b-16e-instruct` API.

### **The Technical Hurdles & Errors**
1. **API Rate Limiting (The 429 Error):** Sending raw images to an LLM uses thousands of tokens per frame. The continuous vision loop exhausted Groq API daily token limits within minutes, constantly crashing the primary Llama 3 70B text model and forcing the system onto smaller backup models.
2. **Audio Overlap (The "Two Voices" Bug):** Because the continuous vision loop ran on an asynchronous Python `threading.Thread`, it would trigger the Azure TTS engine to speak updates exactly while the main thread was also trying to speak. The Azure TTS Python SDK `speak_text_async().get()` did not block until the audio physically finished playing from the speakers. This was temporarily fixed using `pyaudio` to manually push raw WAV bytes sequentially under a strict `threading.Lock()`.
3. **OpenCV Background Threading Freezes:** OpenCV's GUI functions (`cv2.imshow` and `cv2.waitKey`) are notoriously unsafe to run on background threads in Windows. Because ARIA's main thread was permanently blocked waiting for `keyboard.wait('space')`, the OpenCV window on the secondary thread starved for UI event pumping. This caused the live video feed to lag heavily and ultimately hard-froze the entire Python process, ignoring `Ctrl+C` entirely.
4. **IP Camera Network Buffering:** Streaming from a mobile IP camera caused massive latency because OpenCV defaults to buffering old frames in the background. This was mitigated by strictly enforcing `cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)`.

### **The Conclusion**
The Computer Vision architecture fundamentally conflicted with ARIA's goal of being a lightning-fast, highly responsive OS assistant. The heavy `cv2` dependencies, continuous network streaming, and exponential token usage caused immense friction. All code related to vision, threaded background loops, and camera access was completely erased from the codebase to optimize speed and strictly preserve API limits for core functionality (like Desktop Automation and RAG memory integration).
