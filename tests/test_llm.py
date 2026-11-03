import io
import json
import os
import sys
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import llm_available, summarize_with_llm


def _fake_response(payload):
    response = mock.MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__.return_value = response
    return response


def test_llm_available_false_without_key():
    with mock.patch.dict(os.environ, {}, clear=True):
        assert llm_available() is False


def test_llm_available_true_with_key():
    with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True):
        assert llm_available() is True


def test_summarize_with_llm_parses_valid_response():
    payload = {
        "choices": [{"message": {"content": json.dumps({
            "tldr": "Launched beta.",
            "key_points": ["Four onboarding screens"],
            "decisions": ["Invite-only beta"],
            "actions": [{"text": "Draft copy", "owner": "Hana", "due": "Friday"}],
        })}}]
    }
    with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True), \
         mock.patch.object(urllib.request, "urlopen", return_value=_fake_response(payload)):
        result = summarize_with_llm("Amr: hello")
    assert result["tldr"] == "Launched beta."
    assert result["actions"][0]["owner"] == "Hana"


def test_summarize_with_llm_strips_code_fences():
    inner = json.dumps({"tldr": "t", "key_points": [], "decisions": [], "actions": []})
    payload = {"choices": [{"message": {"content": "```json\n" + inner + "\n```"}}]}
    with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True), \
         mock.patch.object(urllib.request, "urlopen", return_value=_fake_response(payload)):
        assert summarize_with_llm("Amr: hello")["tldr"] == "t"


def test_summarize_with_llm_returns_none_on_network_error():
    with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True), \
         mock.patch.object(urllib.request, "urlopen", side_effect=OSError("down")):
        assert summarize_with_llm("Amr: hello") is None


def test_summarize_with_llm_returns_none_on_bad_json():
    payload = {"choices": [{"message": {"content": "not json"}}]}
    with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True), \
         mock.patch.object(urllib.request, "urlopen", return_value=_fake_response(payload)):
        assert summarize_with_llm("Amr: hello") is None


def test_summarize_with_llm_bad_base_url_does_not_raise():
    env = {"OPENAI_API_KEY": "x", "OPENAI_BASE_URL": "not-a-url"}
    with mock.patch.dict(os.environ, env, clear=True):
        assert summarize_with_llm("Amr: hello") is None


def test_summarize_with_llm_empty_transcript_returns_none():
    assert summarize_with_llm("") is None
