import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from summarize import (
    split_sentences,
    parse_transcript,
    detect_speakers,
    score_sentences,
    extract_summary,
    extract_key_points,
    extract_decisions,
    extract_actions,
    stats,
)

SAMPLE_PATH = ROOT / "data" / "sample_transcript.txt"
SAMPLE_TEXT = SAMPLE_PATH.read_text(encoding="utf-8")


def test_split_sentences_keeps_abbreviations_and_decimals():
    text = "Use e.g. apples. It is 1.5 meters. Done."
    sentences = split_sentences(text)
    assert len(sentences) == 3
    assert any("e.g." in s for s in sentences)
    assert any("1.5" in s for s in sentences)


def test_split_sentences_splits_normal_sentences():
    text = "First sentence. Second sentence. Third sentence."
    assert len(split_sentences(text)) == 3


def test_parse_transcript_groups_two_speakers_and_continuation():
    transcript = "Amr: hi\nLidia: hello\nthis is a continuation"
    turns = parse_transcript(transcript)
    assert len(turns) == 2
    assert turns[0]["speaker"] == "Amr"
    assert turns[1]["speaker"] == "Lidia"
    assert "hello" in turns[1]["text"]
    assert "continuation" in turns[1]["text"]


def test_parse_transcript_without_speaker_labels_returns_none_speaker():
    transcript = "Just a plain line of text."
    turns = parse_transcript(transcript)
    assert len(turns) == 1
    assert turns[0]["speaker"] is None


def test_detect_speakers_returns_unique_names_in_first_appearance_order():
    transcript = "Bob: one\nAlice: two\nBob: three"
    speakers = detect_speakers(parse_transcript(transcript))
    assert speakers == ["Bob", "Alice"]


def test_sample_extract_decisions_has_at_least_three_items():
    decisions = extract_decisions(SAMPLE_TEXT)
    assert len(decisions) >= 3


def test_sample_extract_actions_has_at_least_four_items():
    actions = extract_actions(SAMPLE_TEXT)
    assert len(actions) >= 4


def test_sample_extract_actions_contains_amr_owner():
    actions = extract_actions(SAMPLE_TEXT)
    assert any(action["owner"] == "Amr" for action in actions)


def test_sample_extract_actions_contains_a_due_date():
    actions = extract_actions(SAMPLE_TEXT)
    assert any(action["due"] is not None for action in actions)


def test_extract_key_points_returns_at_most_n_in_document_order():
    key_points = extract_key_points(SAMPLE_TEXT, n=3)
    assert len(key_points) <= 3
    positions = [SAMPLE_TEXT.find(point) for point in key_points]
    assert all(p >= 0 for p in positions)
    assert positions == sorted(positions)


def test_extract_summary_returns_non_empty_string_for_sample():
    summary = extract_summary(SAMPLE_TEXT)
    assert isinstance(summary, str)
    assert len(summary.strip()) > 0


def test_stats_empty_string_returns_zeros_and_extract_actions_empty():
    result = stats("")
    assert all(value == 0 for value in result.values())
    assert extract_actions("") == []


def test_score_sentences_returns_tuples_with_non_negative_scores():
    scores = score_sentences("This is one sentence. This is another.")
    assert len(scores) == 2
    for sentence, score in scores:
        assert isinstance(sentence, str)
        assert score >= 0
    assert scores[0][0] == "This is one sentence."


def test_sample_detect_speakers_includes_amr_and_lidia():
    speakers = detect_speakers(parse_transcript(SAMPLE_TEXT))
    assert "Amr" in speakers
    assert "Lidia" in speakers


def test_extract_actions_falls_back_to_turn_speaker_as_owner():
    actions = extract_actions("Lidia: I will draft the announcement by Thursday.")
    assert len(actions) == 1
    assert actions[0]["owner"] == "Lidia"
    assert actions[0]["due"] == "by Thursday"


def test_extract_actions_strips_speaker_prefix_from_text():
    actions = extract_actions("Lidia: I will draft the announcement.")
    assert actions
    assert not actions[0]["text"].startswith("Lidia:")


def test_extract_actions_explicit_owner_beats_speaker_fallback():
    actions = extract_actions("Lidia: Amr will review the legal copy by Thursday.")
    assert actions[0]["owner"] == "Amr"


def test_extract_actions_pronoun_owner_gives_none():
    actions = extract_actions("Lidia: He will review the copy by Thursday.")
    assert actions[0]["owner"] is None


def test_parse_transcript_mid_line_label_starts_new_turn():
    turns = parse_transcript("Amr: We decided to launch on Friday. Lidia: I will draft it.")
    assert [t["speaker"] for t in turns] == ["Amr", "Lidia"]


def test_parse_transcript_action_item_label_is_not_a_speaker():
    speakers = detect_speakers(parse_transcript("Hana: Action item: Hana will draft the copy."))
    assert speakers == ["Hana"]
    assert "Action item" not in speakers


def test_extract_actions_skips_questions():
    actions = extract_actions("Lidia: Should we include crash-free sessions too?")
    assert actions == []


def test_extract_decisions_drops_bare_fragments():
    decisions = extract_decisions("Hana: Agreed. Amr: We agreed on that timing.")
    assert decisions == ["We agreed on that timing."]
