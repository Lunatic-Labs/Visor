"""Load catalog + section CSVs (starting point for KAN-25).

Idempotent: running it twice doesn't create duplicates.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from .models import (Course, Equivalency, EquivalencyReview, ExternalCourse, MeetingTime, PrereqGroup,
                     PrereqItem, School, Section, Term, db)


def _t(s: str):
    return datetime.strptime(s.strip(), "%H:%M").time()


def _course(code: str) -> Course:
    subject, number = code.split()
    c = Course.query.filter_by(subject=subject, number=number).first()
    if c is None:
        raise ValueError(f"unknown course {code!r}")
    return c


def load(data_dir: str | Path) -> dict[str, int]:
    d = Path(data_dir)
    counts = {"terms": 0, "courses": 0, "sections": 0, "meetings": 0, "prereq_groups": 0}

    with open(d / "terms.csv", newline="") as f:
        for r in csv.DictReader(f):
            if not Term.query.filter_by(code=r["code"]).first():
                db.session.add(Term(code=r["code"], name=r["name"]))
                counts["terms"] += 1
    db.session.flush()

    with open(d / "courses.csv", newline="") as f:
        for r in csv.DictReader(f):
            if not Course.query.filter_by(subject=r["subject"], number=r["number"]).first():
                db.session.add(Course(subject=r["subject"], number=r["number"],
                                      title=r["title"], credits=int(r["credits"])))
                counts["courses"] += 1
    db.session.flush()

    with open(d / "prereqs.csv", newline="") as f:
        # one row per OR-group: course, "CS 1113|CS 1213"
        for r in csv.DictReader(f):
            course = _course(r["course"])
            wanted = sorted(x.strip() for x in r["any_of"].split("|"))
            existing = [sorted(i.required_course.code for i in g.items)
                        for g in PrereqGroup.query.filter_by(course_id=course.id)]
            if wanted in existing:
                continue
            g = PrereqGroup(course_id=course.id)
            g.items = [PrereqItem(required_course_id=_course(c).id) for c in wanted]
            db.session.add(g)
            counts["prereq_groups"] += 1
    db.session.flush()

    with open(d / "sections.csv", newline="") as f:
        for r in csv.DictReader(f):
            course = _course(r["course"])
            term = Term.query.filter_by(code=r["term"]).one()
            sec = Section.query.filter_by(course_id=course.id, term_id=term.id,
                                          section_no=r["section"]).first()
            if sec is None:
                sec = Section(course_id=course.id, term_id=term.id, section_no=r["section"],
                              capacity=int(r["capacity"]), enrolled_count=int(r["enrolled"]))
                db.session.add(sec)
                counts["sections"] += 1
            db.session.flush()
            key = (r["days"], _t(r["start"]), _t(r["end"]))
            if key not in {(m.days, m.start_time, m.end_time) for m in sec.meetings}:
                sec.meetings.append(MeetingTime(days=key[0], start_time=key[1], end_time=key[2]))
                counts["meetings"] += 1

    db.session.commit()
    return counts


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
