"""HTTP upload for the registrar's catalog/section CSVs (KAN-25).

Thin wrapper around seed.load(): saves whichever of terms/courses/prereqs/sections.csv were
actually uploaded into a temp directory under the names load() expects, imports just those,
and returns the same counts/errors load() produces. All the row validation, line-numbered
error reporting, and idempotent-upsert behavior lives in seed.py; this module only deals with
getting uploaded files onto disk in the shape load() already understands.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from .seed import load

bp = Blueprint("catalog_import", __name__, url_prefix="/api")

FILES = ("terms", "courses", "prereqs", "sections")


@bp.post("/import/catalog")
def import_catalog():
    """multipart/form-data with any subset of file fields named terms, courses, prereqs,
    sections (each a .csv). ?dry_run=1 checks everything without saving."""
    uploaded = {name: request.files[name] for name in FILES
               if name in request.files and request.files[name].filename}
    if not uploaded:
        return jsonify({"error": "upload at least one of: " + ", ".join(f"{n}.csv" for n in FILES)}), 400

    dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes")

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for name, file in uploaded.items():
            file.save(d / f"{name}.csv")
        result = load(d, dry_run=dry_run, only=[f"{name}.csv" for name in uploaded])

    return jsonify({"ok": result.ok, "counts": result.counts, "errors": result.errors})
