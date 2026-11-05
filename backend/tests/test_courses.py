"""GET /api/courses: Lipscomb's own catalog, used when confirming an equivalency manually."""


def test_lists_all_courses(client):
    body = client.get("/api/courses").json
    assert any(c["code"] == "CS 1113" for c in body)
    assert all({"id", "code", "title", "credits"} <= c.keys() for c in body)


def test_search_by_subject_number_or_title(client):
    assert {c["code"] for c in client.get("/api/courses?q=1113").json} == {"CS 1113"}
    assert {c["code"] for c in client.get("/api/courses?q=programming").json} >= {"CS 1113", "CS 1213"}


def test_search_no_match_is_empty_list(client):
    assert client.get("/api/courses?q=nope-not-a-course").json == []
