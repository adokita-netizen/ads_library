# Agent D Task: AWS Media Infrastructure (S3 + CloudFront)

## Goal
Move all media to S3 with CloudFront CDN. No more local file serving. Fast, reliable, scalable.

## What to do

### 1. S3 upload pipeline
`backend/scripts/upload_to_s3.py`
- Upload all media_cache/ files to S3 bucket
- Bucket structure: s3://vaap-media/{thumbnails,images,videos,frames}/{ad_id}.{ext}
- Update thumbnail_s3_key, image_s3_key in DB with S3 keys
- Use boto3 with multipart upload for large videos
- Set Content-Type metadata correctly (image/jpeg, video/mp4)

### 2. CloudFront distribution setup script
`backend/scripts/setup_cloudfront.py`
- Create or configure CloudFront distribution for the S3 bucket
- Generate signed URLs for private content
- Cache policy: 30 days for images, 7 days for videos

### 3. Update media.py endpoints
- Instead of serving local files, redirect to CloudFront URLs
- `GET /media/thumbnail/{ad_id}` -> 302 redirect to CloudFront
- `GET /media/image/{ad_id}` -> 302 redirect to CloudFront
- `GET /media/video/{ad_id}` -> 302 redirect to CloudFront
- Fallback to local file if S3 key not set
- Add `GET /media/signed-url/{ad_id}` for temporary download links (presigned S3 URL, 1h expiry)

### 4. Auto-upload on crawl
- After media download, automatically upload to S3
- Update s3_key in DB
- Delete local copy after successful upload (optional, configurable)

### 5. Config
Add to backend/.env or config:
```
AWS_S3_BUCKET=vaap-media
AWS_REGION=ap-northeast-1
AWS_CLOUDFRONT_DOMAIN=xxxx.cloudfront.net
```

## Constraints
- Use boto3 library
- English-only print, no rankings.py/frontend changes
- Graceful fallback if AWS credentials not configured
