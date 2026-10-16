"""Import catalog + section CSVs (KAN-25).

- Idempotent: running it twice doesn't create duplicates. Re-importing updates a
  course's title/credits and a section's capacity/enrolled count.
- All or nothing: every row is checked first. If any row is bad, nothing is saved
  and CsvImportError lists every problem as "file line N: message".

File formats are described in data/sample/README.md.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .models import Course, MeetingTime, PrereqGroup, PrereqItem, Section, Term, db

COLUMNS = {
    "terms.csv": ["code", "name"],
    "courses.csv": ["subject", "number", "title", "credits"],
    "prereqs.csv": ["course", "any_of"],
    "sections.csv": ["term", "course", "section", "capacity", "enrolled", "days", "start", "end"],
}
DAY_LETTERS = "MTWRFSU"


class CsvImportError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__(f"{len(errors)} problem(s) in import:\n" + "\n".join(errors))
        self.errors = errors


class _RowError(ValueError):
    pass


def _rows(d: Path, name: str, errors: list[str]):
    """Yield (line_no, row) with whitespace stripped. Handles Excel's UTF-8 BOM."""
    path = d / name
    if not path.exists():
        errors.append(f"{name}: file not found")
        return
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS[name] if c not in (reader.fieldnames or [])]
        if missing:
            errors.append(f"{name}: missing column(s) {', '.join(missing)}")
            return
        for line_no, raw in enumerate(reader, start=2):
            row = {k: (v or "").strip() for k, v in raw.items() if k}
            if not any(row.values()):
                continue  # blank line
            yield line_no, row


def _required(row: dict, *cols: str) -> None:
    empty = [c for c in cols if not row[c]]
    if empty:
        raise _RowError(f"empty {', '.join(empty)}")


def _int(row: dict, col: str) -> int:
    try:
        n = int(row[col])
    except ValueError:
        raise _RowError(f"{col} {row[col]!r} is not a whole number") from None
    if n < 0:
        raise _RowError(f"{col} can't be negative")
    return n


def _time(row: dict, col: str):
    try:
        return datetime.strptime(row[col], "%H:%M").time()
    except ValueError:
        raise _RowError(f"{col} {row[col]!r} is not a 24-hour HH:MM time") from None


def _days(value: str) -> str:
    bad = set(value) - set(DAY_LETTERS)
    if not value or bad or len(set(value)) != len(value):
        raise _RowError(f"days {value!r} must be letters from {DAY_LETTERS} with no repeats")
    return value


def _course(code: str) -> Course:
    parts = code.split()
    c = Course.query.filter_by(subject=parts[0], number=parts[1]).first() if len(parts) == 2 else None
    if c is None:
        raise _RowError(f"unknown course {code!r}")
    return c


def _term(code: str) -> Term:
    t = Term.query.filter_by(code=code).first()
    if t is None:
        raise _RowError(f"unknown term {code!r}")
    return t


def _import_term(row: dict, counts: dict) -> None:
    _required(row, "code", "name")
    t = Term.query.filter_by(code=row["code"]).first()
    if t is None:
        db.session.add(Term(code=row["code"], name=row["name"]))
        counts["terms"] += 1
    elif t.name != row["name"]:
        t.name = row["name"]
        counts["updated"] += 1


def _import_course(row: dict, counts: dict) -> None:
    _required(row, "subject", "number", "title", "credits")
    credits = _int(row, "credits")
    c = Course.query.filter_by(subject=row["subject"], number=row["number"]).first()
    if c is None:
        db.session.add(Course(subject=row["subject"], number=row["number"],
                              title=row["title"], credits=credits))
        counts["courses"] += 1
    elif (c.title, c.credits) != (row["title"], credits):
        c.title, c.credits = row["title"], credits
        counts["updated"] += 1


def _import_prereq(row: dict, counts: dict) -> None:
    """One row per OR-group: course, "CS 1113|CS 1213"."""
    _required(row, "course", "any_of")
    course = _course(row["course"])
    wanted = sorted({x.strip() for x in row["any_of"].split("|") if x.strip()})
    if course.code in wanted:
        raise _RowError(f"{course.code} can't be its own prerequisite")
    required = [_course(c) for c in wanted]
    existing = [sorted(i.required_course.code for i in g.items)
                for g in PrereqGroup.query.filter_by(course_id=course.id)]
    if wanted in existing:
        return
    g = PrereqGroup(course_id=course.id)
    g.items = [PrereqItem(required_course_id=c.id) for c in required]
    db.session.add(g)
    counts["prereq_groups"] += 1


def _import_section(row: dict, counts: dict) -> None:
    """One row per meeting; a section with a lab has two rows."""
    _required(row, *COLUMNS["sections.csv"])
    term, course = _term(row["term"]), _course(row["course"])
    if len(row["section"]) > 4:
        raise _RowError(f"section {row['section']!r} is longer than 4 characters")
    capacity, enrolled = _int(row, "capacity"), _int(row, "enrolled")
    days, start, end = _days(row["days"]), _time(row, "start"), _time(row, "end")
    if end <= start:
        raise _RowError(f"end {row['end']} is not after start {row['start']}")

    sec = Section.query.filter_by(course_id=course.id, term_id=term.id,
                                  section_no=row["section"]).first()
    if sec is None:
        sec = Section(course_id=course.id, term_id=term.id, section_no=row["section"],
                      capacity=capacity, enrolled_count=enrolled)
        db.session.add(sec)
        counts["sections"] += 1
    elif (sec.capacity, sec.enrolled_count) != (capacity, enrolled):
        sec.capacity, sec.enrolled_count = capacity, enrolled
        counts["updated"] += 1
    db.session.flush()
    if (days, start, end) not in {(m.days, m.start_time, m.end_time) for m in sec.meetings}:
        sec.meetings.append(MeetingTime(days=days, start_time=start, end_time=end))
        counts["meetings"] += 1


STEPS = [
    ("terms.csv", _import_term),
    ("courses.csv", _import_course),
    ("prereqs.csv", _import_prereq),
    ("sections.csv", _import_section),
]


def load(data_dir: str | Path, dry_run: bool = False) -> dict[str, int]:
    """Import the four CSVs in data_dir. Returns counts of new/updated rows.

    Raises CsvImportError (and saves nothing) if any row is invalid.
    With dry_run=True, checks everything and returns the counts but saves nothing.
    """
    d = Path(data_dir)
    counts = {"terms": 0, "courses": 0, "prereq_groups": 0, "sections": 0, "meetings": 0, "updated": 0}
    errors: list[str] = []

    for name, import_row in STEPS:
        for line_no, row in _rows(d, name, errors):
            try:
                import_row(row, counts)
            except _RowError as e:
                errors.append(f"{name} line {line_no}: {e}")
        # later files look up rows added by earlier ones
        db.session.flush()

    if errors or dry_run:
        db.session.rollback()
        if errors:
            raise CsvImportError(errors)
    else:
        db.session.commit()
    return counts
