"""Central registry for stable API error and failure reason codes."""

from __future__ import annotations

DEFAULT_RUNBOOK = "/docs/ops/error-codes"
SCOPE_OWNER_MAP = {
    "global": "backend_api",
    "gateway": "platform_ops",
    "database": "backend_data",
    "rankings_quality_gate": "ranking_quality",
    "crawl": "crawl_ops",
    "tasks": "worker_ops",
    "media": "media_ops",
    "media_status": "media_ops",
    "rankings_cache": "backend_api",
}
CATEGORY_SEVERITY_MAP = {
    "user": "low",
    "not_found": "low",
    "data_quality": "medium",
    "external": "high",
    "system": "critical",
}
CATEGORY_FIRST_RESPONSE_MAP = {
    "user": "validate_request",
    "not_found": "confirm_resource_state",
    "data_quality": "run_quality_recovery",
    "external": "check_upstream_dependency",
    "system": "inspect_api_logs",
}

ERROR_CODE_REGISTRY: dict[str, dict] = {
    "validation_error": {
        "category": "user",
        "http_status": 422,
        "scope": "global",
        "message": "リクエストの検証に失敗しました",
        "operator_action": "入力値と必須パラメータを修正して再試行する",
    },
    "gateway_auth_required": {
        "category": "user",
        "http_status": 401,
        "scope": "gateway",
        "message": "API gateway authentication required",
        "operator_action": "gateway API key を付与して再試行する",
    },
    "database_error": {
        "category": "system",
        "http_status": 500,
        "scope": "database",
        "message": "データベースエラーが発生しました",
        "operator_action": "DB 接続状態と直近 migration を確認する",
    },
    "internal_error": {
        "category": "system",
        "http_status": 500,
        "scope": "global",
        "message": "内部サーバーエラーが発生しました",
        "operator_action": "request_id / trace_id でサーバーログを確認する",
    },
    "minimum_count_not_met": {
        "category": "data_quality",
        "http_status": 200,
        "scope": "rankings_quality_gate",
        "message": "サンプル件数が最低件数を下回っています",
        "operator_action": "クロール対象媒体やキーワードを拡張して再実行する",
    },
    "required_fields_fill_rate_low": {
        "category": "data_quality",
        "http_status": 200,
        "scope": "rankings_quality_gate",
        "message": "必須項目充足率がしきい値を下回っています",
        "operator_action": "destination_url・media_url・snapshot_url の補完ジョブを再実行する",
    },
    "image_quality_score_low": {
        "category": "data_quality",
        "http_status": 200,
        "scope": "rankings_quality_gate",
        "message": "画像品質スコアがしきい値を下回っています",
        "operator_action": "needs_media_retry=true の広告を再抽出する",
    },
    "topic_confidence_low": {
        "category": "data_quality",
        "http_status": 200,
        "scope": "rankings_quality_gate",
        "message": "分類信頼度がしきい値を下回っています",
        "operator_action": "classify-topic を再実行し辞書見直し候補を確認する",
    },
    "timeout": {
        "category": "external",
        "http_status": 504,
        "scope": "crawl",
        "message": "外部呼び出しがタイムアウトしました",
        "operator_action": "上流 API の遅延と retry 成否を確認する",
    },
    "dispatch_error": {
        "category": "system",
        "http_status": 500,
        "scope": "tasks",
        "message": "ジョブ dispatch に失敗しました",
        "operator_action": "queue 接続と worker 側ログを確認する",
    },
    "no_cached_media": {
        "category": "not_found",
        "http_status": 404,
        "scope": "media",
        "message": "キャッシュ済みメディアが見つかりません",
        "operator_action": "メディア抽出ジョブを再実行する",
    },
    "invalid_ad_ids": {
        "category": "user",
        "http_status": 400,
        "scope": "media",
        "message": "不正な ad_ids が指定されました",
        "operator_action": "ad_ids の形式と件数上限を確認する",
    },
    "zip_creation_failed": {
        "category": "system",
        "http_status": 500,
        "scope": "media",
        "message": "ZIP 生成に失敗しました",
        "operator_action": "一時ディスク容量と対象ファイル欠損を確認する",
    },
    "download_file_missing": {
        "category": "not_found",
        "http_status": 404,
        "scope": "media",
        "message": "ダウンロード対象ファイルが見つかりません",
        "operator_action": "キャッシュ再生成後に再試行する",
    },
    "missing_media": {
        "category": "data_quality",
        "http_status": 200,
        "scope": "media_status",
        "message": "表示可能なメディアが不足しています",
        "operator_action": "creative fetch を再実行する",
    },
    "missing_lp": {
        "category": "data_quality",
        "http_status": 200,
        "scope": "media_status",
        "message": "LP 情報が不足しています",
        "operator_action": "destination_url を補完する",
    },
    "stale_creative": {
        "category": "external",
        "http_status": 200,
        "scope": "media_status",
        "message": "クリエイティブ参照先が stale です",
        "operator_action": "snapshot / media refresh を再実行する",
    },
    "download_unavailable": {
        "category": "data_quality",
        "http_status": 200,
        "scope": "media_status",
        "message": "閲覧可能ですがダウンロード元がありません",
        "operator_action": "S3/local cache の同期状態を確認する",
    },
    "stale_cache": {
        "category": "system",
        "http_status": 200,
        "scope": "rankings_cache",
        "message": "最新計算に失敗したため stale cache を返却しました",
        "operator_action": "fresh compute の失敗ログを確認し cache 更新を再試行する",
    },
    "fresh_compute_failed": {
        "category": "system",
        "http_status": 200,
        "scope": "rankings_cache",
        "message": "最新計算に失敗し縮退レスポンスを返却しました",
        "operator_action": "compute 経路の例外ログを確認する",
    },
}


def get_error_codes(*, category: str | None = None, scope: str | None = None) -> list[dict]:
    items: list[dict] = []
    for code, meta in sorted(ERROR_CODE_REGISTRY.items()):
        if category and meta["category"] != category:
            continue
        if scope and meta["scope"] != scope:
            continue
        item = {"code": code}
        item.update(meta)
        item["severity"] = meta.get("severity") or CATEGORY_SEVERITY_MAP.get(meta["category"], "medium")
        item["owner"] = meta.get("owner") or SCOPE_OWNER_MAP.get(meta["scope"], "backend_api")
        item["runbook"] = meta.get("runbook") or f"{DEFAULT_RUNBOOK}#{code}"
        item["first_response"] = meta.get("first_response") or CATEGORY_FIRST_RESPONSE_MAP.get(
            meta["category"],
            "inspect_api_logs",
        )
        items.append(item)
    return items


def get_error_code_categories() -> list[str]:
    return sorted({str(meta["category"]) for meta in ERROR_CODE_REGISTRY.values()})


def get_error_code_scopes() -> list[str]:
    return sorted({str(meta["scope"]) for meta in ERROR_CODE_REGISTRY.values()})
