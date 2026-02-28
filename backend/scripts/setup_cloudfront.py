#!/usr/bin/env python3
"""Create or configure a CloudFront distribution for the S3 media bucket.

Usage:
    python -m scripts.setup_cloudfront              # create distribution
    python -m scripts.setup_cloudfront --status      # check existing distribution
    python -m scripts.setup_cloudfront --invalidate  # invalidate cache

This creates a dedicated CloudFront distribution for media files,
separate from the main frontend/API distribution managed by Terraform.

Cache policies:
  - images/thumbnails: 30 days TTL
  - videos: 7 days TTL
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("APP_ENV", "development")

DISTRIBUTION_COMMENT = "vaap-media-cdn"


def _get_boto3_clients():
    """Get boto3 CloudFront and S3 clients."""
    import boto3
    from app.core.config import get_settings
    settings = get_settings()
    region = settings.aws_region
    bucket = settings.aws_s3_bucket

    if not bucket:
        print("ERROR: AWS_S3_BUCKET not set")
        sys.exit(1)

    cf = boto3.client("cloudfront", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    return cf, s3, bucket, region


def _find_existing_distribution(cf_client):
    """Find existing media CDN distribution by comment tag."""
    paginator = cf_client.get_paginator("list_distributions")
    for page in paginator.paginate():
        dist_list = page.get("DistributionList", {})
        for dist in dist_list.get("Items", []):
            if dist.get("Comment") == DISTRIBUTION_COMMENT:
                return dist
    return None


def create_distribution():
    """Create a CloudFront distribution for the media S3 bucket."""
    cf, s3, bucket, region = _get_boto3_clients()

    # Check for existing
    existing = _find_existing_distribution(cf)
    if existing:
        domain = existing["DomainName"]
        dist_id = existing["Id"]
        print(f"Distribution already exists:")
        print(f"  ID:     {dist_id}")
        print(f"  Domain: {domain}")
        print(f"  Status: {existing['Status']}")
        print(f"\nAdd to .env:")
        print(f"  AWS_CLOUDFRONT_DOMAIN={domain}")
        print(f"  AWS_CLOUDFRONT_ENABLED=true")
        return domain

    # Create Origin Access Control
    print("Creating Origin Access Control...")
    oac_resp = cf.create_origin_access_control(
        OriginAccessControlConfig={
            "Name": f"{bucket}-media-oac",
            "OriginAccessControlOriginType": "s3",
            "SigningBehavior": "always",
            "SigningProtocol": "sigv4",
            "Description": "OAC for media S3 bucket",
        }
    )
    oac_id = oac_resp["OriginAccessControl"]["Id"]
    print(f"  OAC ID: {oac_id}")

    # S3 bucket regional domain
    s3_domain = f"{bucket}.s3.{region}.amazonaws.com"

    # Create distribution
    print("Creating CloudFront distribution...")
    import uuid
    caller_ref = str(uuid.uuid4())[:16]

    dist_config = {
        "CallerReference": caller_ref,
        "Comment": DISTRIBUTION_COMMENT,
        "Enabled": True,
        "IsIPV6Enabled": True,
        "PriceClass": "PriceClass_200",
        "Origins": {
            "Quantity": 1,
            "Items": [
                {
                    "Id": "s3-media",
                    "DomainName": s3_domain,
                    "OriginAccessControlId": oac_id,
                    "S3OriginConfig": {
                        "OriginAccessIdentity": "",
                    },
                }
            ],
        },
        "DefaultCacheBehavior": {
            "TargetOriginId": "s3-media",
            "ViewerProtocolPolicy": "redirect-to-https",
            "AllowedMethods": {
                "Quantity": 2,
                "Items": ["GET", "HEAD"],
                "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
            },
            "Compress": True,
            "CachePolicyId": _get_cache_policy_id(cf, "images"),
            "ForwardedValues": None,
        },
        "CacheBehaviors": {
            "Quantity": 1,
            "Items": [
                {
                    "PathPattern": "videos/*",
                    "TargetOriginId": "s3-media",
                    "ViewerProtocolPolicy": "redirect-to-https",
                    "AllowedMethods": {
                        "Quantity": 2,
                        "Items": ["GET", "HEAD"],
                        "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
                    },
                    "Compress": True,
                    "CachePolicyId": _get_cache_policy_id(cf, "videos"),
                    "ForwardedValues": None,
                },
            ],
        },
        "ViewerCertificate": {
            "CloudFrontDefaultCertificate": True,
        },
        "Restrictions": {
            "GeoRestriction": {"RestrictionType": "none", "Quantity": 0},
        },
    }

    # Remove ForwardedValues (not compatible with CachePolicyId)
    del dist_config["DefaultCacheBehavior"]["ForwardedValues"]
    del dist_config["CacheBehaviors"]["Items"][0]["ForwardedValues"]

    resp = cf.create_distribution(DistributionConfig=dist_config)
    dist = resp["Distribution"]
    domain = dist["DomainName"]
    dist_id = dist["Id"]

    print(f"\nDistribution created!")
    print(f"  ID:     {dist_id}")
    print(f"  Domain: {domain}")
    print(f"  Status: {dist['Status']} (deploying, may take 5-15 minutes)")

    # Update S3 bucket policy to allow CloudFront OAC access
    print("\nUpdating S3 bucket policy for CloudFront access...")
    _update_bucket_policy(s3, bucket, dist["ARN"])

    print(f"\n=== Next Steps ===")
    print(f"1. Wait for distribution status to become 'Deployed'")
    print(f"2. Add to backend/.env:")
    print(f"   AWS_CLOUDFRONT_DOMAIN={domain}")
    print(f"   AWS_CLOUDFRONT_ENABLED=true")
    print(f"3. Run: python -m scripts.upload_to_s3")
    return domain


def _get_cache_policy_id(cf_client, media_type: str) -> str:
    """Get or create a cache policy for the given media type."""
    # Try to find existing custom policy
    policy_name = f"vaap-media-{media_type}"
    ttl = 30 * 24 * 3600 if media_type == "images" else 7 * 24 * 3600  # 30d or 7d

    try:
        # List existing policies
        resp = cf_client.list_cache_policies(Type="custom")
        for item in resp.get("CachePolicyList", {}).get("Items", []):
            if item["CachePolicy"]["CachePolicyConfig"]["Name"] == policy_name:
                return item["CachePolicy"]["Id"]
    except Exception:
        pass

    # Create custom cache policy
    print(f"  Creating cache policy: {policy_name} (TTL={ttl}s)")
    import uuid
    resp = cf_client.create_cache_policy(
        CachePolicyConfig={
            "Name": policy_name,
            "Comment": f"Cache policy for {media_type} ({ttl // 86400} days)",
            "DefaultTTL": ttl,
            "MaxTTL": ttl * 2,
            "MinTTL": 1,
            "ParametersInCacheKeyAndForwardedToOrigin": {
                "EnableAcceptEncodingGzip": True,
                "EnableAcceptEncodingBrotli": True,
                "HeadersConfig": {"HeaderBehavior": "none"},
                "CookiesConfig": {"CookieBehavior": "none"},
                "QueryStringsConfig": {"QueryStringBehavior": "none"},
            },
        }
    )
    return resp["CachePolicy"]["Id"]


def _update_bucket_policy(s3_client, bucket: str, distribution_arn: str):
    """Update S3 bucket policy to allow CloudFront OAC access."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowCloudFrontServicePrincipal",
                "Effect": "Allow",
                "Principal": {"Service": "cloudfront.amazonaws.com"},
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket}/*",
                "Condition": {
                    "StringEquals": {
                        "AWS:SourceArn": distribution_arn,
                    }
                },
            }
        ],
    }

    # Merge with existing policy if present
    try:
        existing = json.loads(s3_client.get_bucket_policy(Bucket=bucket)["Policy"])
        # Check if our statement already exists
        existing_sids = {s.get("Sid") for s in existing.get("Statement", [])}
        if "AllowCloudFrontServicePrincipal" not in existing_sids:
            existing["Statement"].append(policy["Statement"][0])
            policy = existing
        else:
            print("  Bucket policy already has CloudFront access")
            return
    except s3_client.exceptions.from_code("NoSuchBucketPolicy"):
        pass
    except Exception:
        pass

    s3_client.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
    print("  Bucket policy updated")


def check_status():
    """Check existing distribution status."""
    cf, _, _, _ = _get_boto3_clients()
    existing = _find_existing_distribution(cf)
    if not existing:
        print("No media CloudFront distribution found.")
        print("Run: python -m scripts.setup_cloudfront")
        return

    print(f"Distribution: {existing['Id']}")
    print(f"Domain:       {existing['DomainName']}")
    print(f"Status:       {existing['Status']}")
    print(f"Enabled:      {existing['Enabled']}")


def invalidate_cache(paths: list[str] | None = None):
    """Invalidate CloudFront cache."""
    cf, _, _, _ = _get_boto3_clients()
    existing = _find_existing_distribution(cf)
    if not existing:
        print("No distribution found.")
        return

    if not paths:
        paths = ["/*"]

    import uuid
    resp = cf.create_invalidation(
        DistributionId=existing["Id"],
        InvalidationBatch={
            "Paths": {"Quantity": len(paths), "Items": paths},
            "CallerReference": str(uuid.uuid4())[:16],
        },
    )
    inv_id = resp["Invalidation"]["Id"]
    print(f"Invalidation created: {inv_id}")
    print(f"Paths: {paths}")


def main():
    parser = argparse.ArgumentParser(description="Setup CloudFront for media")
    parser.add_argument("--status", action="store_true", help="Check distribution status")
    parser.add_argument("--invalidate", action="store_true", help="Invalidate cache")
    parser.add_argument("--paths", nargs="*", help="Paths to invalidate (default: /*)")
    args = parser.parse_args()

    if args.status:
        check_status()
    elif args.invalidate:
        invalidate_cache(args.paths)
    else:
        create_distribution()


if __name__ == "__main__":
    main()
