import os
from pathlib import Path

DATA = Path(os.getenv("CLIPX_DATA", "data")).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA / 'clipx.db'}")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
FFPROBE = os.getenv("FFPROBE_BIN", "ffprobe")
STAGES = [
    "ingest",
    "transcribe",
    "segment",
    "candidates",
    "cleanup",
    "reframe",
    "captions",
    "export",
]
