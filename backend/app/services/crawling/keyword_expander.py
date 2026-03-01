"""Keyword expansion for Japanese ad market crawling.

Short/English-only queries (e.g. "GLP") miss Japanese ads.
This module expands them into relevant Japanese search terms using:
  1. Shortcut mapping  — known abbreviations → genre keywords
  2. Category matching — explicit category → genre keywords
  3. Substring search  — partial match across all genre keywords
  4. AI generation     — LLM fallback for unmatched queries
"""

import json
import re
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()

# ── Config paths ──────────────────────────────────────────────────────
_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"
_GENRE_KEYWORDS_PATH = _CONFIG_DIR / "genre_crawl_keywords.json"

# ── Max expanded keywords (for substring/AI fallback; genre matches are unlimited) ──
MAX_EXPANDED_FALLBACK = 10

# ── Shortcut mapping: query → genre key(s) ────────────────────────────
# Covers English abbreviations, brand names, AND Japanese short terms.
# Each maps to one or more genres for cross-category discovery.
SHORTCUT_MAP: dict[str, list[str]] = {
    # ─── Medical weight loss ───
    "glp":                ["medical_weight_loss", "diet_supplement"],
    "glp-1":              ["medical_weight_loss", "diet_supplement"],
    "glp1":               ["medical_weight_loss", "diet_supplement"],
    "mounjaro":           ["medical_weight_loss"],
    "wegovy":             ["medical_weight_loss"],
    "ozempic":            ["medical_weight_loss"],
    "saxenda":            ["medical_weight_loss"],
    "rybelsus":           ["medical_weight_loss"],
    "医療痩身":           ["medical_weight_loss", "beauty_clinic"],
    "医療ダイエット":     ["medical_weight_loss", "diet_supplement"],
    "痩身":               ["medical_weight_loss", "beauty_clinic"],
    "メディカルダイエット": ["medical_weight_loss"],
    "脂肪吸引":           ["medical_weight_loss", "beauty_clinic"],
    "肥満外来":           ["medical_weight_loss"],
    # ─── Diet supplement ───
    "diet":               ["diet_supplement", "medical_weight_loss"],
    "ダイエット":         ["diet_supplement", "medical_weight_loss"],
    "サプリ":             ["diet_supplement", "health_food"],
    "置き換え":           ["diet_supplement"],
    "ファスティング":     ["diet_supplement"],
    # ─── Beauty clinic ───
    "美容":               ["beauty_clinic", "skincare"],
    "整形":               ["beauty_clinic"],
    "ボトックス":         ["beauty_clinic"],
    "ヒアルロン酸":       ["beauty_clinic"],
    "ハイフ":             ["beauty_clinic"],
    "hifu":               ["beauty_clinic"],
    "小顔":               ["beauty_clinic"],
    "beauty":             ["beauty_clinic", "skincare"],
    # ─── Skincare ───
    "スキンケア":         ["skincare"],
    "美白":               ["skincare"],
    "化粧水":             ["skincare"],
    "美容液":             ["skincare"],
    "レチノール":         ["skincare"],
    "retinol":            ["skincare"],
    # ─── Hair removal ───
    "脱毛":               ["hair_removal"],
    "vio":                ["hair_removal"],
    "ヒゲ脱毛":           ["hair_removal"],
    "メンズ脱毛":         ["hair_removal"],
    # ─── Hair growth / AGA ───
    "aga":                ["hair_growth_aga"],
    "薄毛":               ["hair_growth_aga"],
    "育毛":               ["hair_growth_aga"],
    "minoxidil":          ["hair_growth_aga"],
    "抜け毛":             ["hair_growth_aga"],
    "発毛":               ["hair_growth_aga"],
    "faga":               ["hair_growth_aga"],
    # ─── Fitness ───
    "ジム":               ["fitness"],
    "パーソナル":         ["fitness"],
    "rizap":              ["fitness"],
    "ライザップ":         ["fitness"],
    "筋トレ":             ["fitness"],
    "ボディメイク":       ["fitness"],
    # ─── Yoga / Pilates ───
    "ヨガ":               ["yoga_pilates"],
    "ピラティス":         ["yoga_pilates"],
    "yoga":               ["yoga_pilates"],
    "pilates":            ["yoga_pilates"],
    "lava":               ["yoga_pilates"],
    # ─── Protein / Supplement ───
    "プロテイン":         ["protein_supplement"],
    "bcaa":               ["protein_supplement"],
    "hmb":                ["protein_supplement"],
    "eaa":                ["protein_supplement"],
    "protein":            ["protein_supplement"],
    # ─── Health food ───
    "青汁":               ["health_food"],
    "コラーゲン":         ["health_food"],
    "nmn":                ["health_food"],
    "ビタミン":           ["health_food"],
    "乳酸菌":             ["health_food"],
    "腸活":               ["health_food", "diet_supplement"],
    # ─── EC / Shopping ───
    "通販":               ["ec_shopping"],
    "セール":             ["ec_shopping"],
    "ec":                 ["ec_shopping"],
    # ─── App ───
    "マッチングアプリ":   ["app"],
    "婚活":               ["app", "wedding"],
    "pairs":              ["app"],
    "tinder":             ["app"],
    "メルカリ":           ["app"],
    # ─── Finance / Investment ───
    "nisa":               ["finance_investment"],
    "fx":                 ["finance_investment"],
    "ideco":              ["finance_investment"],
    "投資":               ["finance_investment"],
    "株":                 ["finance_investment"],
    "仮想通貨":           ["finance_investment"],
    "ビットコイン":       ["finance_investment"],
    "カードローン":       ["finance_investment"],
    "クレカ":             ["finance_investment"],
    # ─── Education / School ───
    "toeic":              ["education_school"],
    "プログラミング":     ["education_school"],
    "英会話":             ["education_school"],
    "スクール":           ["education_school"],
    "塾":                 ["education_school"],
    "資格":               ["education_school"],
    # ─── Real estate ───
    "不動産":             ["real_estate"],
    "マンション":         ["real_estate"],
    "リフォーム":         ["real_estate"],
    "住宅ローン":         ["real_estate"],
    # ─── Jobs / Recruitment ───
    "転職":               ["jobs_recruitment"],
    "求人":               ["jobs_recruitment"],
    "バイト":             ["jobs_recruitment"],
    "副業":               ["jobs_recruitment"],
    "リモートワーク":     ["jobs_recruitment"],
    # ─── Dental ───
    "ホワイトニング":     ["dental"],
    "インプラント":       ["dental"],
    "歯科矯正":          ["dental"],
    "矯正":              ["dental"],
    "invisalign":         ["dental"],
    "インビザライン":     ["dental"],
    # ─── Eye care ───
    "レーシック":         ["eye_care"],
    "icl":                ["eye_care"],
    "コンタクト":         ["eye_care"],
    "視力":               ["eye_care"],
    # ─── Wedding ───
    "結婚式":             ["wedding"],
    "ブライダル":         ["wedding"],
    "ウェディング":       ["wedding"],
    "結婚指輪":           ["wedding"],
    # ─── Pet ───
    "ペット":             ["pet"],
    "ドッグフード":       ["pet"],
    "キャットフード":     ["pet"],
    "ペット保険":         ["pet"],
    # ─── Car ───
    "中古車":             ["car"],
    "車検":               ["car"],
    "カーリース":         ["car"],
    # ─── Travel ───
    "旅行":               ["travel"],
    "ホテル":             ["travel"],
    "航空券":             ["travel"],
    "ツアー":             ["travel"],
    # ─── Mental health ───
    "カウンセリング":     ["mental_health"],
    "うつ":               ["mental_health"],
    "不眠":               ["mental_health"],
    "睡眠":               ["mental_health"],
    "メンタル":           ["mental_health"],
}

