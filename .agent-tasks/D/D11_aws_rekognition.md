# Agent D Task: AWS Rekognition - AI Creative Analysis

## Goal
Use AWS Rekognition to DEEPLY analyze what's IN each creative image/video. Detect objects, text, faces, emotions, colors.

## What to do

### 1. Image analysis script
`backend/scripts/rekognition_analyze.py`
- For each cached thumbnail/image, call Rekognition:
  - `detect_labels()` -> objects in image (product, person, food, etc.)
  - `detect_text()` -> OCR text overlays on creative
  - `detect_faces()` -> face count, emotions (happy, surprised, calm)
  - `detect_moderation_labels()` -> content safety check
- Store ALL results in ad_metadata["rekognition"]:
```json
{
  "labels": [{"name": "Person", "confidence": 99.2}, ...],
  "text_detections": ["今だけ50%OFF", "無料体験"],
  "faces": [{"emotions": {"happy": 95.3}, "age_range": [25,35]}],
  "dominant_colors": ["#FF5733", "#FFFFFF"],
  "moderation": []
}
```
- Batch process with rate limiting (Rekognition has API limits)

### 2. Video analysis script
`backend/scripts/rekognition_video.py`
- For cached videos, use Rekognition Video:
  - `start_label_detection()` -> objects throughout video
  - `start_text_detection()` -> text overlays at each timestamp
  - `start_face_detection()` -> faces and emotions over time
- Store in ad_metadata["rekognition_video"]
- Extract key moments (when text appears, when faces show emotion)

### 3. Creative intelligence endpoint
Add to media.py:
`GET /media/intelligence/{ad_id}` - return full Rekognition analysis
- Labels, detected text, faces, colors, video key moments
- "Creative summary" generated from the data

### 4. Batch processor
`backend/scripts/batch_rekognition.py`
- Process all unanalyzed ads (where ad_metadata has no "rekognition" key)
- Rate limit: max 5 calls/second
- Resume capability (skip already processed)
- Cost estimation: print estimated AWS cost before running

## Constraints
- Use boto3 rekognition client
- English-only print
- Store results in ad_metadata with flag_modified
- Handle AWS errors gracefully (throttling, quota)
