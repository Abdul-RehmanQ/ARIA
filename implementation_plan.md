# Transition to Edge-TTS with Native MCI Playback — Implementation Plan

## Goal Description
Replace the heavy and slow local Kokoro ONNX model with `edge-tts` to offload speech synthesis to Microsoft's cloud neural voice servers. Play the resulting audio instantly using the native Windows MCI (`winmm.dll`) player via `ctypes`. This will achieve fast, zero-dependency, and high-quality voice synthesis (<300ms latency) without requiring a paid Azure subscription.

## Proposed Changes

### Step 1 — Dependencies & requirements.txt
- Uninstall `kokoro-onnx`, `onnxruntime`, and `sounddevice`.
- Install `edge-tts`.
- Modify [requirements.txt](file:///c:/Users/AR/Desktop/ARIA/requirements.txt) to reflect these package changes.

### Step 2 — Clean Up Kokoro Files
- Delete the local model directory `audio/kokoro/` and its contents (`kokoro-v1.0.int8.onnx` and `voices-v1.0.bin`) to free up disk space.
- Modify [.gitignore](file:///c:/Users/AR/Desktop/ARIA/.gitignore) to remove the rules ignoring `audio/kokoro/`.

### Step 3 — Voice Configuration in .env
- Expose `EDGE_VOICE="en-GB-RyanNeural"` in [.env](file:///c:/Users/AR/Desktop/ARIA/.env).
- Keep fallback logic in the code so that if `EDGE_VOICE` is not specified, it falls back to `AZURE_SPEECH_VOICE` or `en-GB-RyanNeural` to preserve compatibility with existing configurations.

### Step 4 — Rewrite audio/tts.py
- Re-implement [tts.py](file:///c:/Users/AR/Desktop/ARIA/audio/tts.py) using `edge-tts`.
- Implement native Windows audio playback using the `winmm.dll` MCI (Media Control Interface) DLL via `ctypes` as successfully verified in testing.
- Implement `speak_to_file(text: str) -> str` to generate a temporary MP3 file and return its path.

## Verification Plan

### Automated/Manual Verification
1. Test local TTS synthesis:
   ```powershell
   $env:PYTHONIOENCODING="utf-8"; .\venv\Scripts\python.exe -c "from audio.tts import speak; speak('Hello, ARIA is now running extremely fast with edge text to speech.')"
   ```
2. Verify that the response is spoken immediately and matches the expected voice character.
3. Verify that the `audio/kokoro/` directory is removed.
4. Run the test suite:
   ```powershell
   $env:PYTHONIOENCODING="utf-8"; .\venv\Scripts\python.exe test.py
   ```
