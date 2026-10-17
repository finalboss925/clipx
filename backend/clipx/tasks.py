import os
from celery import Celery, chain
from sqlalchemy import select
from .config import REDIS_URL, STAGES
from .db import Session, Project, Job, Clip, Render, init
from .pipeline import stage, read, project_dir, rerender
from .media import probe

celery = Celery("clipx", broker=REDIS_URL, backend=REDIS_URL)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=86400,
    broker_transport_options={"visibility_timeout": 21600},
)


def persist_clips(project_id, items):
    with Session.begin() as s:
        for item in items:
            c = s.get(Clip, item["id"])
            if c is None:
                s.add(Clip(id=item["id"], project_id=project_id, data=item))
            if not s.scalar(
                select(Render).where(
                    Render.clip_id == item["id"], Render.path == item["render_path"]
                )
            ):
                s.add(
                    Render(
                        clip_id=item["id"],
                        project_id=project_id,
                        path=item["render_path"],
                    )
                )


def perform_stage(project_id, job_id, name):
    with Session.begin() as s:
        job = s.get(Job, job_id)
        p = s.get(Project, project_id)
        job.status = "running"
        job.stage = name
        job.progress = round(STAGES.index(name) / len(STAGES) * 100)
        job.error = None
        p.status = "processing"
    result = stage(project_id, name)
    if name == "ingest":
        with Session.begin() as s:
            s.get(Project, project_id).duration = result["duration"]
    if name == "export":
        persist_clips(project_id, result)
        with Session.begin() as s:
            job = s.get(Job, job_id)
            job.status = "complete"
            job.stage = "complete"
            job.progress = 100
            s.get(Project, project_id).status = "complete"
    return {"stage": name}


def mark_error(project_id, job_id, exc, failed=True):
    # Do not expose provider request bodies/headers or credentials in the UI.
    error = str(exc)[-2000:]
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        secret = os.getenv(key)
        if secret:
            error = error.replace(secret, "[redacted]")
    with Session.begin() as s:
        j = s.get(Job, job_id)
        j.status = "failed" if failed else "retrying"
        j.error = error
        s.get(Project, project_id).status = "failed" if failed else "processing"


TASKS = {}
for stage_name in STAGES:

    def make_task(name):
        @celery.task(
            bind=True,
            name="clipx." + name,
            max_retries=3,
            soft_time_limit=21000,
            time_limit=21600,
        )
        def task(self, project_id, job_id):
            try:
                return perform_stage(project_id, job_id, name)
            except Exception as exc:
                failed = self.request.retries >= self.max_retries
                mark_error(project_id, job_id, exc, failed)
                if failed:
                    raise
                raise self.retry(
                    exc=exc, countdown=min(60, 2**self.request.retries * 5)
                )

        return task

    TASKS[stage_name] = make_task(stage_name)


@celery.task(bind=True, name="clipx.render", max_retries=2)
def render_task(self, project_id, job_id):
    with Session() as s:
        job = s.get(Job, job_id)
        payload = job.payload
        cid = job.clip_id
    try:
        with Session.begin() as s:
            j = s.get(Job, job_id)
            j.status = "running"
            j.stage = "render"
            j.progress = 10
        path = rerender(project_id, payload["clip"], payload["options"])
        with Session.begin() as s:
            render = Render(clip_id=cid, project_id=project_id, path=path)
            s.add(render)
            s.flush()
            c = s.get(Clip, cid)
            c.data = {
                **payload["clip"],
                "render_path": path,
                "duration": probe(path)["duration"],
            }
            j = s.get(Job, job_id)
            j.status = "complete"
            j.stage = "complete"
            j.progress = 100
    except Exception as exc:
        mark_error(project_id, job_id, exc, self.request.retries >= self.max_retries)
        raise self.retry(exc=exc, countdown=5)


def local_pipeline(project_id, job_id):
    try:
        for name in STAGES:
            perform_stage(project_id, job_id, name)
    except Exception as exc:
        mark_error(project_id, job_id, exc)


def dispatch(project_id, job_id, kind="pipeline"):
    if os.getenv("CLIPX_LOCAL_JOBS") == "1":
        # Explicit development adapter only. Production always uses Redis/Celery.
        from concurrent.futures import ThreadPoolExecutor

        executor.submit(
            local_pipeline if kind == "pipeline" else local_render, project_id, job_id
        )
    elif kind == "pipeline":
        chain(*(TASKS[name].si(project_id, job_id) for name in STAGES)).apply_async()
    else:
        render_task.delay(project_id, job_id)


def local_render(project_id, job_id):
    try:
        render_task.apply(args=[project_id, job_id], throw=True)
    except Exception as exc:
        mark_error(project_id, job_id, exc)


from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="clipx-dev")
