import json
import os
import urllib.request


def llm_available() -> bool:
    key = os.getenv("OPENAI_API_KEY", "")
    return bool(key)


def summarize_with_llm(transcript: str) -> dict | None:
    if not transcript:
        return None

    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    system_message = (
        "You are a helpful meeting assistant. "
        "Output strict JSON only with no markdown and no explanation."
    )
    user_message = (
        "Summarize the following meeting transcript into structured notes. "
        "Return ONLY a JSON object with these exact keys: "
        "tldr (string), key_points (list of strings), "
        "decisions (list of strings), actions (list of objects with keys "
        "text, owner, due). "
        "No prose outside the JSON.\n\n"
        f"Transcript:\n{transcript}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        url = f"{base_url}/v1/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read().decode("utf-8")
            response_json = json.loads(body)
            content = response_json["choices"][0]["message"]["content"].strip()

            if content.startswith("```"):
                content = content.strip("`")
                if content.lower().startswith("json"):
                    content = content[4:].strip()

            result = json.loads(content)
            if not isinstance(result, dict):
                return None

            if not isinstance(result.get("tldr"), str):
                return None
            if not isinstance(result.get("key_points"), list):
                return None
            if not isinstance(result.get("decisions"), list):
                return None

            actions = result.get("actions")
            if not isinstance(actions, list):
                return None
            for action in actions:
                if not isinstance(action, dict) or "text" not in action:
                    return None

            return result
    except Exception:
        return None
