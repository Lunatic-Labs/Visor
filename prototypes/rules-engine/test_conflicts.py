from datetime import time as t
from rules.conflicts import Meeting, Section, meetings_overlap, find_conflicts, missing_prereqs

def m(days, s, e): return Meeting(days, t(*s), t(*e))

def test_overlap_same_day():
    assert meetings_overlap(m("MWF", (10, 0), (10, 50)), m("MW", (10, 30), (11, 20)))

def test_back_to_back_is_ok():
    assert not meetings_overlap(m("TR", (9, 30), (10, 45)), m("TR", (10, 45), (12, 0)))

def test_different_days_never_conflict():
    assert not meetings_overlap(m("MWF", (10, 0), (10, 50)), m("TR", (10, 0), (10, 50)))

def test_one_inside_another():
    assert meetings_overlap(m("M", (9, 0), (12, 0)), m("M", (10, 0), (10, 30)))

def test_lab_meeting_causes_conflict():
    a = Section("CS 1", "01", (m("MWF", (8, 0), (8, 50)), m("R", (14, 0), (16, 0))))
    b = Section("PH 1", "01", (m("R", (15, 0), (16, 0)),))
    assert find_conflicts([a, b]) == [("CS 1-01", "PH 1-01")]

def test_prereqs_and_of_or():
    pre = {"CS 3": [["MA 1"], ["CS 1", "CS 2"]]}
    assert missing_prereqs("CS 3", pre, {"MA 1", "CS 2"}) == []
    assert missing_prereqs("CS 3", pre, {"CS 1"}) == [["MA 1"]]
    assert missing_prereqs("CS 9", pre, set()) == []
