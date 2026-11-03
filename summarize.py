import re
from math import sqrt
from collections import Counter

STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
    "her", "was", "one", "our", "out", "day", "get", "has", "him", "his",
    "how", "man", "new", "now", "old", "see", "two", "way", "who", "boy",
    "did", "its", "let", "put", "say", "she", "too", "use", "with", "have",
    "this", "will", "your", "from", "they", "know", "want", "been", "good",
    "much", "some", "time", "very", "when", "come", "here", "just", "like",
    "long", "make", "many", "over", "such", "take", "than", "them", "well",
    "were", "what", "would", "there", "their", "about", "could", "other",
    "after", "first", "never", "these", "think", "where", "being", "every",
    "great", "might", "shall", "still", "those", "while", "should", "really",
}

DECISION_CUES = [
    "decided", "agreed", "decision", "concluded", "final call",
    "approved", "settled on", "we will go with", "was chosen", "were chosen",
]

ACTION_CUES = [
    "will", "'ll", "going to", "needs to", "need to", "should", "must",
    "has to", "have to", "action item", "todo", "follow up", "follow-up",
]

IMPERATIVE_VERBS = {
    "send", "prepare", "schedule", "draft", "review", "update", "fix",
    "call", "email", "share", "create", "finish", "book", "cancel",
    "confirm", "write", "compile", "circulate", "discuss", "make", "do",
    "get", "take", "give", "reach",
}

DUE_PATTERNS = [
    r"\bby\s+(?:next\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|tomorrow|today|EOD|end\s+of\s+day|end\s+of\s+week|the\s+end\s+of\s+(?:the\s+)?(?:week|month))\b",
    r"\bbefore\s+(?:next\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|tomorrow|today)\b",
    r"\bdue\s+(?:on\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|tomorrow|today|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b",
    r"\b(?:next\s+week|this\s+week|coming\s+week|by\s+EOD|by\s+end\s+of\s+day|by\s+COB|end\s+of\s+week)\b",
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?\b",
    r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
]

# Labels that look like "Name:" but are not speakers.
NON_SPEAKERS = {
    "action item", "action items", "note", "decided", "decision",
    "recap", "quick recap", "todo", "reminder",
}

# Pronouns that never resolve to an owner on their own.
_NO_OWNER = {"he", "she", "it", "they", "you"}

_OWNER_RE = re.compile(
    r"\b([A-Z][a-zA-Z]+)(?:'ll|\s+will|\s+is\s+going\s+to|\s+'s\s+going\s+to"
    r"|\s+needs\s+to|\s+need\s+to|\s+should|\s+must|\s+has\s+to|\s+have\s+to)\b"
)


