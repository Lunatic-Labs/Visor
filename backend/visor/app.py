"""Flask app factory and API."""
from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, abort, jsonify, request

from . import rules
from .models import Course, PrereqGroup, Section, Term, db

DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data" / "sample"


def _to_rule_section(s: Section) -> rules.Section:
    return rules.Section(
        course=s.course.code,
        number=s.section_no,
        meetings=tuple(rules.Meeting(m.days, m.start_time, m.end_time) for m in s.meetings),
    )


def _section_json(s: Section) -> dict:
    return {
        "id": s.id,
        "label": f"{s.course.code}-{s.section_no}",
        "course": s.course.code,
        "title": s.course.title,
        "capacity": s.capacity,
        "enrolled": s.enrolled_count,
        "full": s.enrolled_count >= s.capacity,
        "meetings": [
            {"days": m.days, "start": m.start_time.strftime("%H:%M"), "end": m.end_time.strftime("%H:%M")}
            for m in s.meetings
        ],
    }


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///visor-dev.db")
    app.config.update(config or {})
    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.cli.command("seed")
    def seed_cmd():
        """Load the sample CSVs in data/sample into the database."""
        from .seed import load
        print(load(os.environ.get("VISOR_DATA_DIR", DEFAULT_DATA)))

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/terms")
    def terms():
        return jsonify([{"code": t.code, "name": t.name} for t in Term.query.order_by(Term.code)])

    def _term_sections(code: str) -> list[Section]:
        term = Term.query.filter_by(code=code).first() or abort(404, "unknown term")
        return Section.query.filter_by(term_id=term.id).all()

    @app.get("/api/terms/<code>/sections")
    def sections(code):
        return jsonify([_section_json(s) for s in _term_sections(code)])

    @app.get("/api/terms/<code>/conflicts")
    def conflicts(code):
        """Conflicts among the sections given in ?sections=CS 3233-01,CS 3433-01
        (or all sections in the term if omitted)."""
        secs = _term_sections(code)
        wanted = request.args.get("sections")
        if wanted:
            labels = {w.strip() for w in wanted.split(",")}
            secs = [s for s in secs if f"{s.course.code}-{s.section_no}" in labels]
        pairs = rules.find_conflicts([_to_rule_section(s) for s in secs])
        return jsonify([{"a": a, "b": b} for a, b in pairs])

    @app.get("/api/courses/<subject>/<number>/prereq-check")
    def prereq_check(subject, number):
        """?completed=CS 1113,MA 1314 -> which prerequisite groups are still missing."""
        course = Course.query.filter_by(subject=subject, number=number).first() or abort(404)
        groups = PrereqGroup.query.filter_by(course_id=course.id).all()
        prereqs = {course.code: [[i.required_course.code for i in g.items] for g in groups]}
        done = {c.strip() for c in request.args.get("completed", "").split(",") if c.strip()}
        return jsonify({"course": course.code, "missing": rules.missing_prereqs(course.code, prereqs, done)})

    return app
