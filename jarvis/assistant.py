"""JARVIS Assistant - the REPL/voice loop that ties brain + voice together."""
from __future__ import annotations

from typing import Optional

from .brain import Brain
from .voice import VoiceIO


_EXIT_WORDS = {"exit", "quit", "bye", "goodbye", "shut down", "shutdown", "stop"}


class Assistant:
    """Runs an interactive conversation loop using the supplied brain.

    If a VoiceIO with working STT+TTS is provided, voice is used; otherwise
    falls back to typed input + printed output.
    """

    def __init__(
        self,
        brain: Brain,
        voice: Optional[VoiceIO] = None,
        name: str = "JARVIS",
    ) -> None:
        self.brain = brain
        self.voice = voice
        self.name = name

    # ------------------------------------------------------------------
    @property
    def voice_in(self) -> bool:
        return bool(self.voice and self.voice.stt_available)

    @property
    def voice_out(self) -> bool:
        return bool(self.voice and self.voice.tts_available)

    # ------------------------------------------------------------------
    def say(self, text: str) -> None:
        if not text:
            return
        print(f"{self.name}: {text}")
        if self.voice_out:
            self.voice.speak(text)

    def get_input(self) -> Optional[str]:
        if self.voice_in:
            print("(listening...)")
            heard = self.voice.listen()
            if heard is None:
                return ""  # treat as a no-op turn, keep looping
            print(f"You: {heard}")
            return heard
        try:
            return input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()  # newline after ^C / ^D
            return None

    # ------------------------------------------------------------------
    def run(self) -> None:
        mode = "voice" if (self.voice_in or self.voice_out) else "text"
        self.say(f"Hello. {self.name} online in {mode} mode. How may I help?")

        while True:
            user_input = self.get_input()
            if user_input is None:  # EOF / Ctrl+C
                self.say("Goodbye.")
                return
            if not user_input:
                continue

            if user_input.lower().strip(" .!?") in _EXIT_WORDS:
                self.say("Shutting down. Goodbye.")
                return

            try:
                reply = self.brain.respond(user_input)
            except Exception as e:  # noqa: BLE001
                reply = f"Sorry, I ran into an error: {e}"

            self.say(reply or "(no reply)")
