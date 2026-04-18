import os
import datetime
import requests

def get_current_time():
    """Returns the current date and time in a human-readable format."""
    now = datetime.datetime.now()
    return now.strftime("Today is %A, %B %d, %Y, and the current time is %I:%M %p.")

def get_weather(city_name="Islamabad"):
    """Fetches the current weather for a specific city using a free, no-key public API."""
    try:
        # We use wttr.in because it requires zero API keys and is extremely fast
        url = f"https://wttr.in/{city_name}?format=j1"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            current_condition = data['current_condition'][0]
            temp = current_condition['temp_C']
            desc = current_condition['weatherDesc'][0]['value']
            return f"The current weather in {city_name} is {temp}°C and is roughly {desc}."
        else:
            return f"Sorry, I couldn't reach the weather servers for {city_name} right now."
    except Exception as e:
        return f"Error fetching weather: {e}"

def take_screenshot():
    """Takes a screenshot of the main monitor and saves it to the project folder."""
    try:
        from PIL import ImageGrab
        
        filename = f"screenshot_{int(datetime.datetime.now().timestamp())}.png"
        screenshot = ImageGrab.grab()
        screenshot.save(filename)
        return f"Screenshot successfully saved to your Jarvis project folder as {filename}."
        
    except ImportError:
        return "I am missing the 'Pillow' image processing library. Please run: pip install Pillow"
    except Exception as e:
        return f"Failed to take screenshot: {e}"

def open_application(app_name):
    """Attempts to launch a program or website natively via Windows."""
    app_name = app_name.lower().strip()
    try:
        if "youtube" in app_name:
            os.system("start https://youtube.com")
            return "Successfully opened YouTube for you, sir."
        elif "spotify" in app_name:
            os.system("start spotify:")
            return "Successfully opened Spotify for you, sir."
        elif "chrome" in app_name or "browser" in app_name:
            os.system("start chrome")
            return "Successfully opened Google Chrome for you, sir."
        elif "notepad" in app_name:
            os.system("start notepad")
            return "Successfully opened Notepad for you, sir."
        elif "calc" in app_name:
            os.system("start calc")
            return "Successfully opened Calculator for you, sir."
        else:
            # Fallback
            os.system(f"start {app_name}")
            return f"I have asked Windows to attempt to launch {app_name}."
            
    except Exception as e:
        return f"Error opening application {app_name}: {e}"

def play_spotify_media(query, media_type="track"):
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

def control_spotify(command, volume_percent=None):
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

def change_system_volume(volume_percent):
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
            
        return f"Windows system volume successfully set to {safe_volume}%."
    except Exception as e:
        return f"Error changing system volume: {e}"