# ── Known product/brand names (expanded across all genres) ────────────
KNOWN_PRODUCTS = [
    # GLP-1 drugs
    "マンジャロ", "ウゴービ", "オゼンピック", "サクセンダ", "リベルサス",
    # AGA
    "ミノキシジル", "フィナステリド", "デュタステリド",
    # Fitness brands
    "RIZAP", "ライザップ", "チョコザップ", "chocoZAP", "エニタイム",
    # Yoga
    "LAVA", "ゼンプレイス",
    # Beauty clinic
    "湘南美容", "TCB", "品川美容", "聖心美容",
    # Skincare
    "オルビス", "ファンケル", "SK-II", "ドクターシーラボ",
    # Hair removal
    "リゼクリニック", "レジーナクリニック", "エミナルクリニック",
    # App
    "Pairs", "タップル", "with", "メルカリ",
    # Finance
    "楽天証券", "SBI証券", "マネックス",
    # Dental
    "キレイライン", "インビザライン",
    # Supplement
    "マイプロテイン", "ザバス",
    # Health
    "auravita",
]

# ── Katakana regex (3+ chars for brand-like terms) ────────────────────
_RE_KATAKANA = re.compile(r"[\u30A0-\u30FF]{3,}")


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────

def _load_genre_keywords() -> dict:
    """Load genre_crawl_keywords.json. Returns empty dict on failure."""
    try:
        with open(_GENRE_KEYWORDS_PATH, encoding="utf-8") as f:
            return json.load(f).get("genres", {})
    except Exception:
        logger.warning("genre_keywords_load_failed", path=str(_GENRE_KEYWORDS_PATH))
        return {}


