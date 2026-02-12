"""Keyword and keyphrase extraction from ad content."""

import re
from collections import Counter
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()


@dataclass
class ExtractedKeyword:
    """An extracted keyword with relevance score."""

    keyword: str
    score: float
    category: str = ""  # cta, hook, benefit, feature, brand
    frequency: int = 1


@dataclass
class KeywordExtractionResult:
    """Results of keyword extraction."""

    keywords: list[ExtractedKeyword] = field(default_factory=list)
    cta_phrases: list[str] = field(default_factory=list)
    hook_words: list[str] = field(default_factory=list)
    appeal_axes: list[str] = field(default_factory=list)
    brand_mentions: list[str] = field(default_factory=list)


class KeywordExtractor:
    """Extract keywords, CTAs, and key phrases from ad text."""

    # CTA patterns
    CTA_PATTERNS_JA = [
        r"今すぐ\S+",
        r"無料で?\S*",
        r"\S*ダウンロード",
        r"\S*登録",
        r"\S*申し?込[みむ]",
        r"詳[しく]く[はは]?こちら",
        r"LINE\S*追加",
        r"友だち追加",
        r"\S*お試し",
        r"クリック",
        r"\S*購入",
        r"\S*注文",
        r"資料請求",
        r"公式サイト\S*",
    ]

    CTA_PATTERNS_EN = [
        r"(?:shop|buy|order|get|try|start|sign up|subscribe|download|install|register|learn more|click|join)\s*(?:now|today|here|free)?",
    ]

    # Hook patterns
    HOOK_PATTERNS_JA = [
        r"[え!?！？]+",
        r"衝撃\S*",
        r"まだ\S*してない",
        r"知ってた？",
        r"実は\S+",
        r"たった\S+で",
        r"\d+人が\S+",
        r"〇〇が\S+",
        r"あなた[はも]\S+",
    ]

    # Appeal axis patterns
    APPEAL_PATTERNS_JA = {
        "price": [r"円", r"無料", r"お得", r"割引", r"安い", r"コスパ", r"最安"],
        "quality": [r"品質", r"本格", r"プロ", r"高品質", r"こだわり"],
        "convenience": [r"簡単", r"すぐ", r"たった", r"手軽", r"楽々"],
        "authority": [r"No\.?\s*1", r"実績", r"専門", r"認定", r"受賞"],
        "social_proof": [r"万人", r"口コミ", r"レビュー", r"満足度", r"人気"],
        "scarcity": [r"限定", r"残り", r"本日", r"先着", r"在庫"],
        "transformation": [r"変わ[っる]", r"実感", r"効果", r"ビフォーアフター"],
    }

    def __init__(self):
        self._tokenizer = None

    def _get_tokenizer(self):
        """Get Japanese tokenizer (MeCab via fugashi)."""
        if self._tokenizer is None:
            try:
                import fugashi
                self._tokenizer = fugashi.Tagger()
                logger.info("japanese_tokenizer_loaded")
            except ImportError:
                logger.warning("fugashi_not_available, falling_back_to_simple_tokenization")
                self._tokenizer = "simple"
        return self._tokenizer

    def extract_keywords(self, text: str, top_n: int = 20) -> KeywordExtractionResult:
        """Extract keywords and categorize them."""
        if not text or not text.strip():
            return KeywordExtractionResult()

        result = KeywordExtractionResult()

        # Extract CTAs
        result.cta_phrases = self._extract_ctas(text)

        # Extract hook words
        result.hook_words = self._extract_hooks(text)

        # Extract appeal axes
        result.appeal_axes = self._detect_appeal_axes(text)

        # Extract general keywords
        keywords = self._extract_general_keywords(text, top_n)
        result.keywords = keywords

        return result

    def _extract_ctas(self, text: str) -> list[str]:
        """Extract CTA phrases."""
        ctas: list[str] = []
        text_lower = text.lower()

        for pattern in self.CTA_PATTERNS_JA + self.CTA_PATTERNS_EN:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            ctas.extend(matches)

        return list(set(ctas))

    def _extract_hooks(self, text: str) -> list[str]:
        """Extract hook words/phrases."""
        hooks: list[str] = []

        for pattern in self.HOOK_PATTERNS_JA:
            matches = re.findall(pattern, text)
            hooks.extend(matches)

        return list(set(hooks))

    def _detect_appeal_axes(self, text: str) -> list[str]:
        """Detect appeal axes used in the ad."""
        detected_axes: list[str] = []
        text_lower = text.lower()

        for axis, patterns in self.APPEAL_PATTERNS_JA.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    detected_axes.append(axis)
                    break

        return detected_axes

    def _extract_general_keywords(self, text: str, top_n: int) -> list[ExtractedKeyword]:
        """Extract general keywords using tokenization."""
        tokenizer = self._get_tokenizer()

        if tokenizer == "simple":
            return self._simple_keyword_extraction(text, top_n)

        try:
            words: list[str] = []
            for word in tokenizer(text):
                # Get part of speech
                features = word.feature
                pos = features.split(",")[0] if features else ""

                # Keep nouns and adjectives
                if pos in ("名詞", "形容詞") and len(str(word)) >= 2:
                    words.append(str(word))

            # Count frequencies
            counter = Counter(words)
            keywords = []

            for word, count in counter.most_common(top_n):
                # Categorize
                category = self._categorize_keyword(word)
                score = count / len(words) if words else 0

                keywords.append(ExtractedKeyword(
                    keyword=word,
                    score=round(score, 4),
                    category=category,
                    frequency=count,
                ))

            return keywords

        except Exception as e:
            logger.error("keyword_extraction_failed", error=str(e))
            return self._simple_keyword_extraction(text, top_n)

    def _simple_keyword_extraction(self, text: str, top_n: int) -> list[ExtractedKeyword]:
        """Simple keyword extraction without Japanese tokenizer."""
        # Split on whitespace and punctuation
        words = re.findall(r'[\w\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]+', text)
        words = [w for w in words if len(w) >= 2]

        counter = Counter(words)
        keywords = []
        total = len(words) or 1

        for word, count in counter.most_common(top_n):
            keywords.append(ExtractedKeyword(
                keyword=word,
                score=round(count / total, 4),
                category=self._categorize_keyword(word),
                frequency=count,
            ))

        return keywords

    def _categorize_keyword(self, word: str) -> str:
        """Categorize a keyword."""
        word_lower = word.lower()

        cta_words = {"購入", "登録", "申込", "ダウンロード", "buy", "shop", "sign", "download"}
        if word_lower in cta_words or any(w in word_lower for w in cta_words):
            return "cta"

        hook_words = {"衝撃", "驚き", "秘密", "注目", "shocking", "amazing", "secret"}
        if word_lower in hook_words or any(w in word_lower for w in hook_words):
            return "hook"

        benefit_words = {"無料", "割引", "お得", "free", "discount", "save"}
        if word_lower in benefit_words or any(w in word_lower for w in benefit_words):
            return "benefit"

        return "feature"

    def extract_from_segments(
        self,
        segments: list[dict],
    ) -> dict:
        """Extract keywords from timed segments, tracking when they appear."""
        keyword_timestamps: dict[str, list[float]] = {}
        all_text = ""

        for seg in segments:
            text = seg.get("text", "")
            start_time = seg.get("start_time_ms", 0) / 1000.0
            all_text += " " + text

            # Simple extraction per segment
            words = re.findall(r'[\w\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]+', text)
            for word in words:
                if len(word) >= 2:
                    if word not in keyword_timestamps:
                        keyword_timestamps[word] = []
                    keyword_timestamps[word].append(start_time)

        # Full extraction
        result = self.extract_keywords(all_text)

        # Add timing info
        keyword_timeline = {}
        for kw in result.keywords[:10]:
            if kw.keyword in keyword_timestamps:
                keyword_timeline[kw.keyword] = {
                    "first_mention": min(keyword_timestamps[kw.keyword]),
                    "mentions": keyword_timestamps[kw.keyword],
                    "count": len(keyword_timestamps[kw.keyword]),
                }

        return {
            "keywords": [
                {"keyword": k.keyword, "score": k.score, "category": k.category, "frequency": k.frequency}
                for k in result.keywords
            ],
            "cta_phrases": result.cta_phrases,
            "hook_words": result.hook_words,
            "appeal_axes": result.appeal_axes,
            "keyword_timeline": keyword_timeline,
        }
