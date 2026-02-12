"""Video frame extraction using FFmpeg and OpenCV."""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class ExtractedFrame:
    """A single extracted frame from a video."""

    frame_number: int
    timestamp_seconds: float
    image: np.ndarray  # BGR format
    is_keyframe: bool = False

    @property
    def height(self) -> int:
        return self.image.shape[0]

    @property
    def width(self) -> int:
        return self.image.shape[1]

    def to_rgb(self) -> np.ndarray:
        return cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)

    def save(self, path: str, quality: int = 95):
        cv2.imwrite(path, self.image, [cv2.IMWRITE_JPEG_QUALITY, quality])

    def to_bytes(self, format: str = ".jpg", quality: int = 95) -> bytes:
        params = [cv2.IMWRITE_JPEG_QUALITY, quality] if format == ".jpg" else []
        _, buffer = cv2.imencode(format, self.image, params)
        return buffer.tobytes()


@dataclass
class VideoMetadata:
    """Video file metadata."""

    duration_seconds: float
    fps: float
    total_frames: int
    width: int
    height: int
    codec: str
    file_size_bytes: int


class FrameExtractor:
    """Extract frames from video files using OpenCV and FFmpeg."""

    def __init__(self, target_fps: float = 2.0, max_dimension: int = 720):
        self.target_fps = target_fps
        self.max_dimension = max_dimension

    def get_video_metadata(self, video_path: str) -> VideoMetadata:
        """Extract metadata from video file."""
        cap = cv2.VideoCapture(video_path)
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            codec_int = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec = "".join([chr((codec_int >> 8 * i) & 0xFF) for i in range(4)])
            duration = total_frames / fps if fps > 0 else 0
            file_size = Path(video_path).stat().st_size

            return VideoMetadata(
                duration_seconds=duration,
                fps=fps,
                total_frames=total_frames,
                width=width,
                height=height,
                codec=codec,
                file_size_bytes=file_size,
            )
        finally:
            cap.release()

    def extract_frames(
        self,
        video_path: str,
        fps: float | None = None,
        start_time: float = 0.0,
        end_time: float | None = None,
    ) -> list[ExtractedFrame]:
        """Extract frames from video at specified FPS."""
        target_fps = fps or self.target_fps
        frames: list[ExtractedFrame] = []

        cap = cv2.VideoCapture(video_path)
        try:
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if video_fps <= 0:
                logger.error("invalid_video_fps", path=video_path)
                return frames

            frame_interval = int(video_fps / target_fps)
            if frame_interval < 1:
                frame_interval = 1

            start_frame = int(start_time * video_fps)
            end_frame = int(end_time * video_fps) if end_time else total_frames

            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

            frame_number = start_frame
            while frame_number < end_frame:
                ret, frame = cap.read()
                if not ret:
                    break

                if (frame_number - start_frame) % frame_interval == 0:
                    resized = self._resize_frame(frame)
                    timestamp = frame_number / video_fps

                    frames.append(ExtractedFrame(
                        frame_number=frame_number,
                        timestamp_seconds=timestamp,
                        image=resized,
                    ))

                frame_number += 1

            logger.info(
                "frames_extracted",
                path=video_path,
                total_frames=len(frames),
                target_fps=target_fps,
            )
        finally:
            cap.release()

        return frames

    def extract_keyframes(self, video_path: str, threshold: float = 30.0) -> list[ExtractedFrame]:
        """Extract keyframes based on visual change detection."""
        frames: list[ExtractedFrame] = []
        cap = cv2.VideoCapture(video_path)

        try:
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            prev_frame = None
            frame_number = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                if prev_frame is None:
                    # First frame is always a keyframe
                    resized = self._resize_frame(frame)
                    frames.append(ExtractedFrame(
                        frame_number=frame_number,
                        timestamp_seconds=frame_number / video_fps,
                        image=resized,
                        is_keyframe=True,
                    ))
                else:
                    diff = cv2.absdiff(prev_frame, gray)
                    mean_diff = np.mean(diff)

                    if mean_diff > threshold:
                        resized = self._resize_frame(frame)
                        frames.append(ExtractedFrame(
                            frame_number=frame_number,
                            timestamp_seconds=frame_number / video_fps,
                            image=resized,
                            is_keyframe=True,
                        ))

                prev_frame = gray
                frame_number += 1

        finally:
            cap.release()

        logger.info("keyframes_extracted", path=video_path, count=len(frames))
        return frames

    def extract_first_n_seconds(self, video_path: str, seconds: float = 3.0, fps: float = 5.0) -> list[ExtractedFrame]:
        """Extract frames from the first N seconds (for hook analysis)."""
        return self.extract_frames(video_path, fps=fps, start_time=0.0, end_time=seconds)

    def extract_audio(self, video_path: str, output_path: str | None = None) -> str:
        """Extract audio track from video file using FFmpeg."""
        if output_path is None:
            output_dir = tempfile.mkdtemp()
            output_path = str(Path(output_dir) / "audio.wav")

        cmd = [
            "ffmpeg", "-i", video_path,
            "-vn",  # no video
            "-acodec", "pcm_s16le",
            "-ar", "16000",  # 16kHz for Whisper
            "-ac", "1",  # mono
            "-y",  # overwrite
            output_path,
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=120)
            logger.info("audio_extracted", input=video_path, output=output_path)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error("audio_extraction_failed", error=e.stderr.decode())
            raise

    def _resize_frame(self, frame: np.ndarray) -> np.ndarray:
        """Resize frame maintaining aspect ratio."""
        h, w = frame.shape[:2]
        if max(h, w) <= self.max_dimension:
            return frame

        if w > h:
            new_w = self.max_dimension
            new_h = int(h * self.max_dimension / w)
        else:
            new_h = self.max_dimension
            new_w = int(w * self.max_dimension / h)

        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def generate_thumbnail(self, video_path: str, timestamp: float = 1.0) -> bytes | None:
        """Generate a thumbnail at the specified timestamp."""
        cap = cv2.VideoCapture(video_path)
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(timestamp * fps))
            ret, frame = cap.read()
            if ret:
                resized = self._resize_frame(frame)
                _, buffer = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
                return buffer.tobytes()
        finally:
            cap.release()
        return None
