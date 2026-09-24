from datetime import time as t
from rules.conflicts import Section, Meeting, find_conflicts, missing_prereqs

# Sample fall schedule for one CS student (made-up sections)
plan = [
    Section("CS 3233", "01", (Meeting("MWF", t(10, 0), t(10, 50)),)),
    Section("CS 3433", "01", (Meeting("MWF", t(10, 30), t(11, 20)),)),   # overlaps CS 3233
    Section("MA 2314", "01", (Meeting("TR", t(9, 30), t(10, 45)),)),
    Section("SENG 3233", "01", (Meeting("TR", t(10, 45), t(12, 0)),)),   # back-to-back, OK
]

print("Time conflicts:")
for a, b in find_conflicts(plan) or [("none", "")]:
    print(f"  {a} <-> {b}")

prereqs = {"CS 3433": [["MA 2314"], ["CS 1113", "CS 1213"]]}
completed = {"CS 1113"}
print("\nMissing prereqs for CS 3433:")
for group in missing_prereqs("CS 3433", prereqs, completed):
    print("  need one of:", " / ".join(group))
