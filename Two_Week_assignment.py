'''# Classroom Check Scheduling - Data Squad 25Su  
## Student Room Assignment Based on Full Shift Duration and Proximity Clusters

AUTHOR: Auiannce Euwing '26

This script generates student worker room-check assignments for a two-week period.
Each student's shift is split across two weeks, with rooms evenly divided between the two.
Assignments prioritize high-priority rooms, ensure room availability, and restrict students to one zone per shift.

Workflow Summary:

1. Load Input Data
   - Class schedule: contains room use by day and time.
   - Student shifts: specifies when each student is available.
   - Room list: contains metadata like room names, zone, building, and priority.

2. Data Cleaning and Normalization
   - Class schedule:
     - Filter only confirmed classes.
     - Normalize days (e.g., "Mon" to "Monday").
     - Parse date and time strings into datetime objects.
     - Normalize room lists so that each row maps to one room.
   - Room list:
     - Standardize column names.
     - Extract building name from room code.
     - Normalize zone names and priorities.
   - Student shifts:
     - Convert start and end times to datetime.
     - Normalize day abbreviations to full names.
     - Drop entries with invalid or missing shift information.

3. Build Class Schedule Lookup
   - Construct a fast-access map from (room, day) to all scheduled class time blocks.
   - This allows for quick conflict checking when assigning rooms.

4. Room Assignment Logic
   - For each student:
     - Skip if the shift is too short to fit any rooms.
     - Rank all zones by how many high-priority rooms (priority 1 or 2) remain unassigned.
     - Pick the top zone and try assigning rooms from it.
     - For each candidate room in that zone:
       - Skip if already assigned globally or used in this shift.
       - Skip if there is a class conflict during the student’s shift.
       - Skip if not enough time remains in the shift.
       - Otherwise, assign the room, mark it as used, and update time used.

   - Each student is limited to one zone per shift.

5. Week Splitting Logic
   - After all assignments are collected:
     - Each student's shift on a day is split into two parts (Week 1 and Week 2).
     - Rooms are divided as evenly as possible between the two weeks.
     - The `Day` column is updated to reflect the week, e.g., "Monday 1", "Monday 2".

6. Output
   - Saves the final two-week assignment table as:
     - `Output/two_weeks_assignments.csv`
   - Columns included:
     - Student, Day, Shift Start, Shift End, Room, Building, Zone, Priority, Room Type

Constants Used:
- ROOM_CHECK_TIME: Baseline time to check one room (10 minutes)
- HALF_TIME_FACTOR: Multiplier to reduce check time per room (0.5)
- EFFECTIVE_ROOM_CHECK_TIME: Adjusted time to check one room (5 minutes after rounding)
- SHIFT_START_END_BUFFER: Minutes removed from total shift time (currently set to 0)

Assumptions:
- A room takes EFFECTIVE_ROOM_CHECK_TIME minutes to check.
- Each room can be checked only once during the two-week period.
- No student is assigned rooms from more than one zone in a single shift.
- Rooms with class conflicts are skipped.
- If a student's shift is too short to check even one room, they are skipped.

This script is designed to maximize room coverage while respecting student time limits and logistical constraints.
'''

import pandas as pd
from collections import defaultdict
from math import ceil
import os

# === Constants ===
ROOM_CHECK_TIME = 10
HALF_TIME_FACTOR = 0.5
EFFECTIVE_ROOM_CHECK_TIME = max(1, int(round(ROOM_CHECK_TIME * HALF_TIME_FACTOR)))
SHIFT_START_END_BUFFER = 0

# === Load input files ===
schedule = pd.read_csv("Input/scheduling classroom checks - classScheduleData.csv")
students = pd.read_csv("Input/scheduling classroom checks - studentWorkers.csv")
rooms = pd.read_csv("Input/rooms to check - rooms.csv")

# === Clean schedule ===
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
schedule['Room'] = schedule['Room'].astype(str).str.strip()

