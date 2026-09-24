"""Visor rules engine prototype (KAN-26, KAN-27).

Pure logic, no web or database code, so it can be tested alone and
reused whatever stack we pick (ADR 0001).
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import time
from itertools import combinations


@dataclass(frozen=True)
class Meeting:
    days: str      # e.g. "MWF", "TR"
    start: time
    end: time


@dataclass(frozen=True)
class Section:
    course: str    # e.g. "CS 3233"
    number: str    # e.g. "01"
    meetings: tuple[Meeting, ...]

    @property
    def label(self) -> str:
        return f"{self.course}-{self.number}"


def meetings_overlap(a: Meeting, b: Meeting) -> bool:
    """Two meetings conflict if they share a day and their times overlap.
    Back-to-back (one ends exactly when the other starts) is NOT a conflict."""
    shared_day = set(a.days) & set(b.days)
    return bool(shared_day) and a.start < b.end and b.start < a.end


def find_conflicts(sections: list[Section]) -> list[tuple[str, str]]:
    """Return every pair of sections whose meeting times overlap."""
    out = []
    for s1, s2 in combinations(sections, 2):
        if any(meetings_overlap(m1, m2) for m1 in s1.meetings for m2 in s2.meetings):
            out.append((s1.label, s2.label))
    return out


def missing_prereqs(course: str, prereqs: dict[str, list[list[str]]],
                    completed: set[str]) -> list[list[str]]:
    """Prereqs are stored as AND of OR-groups: [["MA 1"], ["CS 1", "CS 2"]]
    means MA 1 AND (CS 1 OR CS 2). Returns the groups not yet satisfied."""
    return [g for g in prereqs.get(course, []) if not any(c in completed for c in g)]