def split_sentences(text):
    if not text:
        return []
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])(?=\s+(?=[A-Z0-9\"']))", text)
    return [p.strip() for p in parts if p.strip()]


def parse_transcript(text):
    if not text or not text.strip():
        return []
    turns = []
    current = None
    label_re = re.compile(r"^([A-Z][A-Za-z\-]{0,29}):\s*(.*)$")
    bracket_re = re.compile(r"^\[([A-Za-z\s\-]+)\]:\s*(.*)$")

    def push(text, speaker):
        nonlocal current
        current = {"speaker": speaker, "text": text}
        turns.append(current)

    for raw in text.splitlines():
        # also catch "Name:" labels that start mid-line
        fragments = re.split(r"\s+(?=[A-Z][a-z]{1,29}:\s)", raw.strip())
        for frag in fragments:
            frag = frag.strip()
            if not frag:
                continue
            match = label_re.match(frag) or bracket_re.match(frag)
            name = match.group(1).strip() if match else None
            if name and name.lower() not in NON_SPEAKERS:
                push(match.group(2).strip(), name)
            elif current is not None:
                current["text"] += " " + frag
            else:
                push(frag, None)

    return [t for t in turns if t["text"]]


def detect_speakers(turns):
    seen = set()
    speakers = []
    for turn in turns:
        speaker = turn.get("speaker")
        if speaker and speaker not in seen:
            seen.add(speaker)
            speakers.append(speaker)
    return speakers


def _turn_sentences(text):
    """Sentences paired with the speaker of their turn (prefix stripped)."""
    items = []
    for turn in parse_transcript(text):
        sentences = split_sentences(turn["text"])
        # re-attach bare labels ("Action item:", "Decided:") to the sentence
        # that follows them instead of leaving them as fragments
        merged = []
        i = 0
        while i < len(sentences):
            s = sentences[i]
            if re.fullmatch(r"[A-Z][A-Za-z ]{0,30}:", s) and i + 1 < len(sentences):
                merged.append(s + " " + sentences[i + 1])
                i += 2
            else:
                merged.append(s)
                i += 1
        for sentence in merged:
            items.append({"speaker": turn["speaker"], "text": sentence})
    return items


def _word_scores(text):
    words = re.findall(r"[A-Za-z']+", text.lower())
    words = [w for w in words if len(w) >= 3 and w not in STOPWORDS]
    counts = Counter(words)
    peak = max(counts.values()) if counts else 1
    return {word: count / peak for word, count in counts.items()}


def _score_sentence(sentence, scores_map, position_bonus=1.0):
    words = re.findall(r"[A-Za-z']+", sentence.lower())
    words = [w for w in words if len(w) >= 3 and w not in STOPWORDS]
    if not words:
        return 0.0
    total = sum(scores_map.get(w, 0) for w in words)
    return round(total / sqrt(len(words)) * position_bonus, 4)


def score_sentences(text):
    sentences = split_sentences(text)
    if not sentences:
        return []
    scores_map = _word_scores(text)
    total = len(sentences)
    results = []
    for i, sentence in enumerate(sentences):
        bonus = 1.15 if total > 1 and i < total * 0.2 else 1.0
        results.append((sentence, _score_sentence(sentence, scores_map, bonus)))
    return results


def extract_summary(text, n=3):
    items = _turn_sentences(text)
    if not items:
        return ""
    scores_map = _word_scores(" ".join(it["text"] for it in items))
    total = len(items)
    ranked = sorted(
        enumerate(items),
        key=lambda pair: _score_sentence(
            pair[1]["text"], scores_map,
            1.15 if total > 1 and pair[0] < total * 0.2 else 1.0,
        ),
        reverse=True,
    )
    top = sorted(ranked[:n], key=lambda pair: pair[0])
    return " ".join(item["text"] for _, item in top)


def extract_key_points(text, n=5):
    items = _turn_sentences(text)
    if not items:
        return []
    scores_map = _word_scores(" ".join(it["text"] for it in items))
    total = len(items)
    ranked = sorted(
        enumerate(items),
        key=lambda pair: _score_sentence(
            pair[1]["text"], scores_map,
            1.15 if total > 1 and pair[0] < total * 0.2 else 1.0,
        ),
        reverse=True,
    )
    picked = []
    picked_words = []
    for idx, item in ranked:
        words = {
            w for w in re.findall(r"[A-Za-z']+", item["text"].lower())
            if len(w) >= 3 and w not in STOPWORDS
        }
        if not words:
            continue
        if any(len(words & seen) / len(words) > 0.6 for seen in picked_words):
            continue
        picked.append((idx, item["text"]))
        picked_words.append(words)
        if len(picked) >= n:
            break
    picked.sort(key=lambda pair: pair[0])
    return [sentence for _, sentence in picked]


def extract_decisions(text):
    decisions = []
    for item in _turn_sentences(text):
        sentence = item["text"]
        lowered = sentence.lower()
        if not any(cue in lowered for cue in DECISION_CUES):
            continue
        # drop bare fragments like "Agreed." / "Decided." — no content
        words = re.findall(r"[A-Za-z']+", lowered)
        cues_only = {"decided", "agreed", "approved", "concluded", "decision"}
        if len(words) <= 2 and all(w in cues_only for w in words):
            continue
        decisions.append(sentence)
    return decisions


def _extract_owner(sentence, speaker):
    match = _OWNER_RE.search(sentence)
    if match:
        name = match.group(1)
        lowered = name.lower()
        if lowered in _NO_OWNER:
            return None
        if lowered in ("i", "we"):
            return speaker
        return name
    return speaker


def _extract_due(sentence):
    for pattern in DUE_PATTERNS:
        match = re.search(pattern, sentence, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def extract_actions(text):
    actions = []
    for item in _turn_sentences(text):
        sentence = item["text"]
        if re.fullmatch(r"[A-Z][A-Za-z ]{0,30}:", sentence):
            continue  # bare label with nothing after it
        if sentence.strip().endswith("?"):
            continue  # questions are not action items
        lowered = sentence.lower()
        words = re.findall(r"[A-Za-z]+", lowered)
        is_action = any(cue in lowered for cue in ACTION_CUES)
        if not is_action and words and words[0] in IMPERATIVE_VERBS:
            is_action = True
        if is_action:
            actions.append({
                "text": sentence,
                "owner": _extract_owner(sentence, item["speaker"]),
                "due": _extract_due(sentence),
            })
    return actions


def stats(text):
    turns = parse_transcript(text)
    speakers = detect_speakers(turns)
    words = re.findall(r"[A-Za-z']+", text)
    word_count = len(words)
    return {
        "words": word_count,
        "sentences": len(split_sentences(text)),
        "turns": len(turns),
        "speakers": len(speakers),
        "reading_minutes": max(1, round(word_count / 200)) if word_count else 0,
    }
