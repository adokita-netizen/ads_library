"""OCR text detection in video frames."""

from dataclasses import dataclass, field

import cv2
import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class TextRegion:
    """A detected text region in a frame."""

    text: str
    confidence: float
    bbox_x: float  # normalized 0-1
    bbox_y: float
    bbox_width: float
    bbox_height: float
    language: str = ""

    @property
    def is_subtitle_position(self) -> bool:
        """Check if text is in typical subtitle area (bottom 30% of frame)."""
        return self.bbox_y + self.bbox_height > 0.7

    @property
    def is_title_position(self) -> bool:
        """Check if text is in typical title area (top 30%)."""
        return self.bbox_y < 0.3

    @property
    def is_cta_candidate(self) -> bool:
        """Check if text might be a CTA (bottom area, shorter text)."""
        return self.bbox_y > 0.6 and len(self.text) < 30


@dataclass
class FrameOCRResult:
    """OCR results for a single frame."""

    frame_number: int
    timestamp_seconds: float
    text_regions: list[TextRegion] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return " ".join(r.text for r in self.text_regions)

    @property
    def has_subtitle(self) -> bool:
        return any(r.is_subtitle_position for r in self.text_regions)

    @property
    def has_cta(self) -> bool:
        return any(r.is_cta_candidate for r in self.text_regions)

    @property
    def text_overlay_ratio(self) -> float:
        """Ratio of frame area covered by text."""
        total_area = sum(r.bbox_width * r.bbox_height for r in self.text_regions)
        return min(total_area, 1.0)


class OCREngine:
    """OCR engine using EasyOCR for text detection in video frames."""

    # CTA keywords (Japanese + English)
    CTA_KEYWORDS = {
        "ja": [
            "今すぐ", "購入", "申し込み", "無料", "ダウンロード",
            "詳しく", "クリック", "登録", "お試し", "限定",
            "キャンペーン", "割引", "セール", "特別", "初回",
            "公式サイト", "LINE追加", "友だち追加", "資料請求",
        ],
        "en": [
            "buy now", "shop now", "get started", "sign up", "free",
            "download", "learn more", "click", "subscribe", "limited",
            "order now", "try free", "install", "register",
        ],
    }

    HOOK_KEYWORDS = {
        "ja": [
            "衝撃", "驚き", "知ってた", "まだ", "実は",
            "たった", "え？", "注目", "速報", "話題",
            "やばい", "神", "最強", "裏技", "秘密",
        ],
        "en": [
            "shocking", "amazing", "secret", "warning", "breaking",
            "you won't believe", "stop", "wait", "attention",
        ],
    }

    def __init__(self, languages: list[str] | None = None):
        self.languages = languages or ["ja", "en"]
        self._reader = None

    def _get_reader(self):
        if self._reader is None:
            try:
                import easyocr
                self._reader = easyocr.Reader(self.languages, gpu=False)
                logger.info("easyocr_initialized", languages=self.languages)
            except Exception as e:
                logger.error("easyocr_init_failed", error=str(e))
                raise
        return self._reader

    def detect_text(
        self,
        frame: np.ndarray,
        frame_number: int = 0,
        timestamp_seconds: float = 0.0,
    ) -> FrameOCRResult:
        """Detect text in a single frame."""
        reader = self._get_reader()
        text_regions: list[TextRegion] = []

        try:
            h, w = frame.shape[:2]
            results = reader.readtext(frame)

            for bbox, text, conf in results:
                if conf < 0.3 or len(text.strip()) < 1:
                    continue

                # Convert bbox to normalized coordinates
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
                min_x, max_x = min(x_coords), max(x_coords)
                min_y, max_y = min(y_coords), max(y_coords)

                text_regions.append(TextRegion(
                    text=text.strip(),
                    confidence=float(conf),
                    bbox_x=min_x / w,
                    bbox_y=min_y / h,
                    bbox_width=(max_x - min_x) / w,
                    bbox_height=(max_y - min_y) / h,
                ))

        except Exception as e:
            logger.error("ocr_detection_failed", frame=frame_number, error=str(e))

        return FrameOCRResult(
            frame_number=frame_number,
            timestamp_seconds=timestamp_seconds,
            text_regions=text_regions,
        )

    def detect_batch(
        self,
        frames: list[tuple[np.ndarray, int, float]],
    ) -> list[FrameOCRResult]:
        """Detect text in a batch of frames."""
        return [
            self.detect_text(frame, frame_num, timestamp)
            for frame, frame_num, timestamp in frames
        ]

    def analyze_text_patterns(self, ocr_results: list[FrameOCRResult]) -> dict:
        """Analyze text patterns across all frames."""
        if not ocr_results:
            return {}

        all_texts: list[str] = []
        subtitle_texts: list[str] = []
        cta_candidates: list[dict] = []
        hook_candidates: list[dict] = []

        for result in ocr_results:
            for region in result.text_regions:
                all_texts.append(region.text)

                if region.is_subtitle_position:
                    subtitle_texts.append(region.text)

                if region.is_cta_candidate:
                    for lang, keywords in self.CTA_KEYWORDS.items():
                        text_lower = region.text.lower()
                        for kw in keywords:
                            if kw.lower() in text_lower:
                                cta_candidates.append({
                                    "text": region.text,
                                    "keyword": kw,
                                    "timestamp": result.timestamp_seconds,
                                    "confidence": region.confidence,
                                })
                                break

                if result.timestamp_seconds < 3.0:
                    text_lower = region.text.lower()
                    for lang, keywords in self.HOOK_KEYWORDS.items():
                        for kw in keywords:
                            if kw.lower() in text_lower:
                                hook_candidates.append({
                                    "text": region.text,
                                    "keyword": kw,
                                    "timestamp": result.timestamp_seconds,
                                })
                                break

        # Text overlay ratio over time
        text_overlay_timeline = [
            {"timestamp": r.timestamp_seconds, "ratio": r.text_overlay_ratio}
            for r in ocr_results
        ]

        # Has subtitles check
        subtitle_frames = sum(1 for r in ocr_results if r.has_subtitle)
        has_subtitles = subtitle_frames > len(ocr_results) * 0.3

        return {
            "total_text_regions": sum(len(r.text_regions) for r in ocr_results),
            "unique_texts": list(set(all_texts)),
            "has_subtitles": has_subtitles,
            "subtitle_ratio": subtitle_frames / len(ocr_results) if ocr_results else 0,
            "subtitle_texts": list(set(subtitle_texts)),
            "cta_candidates": cta_candidates,
            "hook_text_candidates": hook_candidates,
            "avg_text_overlay_ratio": float(np.mean([r.text_overlay_ratio for r in ocr_results])) if ocr_results else 0,
            "text_overlay_timeline": text_overlay_timeline,
        }
