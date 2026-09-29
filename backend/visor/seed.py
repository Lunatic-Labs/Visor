"""Load catalog + section CSVs (starting point for KAN-25).

Idempotent: running it twice doesn't create duplicates.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .models import Course, MeetingTime, PrereqGroup, PrereqItem, Section, Term, db


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
