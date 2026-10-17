import os
import json
from pathlib import Path
import httpx
from .config import DATA
from .media import file_hash, atomic_json
from .schemas import Transcript


def transcribe(audio, options):
    model = os.getenv("WHISPER_MODEL", "base")
    engine = options["transcription"]
    language = options["language"]
    key = file_hash(audio) + f"-{engine}-{model}-{language}"
    cache = DATA / "cache" / f"{key}.json"
    if cache.exists():
        return Transcript.model_validate_json(cache.read_text()).model_dump()
    if engine == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Set OPENAI_API_KEY for API transcription")
        if Path(audio).stat().st_size > 24 * 1024 * 1024:
            raise ValueError("API audio exceeds 24MB; use local transcription")
        with open(audio, "rb") as f, httpx.Client(timeout=600) as client:
            fields = {
                "model": "whisper-1",
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word",
            }
            if language != "auto":
                fields["language"] = language
            response = client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                data=fields,
                files={"file": ("audio.wav", f, "audio/wav")},
            )
            response.raise_for_status()
            result = response.json()
        words = [
            {"start": w["start"], "end": w["end"], "text": w["word"].strip()}
            for w in result["words"]
            if w["end"] > w["start"] and w["word"].strip()
        ]
        language = result.get("language", language)
    else:
        from faster_whisper import WhisperModel

        whisper = WhisperModel(
            model,
            device=os.getenv("WHISPER_DEVICE", "cpu"),
            compute_type=os.getenv("WHISPER_COMPUTE", "int8"),
            download_root=str(DATA / "models"),
        )
        import wave
        import numpy as np

        with wave.open(str(audio), "rb") as wav:
            if (
                wav.getframerate() != 16000
                or wav.getnchannels() != 1
                or wav.getsampwidth() != 2
            ):
                raise ValueError("Expected 16kHz mono PCM16 audio")
            samples = (
                np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16).astype(
                    np.float32
                )
                / 32768.0
            )
        segments, info = whisper.transcribe(
            samples,
            word_timestamps=True,
            vad_filter=True,
            language=None if language == "auto" else language,
        )
        words = [
            {"start": round(w.start, 3), "end": round(w.end, 3), "text": w.word.strip()}
            for s in segments
            for w in s.words or []
            if w.end > w.start and w.word.strip()
        ]
        language = info.language
    result = Transcript(engine=engine, language=language, words=words).model_dump()
    atomic_json(cache, result)
    return result
