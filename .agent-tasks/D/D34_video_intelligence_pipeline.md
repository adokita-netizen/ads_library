# D34: 動画インテリジェンス・パイプライン

## 概要
動画広告のキーフレーム自動抽出・シーン分析・サムネイル自動生成を本番環境で動作させる。
既存のCV/Audioサービスコードを実際に動くパイプラインとして接続する。

## 背景
backend/app/services/cv/ と backend/app/services/audio/ に分析コードは存在するが、
本番環境（ECS Fargate）で実際に動画を処理するパイプラインが接続されていない。
58件の広告のうち動画は約40件あるが、いずれもキーフレーム抽出やシーン分析は未実施。

## タスク

### Task 1: 動画ダウンロード & 前処理
```python
# backend/app/services/video_pipeline.py (新規)

class VideoPipeline:
    """動画広告の取得→前処理→分析→保存の一連のパイプライン"""

    async def process_video(self, ad_id: int, video_url: str) -> dict:
        """
        1. 動画をダウンロード（S3 or 外部URL）
        2. メタデータ抽出（duration, resolution, fps, codec）
        3. キーフレーム抽出
        4. 各フレームの分析
        5. シーン境界検出
        6. 結果をDBに保存
        7. 一時ファイルをクリーンアップ
        """

    def _download_video(self, url: str, output_path: str) -> str:
        """動画をダウンロードしてローカルパスを返す"""
        # S3キーがあればS3から、なければHTTPダウンロード
        # 最大100MB、タイムアウト60秒

    def _extract_metadata(self, video_path: str) -> dict:
        """ffprobe で動画メタデータを取得"""
        # duration, width, height, fps, codec, bitrate, file_size

    def _extract_keyframes(self, video_path: str, max_frames: int = 10) -> list[str]:
        """
        シーンチェンジ検出に基づくキーフレーム抽出
        - 最初のフレーム（0秒）
        - シーンチェンジポイント
        - 均等間隔フォールバック（シーンチェンジが少ない場合）
        各フレームをJPEGとして一時ディレクトリに保存
        """
```

### Task 2: キーフレーム分析パイプライン
```python
    def _analyze_frames(self, frame_paths: list[str]) -> list[dict]:
        """各キーフレームに対してCV分析を実行"""
        results = []
        for i, path in enumerate(frame_paths):
            result = {
                "frame_index": i,
                "timestamp": ...,
                "objects": self.object_detector.detect(path),      # YOLOv8
                "composition": self.composition_analyzer.analyze(path),
                "colors": self.color_analyzer.analyze(path),
                "text": self.ocr_engine.extract(path),             # EasyOCR
            }
            results.append(result)
        return results
```

### Task 3: ベストサムネイル自動選択
```python
# backend/app/services/thumbnail_selector.py (新規)

class ThumbnailSelector:
    """キーフレームから最適なサムネイルを自動選択する"""

    def select_best_thumbnail(self, frames: list[dict]) -> int:
        """
        スコアリング基準:
        - 人物の顔が含まれている (+30)
        - テキストオーバーレイがある (+20)
        - 色彩が豊か（色数が多い） (+15)
        - 構図がバランスされている (+15)
        - 最初の3秒以内のフレーム (+10)  # フックフレーム
        - ぼやけていない (+10)

        最高スコアのフレームインデックスを返す
        """

    def generate_thumbnail_variants(self, frame_path: str) -> list[str]:
        """
        1枚のフレームから複数サイズのサムネイルを生成:
        - large: 640x360 (16:9)
        - medium: 320x180
        - small: 160x90
        各サイズをS3にアップロードし、キーのリストを返す
        """
```

### Task 4: 分析結果のDB保存
```python
    def _save_results(self, session, ad_id: int, metadata: dict,
                      frames: list[dict], scenes: list[dict]):
        """
        保存先:
        - ad.duration_seconds, ad.resolution_width/height
        - ad_frames テーブル（各キーフレーム）
        - ad_analyses テーブル（統合分析結果）
        - detected_objects テーブル（物体検出結果）
        - text_detections テーブル（OCR結果）
        - scene_boundaries テーブル（シーン境界）

        ad_metadata に追記:
        - video_analyzed: True
        - video_analyzed_at: "2026-03-01T10:00:00"
        - frame_count: 10
        - scene_count: 5
        - best_thumbnail_frame: 3
        - video_quality: "high" / "medium" / "low"
        """
```

### Task 5: Celery タスク & ECS実行
```python
# backend/app/tasks/video_tasks.py (新規)

@celery_app.task(bind=True, max_retries=2, soft_time_limit=300)
def analyze_video_task(self, ad_id: int):
    """
    ECS Fargate で実行される動画分析タスク
    1. DBからadを取得
    2. video_url or video_s3_key から動画を取得
    3. VideoPipeline.process_video() を実行
    4. 結果をDBに保存
    5. media_extraction_status を "analyzed" に更新
    """

@celery_app.task
def batch_analyze_videos(limit: int = 10):
    """
    未分析の動画広告をバッチで分析する
    - video_url IS NOT NULL
    - ad_metadata->>'video_analyzed' IS NULL or != 'true'
    """
```

## 完了条件
- [ ] 動画ダウンロード → キーフレーム抽出が動作する
- [ ] キーフレームに対するCV分析（物体検出/OCR/色/構図）が動作する
- [ ] ベストサムネイルが自動選択される
- [ ] 分析結果がDBの各テーブルに正しく保存される
- [ ] Celery タスクとして実行できる
- [ ] 100MBの動画を5分以内に処理できる

## 触っていいファイル
- backend/app/services/video_pipeline.py (新規)
- backend/app/services/thumbnail_selector.py (新規)
- backend/app/tasks/video_tasks.py (新規)
- backend/app/tasks/media_tasks.py (呼び出し追加)

## 注意
- YOLOv8 / EasyOCR / ffprobe は Dockerfile.worker に既にインストール済みか確認
- 不足していればDockerfile.worker に追加（Agent D の専有領域）
- メモリ使用量に注意: ECS Fargate のタスク定義でメモリ上限を確認
- 一時ファイルは必ず finally ブロックでクリーンアップ