def _is_ascii_only(text: str) -> bool:
    """True if text contains only ASCII characters."""
    return all(ord(c) < 128 for c in text)


def _is_short_query(text: str, threshold: int = 6) -> bool:
    """True if the query is short (likely too vague for Japanese ad search)."""
    return len(text.strip()) <= threshold


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

def should_expand(query: str) -> bool:
    """Determine if a query should be expanded.

    Returns True when the query is:
    - A known shortcut (GLP, AGA, 医療痩身, ヨガ, etc.)
    - Short (≤6 chars) — both ASCII and Japanese
    - Pure ASCII with no Japanese characters
    """
    q = query.strip().lower()

    # Known shortcut (English or Japanese) → always expand
    if q in SHORTCUT_MAP:
        return True

    # Short query (any language) → likely too vague, expand
    if _is_short_query(query):
        return True

    # ASCII-only (no Japanese) → expand to get Japanese results
    if _is_ascii_only(query.strip()) and len(query.strip()) > 0:
        return True

    return False


def expand_query(
    query: str,
    category: Optional[str] = None,
) -> list[str]:
    """Expand a query into Japanese search terms for comprehensive ad discovery.

    For genre matches (shortcut or category), returns ALL genre keywords
    (no limit) to maximize coverage. For substring fallback, caps at
    MAX_EXPANDED_FALLBACK.

    Strategy priority:
    1. Shortcut mapping  — "GLP" → medical_weight_loss + diet_supplement 全キーワード
    2. Category matching — category="medical_weight_loss" → genre 全キーワード
    3. Substring search  — partial match across all genre keywords (capped)
    4. AI generation     — LLM fallback when no static match
    """
    genres = _load_genre_keywords()
    if not genres:
        return []

    q_lower = query.strip().lower()
    candidates: list[str] = []
    is_genre_match = False

    # ── Strategy 1: Shortcut mapping (may map to multiple genres) ──
    genre_keys = SHORTCUT_MAP.get(q_lower, [])
    for gk in genre_keys:
        if gk in genres:
            candidates.extend(genres[gk].get("keywords", []))
            is_genre_match = True

    # ── Strategy 2: Category matching ──
    if not candidates and category:
        cat_lower = category.lower().replace(" ", "_")
        if cat_lower in genres:
            candidates.extend(genres[cat_lower].get("keywords", []))
            is_genre_match = True
        # Also try matching label_jp
        if not candidates:
            for gk, gdata in genres.items():
                if gdata.get("label_jp", "").lower() == cat_lower or gdata.get("label", "").lower() == cat_lower:
                    candidates.extend(gdata.get("keywords", []))
                    is_genre_match = True
                    break

    # ── Strategy 3: Substring search across all genres ──
    if not candidates:
        for genre_data in genres.values():
            for kw in genre_data.get("keywords", []):
                if q_lower in kw.lower():
                    candidates.append(kw)

    # ── Strategy 4: AI-assisted keyword generation (fallback) ──
    if not candidates:
        ai_keywords = _generate_keywords_via_ai(query)
        if ai_keywords:
            candidates.extend(ai_keywords)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    # Genre match → return all keywords; fallback → cap
    result = unique if is_genre_match else unique[:MAX_EXPANDED_FALLBACK]
    if result:
        logger.info(
            "query_expanded",
            original=query,
            category=category,
            genre_match=is_genre_match,
            count=len(result),
            expanded=result,
        )
    return result


