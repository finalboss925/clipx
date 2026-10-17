import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import ipaddress
from urllib.parse import urlparse
from .config import FFMPEG, FFPROBE


def run(args, timeout=7200):
    result = subprocess.run(
        [str(x) for x in args], capture_output=True, text=True, timeout=timeout
    )
    if result.returncode:
        raise RuntimeError(f"{Path(str(args[0])).name} failed: {result.stderr[-1800:]}")
    return result.stdout


def probe(path):
    data = json.loads(
        run(
            [
                FFPROBE,
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                path,
            ],
            60,
        )
    )
    videos = [s for s in data["streams"] if s["codec_type"] == "video"]
    if not videos:
        raise ValueError("The file contains no video stream")
    v = videos[0]
    duration = float(data["format"]["duration"])
    if duration <= 0 or duration > 6 * 3600:
        raise ValueError("Video must be between 0 and 6 hours")
    if not any(s["codec_type"] == "audio" for s in data["streams"]):
        raise ValueError("The video needs a speech audio track")
    return {
        "duration": duration,
        "width": v["width"],
        "height": v["height"],
        "bytes": int(data["format"].get("size", 0)),
    }


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temp.replace(path)


def validate_url(url):
    parsed = urlparse(url)
    # Remote ingest is deliberately limited to known public video platforms;
    # arbitrary extractor redirects could otherwise reach local infrastructure.
    host = (parsed.hostname or "").lower()
    allowed = ("youtube.com", "youtu.be", "vimeo.com", "twitch.tv")
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or not any(host == a or host.endswith("." + a) for a in allowed)
    ):
        raise ValueError("Use an HTTPS YouTube, Vimeo or Twitch video URL")
    for info in socket.getaddrinfo(host, 443):
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise ValueError("Private network URLs are not allowed")
    return url


def ingest(source, directory):
    directory = Path(directory)
    target = directory / "source.mp4"
    if str(source).startswith(("http://", "https://")):
        validate_url(source)
        run(
            [
                "yt-dlp",
                "--no-playlist",
                "--no-live-from-start",
                "--max-filesize",
                "4G",
                "--socket-timeout",
                "30",
                "--retries",
                "3",
                "-f",
                "bv*[height<=1080]+ba/b[height<=1080]",
                "--merge-output-format",
                "mp4",
                "--remux-video",
                "mp4",
                "-o",
                str(directory / "download.%(ext)s"),
                source,
            ]
        )
        target_download = directory / "download.mp4"
        if not target_download.exists():
            raise RuntimeError("Downloader did not produce an MP4")
        target_download.replace(target)
    elif Path(source).resolve() != target.resolve():
        shutil.copyfile(source, target)
    metadata = probe(target)
    run(
        [
            FFMPEG,
            "-y",
            "-i",
            target,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            directory / "audio.wav",
        ]
    )
    run(
        [
            FFMPEG,
            "-y",
            "-i",
            target,
            "-frames:v",
            "1",
            "-vf",
            "scale=960:-2",
            directory / "poster.jpg",
        ]
    )
    return metadata


def dimensions(aspect):
    return {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}[aspect]


def track(source, timeline, layout="face", offset=0):
    import cv2
    import av

    cap = av.open(str(source))
    stream = cap.streams.video[0]
    w = stream.width
    h = stream.height
    detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    samples = []
    cx = 0.5
    cy = 0.5
    output = 0
    detected = 0
    for a, b in timeline["spans"]:
        t = a
        while t < b:
            if layout != "center":
                cap.seek(int(t / stream.time_base), stream=stream)
                frame_obj = next(
                    (
                        f
                        for f in cap.decode(stream)
                        if f.time is not None and f.time >= t
                    ),
                    None,
                )
                if frame_obj is not None:
                    frame = frame_obj.to_ndarray(format="bgr24")
                    small = cv2.resize(frame, (480, max(1, round(h * 480 / w))))
                    faces = detector.detectMultiScale(
                        cv2.cvtColor(small, cv2.COLOR_BGR2GRAY),
                        1.1,
                        5,
                        minSize=(24, 24),
                    )
                    if len(faces):
                        # Stable visible face: favor proximity to prior center, then area.
                        face = max(
                            faces,
                            key=lambda f: (
                                f[2]
                                * f[3]
                                / (1 + 8 * abs((f[0] + f[2] / 2) / 480 - cx))
                            ),
                        )
                        x, y, fw, fh = face
                        tx = (x + fw / 2) / 480
                        ty = (y + fh * 0.65) / small.shape[0]
                        cx += max(-0.045, min(0.045, (tx - cx) * 0.3))
                        cy += max(-0.03, min(0.03, (ty - cy) * 0.25))
                        detected += 1
            samples.append(
                {
                    "t": round(output + t - a, 3),
                    "x": max(0, min(1, cx + offset * 0.35)),
                    "y": cy,
                }
            )
            t += 0.5
        output += b - a
    cap.close()
    return {
        "samples": samples,
        "detected_samples": detected,
        "mode": "stable-primary-face" if detected else "center-fallback",
        "speaker_aware": False,
    }


