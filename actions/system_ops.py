import os
import datetime
import subprocess
import requests
from agentscope.tool import Toolkit

tools = Toolkit()

def _action_decorator(description=None):
    def decorator(func):
        if description and not func.__doc__:
            func.__doc__ = description
        tools.register_tool_function(func)
        return func
    return decorator

tools.action = _action_decorator

@tools.action(description="Returns the exact current date and time.")
def get_current_time():
    """Returns the current date and time in a human-readable format."""
    now = datetime.datetime.now()
    return now.strftime("Today is %A, %B %d, %Y, and the current time is %I:%M %p.")

@tools.action(description="Fetches the current weather for a specific city.")
def get_weather(city_name: str = "Islamabad"):
    """Fetches current weather for a city using free no-key providers with fallback."""
    try:
        headers = {"User-Agent": "ARIA/1.0 (+https://local)"}

        # Primary provider: wttr.in
        wttr_url = f"https://wttr.in/{city_name}?format=j1"
        wttr_response = requests.get(wttr_url, headers=headers, timeout=8)
        if wttr_response.status_code == 200:
            data = wttr_response.json()
            current_condition = data.get("current_condition", [{}])[0]
            temp = current_condition.get("temp_C")
            desc = current_condition.get("weatherDesc", [{}])[0].get("value", "unknown")
            if temp is not None:
                return f"The current weather in {city_name} is {temp}°C and is roughly {desc}."

        # Fallback provider: Open-Meteo via geocoding
        geocode_resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city_name, "count": 1},
            headers=headers,
            timeout=8,
        )
        if geocode_resp.status_code == 200:
            geo_data = geocode_resp.json()
            results = geo_data.get("results") or []
            if results:
                latitude = results[0].get("latitude")
                longitude = results[0].get("longitude")
                weather_resp = requests.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": "temperature_2m,weather_code",
                    },
                    headers=headers,
                    timeout=8,
                )
                if weather_resp.status_code == 200:
                    weather_data = weather_resp.json().get("current", {})
                    temp = weather_data.get("temperature_2m")
                    weather_code = weather_data.get("weather_code", "unknown")
                    if temp is not None:
                        return (
                            f"The current weather in {city_name} is {temp}°C "
                            f"(code {weather_code})."
                        )

        return f"Sorry, I couldn't reach the weather servers for {city_name} right now."
    except Exception as e:
        return f"Error fetching weather: {e}"

@tools.action(description="Takes a screenshot of the user's monitor and saves it to their PC. Call this when they ask to take a screenshot or picture of the screen.")
def take_screenshot():
    """Takes a screenshot of the main monitor and saves it to the project folder."""
    try:
        from PIL import ImageGrab
        
        filename = f"screenshot_{int(datetime.datetime.now().timestamp())}.png"
        screenshot = ImageGrab.grab()
        screenshot.save(filename)
        return f"Screenshot successfully saved to your ARIA project folder as {filename}."
        
    except ImportError:
        return "I am missing the 'Pillow' image processing library. Please run: pip install Pillow"
    except Exception as e:
        return f"Failed to take screenshot: {e}"

