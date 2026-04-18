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
        # Dictionary mapping conversational app names to Windows executable commands
        common_apps = {
            "chrome": "start chrome",
            "notepad": "start notepad",
            "calculator": "start calc",
            "explorer": "start explorer",
            "youtube": "start https://youtube.com",
            # We can use Spotify's URI scheme to launch directly into the desktop app
            "spotify": "start spotify:" 
        }
        
        command = common_apps.get(app_name)
        
        if command:
            os.system(command)
            return f"Successfully opened {app_name} for you, sir."
        else:
            # If it's an unrecognized app, tell Windows to guess and try to launch it anyway
            os.system(f"start {app_name}")
            return f"I have asked Windows to attempt to launch {app_name}."
            
    except Exception as e:
        return f"Error opening application {app_name}: {e}"