def interpolation(samples, key):
    # Piecewise linear interpolation yields smooth FFmpeg camera movement.
    selected = samples[::2] or [{"t": 0, key: 0.5}]
    expr = str(round(selected[-1][key], 5))
    for a, b in reversed(list(zip(selected, selected[1:]))):
        dt = max(0.001, b["t"] - a["t"])
        av = round(a[key], 5)
        delta = round(b[key] - a[key], 5)
        expr = f"if(lt(t,{b['t']}),{av}+({delta})*(t-{a['t']})/{dt},{expr})"
    return expr


def render(source, timeline, tracking, ass_path, target, options, logo=None):
    width, height = dimensions(options["aspect"])
    graph = []
    streams = []
    for i, (a, b) in enumerate(timeline["spans"]):
        graph += [
            f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]",
            f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}]",
        ]
        streams.append(f"[v{i}][a{i}]")
    graph.append("".join(streams) + f"concat=n={len(streams)}:v=1:a=1[vcat][audio]")
    x = interpolation(tracking["samples"], "x")
    y = interpolation(tracking["samples"], "y")
    if options["layout"] == "split" and options["aspect"] == "9:16":
        graph += [
            "[vcat]split=2[top][bottom]",
            f"[top]scale={width}:{height // 2}:force_original_aspect_ratio=decrease,pad={width}:{height // 2}:(ow-iw)/2:(oh-ih)/2[content]",
            f"[bottom]scale={width}:{height // 2}:force_original_aspect_ratio=increase,crop={width}:{height // 2}:x='max(0,min(iw-ow,iw*({x})-ow/2))':y='max(0,min(ih-oh,ih*({y})-oh/2))'[face]",
            "[content][face]vstack=inputs=2[framed]",
        ]
    else:
        x = interpolation(tracking["samples"], "x")
        y = interpolation(tracking["samples"], "y")
        graph.append(
            f"[vcat]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}:x='max(0,min(iw-ow,iw*({x})-ow/2))':y='max(0,min(ih-oh,ih*({y})-oh/2))',setsar=1[framed]"
        )
    # Filter script paths are generated in a controlled per-render directory.
    graph.append("[framed]ass=captions.ass[captioned]")
    inputs = [FFMPEG, "-y", "-i", str(Path(source).resolve())]
    if logo:
        inputs += ["-i", str(Path(logo).resolve())]
        graph += [
            "[1:v]scale=140:-1[logo]",
            "[captioned][logo]overlay=W-w-50:50[video]",
        ]
    else:
        graph += ["[captioned]null[video]"]
    script = Path(target).parent / "filters.txt"
    script.write_text(";\n".join(graph))
    args = inputs + [
        "-filter_complex_script",
        "filters.txt",
        "-map",
        "[video]",
        "-map",
        "[audio]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "21",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        "-r",
        "30",
        "output.tmp.mp4",
    ]
    result = subprocess.run(
        args, cwd=Path(target).parent, capture_output=True, text=True, timeout=7200
    )
    if result.returncode:
        raise RuntimeError("Render failed: " + result.stderr[-1800:])
    (Path(target).parent / "output.tmp.mp4").replace(target)
    stitch_brand(target, options)
    run(
        [
            FFMPEG,
            "-y",
            "-ss",
            "0.5",
            "-i",
            target,
            "-frames:v",
            "1",
            Path(target).with_suffix(".jpg"),
        ]
    )


def stitch_brand(target, options):
    from .config import DATA

    brand = options["brand"]
    paths = []
    if brand.get("intro"):
        paths.append(DATA / "brand" / brand["intro"])
    paths.append(Path(target))
    if brand.get("outro"):
        paths.append(DATA / "brand" / brand["outro"])
    if len(paths) == 1:
        return
    width, height = dimensions(options["aspect"])
    args = [FFMPEG, "-y"]
    graph = []
    labels = []
    for i, path in enumerate(paths):
        args += ["-i", path]
        graph += [
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p,setpts=PTS-STARTPTS[v{i}]",
            f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]",
        ]
        labels.append(f"[v{i}][a{i}]")
    graph.append("".join(labels) + f"concat=n={len(paths)}:v=1:a=1[v][a]")
    temp = Path(target).with_name("branded.tmp.mp4")
    run(
        args
        + [
            "-filter_complex",
            ";".join(graph),
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "21",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            temp,
        ]
    )
    temp.replace(target)
