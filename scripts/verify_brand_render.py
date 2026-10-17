"""Real-video integration check for brand media, logo and SRT offset."""

import json, uuid
from pathlib import Path
import httpx
from clipx.config import DATA, FFMPEG, FFPROBE
from clipx.media import run, probe
from clipx.pipeline import rerender, read, project_dir

pid = "d08336b9-374f-4881-b98c-e31324459d71"
source = project_dir(pid) / "source.mp4"
run(
    [
        FFMPEG,
        "-y",
        "-ss",
        "40",
        "-i",
        source,
        "-t",
        "0.6",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "samples/brand-bumper.mp4",
    ]
)
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=60) as client:
    media = {}
    for kind in ("intro", "outro"):
        with open("samples/brand-bumper.mp4", "rb") as f:
            r = client.post(
                "/api/brand/media/" + kind,
                files={"file": ("bumper.mp4", f, "video/mp4")},
            )
        r.raise_for_status()
        media[kind] = r.json()[kind]
    # A freshly generated initials logo tests the image upload and overlay path.
    import cv2, numpy as np

    img = np.zeros((100, 180, 4), np.uint8)
    img[:] = [70, 110, 40, 255]
    cv2.putText(
        img, "CX", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (220, 255, 180, 255), 4
    )
    cv2.imwrite("samples/brand-test-logo.png", img)
    with open("samples/brand-test-logo.png", "rb") as f:
        r = client.post("/api/brand/logo", files={"file": ("logo.png", f, "image/png")})
    r.raise_for_status()
    media["logo"] = r.json()["logo"]
options = read(project_dir(pid) / "project.json")["options"]
options["brand"].update(media)
options["aspect"] = "16:9"
clip = {
    **read(project_dir(pid) / "candidates.json")[0],
    "start": 39.56,
    "end": 43,
    "caption_style": "minimal",
    "offset": 0,
    "deleted_words": [],
}
path = rerender(pid, clip, options)
meta = probe(path)
srt = Path(path).with_suffix(".srt").read_text()
from clipx.captions import srt_time

assert srt_time(probe(DATA / "brand" / media["intro"])["duration"]) in srt, srt
assert meta["width"] == 1920 and meta["height"] == 1080
assert 4.5 < meta["duration"] < 4.8, meta
Path("samples/phase5-brand-render.json").write_text(
    json.dumps({"path": path, "media": media, "metadata": meta, "srt": srt}, indent=2)
)
print("Logo + intro + outro + 16:9 + SRT offset passed:", meta, flush=True)
