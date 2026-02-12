"""Multimodal embedding service for similarity search across ads."""

import hashlib
import math
from typing import Optional

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.analysis import AdAnalysis, TextDetection, Transcription
from app.models.competitive_intel import AdEmbedding

logger = structlog.get_logger()

# Appeal axis keywords for auto-tagging
APPEAL_KEYWORDS = {
    "benefit": ["効果", "実感", "変化", "改善", "結果", "メリット"],
    "problem_solution": ["悩み", "解決", "原因", "なぜ", "対策", "改善"],
    "authority": ["医師", "監修", "特許", "研究", "臨床", "専門"],
    "social_proof": ["口コミ", "評価", "実績", "累計", "万個", "レビュー"],
    "urgency": ["限定", "期間", "今だけ", "先着", "残り", "急いで"],
    "price": ["初回", "割引", "OFF", "無料", "特別価格", "送料"],
    "comparison": ["比較", "違い", "従来", "他社", "倍"],
    "emotional": ["自信", "笑顔", "幸せ", "安心", "輝く"],
    "fear": ["放置", "悪化", "手遅れ", "危険", "リスク"],
    "novelty": ["日本初", "新発売", "業界初", "新技術", "特許"],
}

# Expression type keywords
EXPRESSION_KEYWORDS = {
    "ugc": ["使ってみた", "正直レビュー", "本音", "購入品", "レポ"],
    "comparison": ["vs", "比較", "対決", "違い", "どっち"],
    "authority": ["医師", "専門家", "研究者", "プロ", "監修"],
    "review": ["口コミ", "評判", "レビュー", "体験談", "感想"],
    "tutorial": ["使い方", "方法", "コツ", "ステップ", "やり方"],
}


def _simple_text_hash(text: str, dim: int = 128) -> list[float]:
    """Generate a simple text embedding using character n-gram hashing.

    This is a lightweight fallback when ML models aren't available.
    For production, replace with sentence-transformers or OpenAI embeddings.
    """
    if not text:
        return [0.0] * dim

    embedding = [0.0] * dim
    text_lower = text.lower()

    # Character trigram hashing
    for i in range(len(text_lower) - 2):
        trigram = text_lower[i:i + 3]
        h = int(hashlib.md5(trigram.encode()).hexdigest(), 16)
        idx = h % dim
        embedding[idx] += 1.0

    # Normalize to unit vector
    magnitude = math.sqrt(sum(x * x for x in embedding))
    if magnitude > 0:
        embedding = [x / magnitude for x in embedding]

    return embedding


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot / (mag_a * mag_b)


def _detect_appeal_axes(text: str) -> list[str]:
    """Auto-detect appeal axes from text content."""
    axes = []
    text_lower = text.lower() if text else ""
    for axis, keywords in APPEAL_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            axes.append(axis)
    return axes


def _detect_expression_type(text: str) -> Optional[str]:
    """Auto-detect expression type from text content."""
    text_lower = text.lower() if text else ""
    best_match = None
    best_count = 0
    for expr_type, keywords in EXPRESSION_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > best_count:
            best_count = count
            best_match = expr_type
    return best_match


