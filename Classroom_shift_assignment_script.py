'''
# Classroom Check Scheduling - Data Squad 25Su  
## Student Room Assignment Based on Full Shift Duration and Proximity Clusters

AUTHOR: Auiannce Euwing '26

This script assigns student workers to check unoccupied classrooms during their available work shifts. 
Assignments prioritize high-priority rooms and ensure students are only assigned rooms in one zone per shift. 
Each room takes a fixed amount of time to check, and students are only assigned rooms if they have enough time 
during their shift to complete the checks.

Major Steps:
1. Load input data:
   - Class schedule (with start and end times, room assignments, and days)
   - Student worker shifts (with start and end times and days)
   - Latitude and longitude data (used elsewhere, not in this script)
   - Room metadata (including room names, zones, priorities, and types)

2. Clean and normalize data:
   - Convert columns to consistent formats (e.g., lowercase column names)
   - Parse date and time fields from strings to datetime objects
   - Normalize room names and separate out multiple rooms listed together
   - Extract building codes and zone information from room names

3. Create lookup tables:
   - Map each room and day to its scheduled occupied time blocks
   - This helps identify if a room is available during a student's shift

4. Assign rooms to students:
   - Iterate over each student shift
   - Skip students whose shift is too short
   - Rank zones based on how many high-priority unassigned rooms remain
   - Select the best zone and try to assign rooms in that zone
   - For each candidate room:
     - Skip if already assigned this week
     - Skip if it conflicts with a scheduled class
     - Skip if the student does not have enough remaining time in their shift
     - If eligible, assign the room to the student and update tracking sets

5. Output:
   - Save a list of assigned rooms with student name, day, shift times, room info, and priority
   - Save a list of all unassigned rooms sorted by priority and location

Constants:
- ROOM_CHECK_TIME: Number of minutes required to check one room (default 10)
- SHIFT_START_END_BUFFER: Time buffer removed from each shift (default 0)

Data Files:
- scheduling classroom checks - classScheduleData.csv: class schedule data
- scheduling classroom checks - studentWorkers.csv: student worker shifts
- scheduling classroom checks - LatLong.csv: latitude/longitude info
- rooms to check - rooms.csv: room and zone metadata

Outputs:
- Output/student_room_assignments.csv: assignments of students to rooms
- Output/unchecked_classrooms.csv: rooms that were not assigned to any student that week

Assumptions:
- Each room may be checked only once per week
- Students can only be assigned rooms within one zone per shift
- Rooms cannot be checked if a class is scheduled during the student's shift

This script is optimized for clarity and correctness in assigning student workers to available rooms, with prioritization logic and time constraints enforced consistently.
'''



import pandas as pd
from datetime import datetime
from collections import defaultdict
import os

# === Constants ===
ROOM_CHECK_TIME = 10  # minutes per room
SHIFT_START_END_BUFFER = 0

# === Load input files ===
schedule = pd.read_csv("Input/scheduling classroom checks - classScheduleData.csv")
students = pd.read_csv("Input/scheduling classroom checks - studentWorkers.csv")
latlong = pd.read_csv("Input/scheduling classroom checks - LatLong.csv")
rooms = pd.read_csv("Input/rooms to check - rooms.csv")

# === Clean + normalize ===
latlong.columns = latlong.columns.str.strip().str.lower()

schedule = schedule[schedule['Status'] == 'Confirmed'].copy()
schedule['day'] = schedule['day of week of first session'].map({
    "Mon": "Monday", "Tue": "Tuesday", "Weds": "Wednesday",
    "Thu": "Thursday", "Fri": "Friday"
})
schedule['Start Date'] = pd.to_datetime(schedule['Start Date'], errors='coerce')
time_format = "%Y-%m-%d %I:%M %p"
schedule['Start DateTime'] = pd.to_datetime(schedule['Start Date'].astype(str) + ' ' + schedule['Initial Start Time'], format=time_format, errors='coerce')
schedule['End DateTime'] = pd.to_datetime(schedule['Start Date'].astype(str) + ' ' + schedule['Initial End Time'], format=time_format, errors='coerce')
schedule = schedule.assign(Room=schedule['Locations'].astype(str).str.split(',')).explode('Room')
schedule['Room'] = schedule['Room'].str.strip()

