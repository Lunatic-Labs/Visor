"""Stopgap guard for routes that change data (KAN-46), until real login lands (KAN-30).

`main` deploys to a public URL, so any POST/PUT that writes to the database needs a shared
secret: the request must send header `X-Visor-Token` matching the `VISOR_WRITE_TOKEN` env var.

- Local dev (`flask run --debug`) and tests are left open so nobody needs a token to work.
- Anywhere else with no `VISOR_WRITE_TOKEN` set (e.g. production before someone sets one),
  writes are refused outright. Failing closed is the point.

Reads (GET) and the lookup itself stay open; see specs/03-design-equivalencies.md.
"""
from __future__ import annotations

import hmac
import os
from functools import wraps

from flask import current_app, jsonify, request

TOKEN_ENV = "VISOR_WRITE_TOKEN"
HEADER = "X-Visor-Token"


def write_guard():
    """Return an error response if this request may not write, else None."""
    expected = os.environ.get(TOKEN_ENV, "")
    if not expected:
        if current_app.debug or current_app.testing:
            return None
        return jsonify({"error": "writes are turned off on this deployment"}), 403
    given = request.headers.get(HEADER, "")
    if not hmac.compare_digest(given.encode(), expected.encode()):
        return jsonify({"error": f"missing or wrong {HEADER} header"}), 401
    return None


def require_write_token(view):
    """Decorator for a single route. For a whole blueprint: `bp.before_request(write_guard)`."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if (denied := write_guard()) is not None:
            return denied
        return view(*args, **kwargs)
    return wrapper
