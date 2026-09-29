from pathlib import Path

import pytest

from visor import create_app
from visor.models import db
from visor.seed import load

DATA = Path(__file__).resolve().parents[2] / "data" / "sample"


@pytest.fixture()
def app():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        load(DATA)
        yield app
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
