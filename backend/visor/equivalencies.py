"""Transfer-equivalency API (KAN-38). Contract: specs/03-design-equivalencies.md, "API contract".

Lookup answers one of three ways: confirmed, proposed, or unknown. Nothing here ever sets an
equivalency to confirmed on its own; only a POST/PUT with a person's name in decided_by does.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from .models import (EQUIV_KINDS, EQUIV_SOURCES, EQUIV_STATUSES, Course, Equivalency, EquivalencyReview,
                     ExternalCourse, School, db)

bp = Blueprint("equivalencies", __name__, url_prefix="/api")


def _err(message: str, status: int = 400):
    return jsonify({"error": message}), status


# --- JSON shapes ---------------------------------------------------------------------------------

def course_json(c: Course | None) -> dict | None:
    if c is None:
        return None
    return {"id": c.id, "code": c.code, "title": c.title, "credits": c.credits}


def school_json(s: School) -> dict:
    return {"id": s.id, "name": s.name, "state": s.state, "kind": s.kind}


def external_json(e: ExternalCourse) -> dict:
    return {"id": e.id, "school": e.school.name, "school_id": e.school_id, "subject": e.subject,
            "number": e.number, "title": e.title, "credits": e.credits, "catalog_year": e.catalog_year}


def _day(dt: datetime | None) -> str | None:
    return dt.date().isoformat() if dt else None


def equivalency_json(q: Equivalency, *, embed_external: bool = False) -> dict:
    out = {
        "id": q.id, "kind": q.kind, "status": q.status, "source": q.source, "confidence": q.confidence,
        "course": course_json(q.course), "decided_by": q.decided_by, "decided_at": _day(q.decided_at),
        "notes": q.notes, "updated_at": q.updated_at.isoformat() if q.updated_at else None,
        "pending_reviews": sum(1 for r in q.reviews if r.decision == "pending"),
    }
    if embed_external:
        out["external_course"] = external_json(q.external_course)
    return out


def review_json(r: EquivalencyReview) -> dict:
    return {"id": r.id, "equivalency_id": r.equivalency_id, "requested_by": r.requested_by,
            "requested_at": r.requested_at.isoformat(), "reviewer": r.reviewer, "decision": r.decision,
            "decided_at": r.decided_at.isoformat() if r.decided_at else None, "notes": r.notes}


# --- Schools -------------------------------------------------------------------------------------

@bp.get("/schools")
def schools():
    rows = School.query.filter_by(active=True).order_by(School.name).all()
    return jsonify([school_json(s) for s in rows])


@bp.get("/schools/<int:school_id>/courses")
def school_courses(school_id: int):
    if db.session.get(School, school_id) is None:
        return _err("unknown school", 404)
    query = ExternalCourse.query.filter_by(school_id=school_id)
    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(or_(ExternalCourse.subject.ilike(like), ExternalCourse.number.ilike(like),
                                 ExternalCourse.title.ilike(like)))
    rows = query.order_by(ExternalCourse.subject, ExternalCourse.number).all()
    return jsonify([{k: v for k, v in external_json(e).items() if k not in ("school", "school_id")}
                    for e in rows])


# --- Equivalencies -------------------------------------------------------------------------------

@bp.get("/equivalencies")
def list_equivalencies():
    # Eager-load what equivalency_json touches; lazy loads cost one round trip per row on Neon.
    query = Equivalency.query.join(ExternalCourse).options(
        selectinload(Equivalency.external_course).selectinload(ExternalCourse.school),
        selectinload(Equivalency.course),
        selectinload(Equivalency.reviews),
    )
    status = request.args.get("status")
    if status:
        if status not in EQUIV_STATUSES:
            return _err(f"status must be one of {', '.join(EQUIV_STATUSES)}")
        query = query.filter(Equivalency.status == status)
    school_id = request.args.get("school_id", type=int)
    if school_id:
        query = query.filter(ExternalCourse.school_id == school_id)
    rows = query.order_by(ExternalCourse.school_id, ExternalCourse.subject, ExternalCourse.number).all()
    return jsonify([equivalency_json(q, embed_external=True) for q in rows])


@bp.get("/equivalencies/summary")
def summary():
    """Counts for the dashboard, computed in SQL so it doesn't need the full list."""
    by_status = dict(db.session.query(Equivalency.status, func.count()).group_by(Equivalency.status).all())
    top = (db.session.query(School.name, func.count(Equivalency.id))
           .join(ExternalCourse, ExternalCourse.school_id == School.id)
           .join(Equivalency, Equivalency.external_course_id == ExternalCourse.id)
           .filter(Equivalency.status == "confirmed")
           .group_by(School.name).order_by(func.count(Equivalency.id).desc()).limit(5).all())
    return jsonify({
        "confirmed": by_status.get("confirmed", 0),
        "proposed": by_status.get("proposed", 0),
        "rejected": by_status.get("rejected", 0),
        "electives": Equivalency.query.filter_by(status="confirmed", kind="elective").count(),
        "schools": School.query.filter_by(active=True).count(),
        "pending_reviews": EquivalencyReview.query.filter_by(decision="pending").count(),
        "top_schools": [{"name": name, "confirmed": n} for name, n in top],
    })


