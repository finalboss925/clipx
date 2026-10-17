"""One source-to-output timeline for cuts, captions, tracking and transcript edits."""

import re
from .schemas import Candidate, Word


def sentences(words: list[dict]) -> list[dict]:
    out = []
    group = []
    for word in words:
        group.append(word)
        if re.search(r'[.!?。！？]["\u201d\']?$', word["text"]) or len(group) >= 65:
            out.append(
                {
                    "start": group[0]["start"],
                    "end": group[-1]["end"],
                    "text": " ".join(w["text"] for w in group),
                }
            )
            group = []
    if group:
        out.append(
            {
                "start": group[0]["start"],
                "end": group[-1]["end"],
                "text": " ".join(w["text"] for w in group),
            }
        )
    return out


def snap(candidate: dict, words: list[dict], minimum=15, maximum=90) -> dict | None:
    if not words:
        return None
    spans = sentences(words)
    starts = [s["start"] for s in spans]
    ends = [s["end"] for s in spans]
    start = min(starts, key=lambda x: abs(x - candidate["start"]))
    allowed = [x for x in ends if minimum <= x - start <= maximum]
    if not allowed:
        return None
    end = min(allowed, key=lambda x: abs(x - candidate["end"]))
    if start < words[0]["start"] or end > words[-1]["end"]:
        return None
    return Candidate.model_validate(
        {**candidate, "start": start, "end": end}
    ).model_dump()


def dedupe(candidates: list[dict], count: int) -> list[dict]:
    selected = []
    for c in sorted(candidates, key=lambda c: c["total"], reverse=True):
        if any(
            max(0, min(c["end"], s["end"]) - max(c["start"], s["start"]))
            / min(c["end"] - c["start"], s["end"] - s["start"])
            > 0.25
            for s in selected
        ):
            continue
        selected.append(c)
        if len(selected) >= count:
            break
    return selected


def edit_timeline(words, start, end, cleanup=False, deleted=None):
    deleted = set(deleted or [])
    retained = []
    for i, w in enumerate(words):
        if w["start"] < start or w["end"] > end or i in deleted:
            continue
        if cleanup and w["text"].lower().strip(".,!?") in {"um", "uh", "umm", "uhh"}:
            continue
        retained.append(w)
    if not retained:
        raise ValueError("No words remain in this clip")
    if not cleanup:
        spans = [[start, end]]
    else:
        spans = []
        for w in retained:
            a = max(start, w["start"] - 0.055)
            b = min(end, w["end"] + 0.08)
            if spans and a - spans[-1][1] < 0.22:
                spans[-1][1] = max(spans[-1][1], b)
            else:
                spans.append([a, b])
    # Subtract deleted/filler intervals explicitly, including when neighboring
    # retained words' padding would otherwise cover them.
    removed = [
        w
        for i, w in enumerate(words)
        if (
            i in deleted
            or (
                cleanup
                and w["text"].lower().strip(".,!?") in {"um", "uh", "umm", "uhh"}
            )
        )
        and w["end"] > start
        and w["start"] < end
    ]
    for w in removed:
        cut_a = max(start, w["start"])
        cut_b = min(end, w["end"])
        remaining = []
        for a, b in spans:
            if cut_b <= a or cut_a >= b:
                remaining.append([a, b])
                continue
            if cut_a > a:
                remaining.append([a, cut_a])
            if cut_b < b:
                remaining.append([cut_b, b])
        spans = remaining
    result = []
    offset = 0
    for a, b in spans:
        for w in retained:
            if a <= w["start"] and w["end"] <= b:
                result.append(
                    {
                        **w,
                        "start": round(offset + w["start"] - a, 4),
                        "end": round(offset + w["end"] - a, 4),
                    }
                )
        offset += b - a
    return {"spans": spans, "words": result, "duration": round(offset, 4)}