rooms.columns = rooms.columns.str.strip().str.lower()
rooms['room'] = rooms['complete 25live room name'].str.strip()
rooms['building'] = rooms['room'].str.extract(r'^([A-Z]+)')
rooms['zone'] = rooms['zone'].astype(str).str.strip()
rooms['priority'] = pd.to_numeric(rooms['priority'], errors='coerce').fillna(5).astype(int)

# === Clean student shifts ===
students['start_dt'] = pd.to_datetime(students['start'], errors='coerce')
students['end_dt'] = pd.to_datetime(students['end'], errors='coerce')
students['Day'] = students['day'].map({
    "M": "Monday", "Tu": "Tuesday", "W": "Wednesday", "Th": "Thursday", "F": "Friday"
})
students = students.dropna(subset=['start_dt', 'end_dt', 'Day'])

# === Schedule lookup ===
schedule_by_room_day = defaultdict(list)
for _, row in schedule.iterrows():
    schedule_by_room_day[(row['Room'], row['day'])].append((row['Start DateTime'], row['End DateTime']))

# === Assignment ===
assignments = []
rooms_assigned = set()
room_week_assigned = set()

for _, student in students.iterrows():
    name = student["person"]
    day = student["Day"]
    shift_start = student["start_dt"]
    shift_end = student["end_dt"]
    week_num = shift_start.isocalendar().week
    total_shift_minutes = (shift_end - shift_start).total_seconds() / 60
    usable_time = total_shift_minutes - SHIFT_START_END_BUFFER
    if usable_time <= 0:
        continue

    time_used = 0
    assigned_rooms = set()
    
    # Pick zones with available rooms, sorted by how many unassigned high-priority rooms exist
    zone_scores = (
        rooms[~rooms['room'].isin(rooms_assigned)]
        .groupby('zone')['priority']
        .apply(lambda x: (x <= 2).sum())
        .sort_values(ascending=False)
    )

    zone_chosen = None
    for zone in zone_scores.index:
        available = rooms[(rooms['zone'] == zone) & (~rooms['room'].isin(rooms_assigned))]
        if not available.empty:
            zone_chosen = zone
            break

    if not zone_chosen:
        continue

    zone_rooms_df = rooms[
        (rooms['zone'] == zone_chosen) & (~rooms['room'].isin(rooms_assigned))
    ].sort_values(by='priority')

    for _, room_row in zone_rooms_df.iterrows():
        room_name = room_row['room']
        if (room_name, week_num) in room_week_assigned:
            continue

        # Skip if there is a class scheduled during shift
        conflicts = schedule_by_room_day.get((room_name, day), [])
        if any(start < shift_end and end > shift_start for start, end in conflicts):
            continue

        if time_used + ROOM_CHECK_TIME > usable_time:
            break

        assignments.append({
            "Student": name,
            "Day": day,
            "Shift Start": shift_start.strftime("%H:%M"),
            "Shift End": shift_end.strftime("%H:%M"),
            "Room": room_name,
            "Building": room_row["building"],
            "Zone": room_row["zone"],
            "Priority": room_row["priority"],
            "Room Type": room_row.get("type", "")
        })

        rooms_assigned.add(room_name)
        room_week_assigned.add((room_name, week_num))
        assigned_rooms.add(room_name)
        time_used += ROOM_CHECK_TIME

# === Output ===
os.makedirs("Output", exist_ok=True)

assignments_df = pd.DataFrame(assignments)
assignments_df.to_csv("Output/student_room_assignments2.csv", index=False)

unchecked_rooms = set(rooms['room'].dropna().unique()) - rooms_assigned
unchecked_df = rooms[rooms['room'].isin(unchecked_rooms)][['room', 'building', 'zone', 'priority', 'type']]
unchecked_df = unchecked_df.drop_duplicates().sort_values(by=['priority', 'building', 'room'])
unchecked_df.to_csv("Output/unchecked_classrooms2.csv", index=False)

