"""Write-route guard (KAN-46)."""
import pytest

from visor.auth import HEADER, TOKEN_ENV

WRITES = [
    ("post", "/api/equivalencies", {"external_course_id": 1}),
    ("put", "/api/equivalencies/1", {"notes": "x"}),
    ("post", "/api/equivalencies/1/flag", {"reviewer": "Dr. Nordstrom"}),
]


@pytest.fixture()
def prod(app, monkeypatch):
    """Behave like the deployed site: not testing, not debug."""
    monkeypatch.setitem(app.config, "TESTING", False)
    monkeypatch.setattr(app, "debug", False)
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    return app


@pytest.mark.parametrize("method,url,body", WRITES)
def test_writes_refused_when_no_token_configured(prod, client, method, url, body):
    r = getattr(client, method)(url, json=body)
    assert r.status_code == 403


@pytest.mark.parametrize("method,url,body", WRITES)
def test_writes_need_the_right_token(prod, client, monkeypatch, method, url, body):
    monkeypatch.setenv(TOKEN_ENV, "s3cret")
    assert getattr(client, method)(url, json=body).status_code == 401
    assert getattr(client, method)(url, json=body, headers={HEADER: "wrong"}).status_code == 401
    ok = getattr(client, method)(url, json=body, headers={HEADER: "s3cret"})
    assert ok.status_code in (200, 201)


def test_reads_and_lookup_stay_open(prod, client):
    assert client.get("/api/schools").status_code == 200
    assert client.get("/api/equivalencies").status_code == 200
    school = client.get("/api/schools").get_json()[0]["id"]
    r = client.post("/api/equivalencies/lookup", json={"school_id": school, "subject": "ENGL", "number": "1010"})
    assert r.status_code == 200


def test_local_dev_and_tests_need_no_token(app, client):
    # app fixture runs with TESTING=True, like pytest and `flask run --debug`
    assert client.post("/api/equivalencies/1/flag", json={"reviewer": "Dr. Nordstrom"}).status_code == 201
