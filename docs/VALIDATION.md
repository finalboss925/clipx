# Validation record

## Phase 1

- Eleven shallow clones completed; exact SHA/license snapshots: research/manifest.json.
- Architecture and reuse decisions written before application code.
- Main license discovery: ClippedAI is CC BY-NC, not MIT; no source copied.

## Phase 2

- Local host: bundled Python 3.12; delivery image targets Python 3.11.
- 11 tests passed for boundary normalization, duration constraints, overlap dedupe,
  malformed/nonfinite model data, synchronized cleanup/caption timelines and ASS escaping.
- FFmpeg 7.1 with libass; local FFprobe 3.1 used for file inspection.
- Source: public-domain January 24, 2009 White House weekly address from Wikimedia.
- Real-video input: 75 seconds starting at source timestamp 00:10.
- Whisper tiny.en CPU/int8 model; local heuristic analysis (no paid LLM key).
- Output verification to be appended after CLI run completes.

CLI completed: project d08336b9-374f-4881-b98c-e31324459d71. 226 recognized words; two clips, 25.62s and 25.60s. Both H.264/AAC at 1080×1920. Each tracked 52/52 samples with a detected face. MP4, SRT, ASS and thumbnails created. Resume succeeded after dependency compatibility fixes. Preview: samples/phase2-preview.jpg.

## Phase 3

Real Celery worker executed all eight distinct tasks on sample checkpoints using
memory transport. REST checks passed: completed project, two clip records, HTTP 206
ranged MP4, SRT download, keyword transcript search, ZIP bundle (22,600,028 bytes).
Snapshot: samples/phase3-api.json. This validates Celery dispatch and task behavior,
but does not validate Redis transport or Docker Compose on this Docker-less host.

## Phase 4

Production Vite build passed. Browser QA verified the dashboard, persisted sample
project, two playable captioned clips, progress, score explanations and downloads.
Resolved overlapping Vite optimizer processes during QA by running a single server
from frontend/. Screenshot: samples/phase4-project.png.

## Phase 5

Browser editor check: changed title, trimmed 39.56–55.80 seconds, removed the word
“immediately”, selected neon captions and offset 0.15; Save & re-render completed.
Original render remains on disk. Screenshot: samples/phase5-editor.png.
Brand-kit save persisted and returned success (samples/phase5-brand.png).
Real HTTP upload of the same source with cleanup and center layout produced an
H.264/AAC square export at 1080×1080, duration 15.304s.
Real landscape render with uploaded logo + intro + outro passed at 1920×1080,
4.668 seconds. Exported SRT begins at the measured intro duration (0.601s).
Metadata: samples/phase5-brand-render.json.

15 unit tests now pass, including regression coverage proving word deletion
preserves unrelated pauses and cleanup removes filler audio as well as captions.

## Verification limits

Docker/Compose and Redis binaries are absent on the workstation. Celery task
execution was tested with a real in-process worker using memory transport; local
HTTP/browser processing used the explicit development job adapter. Redis network
transport, PostgreSQL and the Docker image require validation on a Docker host.
OpenAI/Anthropic live calls were not made because no paid provider keys were supplied.
No active-speaker diarization, publishing OAuth flow, or arbitrary font uploads.

Final edited export after pause-preservation fix: {'duration': 15.734, 'width': 1080, 'height': 1920, 'bytes': 6395780}. Metadata and file path: samples/final-output.json.