def _generate_keywords_via_ai(query: str) -> list[str]:
    """Use LLM to generate Japanese ad search keywords when static matching fails.

    Falls back gracefully if no API key is configured.
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()

        api_key = getattr(settings, "openai_api_key", None)
        if not api_key:
            return []

        import httpx

        prompt = (
            f"あなたは日本の広告市場の専門家です。\n"
            f"「{query}」に関連する日本語の広告検索キーワードを8個生成してください。\n"
            f"Meta Ad Library APIで日本市場の広告を検索するためのキーワードです。\n"
            f"各キーワードは2-4語の日本語フレーズで、広告主が実際に使いそうな表現にしてください。\n"
            f"JSON配列のみ返してください。例: [\"キーワード1\", \"キーワード2\"]"
        )

        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 300,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Parse JSON array from response
        match = re.search(r"\[.*?\]", content, re.DOTALL)
        if match:
            keywords = json.loads(match.group())
            if isinstance(keywords, list):
                result = [str(k) for k in keywords if isinstance(k, str)]
                logger.info("ai_keywords_generated", query=query, count=len(result))
                return result

    except Exception as e:
        logger.debug("ai_keyword_generation_skipped", query=query, reason=str(e))

    return []


async def extract_keywords_from_lp(url: str) -> list[str]:
    """Crawl a landing page and extract brand/product keywords.

    Uses LPCrawler to fetch the page, then:
    1. Match against KNOWN_PRODUCTS
    2. Extract katakana brand names from title
    3. Extract brand names near CTA patterns
    Returns up to MAX_EXPANDED_FALLBACK unique keywords.
    """
    from app.services.lp_analysis.lp_crawler import LPCrawler

    crawler = LPCrawler(timeout=20.0)
    keywords: list[str] = []

    try:
        lp = await crawler.crawl_lp(url)
        if not lp:
            return []

        text = crawler.extract_text_content(lp.html_content)
        title = lp.title or ""
        combined = f"{title} {text}"

        # Strategy 1: Known product names
        for product in KNOWN_PRODUCTS:
            if product.lower() in combined.lower():
                keywords.append(product)

        # Strategy 2: Katakana brand names from title
        for match in _RE_KATAKANA.finditer(title):
            word = match.group()
            if word not in keywords:
                keywords.append(word)

        # Strategy 3: Katakana words near CTA patterns (brand signals)
        cta_vicinity = re.findall(
            r"([\u30A0-\u30FF]{3,})\s*(?:公式|通販|クリニック|サプリ|ダイエット|申込|購入|予約)",
            combined,
        )
        for word in cta_vicinity:
            if word not in keywords:
                keywords.append(word)

        # Deduplicate and limit
        seen: set[str] = set()
        unique: list[str] = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)

        result = unique[:MAX_EXPANDED_FALLBACK]
        logger.info("lp_keywords_extracted", url=url, keywords=result)
        return result

    except Exception as e:
        logger.error("lp_keyword_extraction_failed", url=url, error=str(e))
        return []
    finally:
        await crawler.close()
