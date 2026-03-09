#!/usr/bin/env python3
"""Update render_ad URLs with new Meta API token."""

import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))
db_path = os.path.join(BASE_DIR, "vaap_local.db")
engine = create_engine(f"sqlite:///{db_path}")
Session = sessionmaker(bind=engine)
session = Session()

new_token = None
try:
    from app.utils.crypto import decrypt_value

    token_row = session.execute(
        text(
            "SELECT key_value FROM platform_api_keys "
            "WHERE platform='meta' AND key_name='access_token' AND is_active=1 "
            "ORDER BY updated_at DESC LIMIT 1"
        )
    ).fetchone()
    if token_row and token_row[0]:
        new_token = decrypt_value(token_row[0])
except Exception:
    new_token = None

if not new_token:
    new_token = os.getenv("META_ACCESS_TOKEN")
if not new_token:
    print("ERROR: META_ACCESS_TOKEN not found in DB or .env")
    session.close()
    sys.exit(1)

print(f"New token: {new_token[:20]}...{new_token[-10:]}")

rows = session.execute(text(
    "SELECT id, snapshot_url FROM ads WHERE snapshot_url LIKE '%render_ad%' AND snapshot_url LIKE '%access_token=%'"
)).fetchall()

updated = 0
for row in rows:
    ad_id, old_url = row
    new_url = re.sub(r'access_token=[^&]+', f'access_token={new_token}', old_url)
    if new_url != old_url:
        session.execute(text('UPDATE ads SET snapshot_url = :url WHERE id = :id'), {'url': new_url, 'id': ad_id})
        updated += 1

session.commit()
session.close()
print(f"Updated {updated}/{len(rows)} render_ad URLs with new token")
