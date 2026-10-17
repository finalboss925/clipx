import pytest
from pydantic import ValidationError
from clipx.schemas import CandidateResponse, Options, Transcript
from clipx.timeline import snap, dedupe, edit_timeline
from clipx.captions import build_ass, ass_time, build_srt


@pytest.fixture
def words():
    return [
        {
            "start": float(i),
            "end": i + 0.8,
            "text": f"word{i}" + ("." if i % 5 == 4 else ""),
        }
        for i in range(60)
    ]


def candidate(**overrides):
    return {
        "start": 0.4,
        "end": 22.1,
        "title": "A hook",
        "hook": "Why?",
        "reason": "A complete idea",
        "scores": {"hook": 80, "flow": 70, "value": 60, "trend": 50},
        "total": 99,
        **overrides,
    }


def test_snap_sentence_boundaries(words):
    c = snap(candidate(), words, 15, 30)
    assert c["start"] == 0 and c["end"] == 19.8
    assert c["total"] == 68.5


def test_snap_respects_length(words):
    c = snap(candidate(start=1, end=55), words, 15, 20)
    assert 15 <= c["end"] - c["start"] <= 20


def test_empty_and_short_transcript():
    assert snap(candidate(), []) is None
    assert snap(candidate(), [{"start": 0, "end": 2, "text": "Short."}]) is None


def test_dedupe():
    assert (
        len(
            dedupe(
                [
                    candidate(start=0, end=20, total=80),
                    candidate(start=1, end=21, total=60),
                    candidate(start=30, end=50, total=70),
                ],
                5,
            )
        )
        == 2
    )


@pytest.mark.parametrize(
    "override",
    [
        {"end": 10},
        {"start": float("nan")},
        {"scores": {"hook": 101, "flow": 2, "value": 3, "trend": 4}},
        {"unexpected": True},
    ],
)
def test_llm_schema_rejects_invalid(override):
    with pytest.raises(ValidationError):
        CandidateResponse.model_validate({"clips": [candidate(**override)]})


def test_cleanup_and_captions_share_timeline(words):
    words[8]["text"] = "um"
    timeline = edit_timeline(words, 0, 24.8, True, [10, 11])
    assert not any(
        w["text"] == "um" or w["text"].startswith(("word10", "word11"))
        for w in timeline["words"]
    )
    assert timeline["duration"] < 24.8
    assert all(
        0 <= w["start"] < w["end"] <= timeline["duration"] + 0.001
        for w in timeline["words"]
    )


def test_caption_timing_and_escaping():
    words = [
        {"start": 0, "end": 0.5, "text": "{\\pos(0,0)}hello"},
        {"start": 0.6, "end": 1.2, "text": "world!"},
    ]
    ass = build_ass(words)
    assert "Dialogue: 0,0:00:00.00,0:00:00.50" in ass
    assert "Dialogue: 0,0:00:00.60,0:00:01.20" in ass
    assert "{\\pos(0,0)}" not in ass
    assert "00:00:00,000 --> 00:00:01,200" in build_srt(words)
    assert ass_time(59.999) == "0:01:00.00"


def test_options_validation():
    with pytest.raises(ValidationError):
        Options(min_length=80, max_length=20)
    with pytest.raises(ValidationError):
        Options(clip_count=100)


def test_brand_assets_reject_path_traversal():
    from clipx.schemas import Brand

    with pytest.raises(ValidationError):
        Brand(logo="../../private.png")
    with pytest.raises(ValidationError):
        Brand(intro="/tmp/video.mp4")


def test_brand_intro_srt_offset():
    assert "00:00:02,000 --> 00:00:02,800" in build_srt(
        [{"start": 0, "end": 0.8, "text": "Hello"}], offset=2
    )


def test_word_delete_preserves_unselected_pauses():
    words = [
        {"start": 0, "end": 1, "text": "First"},
        {"start": 2, "end": 3, "text": "um"},
        {"start": 4, "end": 5, "text": "last."},
    ]
    timeline = edit_timeline(words, 0, 6, False, [1])
    assert timeline["spans"] == [[0, 2], [3, 6]]
    assert timeline["duration"] == 5
    assert timeline["words"][-1]["start"] == 3


def test_cleanup_removes_filler_audio_not_only_caption():
    words = [
        {"start": 0, "end": 0.5, "text": "Hello"},
        {"start": 0.51, "end": 0.59, "text": "um"},
        {"start": 0.6, "end": 1, "text": "there."},
    ]
    timeline = edit_timeline(words, 0, 1, True)
    assert all(not (a < 0.55 < b) for a, b in timeline["spans"])
