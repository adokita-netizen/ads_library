# D-R2-6: Video Intelligence Pipeline (D34 Phase 2)
# 優先度: P2 | 前提: D-R2-2 完了 | ブロック: なし

## 目的
動画からキーフレーム抽出 + シーン検出 + 自動サムネイル選択を行う。

## 対象ファイル (全て Agent D 専有)
- 新規: `backend/app/services/video_pipeline.py`
- 新規: `backend/app/services/thumbnail_selector.py`
- 新規: `backend/app/tasks/video_tasks.py`

## 実装

### VideoPipeline
```python
# backend/app/services/video_pipeline.py

import cv2
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class VideoPipeline:
    def __init__(self):
        self.frame_interval = 30  # 30フレームごとにサンプリング

    def extract_keyframes(self, video_path: str, max_frames: int = 10) -> list[dict]:
        """動画からキーフレームを抽出"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        # 均等間隔でフレームを抽出
        interval = max(1, total_frames // max_frames)
        frames = []
        prev_hist = None

        for frame_idx in range(0, total_frames, interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break

            # ヒストグラム計算（シーン変化検出用）
            hist = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()

            # 前フレームとの差異
            scene_change = 0.0
            if prev_hist is not None:
                scene_change = 1.0 - cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)

            # フレーム品質スコア
            quality = self._compute_frame_quality(frame)

            frames.append({
                "frame_idx": frame_idx,
                "timestamp": frame_idx / fps if fps > 0 else 0,
                "scene_change": scene_change,
                "quality_score": quality,
                "frame": frame,  # numpy array
            })

            prev_hist = hist

            if len(frames) >= max_frames:
                break

        cap.release()
        return frames

    def detect_scenes(self, video_path: str) -> list[dict]:
        """シーン境界を検出"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        scenes = []
        prev_hist = None
        threshold = 0.4  # シーン変化閾値

        frame_idx = 0
        scene_start = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % self.frame_interval == 0:
                hist = cv2.calcHist([frame], [0], None, [64], [0, 256])
                hist = cv2.normalize(hist, hist).flatten()

                if prev_hist is not None:
                    diff = 1.0 - cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
                    if diff > threshold:
                        scenes.append({
                            "start_frame": scene_start,
                            "end_frame": frame_idx,
                            "start_time": scene_start / fps,
                            "end_time": frame_idx / fps,
                            "duration": (frame_idx - scene_start) / fps,
                        })
                        scene_start = frame_idx

                prev_hist = hist
            frame_idx += 1

        # 最後のシーン
        if scene_start < frame_idx:
            scenes.append({
                "start_frame": scene_start,
                "end_frame": frame_idx,
                "start_time": scene_start / fps,
                "end_time": frame_idx / fps,
                "duration": (frame_idx - scene_start) / fps,
            })

        cap.release()
        return scenes

    def _compute_frame_quality(self, frame: np.ndarray) -> float:
        """フレームの品質スコアを計算 (0-1)"""
        # 1. シャープネス (Laplacian variance)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_score = min(sharpness / 500.0, 1.0)

        # 2. 明るさ (中央が好ましい)
        brightness = np.mean(gray)
        brightness_score = 1.0 - abs(brightness - 128) / 128.0

        # 3. コントラスト
        contrast = np.std(gray)
        contrast_score = min(contrast / 64.0, 1.0)

        # 4. 顔検出ボーナス (人が写っていると良いサムネイル)
        face_score = 0.0
        try:
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
            if len(faces) > 0:
                face_score = 0.3  # 顔あり = ボーナス
        except:
            pass

        return (sharpness_score * 0.3 + brightness_score * 0.2 + contrast_score * 0.2 + face_score) / (0.7 + face_score)
```

### ThumbnailSelector
```python
# backend/app/services/thumbnail_selector.py

class ThumbnailSelector:
    def select_best(self, frames: list[dict]) -> dict:
        """最も視覚的に魅力的なフレームを選択"""
        if not frames:
            return None

        # quality_score でソート
        ranked = sorted(frames, key=lambda f: f["quality_score"], reverse=True)
        return ranked[0]

    def save_thumbnail(self, frame: np.ndarray, output_path: str, size: tuple = (640, 360)):
        """サムネイルを指定サイズで保存"""
        resized = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
        cv2.imwrite(output_path, resized)
        return output_path
```

### VideoTask (Celery)
```python
# backend/app/tasks/video_tasks.py

@celery_app.task(bind=True, max_retries=2)
def analyze_video_task(self, ad_id: int):
    """動画を分析してキーフレーム + シーン検出 + サムネイル選択"""
    session = SyncSessionLocal()
    ad = session.query(Ad).get(ad_id)

    if not ad or not ad.video_url:
        return {"status": "skipped", "reason": "no video"}

    pipeline = VideoPipeline()
    selector = ThumbnailSelector()

    # 動画をダウンロード
    video_path = download_video(ad.video_url, ad.id)

    # キーフレーム抽出
    frames = pipeline.extract_keyframes(video_path, max_frames=5)

    # シーン検出
    scenes = pipeline.detect_scenes(video_path)

    # 最適サムネイル選択
    best = selector.select_best(frames)

    # ad_metadata に保存
    meta = dict(ad.ad_metadata or {})
    meta["video_analyzed"] = True
    meta["video_analyzed_at"] = datetime.utcnow().isoformat()
    meta["frame_count"] = len(frames)
    meta["scene_count"] = len(scenes)
    meta["best_thumbnail_frame"] = best["frame_idx"] if best else None
    meta["video_quality"] = max(f["quality_score"] for f in frames) if frames else 0

    ad.ad_metadata = meta
    flag_modified(ad, "ad_metadata")
    session.commit()

    # cleanup
    os.remove(video_path)
    session.close()

    return {"status": "completed", "frames": len(frames), "scenes": len(scenes)}
```

## 完了条件
- [ ] VideoPipeline がキーフレームを抽出できる
- [ ] シーン検出が動作する
- [ ] ThumbnailSelector が品質スコアベースで最適フレームを選択する
- [ ] Celery タスクが動画分析を完了できる
- [ ] ad_metadata に video_analyzed, frame_count, scene_count が記録される
- [ ] status.md に記録
