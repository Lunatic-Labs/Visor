"""Import the class schedule exported from Lipscomb's public class-schedule page (KAN-25).

One CSV, one row per section, with these columns (the page's Export > CSV):

    Course Code, Section Code, Course Name, Term, Start Date, End Date, Instructor, Start Time,
    End Time, Meeting Days, Total Seats, Seats Filled, Seats Available, Credit Hours, Course Level,
    Delivery Method, Location, Course Notes

Two halves, like sis_import:
- parse_schedule() is pure Python: rows in, a SchedulePlan out. Unit tested directly.
- load_schedule() writes a plan into the database. Idempotent: running it twice adds nothing.

What it does with the quirks in the real export:
- The page adds a filter-dropdown row at the bottom (blank course code); it is skipped.
- Section codes the table can't hold (more than 4 characters, or blank) skip that section.
- Times are 12-hour ("01:00 PM"), days are words ("MonWedFri"); both are converted.
- "MonWed/TuesThurs" with "09:00 AM/09:25 AM" is two meeting patterns; they are paired up.
- Meetings listed as calendar dates, or with an end before the start, are not imported. The section
  is still imported, its meeting times are left as they were, and the problem is reported.
- On a re-import a section's meeting times are made to match the file (a changed time replaces the
  old one). Sections that are no longer in the file are kept unless remove_missing is asked for.
- A course taught under several titles or credit values (special topics, variable-credit "V"
  courses) gets its most common title and its highest credit value.
- Courses already in the database are left alone, so the SIS import's course data is never
  overwritten. The summary says how many existing courses differ.

The real export is not committed: keep it in data/private/ (gitignored).
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

from .sis_import import split_code

COLUMNS = ("Course Code", "Section Code", "Course Name", "Term", "Meeting Days", "Start Time", "End Time",
           "Total Seats", "Seats Filled", "Credit Hours")
SECTION_NO_MAX = 4  # Section.section_no is String(4)

DAY_LETTERS = {"Mon": "M", "Tues": "T", "Wed": "W", "Thurs": "R", "Fri": "F", "Sat": "S", "Sun": "U"}
_DAY = re.compile("|".join(DAY_LETTERS))
_TIME = re.compile(r"^(\d{1,2}):(\d{2})\s*([AP]M)?$", re.I)
_TERM = re.compile(r"^(\d{4})\s+(Spring|Summer|Fall|Winter)\b", re.I)
_SEASON = {"spring": "SP", "summer": "SU", "fall": "FA", "winter": "WI"}

Meeting = tuple[str, time, time]


REMOVAL_ALWAYS_OK = 10  # removing this few sections never trips the partial-export guard


class DatedMeetings(ValueError):
    """Meets on listed calendar dates rather than a weekly pattern."""


class RemovalTooLarge(ValueError):
    """Removing sections not in the file would delete so much it must be a partial export."""


@dataclass
class PlannedSection:
    line: int
    subject: str
    number: str
    section_no: str
    term_code: str
    capacity: int
    enrolled: int
    meetings: list[Meeting]
    meetings_known: bool = True  # False when the row's meeting info couldn't be read; leave existing times alone


@dataclass
class SchedulePlan:
    terms: dict[str, str] = field(default_factory=dict)  # code -> name
    courses: dict[tuple[str, str], tuple[str, int]] = field(default_factory=dict)  # (subj, num) -> (title, credits)
    sections: list[PlannedSection] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    skipped_sections: int = 0
    dated_meeting_sections: int = 0
    bad_meeting_sections: int = 0
    # Sections that ARE in the file but couldn't be read: never treated as "missing from the file".
    unreadable: set[tuple[str, str, str]] = field(default_factory=set)


# --- pure helpers ----------------------------------------------------------------------------

def parse_time(text: str) -> time:
    """'01:00 PM' / '1:00pm' / '17:30' -> time."""
    m = _TIME.match(text.strip())
    if not m:
        raise ValueError(f"{text!r} is not a time")
    hour, minute, ampm = int(m.group(1)), int(m.group(2)), (m.group(3) or "").upper()
    if minute > 59 or (ampm and not 1 <= hour <= 12) or hour > 23:
        raise ValueError(f"{text!r} is not a time")
    if ampm:
        hour = hour % 12 + (12 if ampm == "PM" else 0)
    return time(hour, minute)


def parse_days(text: str) -> str:
    """'MonWedFri' -> 'MWF', 'TuesThurs' -> 'TR' (the letters the rest of Visor uses)."""
    s = text.strip()
    letters = "".join(DAY_LETTERS[d] for d in _DAY.findall(s))
    if not letters or _DAY.sub("", s):
        raise ValueError(f"unrecognized meeting days {text!r}")
    return letters


def parse_meetings(days: str, start: str, end: str) -> list[Meeting]:
    """Meeting patterns for one row. No days -> no meetings (online, independent study).

    Raises DatedMeetings for calendar-date lists and ValueError for anything else unusable.
    """
    days, start, end = days.strip(), start.strip(), end.strip()
    if not days:
        return []
    if re.search(r"\d", days):
        raise DatedMeetings(f"meets on specific dates ({days})")
    parts = [[p.strip() for p in field.split("/")] for field in (days, start, end)]
    if not len(parts[0]) == len(parts[1]) == len(parts[2]):
        raise ValueError(f"days {days!r} don't line up with times {start!r} / {end!r}")
    meetings = []
    for d, s, e in zip(*parts):
        begin, finish = parse_time(s), parse_time(e)
        if finish <= begin:
            raise ValueError(f"end {e} is not after start {s}")
        meetings.append((parse_days(d), begin, finish))
    return meetings


def parse_term(text: str) -> tuple[str, str]:
    """'2027 Spring Term II' -> ('2027SP', 'Spring 2027'). Full Term / Term I / Term II share one term."""
    m = _TERM.match(text.strip())
    if not m:
        raise ValueError(f"unrecognized term {text!r}")
    year, season = m.group(1), m.group(2).capitalize()
    return f"{year}{_SEASON[season.lower()]}", f"{season} {year}"


def _whole(text: str, what: str) -> int:
    try:
        n = float(text)
    except ValueError:
        raise ValueError(f"{what} {text!r} is not a number") from None
    if n < 0 or not n.is_integer():
        raise ValueError(f"{what} {text!r} is not a whole number")
    return int(n)


def parse_schedule(records: list[dict]) -> SchedulePlan:
    """Header-keyed dicts (from the CSV) -> SchedulePlan. Raises ValueError on a missing column."""
    plan = SchedulePlan()
    if not records:
        return plan
    missing = [c for c in COLUMNS if c not in records[0]]
    if missing:
        raise ValueError(f"schedule export is missing columns: {', '.join(missing)}")

    titles: dict[tuple[str, str], Counter] = {}
    credits: dict[tuple[str, str], int] = {}

    for line, r in enumerate(records, start=2):
        code = (r["Course Code"] or "").strip()
        if not code:
            continue  # the page's filter-dropdown row
        label = f"line {line} ({code}-{(r['Section Code'] or '').strip()})"
        subject, number = split_code(code)
        if not subject or not number:
            plan.issues.append(f"{label}: can't split course code into subject and number")
            plan.skipped_sections += 1
            continue
        key = (subject, number)
        try:
            hours = _whole(r["Credit Hours"], "credit hours")
        except ValueError as e:
            plan.issues.append(f"{label}: {e}")
            plan.skipped_sections += 1
            plan.unreadable.add((subject, number, (r["Section Code"] or "").strip()))
            continue
        titles.setdefault(key, Counter())[r["Course Name"].strip() or code] += 1
        credits[key] = max(credits.get(key, 0), hours)

        section_no = (r["Section Code"] or "").strip()
        if not section_no:
            plan.issues.append(f"{label}: no section code, section skipped")
        elif len(section_no) > SECTION_NO_MAX:
            plan.issues.append(f"{label}: section code is longer than {SECTION_NO_MAX} characters, section skipped")
        else:
            try:
                term_code, term_name = parse_term(r["Term"])
                capacity, enrolled = _whole(r["Total Seats"], "total seats"), _whole(r["Seats Filled"], "seats filled")
            except ValueError as e:
                plan.issues.append(f"{label}: {e}, section skipped")
                plan.unreadable.add((subject, number, section_no))
            else:
                meetings: list[Meeting] = []
                known = True
                try:
                    meetings = parse_meetings(r["Meeting Days"], r["Start Time"], r["End Time"])
                except DatedMeetings as e:
                    known = False
                    plan.dated_meeting_sections += 1
                    plan.issues.append(f"{label}: {e}; meeting times not imported")
                except ValueError as e:
                    known = False
                    plan.bad_meeting_sections += 1
                    plan.issues.append(f"{label}: {e}; meeting times not imported")
                plan.terms.setdefault(term_code, term_name)
                plan.sections.append(PlannedSection(line, subject, number, section_no, term_code,
                                                    capacity, enrolled, meetings, known))
                continue
        plan.skipped_sections += 1

    for key, counter in titles.items():
        plan.courses[key] = (counter.most_common(1)[0][0], credits[key])
    return plan


def read_schedule(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# --- database --------------------------------------------------------------------------------

@dataclass
class ScheduleResult:
    counts: dict[str, int]
    issues: list[str]

    def __str__(self) -> str:
        summary = ", ".join(f"{k}={v}" for k, v in self.counts.items())
        return summary + (f"\n{len(self.issues)} note(s):\n" + "\n".join(self.issues) if self.issues else "")


def load_schedule(path: str | Path, dry_run: bool = False, filename: str | None = None,
                  remove_missing: bool = False, max_remove_fraction: float = 0.25) -> ScheduleResult:
    """Load the schedule export into the database. Needs an app context.

    Idempotent: a section already there is updated only if its seats changed, and its meeting
    times are made to match the file. With dry_run=True, reports what would happen and saves nothing.
    remove_missing=True also deletes sections the file no longer lists (cancelled classes), for the
    terms the file covers; use it only with the complete schedule. As a guard against a partial
    export (the page's filters apply to the CSV), removing more than 10 sections AND more than
    max_remove_fraction of the term raises RemovalTooLarge and changes nothing. The summary always
    says how many sections aren't in the file (sections_not_in_file), removed or not.
    Every real run is logged per term (ScheduleImport) so the Schedule screen can show when the
    seat counts were last refreshed, even if nothing changed. filename is what to record for it
    (an upload's original name; defaults to the file's own name).
    """
    from .models import Course, MeetingTime, ScheduleImport, Section, Term, db

    plan = parse_schedule(read_schedule(path))
    counts = {"sections_in_file": len(plan.sections),
              "terms_added": 0, "courses_added": 0, "courses_already_there": 0, "existing_courses_differ": 0,
              "sections_added": 0, "sections_updated": 0, "meetings_added": 0, "meetings_removed": 0,
              "sections_without_meetings": 0, "sections_skipped": plan.skipped_sections}

    terms = {t.code: t for t in Term.query.all()}
    for code, name in plan.terms.items():
        if code not in terms:
            terms[code] = Term(code=code, name=name)
            db.session.add(terms[code])
            counts["terms_added"] += 1

    courses = {(c.subject, c.number): c for c in Course.query.all()}
    for key, (title, credits) in plan.courses.items():
        existing = courses.get(key)
        if existing is None:
            courses[key] = Course(subject=key[0], number=key[1], title=title[:120], credits=credits)
            db.session.add(courses[key])
            counts["courses_added"] += 1
        else:
            counts["courses_already_there"] += 1
            counts["existing_courses_differ"] += (existing.title, existing.credits) != (title[:120], credits)
    db.session.flush()

    sections = {(s.course_id, s.term_id, s.section_no): s
                for s in Section.query.filter(Section.term_id.in_([t.id for t in terms.values()])).all()}
    for ps in plan.sections:
        course, term = courses[(ps.subject, ps.number)], terms[ps.term_code]
        key = (course.id, term.id, ps.section_no)
        sec = sections.get(key)
        if sec is None:
            sec = sections[key] = Section(course_id=course.id, term_id=term.id, section_no=ps.section_no,
                                          capacity=ps.capacity, enrolled_count=ps.enrolled)
            db.session.add(sec)
            counts["sections_added"] += 1
        elif (sec.capacity, sec.enrolled_count) != (ps.capacity, ps.enrolled):
            sec.capacity, sec.enrolled_count = ps.capacity, ps.enrolled
            counts["sections_updated"] += 1
        if ps.meetings_known:
            # Mirror the file: a time that changed is replaced, not stacked next to the old one.
            have = {(m.days, m.start_time, m.end_time): m for m in sec.meetings}
            want = set(ps.meetings)
            for slot, meeting in have.items():
                if slot not in want:
                    sec.meetings.remove(meeting)
                    counts["meetings_removed"] += 1
            for days, start, end in ps.meetings:
                if (days, start, end) not in have:
                    have[(days, start, end)] = MeetingTime(days=days, start_time=start, end_time=end)
                    sec.meetings.append(have[(days, start, end)])
                    counts["meetings_added"] += 1
        counts["sections_without_meetings"] += not ps.meetings

    # Sections already in Visor, for a term this file covers, that the file no longer lists.
    file_terms = {terms[code].id for code in plan.terms}
    in_file = {(courses[(ps.subject, ps.number)].id, terms[ps.term_code].id, ps.section_no) for ps in plan.sections}
    course_key = {c.id: k for k, c in courses.items()}
    missing = [s for k, s in sections.items()
               if k[1] in file_terms and k not in in_file and (*course_key[s.course_id], s.section_no) not in plan.unreadable]
    counts["sections_not_in_file"] = len(missing)
    counts["sections_removed"] = 0
    if remove_missing and missing:
        before = sum(1 for k in sections if k[1] in file_terms) - counts["sections_added"]
        if len(missing) > max(REMOVAL_ALWAYS_OK, max_remove_fraction * before):
            db.session.rollback()
            raise RemovalTooLarge(
                f"That would remove {len(missing):,} of {before:,} existing sections, which looks like a partial "
                "export (for example one filtered by level or subject). Nothing was changed. Export the complete "
                "schedule and try again.")
        for s in missing:
            db.session.delete(s)
        counts["sections_removed"] = len(missing)

    if dry_run:
        db.session.rollback()
    else:
        for code in plan.terms:
            db.session.add(ScheduleImport(term_id=terms[code].id, filename=(filename or Path(path).name)[:200],
                                          sections=sum(ps.term_code == code for ps in plan.sections)))
        db.session.commit()
    return ScheduleResult(counts, plan.issues)
