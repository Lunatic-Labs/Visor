"""Load catalog + section CSVs (KAN-25), plus the equivalency sample data (KAN-38).

Row-level validation: each row in terms/courses/prereqs/sections.csv is checked on its own.
A bad row is skipped and reported as "file line N: reason" in ImportResult.errors; every other
valid row in the same file (and the other files) still loads. Idempotent: re-importing the same
file updates a changed course/section instead of duplicating it, and leaves unchanged rows alone.

File formats are described in data/sample/README.md.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import (Course, Equivalency, EquivalencyReview, ExternalCourse, MeetingTime, PrereqGroup,
                     PrereqItem, School, Section, Term, db)

COLUMNS = {
    "terms.csv": ["code", "name"],
    "courses.csv": ["subject", "number", "title", "credits"],
    "prereqs.csv": ["course", "any_of"],
    "sections.csv": ["term", "course", "section", "capacity", "enrolled", "days", "start", "end"],
}
DAY_LETTERS = "MTWRFSU"


@dataclass
class ImportResult:
    counts: dict[str, int]
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors

    def __str__(self) -> str:
        summary = ", ".join(f"{k}={v}" for k, v in self.counts.items())
        if not self.errors:
            return summary
        return summary + f"; {len(self.errors)} row(s) rejected:\n" + "\n".join(self.errors)


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


def _text(row: dict, col: str, max_len: int) -> str:
    v = row[col]
    if len(v) > max_len:
        raise _RowError(f"{col} is longer than {max_len} characters")
    return v


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
    code, name = _text(row, "code", 10), _text(row, "name", 40)
    t = Term.query.filter_by(code=code).first()
    if t is None:
        db.session.add(Term(code=code, name=name))
        counts["terms"] += 1
    elif t.name != name:
        t.name = name
        counts["updated"] += 1


def _import_course(row: dict, counts: dict) -> None:
    _required(row, "subject", "number", "title", "credits")
    subject, number, title = _text(row, "subject", 8), _text(row, "number", 8), _text(row, "title", 120)
    credits = _int(row, "credits")
    c = Course.query.filter_by(subject=subject, number=number).first()
    if c is None:
        db.session.add(Course(subject=subject, number=number, title=title, credits=credits))
        counts["courses"] += 1
    elif (c.title, c.credits) != (title, credits):
        c.title, c.credits = title, credits
        counts["updated"] += 1


def _import_prereq(row: dict, counts: dict) -> None:
    """One row per OR-group: course, "CS 1113|CS 1213"."""
    _required(row, "course", "any_of")
    course = _course(row["course"])
    wanted = sorted({x.strip() for x in row["any_of"].split("|") if x.strip()})
    if not wanted:
        raise _RowError("any_of has no courses")
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
    section_no = _text(row, "section", 4)
    capacity, enrolled = _int(row, "capacity"), _int(row, "enrolled")
    days, start, end = _days(row["days"]), _time(row, "start"), _time(row, "end")
    if end <= start:
        raise _RowError(f"end {row['end']} is not after start {row['start']}")

    sec = Section.query.filter_by(course_id=course.id, term_id=term.id, section_no=section_no).first()
    if sec is None:
        sec = Section(course_id=course.id, term_id=term.id, section_no=section_no,
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


def load(data_dir: str | Path, dry_run: bool = False, only: list[str] | None = None) -> ImportResult:
    """Import CSVs in data_dir: terms.csv, courses.csv, prereqs.csv, sections.csv by default.

    Each row is validated on its own: a bad row is skipped and reported in .errors as
    "file line N: reason", every other valid row still saves. Idempotent: an unchanged row
    is left alone, a changed one is updated, nothing is ever duplicated.
    With dry_run=True, checks everything and reports what *would* happen, but saves nothing.
    only restricts which of the four files are processed (e.g. the registrar uploaded just
    sections.csv for a term whose courses already exist); the others are neither read nor
    required to be present. Defaults to all four.
    """
    d = Path(data_dir)
    counts = {"terms": 0, "courses": 0, "prereq_groups": 0, "sections": 0, "meetings": 0, "updated": 0}
    errors: list[str] = []
    steps = STEPS if only is None else [(name, fn) for name, fn in STEPS if name in only]

    for name, import_row in steps:
        for line_no, row in _rows(d, name, errors):
            try:
                import_row(row, counts)
            except _RowError as e:
                errors.append(f"{name} line {line_no}: {e}")
        # later files look up rows added by earlier ones
        db.session.flush()

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return ImportResult(counts, errors)


def _date(s: str):
    s = s.strip()
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc) if s else None


def _school(name: str) -> School:
    s = School.query.filter_by(name=name).first()
    if s is None:
        raise ValueError(f"unknown school {name!r}")
    return s


def _external(school: School, code: str) -> ExternalCourse:
    subject, number = code.split()
    ext = (ExternalCourse.query.filter_by(school_id=school.id, subject=subject, number=number)
           .order_by(ExternalCourse.catalog_year.desc()).first())
    if ext is None:
        raise ValueError(f"unknown external course {code!r} at {school.name}")
    return ext


def _lipscomb(code: str) -> Course | None:
    return _course(code) if code.strip() else None


def load_equivalencies(data_dir: str | Path) -> dict[str, int]:
    """Load data/equivalencies/*.csv. Needs the Lipscomb courses loaded first. Idempotent."""
    d = Path(data_dir)
    counts = {"schools": 0, "external_courses": 0, "equivalencies": 0, "reviews": 0}

    with open(d / "schools.csv", newline="") as f:
        for r in csv.DictReader(f):
            if not School.query.filter_by(name=r["name"]).first():
                db.session.add(School(name=r["name"], state=r["state"] or None, kind=r["kind"],
                                      catalog_url=r["catalog_url"] or None))
                counts["schools"] += 1
    db.session.flush()

    with open(d / "external_courses.csv", newline="") as f:
        for r in csv.DictReader(f):
            school = _school(r["school"])
            key = dict(school_id=school.id, subject=r["subject"], number=r["number"],
                       catalog_year=r["catalog_year"])
            if not ExternalCourse.query.filter_by(**key).first():
                db.session.add(ExternalCourse(**key, title=r["title"],
                                              credits=int(r["credits"]) if r["credits"] else None))
                counts["external_courses"] += 1
    db.session.flush()

    def find_equiv(school: School, external: str, lipscomb: str) -> tuple[ExternalCourse, Course | None,
                                                                         Equivalency | None]:
        ext, course = _external(school, external), _lipscomb(lipscomb)
        existing = Equivalency.query.filter_by(external_course_id=ext.id,
                                               course_id=course.id if course else None).first()
        return ext, course, existing

    with open(d / "equivalencies.csv", newline="") as f:
        for r in csv.DictReader(f):
            ext, course, existing = find_equiv(_school(r["school"]), r["external"], r["lipscomb"])
            if existing:
                continue
            db.session.add(Equivalency(
                external_course_id=ext.id, course_id=course.id if course else None,
                kind=r["kind"], status=r["status"], source=r["source"],
                confidence=float(r["confidence"]) if r["confidence"] else None,
                decided_by=r["decided_by"] or None, decided_at=_date(r["decided_at"]),
                notes=r["notes"]))
            counts["equivalencies"] += 1
    db.session.flush()

    reviews = d / "reviews.csv"
    if reviews.exists():
        with open(reviews, newline="") as f:
            for r in csv.DictReader(f):
                _, _, eq = find_equiv(_school(r["school"]), r["external"], r["lipscomb"])
                if eq is None:
                    raise ValueError(f"review for missing equivalency: {r}")
                if any(rv.reviewer == r["reviewer"] for rv in eq.reviews):
                    continue
                eq.reviews.append(EquivalencyReview(reviewer=r["reviewer"],
                                                    requested_by=r["requested_by"], notes=r["notes"]))
                counts["reviews"] += 1

    db.session.commit()
    return counts
