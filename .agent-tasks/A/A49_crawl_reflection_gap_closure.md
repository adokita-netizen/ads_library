# A49: Crawl Reflection Gap Closure

## Objective
`quick-crawl` 実行後に「保存済みなのに検索結果に出ない」ギャップを減らす。

## Scope
- `/rankings/search` の ads 検索で `ad_metadata.crawl_query/topic` を補完マッチに使用
- sparse copy（title/descriptionが薄い広告）でも検索ヒット可能にする

## Acceptance Criteria
- `q=GLP-1` で、本文一致なしでも `crawl_query` が一致する広告が検索結果に出る
- topic/matched_terms 由来の補完一致が効く
- 既存の検索ソート・ページングを壊さない

## Status
Completed (2026-03-03)
