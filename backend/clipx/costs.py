"""Configurable budgeting estimates, never a provider billing quote."""

import os


def estimate(duration, options):
    minutes = max(0, duration) / 60
    audio_rate = float(os.getenv("TRANSCRIPTION_USD_PER_MINUTE", "0.006"))
    input_rate = float(os.getenv("LLM_INPUT_USD_PER_MILLION", "0.15"))
    output_rate = float(os.getenv("LLM_OUTPUT_USD_PER_MILLION", "0.60"))
    input_tokens = minutes * 220 * 2.5
    output_tokens = max(1, options["clip_count"]) * 650 + minutes * 25
    transcription = minutes * audio_rate if options["transcription"] == "openai" else 0
    analysis = (
        (input_tokens * input_rate + output_tokens * output_rate) / 1e6
        if options["provider"] != "local"
        else 0
    )
    return {
        "estimated_usd": round(transcription + analysis, 4),
        "transcription_usd": round(transcription, 4),
        "analysis_usd": round(analysis, 4),
        "basis": "Configurable budgeting rates; not live provider pricing. Audio API has a 24MB limit.",
        "input_tokens_estimate": round(input_tokens),
        "output_tokens_estimate": round(output_tokens),
    }
