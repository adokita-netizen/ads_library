"""Batch image extraction for all ads missing image_url."""
import asyncio
import os
import sqlite3
import sys
import time

sys.path.insert(0, ".")
from app.services.media_extraction import MediaExtractor

DB_PATH = os.path.join(os.path.dirname(__file__), "vaap_local.db") if not os.path.exists("vaap_local.db") else "vaap_local.db"
BATCH_SIZE = 50
DELAY = 2.0

async def extract_batch():
    conn = sqlite3.connect("vaap_local.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('''
        SELECT id, external_id, snapshot_url, creative_type 
        FROM ads 
        WHERE image_url IS NULL AND snapshot_url IS NOT NULL 
        ORDER BY id
    ''')
    ads = c.fetchall()
    
    extractor = MediaExtractor(timeout=45.0)
    stats = {'success': 0, 'failed': 0, 'total': len(ads)}
    
    print(f'Total ads to process: {len(ads)}')
    print(f'Batch size: {BATCH_SIZE}, Delay: {DELAY}s')
    print()
    
    for i, ad in enumerate(ads):
        ad_id = ad['id']
        snapshot = ad['snapshot_url']
        
        try:
            result = await extractor.extract(snapshot, use_playwright=True)
            
            if result.image_urls:
                image_url = result.image_urls[0]
                thumbnail_url = result.thumbnail_url or image_url
                creative_type = result.creative_type or ad['creative_type']
                
                c.execute('''
                    UPDATE ads 
                    SET image_url = ?, thumbnail_url = COALESCE(thumbnail_url, ?), 
                        creative_type = COALESCE(creative_type, ?),
                        media_extraction_status = 'completed'
                    WHERE id = ?
                ''', (image_url, thumbnail_url, creative_type, ad_id))
                
                stats['success'] += 1
                if (i + 1) % 10 == 0:
                    print(f'[{i+1}/{len(ads)}] OK - {stats["success"]} success, {stats["failed"]} failed')
            else:
                stats['failed'] += 1
                
        except Exception as e:
            stats['failed'] += 1
            if (i + 1) % 10 == 0:
                print(f'[{i+1}/{len(ads)}] ERROR: {e}')
        
        # Commit every batch
        if (i + 1) % BATCH_SIZE == 0:
            conn.commit()
            print(f'--- Committed batch {(i+1)//BATCH_SIZE} ({i+1}/{len(ads)}) ---')
        
        if i + 1 < len(ads):
            time.sleep(DELAY)
    
    conn.commit()
    conn.close()
    
    print()
    print('=' * 60)
    print(f'BATCH EXTRACTION COMPLETE')
    print(f'Total: {stats["total"]}')
    print(f'Success: {stats["success"]}')
    print(f'Failed: {stats["failed"]}')
    print('=' * 60)

asyncio.run(extract_batch())
