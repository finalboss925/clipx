import json, time
from pathlib import Path
import httpx

with httpx.Client(base_url="http://127.0.0.1:8000", timeout=120) as c:
    brand = c.get("/api/brand").json()
    opts = {
        "clip_count": 1,
        "min_length": 15,
        "max_length": 20,
        "aspect": "1:1",
        "layout": "center",
        "caption_style": "boxed",
        "cleanup": True,
        "brand": brand,
    }
    with open("samples/real-speech.mp4", "rb") as f:
        response = c.post(
            "/api/projects/upload",
            files={"file": ("real-speech.mp4", f, "video/mp4")},
            data={
                "options": json.dumps(opts),
                "title": "Weekly address · square edition",
            },
        )
    response.raise_for_status()
    project = response.json()
    print("Uploaded:", project, flush=True)
    previous = None
    for _ in range(240):
        j = c.get("/api/jobs/" + project["job_id"]).json()
        if j["stage"] != previous:
            print(j["stage"], j["status"], flush=True)
            previous = j["stage"]
        if j["status"] in ("complete", "failed"):
            break
        time.sleep(1)
    assert j["status"] == "complete", j
    p = c.get("/api/projects/" + project["id"]).json()
    Path("samples/phase5-upload.json").write_text(json.dumps(p, indent=2))
    print("Real HTTP upload -> pipeline -> square export passed", flush=True)
