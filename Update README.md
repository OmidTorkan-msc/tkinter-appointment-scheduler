# Tkinter Appointment Scheduler

Desktop app in Python (Tkinter) for scheduling appointments with a calendar picker, input validation, auto-sorting, JSON persistence, and overlap warnings.

## How to run
1. pip install -r requirements.txt
2. python app.py

## Fix explained
Original code bound one handler for add/delete and missed overlap detection.
Refactor adds clear methods, validation, and warns on collisions.
