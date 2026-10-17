import json
import uuid
import hashlib
from pathlib import Path
from .config import DATA, STAGES
from .schemas import Options
from .media import atomic_json, ingest, track, render, dimensions, probe
from .transcribe import transcribe
from .analysis import chapters, candidates
from .timeline import edit_timeline
from .captions import build_ass, build_srt


def project_dir(project_id):
    uuid.UUID(project_id)
    return DATA / "projects" / project_id


def read(path):
    return json.loads(Path(path).read_text())


def create_project(source, options=None, title=None):
    options = Options.model_validate(options or {}).model_dump()
    pid = str(uuid.uuid4())
    directory = project_dir(pid)
    directory.mkdir(parents=True)
    atomic_json(
        directory / "project.json",
        {
            "id": pid,
            "title": title or Path(source).stem,
            "source": str(source),
            "options": options,
        },
    )
    return pid


def stage(project_id, name):
    directory = project_dir(project_id)
    checkpoint = directory / f"{name}.json"
    if checkpoint.exists():
        return read(checkpoint)
    p = read(directory / "project.json")
    options = p["options"]
    if name == "ingest":
        result = ingest(p["source"], directory)
    elif name == "transcribe":
        result = transcribe(directory / "audio.wav", options)
    elif name == "segment":
        result = chapters(read(directory / "transcribe.json")["words"], options)
    elif name == "candidates":
        result = [
            {
                "id": str(uuid.uuid4()),
                **c,
                "caption_style": options["caption_style"],
                "offset": 0,
                "deleted_words": [],
            }
            for c in candidates(
                read(directory / "transcribe.json")["words"],
                options,
                read(directory / "segment.json"),
            )
        ]
    elif name == "cleanup":
        words = read(directory / "transcribe.json")["words"]
        result = {
            c["id"]: edit_timeline(words, c["start"], c["end"], options["cleanup"])
            for c in read(directory / "candidates.json")
        }
    elif name == "reframe":
        result = {
            cid: track(directory / "source.mp4", timeline, options["layout"])
            for cid, timeline in read(directory / "cleanup.json").items()
        }
    elif name == "captions":
        result = {}
        w, h = dimensions(options["aspect"])
        for c in read(directory / "candidates.json"):
            out = directory / "renders" / c["id"] / "initial"
            out.mkdir(parents=True, exist_ok=True)
            timeline = read(directory / "cleanup.json")[c["id"]]
            (out / "captions.ass").write_text(
                build_ass(timeline["words"], w, h, c["caption_style"], options["brand"])
            )
            (out / "output.srt").write_text(
                build_srt(
                    timeline["words"],
                    probe(DATA / "brand" / options["brand"]["intro"])["duration"]
                    if options["brand"].get("intro")
                    else 0,
                )
            )
            result[c["id"]] = str(out)
    elif name == "export":
        result = []
        for c in read(directory / "candidates.json"):
            out = Path(read(directory / "captions.json")[c["id"]])
            target = out / "output.mp4"
            if not target.exists():
                render(
                    directory / "source.mp4",
                    read(directory / "cleanup.json")[c["id"]],
                    read(directory / "reframe.json")[c["id"]],
                    out / "captions.ass",
                    target,
                    options,
                    DATA / "brand" / options["brand"]["logo"]
                    if options["brand"].get("logo")
                    else None,
                )
            result.append(
                {
                    **c,
                    "render_path": str(target),
                    "duration": read(directory / "cleanup.json")[c["id"]]["duration"],
                }
            )
    else:
        raise ValueError("Unknown pipeline stage")
    atomic_json(checkpoint, result)
    return result


def run_pipeline(project_id, progress=None):
    for i, name in enumerate(STAGES):
        if progress:
            progress(name, round(i / len(STAGES) * 100))
        stage(project_id, name)
    if progress:
        progress("complete", 100)
    return read(project_dir(project_id) / "export.json")


def rerender(project_id, clip, options):
    directory = project_dir(project_id)
    words = read(directory / "transcribe.json")["words"]
    if clip["end"] > read(directory / "ingest.json")["duration"]:
        raise ValueError("Clip extends beyond the source")
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "clip": {
                    k: clip.get(k)
                    for k in (
                        "id",
                        "start",
                        "end",
                        "caption_style",
                        "offset",
                        "deleted_words",
                    )
                },
                "options": options,
                "renderer_version": 3,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:16]
    out = directory / "renders" / clip["id"] / fingerprint
    out.mkdir(parents=True, exist_ok=True)
    target = out / "output.mp4"
    if not target.exists():
        timeline = edit_timeline(
            words,
            clip["start"],
            clip["end"],
            options["cleanup"],
            clip.get("deleted_words"),
        )
        tracking = track(
            directory / "source.mp4", timeline, options["layout"], clip.get("offset", 0)
        )
        w, h = dimensions(options["aspect"])
        (out / "captions.ass").write_text(
            build_ass(timeline["words"], w, h, clip["caption_style"], options["brand"])
        )
        (out / "output.srt").write_text(
            build_srt(
                timeline["words"],
                probe(DATA / "brand" / options["brand"]["intro"])["duration"]
                if options["brand"].get("intro")
                else 0,
            )
        )
        atomic_json(out / "timeline.json", timeline)
        atomic_json(out / "tracking.json", tracking)
        logo = options["brand"].get("logo")
        logo_path = DATA / "brand" / logo if logo else None
        render(
            directory / "source.mp4",
            timeline,
            tracking,
            out / "captions.ass",
            target,
            options,
            logo_path,
        )
    return str(target)
