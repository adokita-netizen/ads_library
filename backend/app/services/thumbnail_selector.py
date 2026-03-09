"""Best-frame selection and thumbnail encoding utilities."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


class ThumbnailSelector:
    def select_best(self, frames: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Pick the highest-quality frame."""
        if not frames:
            return None
        ranked = sorted(frames, key=lambda f: float(f.get("quality_score", 0.0)), reverse=True)
        return ranked[0]

    def save_thumbnail(self, frame, output_path: str, size: tuple[int, int] = (640, 360)) -> str | None:
        """Save thumbnail file from OpenCV frame."""
        if cv2 is None:
            return None
        resized = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
        ok = cv2.imwrite(output_path, resized)
        return output_path if ok else None

    def encode_thumbnail_bytes(self, frame, size: tuple[int, int] = (640, 360), quality: int = 85) -> bytes | None:
        """Encode thumbnail image as JPEG bytes."""
        if cv2 is None:
            return None
        resized = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
        ok, buffer = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            logger.warning("thumbnail_encode_failed")
            return None
        return buffer.tobytes()