def _suggest(external: ExternalCourse) -> list[dict]:
    """Rule-based candidates for an external course with no usable table row.

    Hook for Gabriel's rules.equivalency (KAN-39). Returns [] until that lands, so lookups with no
    table row come back 'unknown'.
    """
    return []


@bp.post("/equivalencies/lookup")
def lookup():
    body = request.get_json(silent=True) or {}
    school_id, subject, number = body.get("school_id"), body.get("subject"), body.get("number")
    if not isinstance(school_id, int) or not subject or not number:
        return _err("school_id (int), subject, and number are required")
    school = db.session.get(School, school_id)
    if school is None:
        return _err("unknown school", 404)
    subject, number = str(subject).strip().upper(), str(number).strip()
    title = (body.get("title") or "").strip()

    ext = (ExternalCourse.query.filter_by(school_id=school.id, subject=subject, number=number)
           .order_by(ExternalCourse.catalog_year.desc()).first())
    if ext is None:
        # Record it so it can be flagged for review; we never invent a mapping for it.
        ext = ExternalCourse(school_id=school.id, subject=subject, number=number,
                             title=title or f"{subject} {number}", catalog_year=str(date.today().year))
        db.session.add(ext)
        db.session.commit()

    rows = Equivalency.query.filter(Equivalency.external_course_id == ext.id,
                                    Equivalency.status.in_(("confirmed", "proposed"))).all()
    confirmed = [q for q in rows if q.status == "confirmed"]
    proposed = sorted((q for q in rows if q.status == "proposed"),
                      key=lambda q: q.confidence or 0, reverse=True)

    if confirmed:
        return jsonify({"status": "confirmed", "external_course": external_json(ext),
                        "equivalency": equivalency_json(confirmed[0]), "candidates": [],
                        "alternates": [equivalency_json(q) for q in proposed]})
    if proposed:
        candidates = [{"id": q.id, "course": course_json(q.course), "score": q.confidence,
                       "why": f"proposed in the equivalency table ({q.source})"}
                      for q in proposed if q.course is not None]
        return jsonify({"status": "proposed", "external_course": external_json(ext),
                        "equivalency": equivalency_json(proposed[0]), "candidates": candidates})
    candidates = _suggest(ext)
    return jsonify({"status": "proposed" if candidates else "unknown", "external_course": external_json(ext),
                    "equivalency": None, "candidates": candidates})