@tools.action(description="Opens a native Windows application or website. Example names: chrome, notepad, spotify, youtube")
def open_application(app_name: str):
    """Attempts to launch a program or website natively via Windows."""
    app_name = app_name.lower().strip()
    try:
        if "youtube" in app_name:
            os.system("start https://youtube.com")
            return "Successfully opened YouTube for you, sir."
        elif "spotify" in app_name:
            os.system("start spotify:")
            return "Successfully opened Spotify for you, sir."
        elif "edge" in app_name or "msedge" in app_name:
            # Use the registered URI scheme — works regardless of install path
            os.system("start microsoft-edge:")
            return "Successfully opened Microsoft Edge for you, sir."
        elif "chrome" in app_name or ("browser" in app_name and "edge" not in app_name):
            os.system("start chrome")
            return "Successfully opened Google Chrome for you, sir."
        elif "notepad" in app_name:
            os.system("start notepad")
            return "Successfully opened Notepad for you, sir."
        elif "calc" in app_name:
            os.system("start calc")
            return "Successfully opened Calculator for you, sir."
        elif "code" in app_name or "vs code" in app_name or "vscode" in app_name:
            os.system("start code")
            return "Successfully opened Visual Studio Code for you, sir."
        elif "explorer" in app_name or "file manager" in app_name or "files" in app_name:
            os.system("start explorer")
            return "Successfully opened File Explorer for you, sir."
        elif "task manager" in app_name or "taskmgr" in app_name:
            os.system("start taskmgr")
            return "Successfully opened Task Manager for you, sir."
        elif "word" in app_name:
            os.system("start winword")
            return "Successfully opened Microsoft Word for you, sir."
        elif "excel" in app_name:
            os.system("start excel")
            return "Successfully opened Microsoft Excel for you, sir."
        elif "powerpoint" in app_name or "ppt" in app_name:
            os.system("start powerpnt")
            return "Successfully opened Microsoft PowerPoint for you, sir."
        elif "paint" in app_name:
            os.system("start mspaint")
            return "Successfully opened Paint for you, sir."
        else:
            # Generic fallback — try the name as-is
            os.system(f"start {app_name}")
            return f"I have asked Windows to attempt to launch {app_name}."

    except Exception as e:
        return f"Error opening application {app_name}: {e}"

@tools.action(description="Forcefully closes or quits a native Windows application. Example names: chrome, notepad, spotify")
def close_application(app_name: str):
    """Attempts to forcefully close a running application in Windows."""
    app_name = app_name.lower().strip()
    try:
        if "spotify" in app_name:
            os.system("taskkill /F /IM Spotify.exe /T")
            return "Successfully closed Spotify."
        elif "chrome" in app_name or "browser" in app_name:
            os.system("taskkill /F /IM chrome.exe /T")
            return "Successfully closed Google Chrome."
        elif "notepad" in app_name:
            os.system("taskkill /F /IM notepad.exe /T")
            return "Successfully closed Notepad."
        elif "calc" in app_name:
            os.system("taskkill /F /IM CalculatorApp.exe /T")
            return "Successfully closed Calculator."
        elif "settings" in app_name:
            # Windows Settings is a UWP app hosted by SystemSettings/ApplicationFrameHost.
            os.system("taskkill /F /IM SystemSettings.exe /T")
            os.system("taskkill /F /IM ApplicationFrameHost.exe /T")
            os.system(
                "powershell -NoProfile -Command \"Get-Process -Name 'SystemSettings','ApplicationFrameHost' -ErrorAction SilentlyContinue | Stop-Process -Force\""
            )
            return "Attempted to close Settings."
        elif "whatsapp" in app_name:
            # Desktop and Store variants can use different process names.
            os.system("taskkill /F /IM WhatsApp.exe /T")
            os.system("taskkill /F /IM WhatsAppBeta.exe /T")
            os.system(
                "powershell -NoProfile -Command \"Get-Process -Name 'WhatsApp*' -ErrorAction SilentlyContinue | Stop-Process -Force\""
            )
            return "Attempted to close WhatsApp."
        else:
            # Fallback
            os.system(f"taskkill /F /IM {app_name}.exe /T")
            return f"I have asked Windows to forcefully close {app_name}."
            
    except Exception as e:
        return f"Error closing application {app_name}: {e}"

@tools.action(description="Lists running processes. Optional filter by name_contains and limit the number of results.")
def list_processes(name_contains: str = None, limit: int = 50):
    """Lists running processes with PID and basic stats."""
    try:
        safe_limit = int(limit)
    except Exception:
        safe_limit = 50

    safe_limit = max(1, min(safe_limit, 200))
    filter_clause = ""
    if name_contains:
        safe_name = str(name_contains).replace("'", "''")
        filter_clause = f" | Where-Object {{ $_.Name -like '*{safe_name}*' }}"

    ps_cmd = (
        "Get-Process"
        + filter_clause
        + " | Sort-Object -Property CPU -Descending"
        + f" | Select-Object -First {safe_limit} Name,Id,CPU,WS"
    )

    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "").strip() or (result.stderr or "").strip()
    if not output:
        return "No processes found."
    header = f"Processes (top {safe_limit})" if not name_contains else f"Processes matching '{name_contains}'"
    return f"{header}:\n{output}"

