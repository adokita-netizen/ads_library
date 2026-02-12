"""Audio transcription using OpenAI Whisper."""

from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()


@dataclass
class TranscriptionSegment:
    """A single transcription segment with timing."""

    text: str
    start_time_ms: int
    end_time_ms: int
    confidence: float = 0.0
    language: str = ""
    speaker_id: str | None = None

    @property
    def duration_ms(self) -> int:
        return self.end_time_ms - self.start_time_ms

    @property
    def start_seconds(self) -> float:
        return self.start_time_ms / 1000.0

    @property
    def end_seconds(self) -> float:
        return self.end_time_ms / 1000.0


@dataclass
class TranscriptionResult:
    """Complete transcription result."""

    full_text: str
    language: str
    segments: list[TranscriptionSegment] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def word_count(self) -> int:
        return len(self.full_text.split())

    def get_text_at_time(self, time_seconds: float) -> str | None:
        """Get the text being spoken at a specific time."""
        time_ms = int(time_seconds * 1000)
        for seg in self.segments:
            if seg.start_time_ms <= time_ms <= seg.end_time_ms:
                return seg.text
        return None

    def get_first_n_seconds_text(self, seconds: float = 3.0) -> str:
        """Get text from the first N seconds."""
        time_ms = int(seconds * 1000)
        texts = [seg.text for seg in self.segments if seg.start_time_ms < time_ms]
        return " ".join(texts)


class Transcriber:
    """Audio transcription using Whisper."""

    def __init__(self, model_size: str = "base", device: str = "cpu"):
        self.model_size = model_size
        self.device = device
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                import whisper
                self._model = whisper.load_model(self.model_size, device=self.device)
                logger.info("whisper_model_loaded", model=self.model_size, device=self.device)
            except Exception as e:
                logger.error("whisper_model_load_failed", error=str(e))
                raise
        return self._model

    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio file."""
        model = self._get_model()

        logger.info("transcription_started", path=audio_path, language=language)

        try:
            options = {
                "fp16": False if self.device == "cpu" else True,
                "verbose": False,
            }
            if language:
                options["language"] = language
            if initial_prompt:
                options["initial_prompt"] = initial_prompt

            result = model.transcribe(audio_path, **options)

            segments = []
            for seg in result.get("segments", []):
                segments.append(TranscriptionSegment(
                    text=seg["text"].strip(),
                    start_time_ms=int(seg["start"] * 1000),
                    end_time_ms=int(seg["end"] * 1000),
                    confidence=1.0 - seg.get("no_speech_prob", 0),
                    language=result.get("language", ""),
                ))

            full_text = result.get("text", "").strip()
            detected_lang = result.get("language", "unknown")

            # Calculate duration
            duration = segments[-1].end_seconds if segments else 0.0

            transcription = TranscriptionResult(
                full_text=full_text,
                language=detected_lang,
                segments=segments,
                duration_seconds=duration,
            )

            logger.info(
                "transcription_completed",
                language=detected_lang,
                segments=len(segments),
                word_count=transcription.word_count,
            )

            return transcription

        except Exception as e:
            logger.error("transcription_failed", error=str(e))
            raise

    def detect_language(self, audio_path: str) -> str:
        """Detect the language of the audio."""
        model = self._get_model()

        try:
            import whisper
            audio = whisper.load_audio(audio_path)
            audio = whisper.pad_or_trim(audio)
            mel = whisper.log_mel_spectrogram(audio).to(model.device)
            _, probs = model.detect_language(mel)

            detected_lang = max(probs, key=probs.get)
            logger.info("language_detected", language=detected_lang, confidence=probs[detected_lang])
            return detected_lang

        except Exception as e:
            logger.error("language_detection_failed", error=str(e))
            return "unknown"