class EmbeddingService:
    """Generate and search multimodal embeddings for ads."""

    def generate_embedding(self, session: Session, ad_id: int) -> Optional[AdEmbedding]:
        """Generate embeddings for an ad from its analysis data."""
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            return None

        analysis = session.query(AdAnalysis).filter(AdAnalysis.ad_id == ad_id).first()

        # Collect text from all sources
        texts = []
        if ad.title:
            texts.append(ad.title)
        if ad.description:
            texts.append(ad.description)

        if analysis:
            # Transcript text
            transcripts = session.query(Transcription).filter(
                Transcription.analysis_id == analysis.id
            ).all()
            for t in transcripts:
                texts.append(t.text)

            # OCR text
            text_detections = session.query(TextDetection).filter(
                TextDetection.analysis_id == analysis.id
            ).all()
            for td in text_detections:
                texts.append(td.text)

            # Full transcript
            if analysis.full_transcript:
                texts.append(analysis.full_transcript)

        combined_text = " ".join(texts)

        # Generate embeddings
        text_emb = _simple_text_hash(combined_text, dim=128)
        visual_emb = _simple_text_hash(
            f"{ad.title or ''} {analysis.hook_type or ''} {analysis.overall_sentiment or ''}" if analysis else (ad.title or ""),
            dim=128,
        )

        # Combined: average of text and visual
        combined_emb = [(t + v) / 2 for t, v in zip(text_emb, visual_emb)]
        mag = math.sqrt(sum(x * x for x in combined_emb))
        if mag > 0:
            combined_emb = [x / mag for x in combined_emb]

        # Auto-tagging
        appeal_axes = _detect_appeal_axes(combined_text)
        expression_type = _detect_expression_type(combined_text)

        # Structure detection from analysis
        structure_type = None
        if analysis:
            parts = []
            if analysis.hook_type:
                parts.append("hook")
            if analysis.full_transcript and len(analysis.full_transcript) > 100:
                parts.append("body")
            if analysis.cta_text:
                parts.append("CTA")
            structure_type = "→".join(parts) if parts else None

        embedding = AdEmbedding(
            ad_id=ad_id,
            visual_embedding=visual_emb,
            text_embedding=text_emb,
            combined_embedding=combined_emb,
            embedding_type="multimodal",
            embedding_dim=128,
            model_version="hash_v1",
            auto_appeal_axes=appeal_axes,
            auto_expression_type=expression_type,
            auto_structure_type=structure_type,
        )

        # Upsert
        existing = session.query(AdEmbedding).filter(AdEmbedding.ad_id == ad_id).first()
        if existing:
            existing.visual_embedding = visual_emb
            existing.text_embedding = text_emb
            existing.combined_embedding = combined_emb
            existing.auto_appeal_axes = appeal_axes
            existing.auto_expression_type = expression_type
            existing.auto_structure_type = structure_type
            embedding = existing
        else:
            session.add(embedding)

        session.commit()
        session.refresh(embedding)
        return embedding

    def find_similar(
        self,
        session: Session,
        ad_id: int,
        limit: int = 20,
        embedding_field: str = "combined",
        min_similarity: float = 0.3,
    ) -> list[dict]:
        """Find ads similar to the given ad using embedding similarity."""
        # Get source embedding
        source = session.query(AdEmbedding).filter(AdEmbedding.ad_id == ad_id).first()
        if not source:
            return []

        if embedding_field == "text":
            source_vec = source.text_embedding
        elif embedding_field == "visual":
            source_vec = source.visual_embedding
        else:
            source_vec = source.combined_embedding

        if not source_vec:
            return []

        # Get all embeddings (in production, use pgvector for efficient ANN search)
        all_embeddings = session.query(AdEmbedding).filter(
            AdEmbedding.ad_id != ad_id
        ).limit(1000).all()

        results = []
        for emb in all_embeddings:
            if embedding_field == "text":
                target_vec = emb.text_embedding
            elif embedding_field == "visual":
                target_vec = emb.visual_embedding
            else:
                target_vec = emb.combined_embedding

            if not target_vec:
                continue

            similarity = _cosine_similarity(source_vec, target_vec)
            if similarity >= min_similarity:
                results.append({
                    "ad_id": emb.ad_id,
                    "similarity": round(similarity, 4),
                    "auto_appeal_axes": emb.auto_appeal_axes,
                    "auto_expression_type": emb.auto_expression_type,
                    "auto_structure_type": emb.auto_structure_type,
                })

        # Sort by similarity descending
        results.sort(key=lambda x: -x["similarity"])
        return results[:limit]

    def search_by_text(
        self,
        session: Session,
        query_text: str,
        limit: int = 20,
        min_similarity: float = 0.2,
    ) -> list[dict]:
        """Semantic search: find ads similar to a text query."""
        query_vec = _simple_text_hash(query_text, dim=128)

        all_embeddings = session.query(AdEmbedding).limit(1000).all()

        results = []
        for emb in all_embeddings:
            if not emb.text_embedding:
                continue

            similarity = _cosine_similarity(query_vec, emb.text_embedding)
            if similarity >= min_similarity:
                results.append({
                    "ad_id": emb.ad_id,
                    "similarity": round(similarity, 4),
                    "auto_appeal_axes": emb.auto_appeal_axes,
                    "auto_expression_type": emb.auto_expression_type,
                })

        results.sort(key=lambda x: -x["similarity"])
        return results[:limit]
