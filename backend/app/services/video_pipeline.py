"""Video intelligence pipeline: keyframes + scene detection + quality scoring."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()

try:
    import cv2
    import numpy as np
except Exception:  # pragma: no cover
    cv2 = None
    np = None


class VideoPipeline:
    def __init__(self, frame_interval: int = 30):
        self.frame_interval = frame_interval

    def extract_keyframes(self, video_path: str, max_frames: int = 10) -> list[dict[str, Any]]:
        """Extract evenly sampled keyframes with quality and scene-change signals."""
        if cv2 is None or np is None:
            logger.warning("opencv_not_available_for_video_pipeline")
            return []

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning("video_open_failed", path=video_path)
            return []

        frames: list[dict[str, Any]] = []
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            interval = max(1, total_frames // max_frames) if max_frames > 0 else 1
            prev_hist = None

            for frame_idx in range(0, max(total_frames, 1), interval):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ok, frame = cap.read()
                if not ok:
                    break

                hist = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
                hist = cv2.normalize(hist, hist).flatten()

                scene_change = 0.0
                if prev_hist is not None:
                    scene_change = float(1.0 - cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL))

                quality = self._compute_frame_quality(frame)

                frames.append(
                    {
                        "frame_idx": frame_idx,
                        "timestamp": frame_idx / fps if fps > 0 else 0.0,
                        "scene_change": scene_change,
                        "quality_score": quality,
                        "frame": frame,
                    }
                )
                prev_hist = hist
                if len(frames) >= max_frames:
                    break
        finally:
            cap.release()

        return frames

    def detect_scenes(self, video_path: str, threshold: float = 0.4) -> list[dict[str, float]]:
        """Detect scene boundaries using histogram delta over sampled frames."""
        if cv2 is None or np is None:
            return []

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        scenes: list[dict[str, float]] = []
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            prev_hist = None
            frame_idx = 0
            scene_start = 0

            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                if frame_idx % self.frame_interval == 0:
                    hist = cv2.calcHist([frame], [0], None, [64], [0, 256])
                    hist = cv2.normalize(hist, hist).flatten()
                    if prev_hist is not None:
                        diff = float(1.0 - cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL))
                        if diff > threshold:
                            scenes.append(
                                {
                                    "start_frame": float(scene_start),
                                    "end_frame": float(frame_idx),
                                    "start_time": scene_start / fps if fps > 0 else 0.0,
                                    "end_time": frame_idx / fps if fps > 0 else 0.0,
                                    "duration": (frame_idx - scene_start) / fps if fps > 0 else 0.0,
                                }
                            )
                            scene_start = frame_idx
                    prev_hist = hist
                frame_idx += 1

            if scene_start < frame_idx:
                scenes.append(
                    {
                        "start_frame": float(scene_start),
                        "end_frame": float(frame_idx),
                        "start_time": scene_start / fps if fps > 0 else 0.0,
                        "end_time": frame_idx / fps if fps > 0 else 0.0,
                        "duration": (frame_idx - scene_start) / fps if fps > 0 else 0.0,
                    }
                )
        finally:
            cap.release()

        return scenes

    def _compute_frame_quality(self, frame) -> float:
        """Compute frame quality score in [0, 1]."""
        if cv2 is None or np is None:
            return 0.0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_score = min(float(sharpness) / 500.0, 1.0)

        brightness = float(np.mean(gray))
        brightness_score = max(0.0, 1.0 - abs(brightness - 128.0) / 128.0)

        contrast = float(np.std(gray))
        contrast_score = min(contrast / 64.0, 1.0)

        face_score = 0.0
        try:
            cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
            if len(faces) > 0:
                face_score = 0.3
        except Exception:
            face_score = 0.0

        denom = 0.7 + face_score
        return float((sharpness_score * 0.3 + brightness_score * 0.2 + contrast_score * 0.2 + face_score) / denom)

