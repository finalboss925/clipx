import argparse
import json
from .pipeline import create_project, run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="ClipX: convert speech videos into captioned short clips"
    )
    parser.add_argument("source", nargs="?")
    parser.add_argument("--resume")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--min-length", type=int, default=15)
    parser.add_argument("--max-length", type=int, default=60)
    parser.add_argument(
        "--provider", choices=["local", "openai", "anthropic"], default="local"
    )
    parser.add_argument("--aspect", choices=["9:16", "1:1", "16:9"], default="9:16")
    parser.add_argument("--style", default="karaoke")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    if not args.source and not args.resume:
        parser.error("Supply a source file/URL or --resume PROJECT_ID")
    pid = args.resume or create_project(
        args.source,
        {
            "clip_count": args.count,
            "min_length": args.min_length,
            "max_length": args.max_length,
            "provider": args.provider,
            "aspect": args.aspect,
            "caption_style": args.style,
            "cleanup": args.cleanup,
        },
    )
    print("Project:", pid, flush=True)
    clips = run_pipeline(
        pid, lambda stage, percent: print(f"{percent:3}% {stage}", flush=True)
    )
    print(json.dumps(clips, indent=2))


if __name__ == "__main__":
    main()
