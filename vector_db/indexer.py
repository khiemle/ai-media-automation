"""
ChromaDB indexer — embeds viral videos and scripts into vector collections.
Uses sentence-transformers for Vietnamese SBERT embeddings.
"""
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

CHROMA_DB_PATH  = os.environ.get("CHROMA_DB_PATH", "./chroma_db")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "keepitreal/vietnamese-sbert")

_client    = None
_embed_fn  = None


def _get_client():
    global _client
    if _client is None:
        import chromadb
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return _client


def _get_embed_fn():
    global _embed_fn
    if _embed_fn is None:
        try:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
            _embed_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        except Exception:
            try:
                from chromadb.utils.embedding_functions.sentence_transformer_embedding_function import SentenceTransformerEmbeddingFunction
                _embed_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
            except Exception as e:
                logger.warning(f"sentence-transformers not available ({e}), using ChromaDB default embeddings")
                _embed_fn = None
    return _embed_fn


def _collection(name: str):
    """Get or create a ChromaDB collection (compatible with chromadb 1.x)."""
    client = _get_client()
    embed_fn = _get_embed_fn()
    kwargs = {"name": name, "metadata": {"hnsw:space": "cosine"}}
    if embed_fn:
        kwargs["embedding_function"] = embed_fn
    return client.get_or_create_collection(**kwargs)


def index_videos(video_ids: list[int]) -> int:
    """
    Embed hook_text from viral_videos and upsert into `viral_hooks` collection.
    Returns number of vectors upserted.
    """
    if not video_ids:
        return 0

    from database.connection import get_session
    from database.models import ViralVideo
    from datetime import datetime, timezone

    db = get_session()
    try:
        videos = db.query(ViralVideo).filter(ViralVideo.id.in_(video_ids)).all()
        if not videos:
            return 0

        collection = _collection("viral_hooks")

        ids       = [str(v.id) for v in videos if v.hook_text]
        documents = [v.hook_text for v in videos if v.hook_text]
        metadatas = [
            {
                "video_id":    v.video_id,
                "niche":       v.niche or "",
                "region":      v.region or "vn",
                "play_count":  str(v.play_count or 0),
                "source":      v.source,
                "author":      v.author or "",
            }
            for v in videos if v.hook_text
        ]

        if not ids:
            return 0

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        # Mark videos as indexed
        now = datetime.now(timezone.utc)
        for v in videos:
            v.indexed_at = now
        db.commit()

        logger.info(f"[Indexer] Indexed {len(ids)} hooks into viral_hooks")
        return len(ids)
    finally:
        db.close()


def index_script(script_id: int) -> bool:
    """
    Embed full script JSON into `viral_scripts` collection.
    Called after a script is marked high-quality by the feedback loop.
    """
    from database.connection import get_session
    from database.models import GeneratedScript

    db = get_session()
    try:
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script or not script.script_json:
            return False

        collection = _collection("viral_scripts")

        # Build a rich text document from the script
        sj   = script.script_json
        meta = sj.get("meta", {})
        scenes_text = " ".join(
            s.get("narration", "") for s in sj.get("scenes", [])
        )
        document = (
            f"Topic: {meta.get('topic', '')} "
            f"Niche: {meta.get('niche', '')} "
            f"Template: {meta.get('template', '')} "
            f"Scenes: {scenes_text}"
        )

        collection.upsert(
            ids=[str(script_id)],
            documents=[document],
            metadatas=[{
                "script_id":    str(script_id),
                "topic":        meta.get("topic", ""),
                "niche":        meta.get("niche", ""),
                "template":     meta.get("template", ""),
                "quality_score": str(script.quality_score or 0),
            }],
        )
        logger.info(f"[Indexer] Indexed script {script_id} into viral_scripts")
        return True
    finally:
        db.close()


def index_patterns(niche: str | None = None) -> int:
    """
    Embed viral_patterns into `viral_patterns` collection.
    """
    from database.connection import get_session
    from database.models import ViralPattern

    db = get_session()
    try:
        query = db.query(ViralPattern)
        if niche:
            query = query.filter(ViralPattern.niche == niche)
        patterns = query.all()

        if not patterns:
            return 0

        collection = _collection("viral_patterns")
        ids, docs, metas = [], [], []

        for p in patterns:
            doc = (
                f"Niche: {p.niche} Region: {p.region} "
                f"Hooks: {' | '.join(p.hook_templates or [])} "
                f"CTA: {' | '.join(p.cta_phrases or [])} "
                f"Tags: {' '.join(p.hashtag_clusters or [])}"
            )
            ids.append(f"{p.niche}_{p.region}")
            docs.append(doc)
            metas.append({
                "niche":        p.niche,
                "region":       p.region,
                "sample_count": str(p.sample_count or 0),
            })

        collection.upsert(ids=ids, documents=docs, metadatas=metas)
        logger.info(f"[Indexer] Indexed {len(patterns)} patterns into viral_patterns")
        return len(patterns)
    finally:
        db.close()