def _apply(q: Equivalency, body: dict):
    """Validate and copy writable fields onto q. Returns an error response or None."""
    if "course_id" in body:
        cid = body["course_id"]
        if cid is not None and db.session.get(Course, cid) is None:
            return _err("unknown course_id")
        q.course_id = cid
    for field, allowed in (("kind", EQUIV_KINDS), ("status", EQUIV_STATUSES), ("source", EQUIV_SOURCES)):
        if field in body:
            if body[field] not in allowed:
                return _err(f"{field} must be one of {', '.join(allowed)}")
            setattr(q, field, body[field])
    for field in ("decided_by", "notes"):
        if field in body:
            setattr(q, field, body[field] or ("" if field == "notes" else None))
    if "confidence" in body:
        q.confidence = body["confidence"]

    if q.kind == "direct" and q.course_id is None and q.status == "confirmed":
        return _err("a confirmed direct equivalency needs a course_id")
    if q.kind in ("elective", "none"):
        q.course_id = None
    if q.status in ("confirmed", "rejected"):
        if not q.decided_by:
            return _err(f"{q.status} needs decided_by (the person who decided)")
        q.decided_at = q.decided_at or datetime.now(timezone.utc)
    if q.status == "confirmed":
        clash = Equivalency.query.filter(Equivalency.external_course_id == q.external_course_id,
                                         Equivalency.status == "confirmed",
                                         Equivalency.id != q.id).first()
        if clash:
            return _err(f"external course already has a confirmed equivalency (id {clash.id})", 409)
    return None


@bp.post("/equivalencies")
def create_equivalency():
    body = request.get_json(silent=True) or {}
    ext = db.session.get(ExternalCourse, body.get("external_course_id") or 0)
    if ext is None:
        return _err("external_course_id is required and must exist")
    q = Equivalency(external_course_id=ext.id, kind="direct", status="proposed", source="registrar",
                    notes="")
    if (error := _apply(q, body)) is not None:
        return error
    db.session.add(q)
    db.session.commit()
    return jsonify(equivalency_json(q, embed_external=True)), 201


@bp.put("/equivalencies/<int:equiv_id>")
def update_equivalency(equiv_id: int):
    q = db.session.get(Equivalency, equiv_id)
    if q is None:
        return _err("unknown equivalency", 404)
    if (error := _apply(q, request.get_json(silent=True) or {})) is not None:
        db.session.rollback()
        return error
    db.session.commit()
    return jsonify(equivalency_json(q, embed_external=True))


@bp.post("/equivalencies/<int:equiv_id>/make-primary")
def make_primary(equiv_id: int):
    """Confirm this equivalency and move whatever was confirmed for the same external course back
    to proposed, in one transaction. For external courses approved as more than one Lipscomb
    course, where the registrar decides which one should be the default."""
    q = db.session.get(Equivalency, equiv_id)
    if q is None:
        return _err("unknown equivalency", 404)
    decided_by = ((request.get_json(silent=True) or {}).get("decided_by") or "").strip()
    if not decided_by:
        return _err("decided_by is required (the person making this the primary match)")
    if q.kind == "direct" and q.course_id is None:
        return _err("a confirmed direct equivalency needs a course_id")
    now = datetime.now(timezone.utc)
    for old in Equivalency.query.filter(Equivalency.external_course_id == q.external_course_id,
                                        Equivalency.status == "confirmed", Equivalency.id != q.id):
        old.status = "proposed"
        note = f"Replaced as the primary match by {decided_by} on {now.date().isoformat()}"
        old.notes = f"{old.notes}; {note}" if old.notes else note
    q.status, q.decided_by, q.decided_at = "confirmed", decided_by, now
    db.session.commit()
    return jsonify(equivalency_json(q, embed_external=True))


@bp.post("/equivalencies/<int:equiv_id>/flag")
def flag(equiv_id: int):
    q = db.session.get(Equivalency, equiv_id)
    if q is None:
        return _err("unknown equivalency", 404)
    body = request.get_json(silent=True) or {}
    reviewer = (body.get("reviewer") or "").strip()
    if not reviewer:
        return _err("reviewer is required")
    r = EquivalencyReview(equivalency_id=q.id, reviewer=reviewer,
                          requested_by=(body.get("requested_by") or "registrar").strip(),
                          notes=(body.get("notes") or "").strip())
    db.session.add(r)
    db.session.commit()
    return jsonify(review_json(r)), 201