# === Clean rooms.csv ===
rooms.columns = rooms.columns.str.strip().str.lower()
rooms['room'] = rooms['complete 25live room name'].astype(str).str.strip()
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

# === Index schedule for fast conflict check ===
schedule_by_room_day = defaultdict(list)
for _, row in schedule.iterrows():
    key = (str(row['Room']).strip(), row['day'])
    schedule_by_room_day[key].append((row['Start DateTime'], row['End DateTime']))

# === Assignment ===
assignments_base = []
rooms_assigned_global = set()

for _, student in students.iterrows():
    name = student["person"]
    day = student["Day"]
    shift_start = student["start_dt"]
    shift_end = student["end_dt"]

    total_shift_minutes = (shift_end - shift_start).total_seconds() / 60
    usable_time = total_shift_minutes - SHIFT_START_END_BUFFER
    if usable_time <= 0:
        continue

    time_used = 0
    used_this_shift = set()
    zone_locked = None

    # Pick zones by most unassigned high-priority rooms
    zone_scores = (
        rooms[~rooms['room'].isin(rooms_assigned_global)]
        .groupby('zone')['priority']
        .apply(lambda x: (x <= 2).sum())
        .sort_values(ascending=False)
    )

    for zone in zone_scores.index:
        candidate = rooms[
            (rooms['zone'] == zone) & (~rooms['room'].isin(rooms_assigned_global))
        ].sort_values(by=['priority', 'building', 'room'])

        if candidate.empty:
            continue

        zone_locked = zone

        for _, room_row in candidate.iterrows():
            room_name = room_row['room']
            key = (room_name, day)

            if room_name in used_this_shift or room_name in rooms_assigned_global:
                continue

            # Conflict?
            conflicts = schedule_by_room_day.get(key, [])
            if any(start < shift_end and end > shift_start for start, end in conflicts):
                continue

            if time_used + EFFECTIVE_ROOM_CHECK_TIME > usable_time:
                break

            # Assign room
            assignments_base.append({
                "Student": name,
                "Day": day,  # temporary; will be split to "Monday 1" / "Monday 2"
                "Shift Start": shift_start.strftime("%H:%M"),
                "Shift End": shift_end.strftime("%H:%M"),
                "Room": room_name,
                "Building": room_row["building"],
                "Zone": room_row["zone"],
                "Priority": int(room_row["priority"]),
                "Room Type": room_row.get("type", "")
            })

            used_this_shift.add(room_name)
            rooms_assigned_global.add(room_name)
            time_used += EFFECTIVE_ROOM_CHECK_TIME

        break  # one zone per shift

# === Split each shift into two weeks ===
df_base = pd.DataFrame(assignments_base)
desired_cols = ["Student", "Day", "Shift Start", "Shift End", "Room", "Building", "Zone", "Priority", "Room Type"]

if not df_base.empty:
    df_base["_order"] = range(len(df_base))  # to preserve greedy order
    parts = []
    for (student_name, day), grp in df_base.groupby(["Student", "Day"], sort=False):
        grp_sorted = grp.sort_values(by="_order")
        n = len(grp_sorted)
        split_idx = ceil(n / 2)
        w1 = grp_sorted.iloc[:split_idx].copy()
        w2 = grp_sorted.iloc[split_idx:].copy()
        w1["Day"] = f"{day} 1"
        w2["Day"] = f"{day} 2"
        parts.append(w1.drop(columns=["_order"]))
        parts.append(w2.drop(columns=["_order"]))
    df_out = pd.concat(parts, ignore_index=True)
else:
    df_out = pd.DataFrame(columns=desired_cols)

# Ensure consistent column order
for col in desired_cols:
    if col not in df_out.columns:
        df_out[col] = ""
df_out = df_out[desired_cols]

# === Output ===
os.makedirs("Output", exist_ok=True)
df_out.sort_values(by=["Student", "Day", "Priority", "Building", "Room"]).to_csv(
    "Output/two_weeks_assignments.csv", index=False
)
