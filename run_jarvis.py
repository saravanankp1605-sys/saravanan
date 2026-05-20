"""Run JARVIS - your modular AI assistant.

Examples:
    python run_jarvis.py                              # text mode, auto brain
    python run_jarvis.py --brain echo                 # offline mode (no API key)
    python run_jarvis.py --brain openai               # explicit OpenAI brain
    python run_jarvis.py --voice                      # enable voice I/O
    python run_jarvis.py --once "what time is it?"    # one-shot, then exit
    python run_jarvis.py --list-skills                # print skills and exit

Environment:
    OPENAI_API_KEY    required for --brain openai
    OPENAI_MODEL      override model (default: gpt-4o-mini)
"""
from __future__ import annotations

import argparse
import sys

from jarvis import Assistant, VoiceIO, build_brain, default_skills


def _list_skills() -> int:
    for s in default_skills():
        print(f"- {s.name}: {s.description}")
        for p in s.parameters:
            req = "required" if p.required else "optional"
            print(f"    * {p.name} ({p.type}, {req}): {p.description}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="JARVIS - a modular AI assistant",
    )
    parser.add_argument(
        "--brain", default="auto", choices=["auto", "openai", "echo"],
        help="Brain implementation. 'auto' uses openai if OPENAI_API_KEY is set, else echo.",
    )
    parser.add_argument(
        "--voice", action="store_true",
        help="Enable voice I/O (needs SpeechRecognition + pyttsx3 + a mic).",
    )
    parser.add_argument(
        "--once", metavar="MSG",
        help="Send a single message, print the reply, then exit.",
    )
    parser.add_argument(
        "--list-skills", action="store_true",
        help="Print the available skills and exit.",
    )
    args = parser.parse_args(argv)

    if args.list_skills:
        return _list_skills()

    skills = default_skills()

    try:
        brain = build_brain(args.brain, skills)
    except Exception as e:  # noqa: BLE001
        print(f"[error] Failed to build brain: {e}", file=sys.stderr)
        return 2

    # One-shot mode
    if args.once:
        try:
            print(brain.respond(args.once))
            return 0
        except Exception as e:  # noqa: BLE001
            print(f"[error] {e}", file=sys.stderr)
            return 1

    # Optional voice
    voice = None
    if args.voice:
        voice = VoiceIO()
        if not voice.stt_available or not voice.tts_available:
            print("[warning] Voice mode requested but some components are unavailable:",
                  file=sys.stderr)
            print(f"  STT (mic + recognizer) available: {voice.stt_available}",
                  file=sys.stderr)
            print(f"  TTS available:                    {voice.tts_available}",
                  file=sys.stderr)
            print("  Install: pip install SpeechRecognition pyttsx3 PyAudio",
                  file=sys.stderr)

    Assistant(brain=brain, voice=voice).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
