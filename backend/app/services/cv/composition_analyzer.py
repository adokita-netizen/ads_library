"""Frame composition analysis."""

from dataclasses import dataclass

import cv2
import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class CompositionResult:
    """Composition analysis for a frame."""

    frame_number: int
    timestamp_seconds: float

    # Brightness & contrast
    brightness: float  # 0-255
    contrast: float  # 0-127
    is_dark: bool
    is_high_contrast: bool

    # Rule of thirds score
    thirds_score: float  # 0-1

    # Visual weight distribution
    weight_balance: str  # "center", "left", "right", "top", "bottom"
    visual_complexity: float  # 0-1

    # Edge density (visual busyness)
    edge_density: float  # 0-1

    # Symmetry score
    symmetry_score: float  # 0-1


class CompositionAnalyzer:
    """Analyze visual composition of video frames."""

    def analyze_frame(
        self,
        frame: np.ndarray,
        frame_number: int = 0,
        timestamp_seconds: float = 0.0,
    ) -> CompositionResult:
        """Analyze composition of a single frame."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))

        thirds_score = self._rule_of_thirds_score(gray)
        weight_balance = self._analyze_weight_distribution(gray)
        edge_density = self._calculate_edge_density(gray)
        symmetry_score = self._calculate_symmetry(gray)
        visual_complexity = self._calculate_visual_complexity(frame)

        return CompositionResult(
            frame_number=frame_number,
            timestamp_seconds=timestamp_seconds,
            brightness=brightness,
            contrast=contrast,
            is_dark=brightness < 80,
            is_high_contrast=contrast > 60,
            thirds_score=thirds_score,
            weight_balance=weight_balance,
            visual_complexity=visual_complexity,
            edge_density=edge_density,
            symmetry_score=symmetry_score,
        )

    def _rule_of_thirds_score(self, gray: np.ndarray) -> float:
        """Score how well content aligns with rule of thirds."""
        h, w = gray.shape
        edges = cv2.Canny(gray, 50, 150)

        # Rule of thirds lines
        third_h = h // 3
        third_w = w // 3
        margin = min(h, w) // 20

        # Count edge pixels near thirds lines
        total_edges = np.sum(edges > 0) or 1
        thirds_edges = 0

        for y in [third_h, 2 * third_h]:
            thirds_edges += np.sum(edges[max(0, y - margin):y + margin, :] > 0)
        for x in [third_w, 2 * third_w]:
            thirds_edges += np.sum(edges[:, max(0, x - margin):x + margin] > 0)

        return min(float(thirds_edges / total_edges) * 3, 1.0)

    def _analyze_weight_distribution(self, gray: np.ndarray) -> str:
        """Determine visual weight distribution."""
        h, w = gray.shape
        mid_h, mid_w = h // 2, w // 2

        # Calculate mean intensity in each quadrant (darker = more visual weight)
        top_left = np.mean(255 - gray[:mid_h, :mid_w])
        top_right = np.mean(255 - gray[:mid_h, mid_w:])
        bottom_left = np.mean(255 - gray[mid_h:, :mid_w])
        bottom_right = np.mean(255 - gray[mid_h:, mid_w:])

        top = top_left + top_right
        bottom = bottom_left + bottom_right
        left = top_left + bottom_left
        right = top_right + bottom_right

        total = top + bottom
        if total == 0:
            return "center"

        h_balance = abs(left - right) / total
        v_balance = abs(top - bottom) / total

        if h_balance < 0.1 and v_balance < 0.1:
            return "center"
        elif h_balance > v_balance:
            return "left" if left > right else "right"
        else:
            return "top" if top > bottom else "bottom"

    def _calculate_edge_density(self, gray: np.ndarray) -> float:
        """Calculate edge density as a measure of visual complexity."""
        edges = cv2.Canny(gray, 50, 150)
        return float(np.sum(edges > 0) / edges.size)

    def _calculate_symmetry(self, gray: np.ndarray) -> float:
        """Calculate horizontal symmetry score."""
        h, w = gray.shape
        left_half = gray[:, :w // 2]
        right_half = cv2.flip(gray[:, w // 2:w // 2 * 2], 1)

        if left_half.shape != right_half.shape:
            min_w = min(left_half.shape[1], right_half.shape[1])
            left_half = left_half[:, :min_w]
            right_half = right_half[:, :min_w]

        diff = cv2.absdiff(left_half, right_half)
        return max(0, 1.0 - float(np.mean(diff)) / 128)

    def _calculate_visual_complexity(self, frame: np.ndarray) -> float:
        """Calculate visual complexity using color histogram entropy."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0], None, [180], [0, 180])
        hist = hist.flatten()
        hist = hist / (hist.sum() or 1)

        # Shannon entropy
        nonzero = hist[hist > 0]
        entropy = -np.sum(nonzero * np.log2(nonzero))
        max_entropy = np.log2(180)

        return float(entropy / max_entropy) if max_entropy > 0 else 0.0

    def analyze_batch(
        self,
        frames: list[tuple[np.ndarray, int, float]],
    ) -> list[CompositionResult]:
        """Analyze composition for a batch of frames."""
        return [
            self.analyze_frame(frame, frame_num, timestamp)
            for frame, frame_num, timestamp in frames
        ]

    def summarize(self, results: list[CompositionResult]) -> dict:
        """Summarize composition analysis across all frames."""
        if not results:
            return {}

        return {
            "avg_brightness": float(np.mean([r.brightness for r in results])),
            "avg_contrast": float(np.mean([r.contrast for r in results])),
            "avg_edge_density": float(np.mean([r.edge_density for r in results])),
            "avg_symmetry": float(np.mean([r.symmetry_score for r in results])),
            "avg_visual_complexity": float(np.mean([r.visual_complexity for r in results])),
            "avg_thirds_score": float(np.mean([r.thirds_score for r in results])),
            "dark_frame_ratio": sum(1 for r in results if r.is_dark) / len(results),
            "high_contrast_ratio": sum(1 for r in results if r.is_high_contrast) / len(results),
            "dominant_weight_balance": max(
                set(r.weight_balance for r in results),
                key=lambda x: sum(1 for r in results if r.weight_balance == x),
            ),
        }
