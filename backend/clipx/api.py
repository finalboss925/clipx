import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import uuid
import zipfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from .config import DATA
from .db import init, Session, Project, Job, Clip, Render, uid
from .schemas import Options, Edit, Brand
from .pipeline import create_project, project_dir, read
from .media import validate_url, atomic_json, probe, run
from .costs import estimate
from .tasks import dispatch


@asynccontextmanager
async def lifespan(app):
    init()
    yield


app = FastAPI(title="ClipX API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","),
    allow_methods=["GET", "POST", "PATCH", "PUT"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def local_origin_guard(request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        allowed = os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if (
            origin
            and origin not in allowed
            and origin != f"{request.url.scheme}://{request.url.netloc}"
        ):
            return __import__(
                "starlette.responses", fromlist=["JSONResponse"]
            ).JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    return await call_next(request)


def get_or_404(s, model, id):
    obj = s.get(model, id)
    if obj is None:
        raise HTTPException(404, "Not found")
    return obj


def job_json(j):
    return {
        k: getattr(j, k)
        for k in [
            "id",
            "project_id",
            "kind",
            "status",
            "stage",
            "progress",
            "error",
            "clip_id",
        ]
    }


def clip_json(s, c):
    renders = s.scalars(
        select(Render).where(Render.clip_id == c.id).order_by(Render.created_at.desc())
    ).all()
    r = renders[0] if renders else None
    data = {k: v for k, v in c.data.items() if k != "render_path"}
    return {
        **data,
        "project_id": c.project_id,
        "render_id": r.id if r else None,
        "video_url": f"/api/renders/{r.id}/video" if r else None,
        "thumbnail_url": f"/api/renders/{r.id}/thumbnail" if r else None,
        "srt_url": f"/api/renders/{r.id}/srt" if r else None,
    }


def project_json(s, p):
    jobs = s.scalars(
        select(Job).where(Job.project_id == p.id).order_by(Job.created_at.desc())
    ).all()
    clips = s.scalars(select(Clip).where(Clip.project_id == p.id)).all()
    return {
        "id": p.id,
        "title": p.title,
        "status": p.status,
        "duration": p.duration,
        "options": p.options,
        "created_at": p.created_at.isoformat(),
        "jobs": [job_json(j) for j in jobs],
        "clips": [clip_json(s, c) for c in clips],
        "poster_url": f"/api/projects/{p.id}/poster",
        "cost": estimate(p.duration, p.options),
    }


def submit(pid, title, options):
    with Session.begin() as s:
        p = Project(id=pid, title=title, options=options)
        s.add(p)
        j = Job(project_id=pid)
        s.add(j)
        s.flush()
        jid = j.id
    try:
        dispatch(pid, jid)
    except Exception:
        with Session.begin() as s:
            s.get(Job, jid).status = "failed"
            s.get(
                Job, jid
            ).error = (
                "Queue unavailable. Start Redis and the Celery worker, then retry."
            )
            s.get(Project, pid).status = "failed"
    return {"id": pid, "job_id": jid}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "local_jobs": os.getenv("CLIPX_LOCAL_JOBS") == "1",
        "publishing_enabled": os.getenv("ENABLE_PUBLISHING") == "1",
    }


@app.get("/api/projects")
def list_projects():
    with Session() as s:
        return [
            project_json(s, p)
            for p in s.scalars(select(Project).order_by(Project.created_at.desc()))
        ]


@app.post("/api/projects/upload", status_code=201)
async def upload(
    file: UploadFile = File(...), options: str = Form("{}"), title: str = Form("")
):
    try:
        opts = Options.model_validate_json(options).model_dump()
    except ValidationError as e:
        raise HTTPException(422, str(e))
    title = (title or file.filename or "Untitled video")[:180]
    upload_dir = DATA / "uploads"
    upload_dir.mkdir(exist_ok=True)
    target = upload_dir / f"{uuid.uuid4()}.upload"
    size = 0
    try:
        with target.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > 4 * 1024**3:
                    raise HTTPException(413, "Video exceeds 4GB")
                out.write(chunk)
        if not size:
            raise HTTPException(422, "Empty video")
        pid = create_project(str(target), opts, title)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return submit(pid, title, opts)


class URLInput(BaseModel):
    url: str = Field(max_length=2000)
    title: str = Field(default="Imported video", max_length=180)
    options: Options = Field(default_factory=Options)


@app.post("/api/projects/url", status_code=201)
def import_url(body: URLInput):
    try:
        validate_url(body.url)
    except (ValueError, OSError) as e:
        raise HTTPException(422, str(e))
    pid = create_project(body.url, body.options.model_dump(), body.title)
    return submit(pid, body.title, body.options.model_dump())


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    with Session() as s:
        return project_json(s, get_or_404(s, Project, pid))


@app.get("/api/projects/{pid}/poster")
def poster(pid: str):
    with Session() as s:
        get_or_404(s, Project, pid)
    path = project_dir(pid) / "poster.jpg"
    if not path.exists():
        raise HTTPException(404, "Poster not ready")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/projects/{pid}/source")
def source(pid: str):
    with Session() as s:
        get_or_404(s, Project, pid)
    path = project_dir(pid) / "source.mp4"
    if not path.exists():
        raise HTTPException(404, "Source not ready")
    return FileResponse(path, media_type="video/mp4")


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    with Session() as s:
        return job_json(get_or_404(s, Job, jid))


@app.get("/api/projects/{pid}/events")
async def events(pid: str, request: Request):
    with Session() as s:
        get_or_404(s, Project, pid)

    async def stream():
        previous = None
        while not await request.is_disconnected():
            with Session() as s:
                jobs = s.scalars(
                    select(Job)
                    .where(Job.project_id == pid)
                    .order_by(Job.created_at.desc())
                ).all()
                payload = json.dumps([job_json(j) for j in jobs])
            if payload != previous:
                yield f"data: {payload}\n\n"
                previous = payload
            else:
                yield ": heartbeat\n\n"
            if jobs and all(j.status in ("complete", "failed") for j in jobs):
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/jobs/{jid}/retry")
def retry(jid: str):
    with Session.begin() as s:
        job = get_or_404(s, Job, jid)
        if job.status not in ("failed",):
            raise HTTPException(409, "Only failed jobs can be resumed")
        job.status = "queued"
        job.error = None
        pid = job.project_id
        kind = job.kind
    try:
        dispatch(pid, jid, kind)
    except Exception:
        with Session.begin() as s:
            s.get(Job, jid).status = "failed"
        raise HTTPException(503, "Queue unavailable")
    return {"job_id": jid}


@app.get("/api/projects/{pid}/transcript")
def transcript(pid: str, q: str = ""):
    with Session() as s:
        get_or_404(s, Project, pid)
    path = project_dir(pid) / "transcribe.json"
    if not path.exists():
        raise HTTPException(409, "Transcript not ready")
    t = read(path)
    return {
        **t,
        "words": [
            {**w, "index": i}
            for i, w in enumerate(t["words"])
            if not q or q.casefold() in w["text"].casefold()
        ],
    }


@app.get("/api/clips/{cid}")
def get_clip(cid: str):
    with Session() as s:
        return clip_json(s, get_or_404(s, Clip, cid))


@app.patch("/api/clips/{cid}")
def edit_clip(cid: str, body: Edit):
    with Session.begin() as s:
        c = get_or_404(s, Clip, cid)
        p = get_or_404(s, Project, c.project_id)
        if body.end > p.duration:
            raise HTTPException(422, "Trim exceeds source duration")
        words = read(project_dir(p.id) / "transcribe.json")["words"]
        if any(i >= len(words) for i in body.deleted_words):
            raise HTTPException(422, "Word index out of range")
        if s.scalar(
            select(Job).where(
                Job.clip_id == cid, Job.status.in_(["queued", "running", "retrying"])
            )
        ):
            raise HTTPException(409, "Wait for the current render")
        c.data = {**c.data, **body.model_dump()}
        return clip_json(s, c)


@app.post("/api/clips/{cid}/renders", status_code=202)
def request_render(cid: str):
    with Session.begin() as s:
        c = get_or_404(s, Clip, cid)
        p = get_or_404(s, Project, c.project_id)
        if s.scalar(
            select(Job).where(
                Job.clip_id == cid, Job.status.in_(["queued", "running", "retrying"])
            )
        ):
            raise HTTPException(409, "A render is already in progress")
        j = Job(
            project_id=p.id,
            kind="render",
            clip_id=cid,
            payload={"clip": c.data, "options": p.options},
        )
        s.add(j)
        s.flush()
        jid = j.id
        pid = p.id
    try:
        dispatch(pid, jid, "render")
    except Exception:
        with Session.begin() as s:
            s.get(Job, jid).status = "failed"
        raise HTTPException(503, "Queue unavailable")
    return {"job_id": jid}


class CustomClip(Edit):
    pass


@app.post("/api/projects/{pid}/clips", status_code=201)
def custom_clip(pid: str, body: CustomClip):
    with Session.begin() as s:
        p = get_or_404(s, Project, pid)
        if body.end > p.duration:
            raise HTTPException(422, "Clip exceeds source duration")
        path = project_dir(pid) / "transcribe.json"
        if not path.exists():
            raise HTTPException(409, "Transcript not ready")
        if any(i >= len(read(path)["words"]) for i in body.deleted_words):
            raise HTTPException(422, "Invalid word index")
        cid = uid()
        c = Clip(
            id=cid,
            project_id=pid,
            data={
                "id": cid,
                **body.model_dump(),
                "total": 0,
                "scores": {"hook": 0, "flow": 0, "value": 0, "trend": 0},
                "hook": "Custom selection",
                "reason": "Created manually from the transcript",
                "description": "",
                "hashtags": [],
            },
        )
        s.add(c)
        s.flush()
        return clip_json(s, c)


@app.get("/api/renders/{rid}/{asset}")
def asset(rid: str, asset: str, download: bool = False):
    with Session() as s:
        r = get_or_404(s, Render, rid)
        path = Path(r.path)
    ext = {"video": ".mp4", "thumbnail": ".jpg", "srt": ".srt"}.get(asset)
    if not ext:
        raise HTTPException(404, "Unknown asset")
    path = path.with_suffix(ext)
    if not path.exists():
        raise HTTPException(404, "Asset not ready")
    return FileResponse(
        path,
        media_type={
            ".mp4": "video/mp4",
            ".jpg": "image/jpeg",
            ".srt": "application/x-subrip",
        }[ext],
        filename=f"clipx-{rid}{ext}" if download or asset == "srt" else None,
    )


@app.get("/api/projects/{pid}/download")
def bundle(pid: str):
    with Session() as s:
        get_or_404(s, Project, pid)
        clips = s.scalars(select(Clip).where(Clip.project_id == pid)).all()
        items = []
        for c in clips:
            r = s.scalar(
                select(Render)
                .where(Render.clip_id == c.id)
                .order_by(Render.created_at.desc())
            )
            if r:
                items.append((c.id, Path(r.path)))
    if not items:
        raise HTTPException(409, "No rendered clips yet")
    target = project_dir(pid) / f"bundle-{uuid.uuid4()}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_STORED) as z:
        for cid, path in items:
            for ext in (".mp4", ".jpg", ".srt"):
                p = path.with_suffix(ext)
                if p.exists():
                    z.write(p, f"{cid}/clip{ext}")
    from starlette.background import BackgroundTask

    return FileResponse(
        target,
        filename="clipx-exports.zip",
        background=BackgroundTask(target.unlink, missing_ok=True),
    )


@app.get("/api/brand")
def get_brand():
    path = DATA / "brand.json"
    return read(path) if path.exists() else Brand().model_dump()


@app.put("/api/brand")
def save_brand(body: Brand):
    if body.logo and (
        Path(body.logo).name != body.logo or not (DATA / "brand" / body.logo).exists()
    ):
        raise HTTPException(422, "Unknown brand logo")
    for kind in ("intro", "outro"):
        asset = getattr(body, kind)
        if asset and not (DATA / "brand" / asset).exists():
            raise HTTPException(422, "Unknown brand media")
    atomic_json(DATA / "brand.json", body.model_dump())
    return body


@app.post("/api/brand/logo")
async def logo(file: UploadFile = File(...)):
    import cv2, numpy as np

    data = await file.read(5 * 1024 * 1024 + 1)
    await file.close()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "Logo exceeds 5MB")
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None or max(image.shape[:2]) > 4096:
        raise HTTPException(422, "Use a PNG/JPEG logo up to 4096px")
    directory = DATA / "brand"
    directory.mkdir(exist_ok=True)
    name = f"{uuid.uuid4()}.png"
    cv2.imwrite(str(directory / name), image)
    return {"logo": name, "url": f"/api/brand/logo/{name}"}


@app.get("/api/brand/logo/{name}")
def brand_logo(name: str):
    if Path(name).name != name:
        raise HTTPException(404)
    path = DATA / "brand" / name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/png")


@app.post("/api/clips/{cid}/publish/youtube")
def publish(cid: str):
    if os.getenv("ENABLE_PUBLISHING") != "1":
        raise HTTPException(403, "Publishing is disabled")
    raise HTTPException(
        501,
        "YouTube publishing extension not configured; export the MP4 for manual upload",
    )


@app.post("/api/brand/media/{kind}")
async def brand_media(kind: str, file: UploadFile = File(...)):
    if kind not in ("intro", "outro"):
        raise HTTPException(404)
    directory = DATA / "brand"
    directory.mkdir(exist_ok=True)
    name = f"{uuid.uuid4()}.mp4"
    target = directory / name
    size = 0
    try:
        with target.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > 100 * 1024 * 1024:
                    raise HTTPException(413, "Brand video exceeds 100MB")
                f.write(chunk)
        info = await asyncio.to_thread(probe, target)
        if info["duration"] > 15:
            raise HTTPException(
                422, "Intro/outro must be at most 15 seconds and have audio"
            )
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return {kind: name, "duration": info["duration"]}
