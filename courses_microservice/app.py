import os
import requests
import pandas as pd
from datetime import datetime

def fetchIfNotExists(url, fileName):
  if not os.path.exists(fileName):
    print("Fetching course catalog from @wadefagen/course-catalog...")
    r = requests.get(url, stream=True)
    with open(fileName, 'wb') as fd:
      for chunk in r.iter_content(chunk_size=4096):
        fd.write(chunk)

# Ensure we have a GPA dataset and a courses dataset
fetchIfNotExists("https://raw.githubusercontent.com/wadefagen/datasets/master/course-catalog/data/2023-sp.csv", "courses.csv")

# Open both as a pandas
df_courses = pd.read_csv("courses.csv")


from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/<subject>/<number>/')
def GET_subject_number(subject, number):
  # Prep result:
  result = { "course": f"{subject} {number}" }

  # Cast `number` as an int and ensure `subject` is all caps:
  try:
    number = int(number)
  except:
    result["error"] = f"Course number `{number}` is not a number"
    status_code = 404
    return jsonify(result), status_code
  subject = subject.upper()

  # A test course for the forecast unavailable states:
  if subject == "TEST" and number == 999:
    return TEST_999(result)

  # Fetch data:
  courses = df_courses[ (df_courses["Subject"] == subject) & (df_courses["Number"] == number) & (df_courses["Start Time"] != "") & (df_courses["Start Time"] != "ARRANGED") ] 

  if len(courses) == 0:
    # Provide an error:
    result["error"] = f"No course data available for {subject} {number}"
    status_code = 404
  else:
    # Prefer LEC sections (for courses with discussions/labs)
    course_lec = courses[ courses["Type Code"] == "LEC" ]
    if len(course_lec) > 0:
      courses = course_lec

    # Get the first result's data:
    c = courses.iloc[0]
    result["Start Time"] = c["Start Time"]
    result["Days of Week"] = c["Days of Week"]
    status_code = 200

  return jsonify(result), status_code


# Special case for "TEST 999" course to always return a date/time
# that is 6 days and 23 hours in the future for testing:
def TEST_999(result):
  hour = datetime.now().hour
  minute = 0
  day = 0
  hour -= 1
  if hour < 0:
    hour += 24 
    day = -1
  mark = "AM"
  if hour > 12:
    hour = hour - 12
    mark = "PM"
  elif hour == 12:
    mark = "PM"
  result["Start Time"] = f"{hour}".zfill(2) + ":" + f"{minute}".zfill(2) + " " + mark
  today_of_week = datetime.today().weekday()
  six_days_later = (today_of_week + 7 + day) % 7
  if six_days_later == 0:
    result["Days of Week"] = "M"
  elif six_days_later == 1:
    result["Days of Week"] = "T"
  elif six_days_later == 2:
    result["Days of Week"] = "W"
  elif six_days_later == 3:
    result["Days of Week"] = "R"
  elif six_days_later == 4:
    result["Days of Week"] = "F"
  elif six_days_later == 5:
    result["Days of Week"] = "S"
  elif six_days_later == 6:
    result["Days of Week"] = "U"
  return jsonify(result), 200