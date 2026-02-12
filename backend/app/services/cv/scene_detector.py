"""Scene/shot boundary detection."""

from dataclasses import dataclass

import cv2
import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class SceneInfo:
    """Information about a detected scene."""

    scene_number: int
    start_frame: int
    end_frame: int
    start_time_seconds: float
    end_time_seconds: float
    duration_seconds: float
    avg_brightness: float = 0.0
    dominant_color: str = ""
    has_text: bool = False
    has_person: bool = False
    transition_type: str = "cut"  # cut, dissolve, fade


class SceneDetector:
    """Detect scene boundaries in video using content-aware analysis."""

    def __init__(
        self,
        threshold: float = 30.0,
        min_scene_length_frames: int = 10,
        adaptive_threshold: bool = True,
    ):
        self.threshold = threshold
        self.min_scene_length_frames = min_scene_length_frames
        self.adaptive_threshold = adaptive_threshold

    def detect_scenes(self, video_path: str) -> list[SceneInfo]:
        """Detect scene boundaries using histogram-based content detection."""
        scenes: list[SceneInfo] = []
        cap = cv2.VideoCapture(video_path)

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if fps <= 0 or total_frames <= 0:
                logger.error("invalid_video", path=video_path)
                return scenes

            prev_hist = None
            scene_start_frame = 0
            scene_number = 0
            frame_diffs: list[float] = []

            for frame_idx in range(total_frames):
                ret, frame = cap.read()
                if not ret:
                    break

                # Convert to HSV for better color comparison
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
                cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)

                if prev_hist is not None:
                    diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
                    frame_diffs.append(diff)

                    # Determine threshold
                    if self.adaptive_threshold and len(frame_diffs) > 30:
                        adaptive_thresh = np.mean(frame_diffs[-30:]) + 2 * np.std(frame_diffs[-30:])
                        current_threshold = max(adaptive_thresh, self.threshold / 100)
                    else:
                        current_threshold = self.threshold / 100

                    scene_length = frame_idx - scene_start_frame
                    if diff > current_threshold and scene_length >= self.min_scene_length_frames:
                        # Scene boundary detected
                        scene = SceneInfo(
                            scene_number=scene_number,
                            start_frame=scene_start_frame,
                            end_frame=frame_idx - 1,
                            start_time_seconds=scene_start_frame / fps,
                            end_time_seconds=(frame_idx - 1) / fps,
                            duration_seconds=(frame_idx - scene_start_frame) / fps,
                            transition_type=self._detect_transition_type(diff),
                        )
                        scenes.append(scene)

                        scene_number += 1
                        scene_start_frame = frame_idx

                prev_hist = hist

            # Add the last scene
            if scene_start_frame < total_frames:
                scenes.append(SceneInfo(
                    scene_number=scene_number,
                    start_frame=scene_start_frame,
                    end_frame=total_frames - 1,
                    start_time_seconds=scene_start_frame / fps,
                    end_time_seconds=(total_frames - 1) / fps,
                    duration_seconds=(total_frames - scene_start_frame) / fps,
                ))

        finally:
            cap.release()

        logger.info("scenes_detected", path=video_path, scene_count=len(scenes))
        return scenes

    def _detect_transition_type(self, diff_value: float) -> str:
        """Classify scene transition type based on difference magnitude."""
        if diff_value > 0.8:
            return "cut"
        elif diff_value > 0.4:
            return "dissolve"
        else:
            return "fade"

    def analyze_scene_pacing(self, scenes: list[SceneInfo]) -> dict:
        """Analyze the pacing/rhythm of scenes."""
        if not scenes:
            return {"avg_scene_duration": 0, "total_scenes": 0}

        durations = [s.duration_seconds for s in scenes]
        transitions = [s.transition_type for s in scenes]

        return {
            "total_scenes": len(scenes),
            "avg_scene_duration": float(np.mean(durations)),
            "min_scene_duration": float(np.min(durations)),
            "max_scene_duration": float(np.max(durations)),
            "std_scene_duration": float(np.std(durations)),
            "pacing_score": self._calculate_pacing_score(durations),
            "transition_counts": {
                "cut": transitions.count("cut"),
                "dissolve": transitions.count("dissolve"),
                "fade": transitions.count("fade"),
            },
            "scene_durations": durations,
        }

    def _calculate_pacing_score(self, durations: list[float]) -> float:
        """Calculate a pacing score (0-100). Higher = faster pacing."""
        if not durations:
            return 0.0

        avg_duration = np.mean(durations)
        # Fast-paced: avg < 2s, slow: avg > 5s
        if avg_duration <= 1.0:
            return 100.0
        elif avg_duration >= 10.0:
            return 0.0
        else:
            return float(max(0, 100 - (avg_duration - 1.0) * (100.0 / 9.0)))

    def get_hook_analysis(self, scenes: list[SceneInfo]) -> dict:
        """Analyze the first 3 seconds (hook section)."""
        hook_scenes = [s for s in scenes if s.start_time_seconds < 3.0]
        hook_scene_count = len(hook_scenes)
        hook_transitions = sum(1 for s in hook_scenes if s.start_time_seconds > 0)

        return {
            "hook_scene_count": hook_scene_count,
            "hook_transitions": hook_transitions,
            "hook_pacing": "fast" if hook_scene_count >= 3 else "moderate" if hook_scene_count >= 2 else "slow",
            "hook_scenes": [
                {
                    "scene_number": s.scene_number,
                    "start": s.start_time_seconds,
                    "end": s.end_time_seconds,
                    "duration": s.duration_seconds,
                    "transition": s.transition_type,
                }
                for s in hook_scenes
            ],
        }
