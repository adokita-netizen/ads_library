"""Object detection using YOLOv8."""

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class Detection:
    """A single object detection result."""

    class_name: str
    confidence: float
    bbox_x: float  # normalized 0-1
    bbox_y: float
    bbox_width: float
    bbox_height: float
    frame_number: int = 0
    timestamp_seconds: float = 0.0

    @property
    def area_ratio(self) -> float:
        """Ratio of detection area to frame area."""
        return self.bbox_width * self.bbox_height

    @property
    def center_x(self) -> float:
        return self.bbox_x + self.bbox_width / 2

    @property
    def center_y(self) -> float:
        return self.bbox_y + self.bbox_height / 2


@dataclass
class FrameDetectionResult:
    """Detection results for a single frame."""

    frame_number: int
    timestamp_seconds: float
    detections: list[Detection] = field(default_factory=list)

    @property
    def person_count(self) -> int:
        return sum(1 for d in self.detections if d.class_name == "person")

    @property
    def has_person(self) -> bool:
        return self.person_count > 0

    @property
    def has_product(self) -> bool:
        product_classes = {"bottle", "cup", "bowl", "food", "cell phone", "laptop", "book"}
        return any(d.class_name in product_classes for d in self.detections)


class ObjectDetector:
    """Object detection using YOLOv8."""

    # Ad-relevant COCO classes
    AD_RELEVANT_CLASSES = {
        0: "person",
        24: "backpack",
        25: "umbrella",
        26: "handbag",
        39: "bottle",
        41: "cup",
        42: "fork",
        43: "knife",
        44: "spoon",
        45: "bowl",
        46: "banana",
        47: "apple",
        48: "sandwich",
        49: "orange",
        50: "broccoli",
        51: "carrot",
        52: "hot dog",
        53: "pizza",
        54: "donut",
        55: "cake",
        56: "chair",
        57: "couch",
        58: "potted plant",
        59: "bed",
        60: "dining table",
        62: "tv",
        63: "laptop",
        64: "mouse",
        65: "remote",
        66: "keyboard",
        67: "cell phone",
        72: "refrigerator",
        73: "book",
        74: "clock",
        75: "vase",
    }

    def __init__(self, model_path: str = "yolov8n.pt", confidence_threshold: float = 0.5):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from ultralytics import YOLO
                self._model = YOLO(self.model_path)
                logger.info("yolo_model_loaded", model=self.model_path)
            except Exception as e:
                logger.error("yolo_model_load_failed", error=str(e))
                raise
        return self._model

    def detect_objects(
        self,
        frame: np.ndarray,
        frame_number: int = 0,
        timestamp_seconds: float = 0.0,
    ) -> FrameDetectionResult:
        """Detect objects in a single frame."""
        model = self._get_model()
        detections: list[Detection] = []

        try:
            results = model(frame, conf=self.confidence_threshold, verbose=False)

            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue

                h, w = frame.shape[:2]

                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i])
                    conf = float(boxes.conf[i])
                    xyxy = boxes.xyxy[i].cpu().numpy()

                    class_name = model.names.get(cls_id, f"class_{cls_id}")

                    # Normalize bbox to 0-1
                    detections.append(Detection(
                        class_name=class_name,
                        confidence=conf,
                        bbox_x=float(xyxy[0] / w),
                        bbox_y=float(xyxy[1] / h),
                        bbox_width=float((xyxy[2] - xyxy[0]) / w),
                        bbox_height=float((xyxy[3] - xyxy[1]) / h),
                        frame_number=frame_number,
                        timestamp_seconds=timestamp_seconds,
                    ))

        except Exception as e:
            logger.error("object_detection_failed", frame=frame_number, error=str(e))

        return FrameDetectionResult(
            frame_number=frame_number,
            timestamp_seconds=timestamp_seconds,
            detections=detections,
        )

    def detect_batch(
        self,
        frames: list[tuple[np.ndarray, int, float]],
    ) -> list[FrameDetectionResult]:
        """Detect objects in a batch of frames.

        Args:
            frames: List of (image, frame_number, timestamp) tuples
        """
        results: list[FrameDetectionResult] = []

        for frame_img, frame_num, timestamp in frames:
            result = self.detect_objects(frame_img, frame_num, timestamp)
            results.append(result)

        return results

    def analyze_person_presence(self, detection_results: list[FrameDetectionResult]) -> dict:
        """Analyze person presence patterns across frames."""
        if not detection_results:
            return {"person_present_ratio": 0.0, "avg_person_count": 0.0}

        person_frames = sum(1 for r in detection_results if r.has_person)
        total_persons = sum(r.person_count for r in detection_results)

        # Face close-up detection (person bbox > 30% of frame)
        closeup_frames = 0
        for result in detection_results:
            for det in result.detections:
                if det.class_name == "person" and det.area_ratio > 0.3:
                    closeup_frames += 1
                    break

        return {
            "person_present_ratio": person_frames / len(detection_results),
            "avg_person_count": total_persons / len(detection_results),
            "max_person_count": max((r.person_count for r in detection_results), default=0),
            "face_closeup_ratio": closeup_frames / len(detection_results),
            "total_frames_analyzed": len(detection_results),
        }

    def analyze_product_display(self, detection_results: list[FrameDetectionResult]) -> dict:
        """Analyze product display patterns."""
        if not detection_results:
            return {"product_display_ratio": 0.0}

        product_frames = sum(1 for r in detection_results if r.has_product)

        # Find product display timing
        first_product_time = None
        for result in detection_results:
            if result.has_product:
                first_product_time = result.timestamp_seconds
                break

        # Aggregate object types
        object_counts: dict[str, int] = {}
        for result in detection_results:
            for det in result.detections:
                object_counts[det.class_name] = object_counts.get(det.class_name, 0) + 1

        return {
            "product_display_ratio": product_frames / len(detection_results),
            "first_product_timestamp": first_product_time,
            "object_type_counts": dict(sorted(object_counts.items(), key=lambda x: -x[1])),
            "total_detections": sum(object_counts.values()),
        }
