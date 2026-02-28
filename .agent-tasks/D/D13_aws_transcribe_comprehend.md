# Agent D Task: AWS Transcribe + Comprehend for Video/Text AI

## Goal
Transcribe video ad audio and run NLP on all ad text for deep insights.

## What to do

### 1. Video transcription
`backend/scripts/transcribe_videos.py`
- Upload cached videos to S3 (temp)
- Call AWS Transcribe:
  - `start_transcription_job()` for each video
  - Wait for completion, download transcript
  - Language: ja-JP (Japanese)
- Store transcript in ad_metadata["transcript"]:
```json
{
  "full_text": "...",
  "segments": [{"start": 0.0, "end": 2.5, "text": "..."}, ...],
  "language": "ja-JP",
  "confidence": 0.95
}
```

### 2. NLP analysis with Comprehend
`backend/scripts/comprehend_analysis.py`
- For each ad's title + description (+ transcript if available):
  - `detect_sentiment()` -> positive/negative/neutral/mixed
  - `detect_key_phrases()` -> important phrases
  - `detect_entities()` -> brands, products, quantities
  - `detect_dominant_language()` -> confirm Japanese
- Store in ad_metadata["nlp"]:
```json
{
  "sentiment": "POSITIVE",
  "sentiment_score": {"positive": 0.85, "negative": 0.02},
  "key_phrases": ["無料体験", "今だけ限定"],
  "entities": [{"text": "コラーゲン", "type": "OTHER"}]
}
```

### 3. Combined intelligence
`backend/scripts/build_creative_intelligence.py`
- Merge Rekognition + Transcribe + Comprehend + creative_analysis into one unified "creative intelligence" object
- ad_metadata["creative_intelligence"]:
```json
{
  "visual_elements": [...],  // from Rekognition
  "text_overlay": [...],     // from Rekognition OCR
  "audio_script": "...",     // from Transcribe
  "sentiment": "POSITIVE",   // from Comprehend
  "key_phrases": [...],      // from Comprehend
  "hook_type": "pain_point", // from creative_analysis
  "overall_score": 87,       // computed
  "strengths": ["strong CTA", "emotional hook", "social proof"],
  "weaknesses": ["no urgency element", "long intro"]
}
```

## Constraints
- boto3, English-only print, flag_modified
- Handle AWS costs carefully (print cost estimate before batch run)
- Skip if AWS credentials not configured
