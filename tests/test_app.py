import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app


def test_index_get():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"<form" in response.data


def test_summarize_empty_transcript():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.post("/summarize", data={"transcript": ""})
    assert response.status_code == 200
    assert b"Paste a transcript" in response.data


def test_summarize_valid_transcript():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.post(
        "/summarize",
        data={
            "transcript": "Amr: We decided to launch on Friday. Lidia: I will draft the announcement by Thursday."
        },
    )
    assert response.status_code == 200
    assert b"TL;DR" in response.data


def test_api_summarize_valid_transcript():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.post(
        "/api/summarize",
        json={"transcript": "Amr: We decided to launch on Friday."},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["result"]["tldr"]
    assert data["result"]["mode"] == "local"


def test_api_summarize_empty_transcript():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.post("/api/summarize", json={"transcript": ""})
    assert response.status_code == 400


def test_download_valid_transcript():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.post(
        "/download",
        data={"transcript": "Amr: We decided to launch on Friday."},
    )
    assert response.status_code == 200
    assert "markdown" in response.content_type
    assert b"# Meeting notes" in response.data
