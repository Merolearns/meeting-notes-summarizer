import os
from flask import Flask, render_template, request, jsonify, Response

from summarize import (
    parse_transcript,
    detect_speakers,
    extract_summary,
    extract_key_points,
    extract_decisions,
    extract_actions,
    stats,
)
from llm import llm_available, summarize_with_llm

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-not-for-production")

SUMMARY_KEYS = {"tldr", "key_points", "decisions", "actions"}


def _load_sample_transcript():
    path = os.path.join(os.path.dirname(__file__), "data", "sample_transcript.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _run_local_engine(transcript):
    speakers = detect_speakers(parse_transcript(transcript))
    return {
        "tldr": extract_summary(transcript),
        "key_points": extract_key_points(transcript),
        "decisions": extract_decisions(transcript),
        "actions": extract_actions(transcript),
        "speakers": speakers,
        "stats": stats(transcript),
        "mode": "local",
    }


def build_result(transcript, mode):
    if mode == "ai" and llm_available():
        ai_result = summarize_with_llm(transcript)
        if isinstance(ai_result, dict) and SUMMARY_KEYS.issubset(ai_result.keys()):
            speakers = detect_speakers(parse_transcript(transcript))
            ai_result["speakers"] = speakers
            ai_result["stats"] = stats(transcript)
            ai_result["mode"] = "ai"
            return ai_result
    return _run_local_engine(transcript)


@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        sample=_load_sample_transcript(),
        transcript=_load_sample_transcript(),
        mode="local",
        llm_on=llm_available(),
    )


@app.route("/summarize", methods=["POST"])
def summarize():
    transcript = request.form.get("transcript", "").strip()
    mode = request.form.get("mode", "local")
    if mode == "ai" and not llm_available():
        mode = "local"
    if not transcript:
        return render_template(
            "index.html",
            sample=_load_sample_transcript(),
            transcript=transcript,
            mode=mode,
            llm_on=llm_available(),
            error="Paste a transcript or load the sample to get started.",
        )
    result = build_result(transcript, mode)
    return render_template(
        "index.html",
        sample=_load_sample_transcript(),
        transcript=transcript,
        mode=result["mode"],
        llm_on=llm_available(),
        result=result,
    )


@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    data = request.get_json(silent=True) or {}
    transcript = (data.get("transcript") or "").strip()
    mode = data.get("mode", "local")
    if not transcript:
        return jsonify({"error": "Transcript is required."}), 400
    result = build_result(transcript, mode)
    return jsonify({"mode": result["mode"], "result": result})


@app.route("/download", methods=["POST"])
def download():
    transcript = request.form.get("transcript", "")
    mode = request.form.get("mode", "local")
    result = build_result(transcript, mode)
    return Response(
        _to_markdown(result),
        mimetype="text/markdown",
        headers={"Content-Disposition": "attachment; filename=meeting-notes.md"},
    )


def _to_markdown(result):
    lines = ["# Meeting notes", "", "## TL;DR", "", result.get("tldr", "")]
    lines.extend(["", "## Key points", ""])
    for point in result.get("key_points", []):
        lines.append(f"- {point}")
    lines.extend(["", "## Decisions", ""])
    for decision in result.get("decisions", []):
        lines.append(f"- {decision}")
    lines.extend(["", "## Action items", ""])
    for action in result.get("actions", []):
        if isinstance(action, dict):
            text = action.get("text", "")
            owner = action.get("owner")
            due = action.get("due")
            parts = []
            if owner:
                parts.append(f"Owner: {owner}")
            if due:
                parts.append(f"Due: {due}")
            suffix = " · ".join(parts)
            lines.append(f"- [ ] {text}" + (f" ({suffix})" if suffix else ""))
        else:
            lines.append(f"- [ ] {action}")
    lines.extend(["", "## Participants", ""])
    for speaker in result.get("speakers", []):
        lines.append(f"- {speaker}")
    return "\n".join(lines)


if __name__ == "__main__":
    app.run(debug=True)
