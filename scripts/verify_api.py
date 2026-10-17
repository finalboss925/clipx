"""Exercise the real sample through Celery task dispatch and the REST API."""

import json
from pathlib import Path
from celery.contrib.testing.worker import start_worker
from fastapi.testclient import TestClient
from sqlalchemy import select
from clipx.api import app
from clipx.tasks import celery, dispatch
from clipx.db import init, Session, Project, Job, Clip, Render
from clipx.pipeline import read, project_dir

init()
pid = "d08336b9-374f-4881-b98c-e31324459d71"
p = read(project_dir(pid) / "project.json")
with Session.begin() as s:
    if not s.get(Project, pid):
        s.add(
            Project(
                id=pid, title="Weekly address · real video test", options=p["options"]
            )
        )
    j = Job(project_id=pid)
    s.add(j)
    s.flush()
    jid = j.id
# Real Celery worker and distinct tasks; memory transport only for portable verification.
celery.conf.update(broker_url="memory://", result_backend="cache+memory://")
with start_worker(celery, perform_ping_check=False, pool="solo", concurrency=1):
    dispatch(pid, jid)
    import time

    for _ in range(30):
        with Session() as s:
            status = s.get(Job, jid).status
        if status in ("complete", "failed"):
            break
        time.sleep(0.5)
    assert status == "complete", status
with TestClient(app) as client:
    p = client.get("/api/projects/" + pid).json()
    assert p["status"] == "complete" and len(p["clips"]) == 2
    c = p["clips"][0]
    assert (
        client.get(c["video_url"], headers={"Range": "bytes=0-1023"}).status_code == 206
    )
    assert client.get(c["srt_url"]).status_code == 200
    assert client.get("/api/projects/" + pid + "/transcript?q=recovery").json()["words"]
    bundle = client.get("/api/projects/" + pid + "/download")
    assert bundle.status_code == 200
    Path("samples/phase3-api.json").write_text(json.dumps(p, indent=2))
    print(
        json.dumps(
            {
                "celery_job": jid,
                "status": status,
                "clips": len(p["clips"]),
                "zip_bytes": len(bundle.content),
                "video_range": 206,
                "transcript_search": "passed",
            },
            indent=2,
        )
    )