@tools.action(description="Forcefully closes a process by name or PID. Example: 'notepad' or '1234'.")
def close_process(process_name_or_id: str):
    """Forcefully closes a process by name or PID."""
    value = str(process_name_or_id or "").strip()
    if not value:
        return "Error: process_name_or_id is required."

    try:
        pid = int(value)
    except ValueError:
        pid = None

    try:
        if pid is not None:
            os.system(f"taskkill /F /PID {pid} /T")
            return f"Attempted to close process with PID {pid}."

        safe_name = value.replace("\"", "").replace("'", "")
        os.system(f"taskkill /F /IM {safe_name}.exe /T")
        os.system(f"taskkill /F /IM {safe_name}* /T")
        os.system(
            "powershell -NoProfile -Command "
            f"\"Get-Process -Name '{safe_name}' -ErrorAction SilentlyContinue | Stop-Process -Force\""
        )
        return f"Attempted to close process '{safe_name}'."
    except Exception as e:
        return f"Error closing process {value}: {e}"

@tools.action(description="Plays music on Spotify. Can play a specific track, an album, a public playlist, or the user's personal 'Liked Songs'. Types: 'track', 'album', 'playlist', 'liked_songs'.")
def play_spotify_media(query: str, media_type: str = "track"):
    """Searches for and plays a track, album, playlist, or liked songs."""
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        
        # Added user-library-read scope to access Liked Songs
        auth_manager = SpotifyOAuth(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
            scope="user-modify-playback-state user-read-playback-state user-library-read",
            open_browser=True 
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        
        devices = sp.devices()
        device_id = None
        if devices and devices.get('devices'):
            device_id = devices['devices'][0]['id']
            for d in devices['devices']:
                if d['is_active']:
                    device_id = d['id']
                    break
                    
        if not device_id:
            return "No available Spotify device found. Please manually open your Spotify App and click play on any song once to wake it up."
        
        media_type = media_type.lower()
        query_clean = query.replace(" by ", " ").replace("play ", "").strip()

        if media_type == "liked_songs":
            # Fetch user's saved tracks
            results = sp.current_user_saved_tracks(limit=50)
            if not results['items']:
                return "You don't have any Liked Songs saved in your Spotify library."
            uris = [item['track']['uri'] for item in results['items']]
            
            try:
                sp.start_playback(device_id=device_id, uris=uris)
                return "I am now playing your Liked Songs."
            except Exception as e:
                return f"Error starting Liked Songs: {e}"
            
        elif media_type in ["album", "playlist"]:
            results = sp.search(q=query_clean, limit=1, type=media_type)
            items = results[media_type + 's']['items']
            if not items:
                return f"Could not find any {media_type} matching '{query}'."
            context_uri = items[0]['uri']
            name = items[0]['name']
            
            try:
                sp.start_playback(device_id=device_id, context_uri=context_uri)
                return f"I am now playing the {media_type} '{name}'."
            except Exception as e:
                return f"Error playing {media_type}: {e}"
            
        else: # "track"
            results = sp.search(q=query_clean, limit=1, type='track')
            if not results['tracks']['items']:
                return f"Could not find any song matching '{query}'."
            track = results['tracks']['items'][0]
            track_uri = track['uri']
            track_name = track['name']
            artist_name = track['artists'][0]['name']
            
            try:
                sp.start_playback(device_id=device_id, uris=[track_uri])
                return f"I am now playing '{track_name}' by {artist_name}."
            except spotipy.exceptions.SpotifyException as e:
                if "PREMIUM_REQUIRED" in str(e):
                    return "Spotify Error: You must have a Spotify Premium account to control playback."
                return f"Spotify API error: {e}"
            
    except Exception as e:
        return f"Error interacting with Spotify: {e}"

@tools.action(description="Controls the currently playing music on Spotify. Commands: 'pause', 'resume', 'next', 'previous', 'volume'. If 'volume', pass volume_percent.")
def control_spotify(command: str, volume_percent: int = None):
    """Controls Spotify playback (pause, resume, next, previous) and volume."""
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        
        auth_manager = SpotifyOAuth(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
            scope="user-modify-playback-state user-read-playback-state"
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        
        devices = sp.devices()
        device_id = None
        if devices and devices.get('devices'):
            device_id = devices['devices'][0]['id']
            for d in devices['devices']:
                if d['is_active']:
                    device_id = d['id']
                    break
                    
        if not device_id:
            return "No active Spotify device found."

        if command == "pause":
            sp.pause_playback(device_id=device_id)
            return "Playback paused."
        elif command == "resume" or command == "play":
            sp.start_playback(device_id=device_id)
            return "Playback resumed."
        elif command == "next" or command == "skip":
            sp.next_track(device_id=device_id)
            return "Skipped to the next track."
        elif command == "previous" or command == "back":
            sp.previous_track(device_id=device_id)
            return "Going back to the previous track."
        elif command == "volume" and volume_percent is not None:
            sp.volume(volume_percent=int(volume_percent), device_id=device_id)
            return f"Spotify volume set to {int(volume_percent)}%."
        else:
            return f"Unknown command: {command}"
            
    except Exception as e:
        # Spotify throws errors if you try to pause while already paused, etc.
        if "Restriction violated" in str(e) or "Player command failed" in str(e):
            return "Action processed, though it may already be in that state."
        return f"Error controlling Spotify: {e}"

@tools.action(description="Changes the master volume of the entire Windows system to a given percentage (0-100).")
def change_system_volume(volume_percent: int):
    """Changes the master volume of the entire Windows system."""
    try:
        import keyboard
        import time
        
        # Windows 11 occasionally blocks background COM threads from overriding audio endpoints (e.g. bluetooth headsets).
        # The most bulletproof fallback is physically sending raw media keystrokes exactly like a physical keyboard.
        # Windows volume changes by 2% per keystroke.
        
        # Quickly drop volume to 0%
        for _ in range(50):
            keyboard.send("volume down")
            
        # Raise volume to target percentage
        safe_volume = int(float(volume_percent))
        target_steps = int(safe_volume / 2)
        for _ in range(target_steps):
            keyboard.send("volume up")
            
        return f"Windows system volume successfully set to {volume_percent}%."
    except Exception as e:
        return f"Error changing system volume: {e}"

@tools.action(description="Lists the contents of a specified directory on the computer.")
def list_directory(path: str):
    """Lists the contents of a specified directory on the computer."""
    try:
        if not os.path.exists(path):
            return f"Error: The path '{path}' does not exist."
        if not os.path.isdir(path):
            return f"Error: '{path}' is a file, not a directory."
            
        items = os.listdir(path)
        if not items:
            return f"The directory '{path}' is empty."
            
        folders = []
        files = []
        for item in items:
            full_path = os.path.join(path, item)
            if os.path.isdir(full_path):
                folders.append(f"[Folder] {item}")
            else:
                files.append(f"[File] {item}")
                
        result = f"Contents of {path}:\n"
        result += "\n".join(folders + files)
        return result
    except Exception as e:
        return f"Error reading directory {path}: {e}"

@tools.action(description="Reads the text contents of a file at the given absolute path.")
def read_file(path: str):
    """Reads the text contents of a file."""
    try:
        if not os.path.exists(path):
            return f"Error: The file '{path}' does not exist."
        if not os.path.isfile(path):
            return f"Error: '{path}' is a directory, not a file."
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # To prevent overwhelming the LLM context limit, we cap reading to first 5000 chars
        if len(content) > 5000:
            return f"File contents (Truncated to 5000 characters):\n{content[:5000]}...\n[End of truncated read]"
        return f"File contents:\n{content}"
    except UnicodeDecodeError:
        return f"Error: '{path}' appears to be a binary or non-text file, which I cannot read."
    except Exception as e:
        return f"Error reading file {path}: {e}"

@tools.action(description="Creates a new file or overwrites an existing one with the specified text content at the given absolute path.")
def create_file(path: str, content: str):
    """Creates a new file or overwrites an existing one with text content."""
    try:
        # Ensure the parent directory exists
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully created file at '{path}'."
    except Exception as e:
        return f"Error writing file to {path}: {e}"

