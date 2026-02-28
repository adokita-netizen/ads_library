# Agent D Task: Video Processing & Frame Extraction

## Goal
For video ads, extract key frames and generate proper thumbnails. Make video creatives fully viewable.

## What to do

### 1. Video downloader
`backend/scripts/download_videos.py`
- Find all ads with video_url but no cached video file
- Download video to media_cache/videos/{ad_id}.mp4
- Skip if file size > 100MB
- Update ad_metadata["video_cached"] = true
- Print: downloaded X videos, skipped Y (too large), failed Z

### 2. Video frame extractor
`backend/scripts/extract_video_frames.py`
- For each cached video, extract 3 frames: 0s, middle, 2/3 point
- Save to media_cache/frames/{ad_id}_frame_{0,1,2}.jpg
- If thumbnail is missing, use frame_0 as thumbnail
- Use ffmpeg (subprocess) or cv2 if available, else skip
- Update ad_metadata["frames_extracted"] = true

### 3. Video info extractor
`backend/scripts/extract_video_info.py`
- For each cached video, extract: duration, resolution, file_size, codec
- Update duration_seconds, resolution_width, resolution_height, file_size_bytes in Ad model
- Print summary

### 4. Frame serving endpoints
Add to media.py:
`GET /media/frames/{ad_id}` - return list of frame URLs
`GET /media/frame/{ad_id}/{frame_index}` - serve specific frame image

## Constraints
- English-only print, no rankings.py/frontend changes
- If ffmpeg/cv2 not available, skip gracefully with warning
