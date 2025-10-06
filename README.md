# Automating-Classroom-Check
## Overview

This project assigns Carleton College student workers to check classrooms across campus. It uses Python scripts to generate room-check schedules that respect the following constraints:

- Student **work shift availability**
- **Classroom availability** (based on scheduled classes)
- **Room priority** (1 = highest priority)
- **Zone restrictions** (only one zone per shift)
- **Time limits** within each shift
- Optional **two-week scheduling** to spread room coverage

The goal is to assign as many high-priority rooms as possible each week in a fair and efficient way, while ensuring no overlap with scheduled class times.

---

## Scripts

### 1. `Classroom_shift_assignment_script.py`  
**One-week full-shift assignment**

This version assigns students to check as many rooms as possible within their shift duration using:

- A fixed **10-minute check time per room**
- No artificial cap on number of rooms (other than available shift time)
- One **zone per shift**
- Each room may only be assigned **once per week**
- Rooms are only assigned if they are **not occupied** during the shift

**Output:**
- `Output/student_room_assignments.csv`: Room assignments per student
- `Output/unchecked_classrooms.csv`: Rooms that were not assigned to any student

---

### 2. `Two_Week_assignment.py`  
**Two-week assignment with halved room check time**

This version is optimized to simulate **faster room checks** and spreads room assignments over **two weeks**:

- Uses a **5-minute room check time**
- Each shift is still used to its full duration (minus optional buffer)
- Each student is assigned **rooms from only one zone per shift**
- Room assignments are **split evenly** into:
  - Week 1: first half (e.g., “Monday 1”)
  - Week 2: second half (e.g., “Monday 2”)
- No room is checked more than once over the two-week period
- Only rooms **without class conflicts** are eligible

**Output:**
- `Output/two_weeks_assignments.csv`: Split assignments across two weeks
- `Output/unchecked_classrooms.csv`: Rooms not assigned in either week

---

## Required Input Files (place in the `Input/` folder)

| File Name                               | Description |
|----------------------------------------|-------------|
| `scheduling classroom checks - classScheduleData.csv` | Class schedule with confirmed sessions, start/end times, and room names |
| `scheduling classroom checks - studentWorkers.csv`     | Student names, days available, and shift times |
| `rooms to check - rooms.csv`                         | Room metadata including 25Live name, zone, building, type, and priority |
| `scheduling classroom checks - LatLong.csv`           | Building coordinate reference (used in one-week version only) |

---

## Output Files

| File Name                           | Description |
|------------------------------------|-------------|
| `student_room_assignments.csv`     | One-week assignments per student (one zone per shift) |
| `two_weeks_assignments.csv`        | Two-week assignments split into Week 1 and Week 2 |
| `unchecked_classrooms.csv`         | All unassigned rooms sorted by priority and location |

---

## Configuration (Script Constants)

You can modify the following values at the top of each script:

```python
ROOM_CHECK_TIME = 10                 # Minutes per room (used in full-shift version)
HALF_TIME_FACTOR = 0.5              # Applies in the two-week version to simulate faster checks
EFFECTIVE_ROOM_CHECK_TIME = 5       # Final per-room time in two-week version after applying HALF_TIME_FACTOR
SHIFT_START_END_BUFFER = 0          # Optional buffer removed from each shift

```

### Step 3: Install Required Python Packages

Type the following command into your terminal and press Enter:

```bash
python Classroom_shift_assignment_script.py
python Assignment_student_Time_Limit.py 
```

---
## How to Run the Scripts 

### Step 1: Install Python

- Go to [https://www.python.org/downloads/](https://www.python.org/downloads/)
- Download and install Python
- **IMPORTANT**: During installation, make sure to check the box that says **"Add Python to PATH"**
---

### Step 2: Open a Terminal or Command Prompt

- **On Windows**: Press `Win + R`, type `cmd`, and press Enter  
- **On Mac**: Open the **Terminal** app  
- **On Linux**: Open your preferred terminal application

---

### Step 3: Install Required Python Packages

Type the following command into your terminal and press Enter:

```bash
pip install pandas geopy
python Classroom_shift_assignment_script.py
python Assignment_student_Time_Limit.py 
```

### Step 4: How to Run in VS Code
- Go to the .py file that you want to run
- Click the Play button on the top right  
