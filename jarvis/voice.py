"""Voice I/O for JARVIS - speech-to-text and text-to-speech.

Both subsystems are *optional*. If their underlying libraries (or hardware,
like a microphone) are not available, VoiceIO simply reports them as
unavailable and the assistant falls back to text mode.

Required (only if you want voice):
    pip install SpeechRecognition pyttsx3
    # plus a microphone backend, e.g. PyAudio (or sounddevice)
"""
from __future__ import annotations

from typing import Optional


class VoiceIO:
    """Wraps optional speech recognition (STT) and text-to-speech (TTS)."""

    def __init__(self, voice_rate: int = 175) -> None:
        self._tts = None
        self._stt = None
        self._mic = None
        self._sr = None  # cached speech_recognition module

        # ---- TTS (pyttsx3, offline) ------------------------------------
        try:
            import pyttsx3  # type: ignore
            self._tts = pyttsx3.init()
            self._tts.setProperty("rate", voice_rate)
        except Exception:
            self._tts = None

        # ---- STT (speech_recognition + microphone) ---------------------
        try:
            import speech_recognition as sr  # type: ignore
            self._sr = sr
            self._stt = sr.Recognizer()
            # Microphone construction can fail if no input device / no PyAudio
            self._mic = sr.Microphone()
            with self._mic as src:
                self._stt.adjust_for_ambient_noise(src, duration=0.5)
        except Exception:
            self._stt = None
            self._mic = None

    # -- capability flags ------------------------------------------------
    @property
    def tts_available(self) -> bool:
        return self._tts is not None

    @property
    def stt_available(self) -> bool:
        return self._stt is not None and self._mic is not None

    # -- output ----------------------------------------------------------
    def speak(self, text: str) -> None:
        if not text or self._tts is None:
            return
        try:
            self._tts.say(text)
            self._tts.runAndWait()
        except Exception:
            # Never let TTS errors kill the assistant
            pass

    # -- input -----------------------------------------------------------
    def listen(self, timeout: float = 6.0, phrase_limit: float = 8.0) -> Optional[str]:
        """Return recognised text, or None on timeout / failure."""
        if self._stt is None or self._mic is None or self._sr is None:
            return None

        try:
            with self._mic as src:
                try:
                    audio = self._stt.listen(src, timeout=timeout, phrase_time_limit=phrase_limit)
                except self._sr.WaitTimeoutError:
                    return None
            return self._stt.recognize_google(audio)
        except self._sr.UnknownValueError:
            return None
        except Exception:
            return None
