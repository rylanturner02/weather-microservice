from flask import Flask, render_template, request, jsonify
import os
import requests
import re
from datetime import datetime, timedelta, time, timezone

app = Flask(__name__)

# Set the URL for the courses microservice; default to localhost if not set.
COURSES_MICROSERVICE_URL = os.getenv('COURSES_MICROSERVICE_URL', 'http://127.0.0.1:34000')

# Dictionary to cache weather data to avoid excessive API calls.
weather_cache = {}

@app.route('/')
def index():
    """
    Render the homepage that provides an interface for the user to input course codes
    and request weather information.
    """
    return render_template("index.html")

def parse_course(course_code):
    """
    Parses the given course code into a standardized format suitable for API requests.
    
    This function removes any extraneous spaces, handles different capitalizations,
    and splits the course subject and number even if they are not separated by a space.
    
    Args:
    course_code (str): A string that may contain a course number and subject, like 'cs 340'.
    
    Returns:
    tuple: Returns a tuple of the subject and number as uppercase strings, or (None, None) if parsing fails.
    """
    # Strip any leading/trailing whitespace and convert to uppercase
    course_code = course_code.strip().upper()
    
    # Using regex to find the subject and number parts
    match = re.match(r"([A-Z]+)\s*(\d+)", course_code)
    if match:
        subject, number = match.groups()
        return subject, number
    
    return None, None

def get_next_meeting_datetime(start_time, days_of_week):
    """
    Calculates the next meeting datetime for a course based on its start time and meeting days.
    
    Args:
    start_time (str): Start time of the class (e.g., '12:30 PM').
    days_of_week (str): String representing meeting days (e.g., 'MWF').
    
    Returns:
    datetime: The next meeting datetime object.
    """
    now = datetime.now()
    today = now.weekday()
    meeting_days = [0 if day == 'M' else 1 if day == 'T' else 2 if day == 'W' else 3 if day == 'R' else 4 if day == 'F' else 5 if day == 'S' else 6 for day in days_of_week]
    for offset in range(7):
        next_day = (today + offset) % 7
        if next_day in meeting_days:
            break
    next_meeting_date = now.date() + timedelta(days=offset)
    meeting_time = datetime.strptime(start_time, '%I:%M %p').time()
    return datetime.combine(next_meeting_date, meeting_time)

@app.route('/weather', methods=["POST"])
def post_weather():
    """
    Handles POST requests to fetch weather information for the next meeting of a given course.
    
    Form Params:
    course (str): Course identifier input by the user.
    
    Returns:
    json: A JSON response containing weather information or an error message.
    """
    course_code = request.form["course"]
    subject, number = parse_course(course_code)
    course_url = f"{COURSES_MICROSERVICE_URL}/{subject}/{number}/"
    response = requests.get(course_url)
    if response.status_code != 200:
        return jsonify(error="Course not found"), 400
    course_data = response.json()
    next_meeting = get_next_meeting_datetime(course_data["Start Time"], course_data["Days of Week"])
    cache_key = f"{course_data['course']}_{next_meeting.strftime('%Y-%m-%d_%H:%M')}"
    if cache_key in weather_cache:
        return jsonify(weather_cache[cache_key])
    weather = fetch_weather(next_meeting)
    weather_cache[cache_key] = weather
    return jsonify(weather)

@app.route('/weatherCache')
def get_cached_weather():
    """
    Provides the cached weather data.
    
    Returns:
    json: A JSON representation of the weather cache.
    """
    return jsonify(weather_cache)

def fetch_weather(next_meeting):
    """
    Fetches weather data from the National Weather Service API for a given datetime.
    
    Args:
    next_meeting (datetime): The datetime for which to fetch the weather.
    
    Returns:
    dict: A dictionary containing the weather forecast data or an error message.
    """
    latitude = 40.1125
    longitude = -88.2284
    points_url = f"https://api.weather.gov/points/{latitude},{longitude}"
    response = requests.get(points_url)
    if response.status_code != 200:
        return {"error": f"Failed to fetch grid point data, status code {response.status_code}"}

    forecast_response = requests.get("https://api.weather.gov/gridpoints/ILX/96,72/forecast/hourly")
    if forecast_response.status_code != 200:
        return {"error": f"Failed to fetch forecast data, status code {forecast_response.status_code}"}

    forecast = forecast_response.json()
    next_meeting_utc = next_meeting.astimezone(timezone.utc)

    subject, num = parse_course(request.form["course"])
    course_name = f"{subject} {num}"

    for period in forecast['properties']['periods']:
        forecast_time = datetime.fromisoformat(period['startTime'].replace('Z', '+00:00'))
        if forecast_time.replace(minute=0, second=0, microsecond=0) == next_meeting_utc.replace(minute=0, second=0, microsecond=0):
            return {
                "course": course_name,
                "nextCourseMeeting": next_meeting.strftime("%Y-%m-%d %H:%M:%S"),
                "forecastTime": forecast_time.strftime("%Y-%m-%d %H:%M:%S"),
                "temperature": period['temperature'],
                "shortForecast": period['shortForecast']
            }

    return {
        "course": course_name,
        "nextCourseMeeting": next_meeting.strftime("%Y-%m-%d %H:%M:%S"),
        "forecastTime": forecast_time.strftime("%Y-%m-%d %H:%M:%S"),
        "temperature": "forecast unavailable",
        "shortForecast": "forecast unavailable"
    }

if __name__ == '__main__':
    app.run(debug=True)
