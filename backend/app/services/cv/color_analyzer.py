"""Color palette and color analysis for video frames."""

from collections import Counter
from dataclasses import dataclass, field

import cv2
import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class ColorInfo:
    """A single color with its properties."""

    rgb: tuple[int, int, int]
    hex_code: str
    percentage: float
    name: str = ""

    @classmethod
    def from_rgb(cls, r: int, g: int, b: int, percentage: float = 0.0) -> "ColorInfo":
        hex_code = f"#{r:02x}{g:02x}{b:02x}"
        name = cls._get_color_name(r, g, b)
        return cls(rgb=(r, g, b), hex_code=hex_code, percentage=percentage, name=name)

    @staticmethod
    def _get_color_name(r: int, g: int, b: int) -> str:
        """Map RGB to basic color name."""
        h, s, v = cv2.cvtColor(
            np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV
        )[0][0]

        if v < 40:
            return "black"
        if s < 30:
            if v > 200:
                return "white"
            return "gray"
        if h < 10 or h > 170:
            return "red"
        if h < 25:
            return "orange"
        if h < 35:
            return "yellow"
        if h < 80:
            return "green"
        if h < 130:
            return "blue"
        if h < 160:
            return "purple"
        return "pink"


@dataclass
class FrameColorResult:
    """Color analysis result for a frame."""

    frame_number: int
    timestamp_seconds: float
    dominant_colors: list[ColorInfo] = field(default_factory=list)
    color_temperature: str = ""  # warm, cool, neutral
    saturation_level: str = ""  # high, medium, low
    brightness_level: str = ""  # bright, medium, dark


class ColorAnalyzer:
    """Analyze color palettes and color properties of video frames."""

    def __init__(self, n_colors: int = 5):
        self.n_colors = n_colors

    def analyze_frame(
        self,
        frame: np.ndarray,
        frame_number: int = 0,
        timestamp_seconds: float = 0.0,
    ) -> FrameColorResult:
        """Extract dominant colors and analyze color properties."""
        # Resize for faster processing
        small = cv2.resize(frame, (150, 150))
        pixels = small.reshape(-1, 3).astype(np.float32)

        # K-means clustering for dominant colors
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, labels, centers = cv2.kmeans(
            pixels, self.n_colors, None, criteria, 3, cv2.KMEANS_PP_CENTERS
        )

        # Calculate percentages
        label_counts = Counter(labels.flatten())
        total = len(labels)

        colors: list[ColorInfo] = []
        for idx in range(self.n_colors):
            bgr = centers[idx]
            percentage = label_counts.get(idx, 0) / total * 100
            colors.append(ColorInfo.from_rgb(
                r=int(bgr[2]),
                g=int(bgr[1]),
                b=int(bgr[0]),
                percentage=round(percentage, 1),
            ))

        colors.sort(key=lambda c: -c.percentage)

        # Analyze overall properties
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        avg_h = float(np.mean(hsv[:, :, 0]))
        avg_s = float(np.mean(hsv[:, :, 1]))
        avg_v = float(np.mean(hsv[:, :, 2]))

        color_temp = self._determine_temperature(avg_h, avg_s)
        sat_level = "high" if avg_s > 150 else "low" if avg_s < 60 else "medium"
        brightness = "bright" if avg_v > 170 else "dark" if avg_v < 85 else "medium"

        return FrameColorResult(
            frame_number=frame_number,
            timestamp_seconds=timestamp_seconds,
            dominant_colors=colors,
            color_temperature=color_temp,
            saturation_level=sat_level,
            brightness_level=brightness,
        )

    def _determine_temperature(self, avg_hue: float, avg_saturation: float) -> str:
        """Determine color temperature."""
        if avg_saturation < 30:
            return "neutral"
        if avg_hue < 30 or avg_hue > 160:
            return "warm"
        elif 90 < avg_hue < 140:
            return "cool"
        return "neutral"

    def analyze_batch(
        self,
        frames: list[tuple[np.ndarray, int, float]],
    ) -> list[FrameColorResult]:
        """Analyze colors for a batch of frames."""
        return [
            self.analyze_frame(frame, frame_num, timestamp)
            for frame, frame_num, timestamp in frames
        ]

    def summarize(self, results: list[FrameColorResult]) -> dict:
        """Summarize color analysis across all frames."""
        if not results:
            return {}

        # Aggregate all dominant colors
        all_color_names: list[str] = []
        all_hex_codes: list[str] = []
        for result in results:
            for color in result.dominant_colors[:3]:
                all_color_names.append(color.name)
                all_hex_codes.append(color.hex_code)

        color_name_counts = Counter(all_color_names)
        top_colors = color_name_counts.most_common(5)

        # Temperature distribution
        temp_counts = Counter(r.color_temperature for r in results)
        dominant_temp = temp_counts.most_common(1)[0][0] if temp_counts else "neutral"

        # Build palette from most common hex codes
        hex_counts = Counter(all_hex_codes)
        palette = [hex_code for hex_code, _ in hex_counts.most_common(self.n_colors)]

        return {
            "dominant_palette": palette,
            "top_color_names": [{"name": name, "count": count} for name, count in top_colors],
            "color_temperature": dominant_temp,
            "temperature_distribution": dict(temp_counts),
            "saturation_distribution": dict(Counter(r.saturation_level for r in results)),
            "brightness_distribution": dict(Counter(r.brightness_level for r in results)),
        }
