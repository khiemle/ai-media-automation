"""
ChromaDB retriever — semantic search for RAG context.
"""
import logging
import os

logger = logging.getLogger(__name__)

CHROMA_DB_PATH  = os.environ.get("CHROMA_DB_PATH", "./chroma_db")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "keepitreal/vietnamese-sbert")

_client   = None
_embed_fn = None


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
                # chromadb 1.x moved embedding functions
                from chromadb.utils.embedding_functions.sentence_transformer_embedding_function import SentenceTransformerEmbeddingFunction
                _embed_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
            except Exception:
                _embed_fn = None
    return _embed_fn


def _collection(name: str):
    """Get or create a ChromaDB collection (compatible with chromadb 1.x)."""
    client   = _get_client()
    embed_fn = _get_embed_fn()
    kwargs   = {"name": name, "metadata": {"hnsw:space": "cosine"}}
    if embed_fn:
        kwargs["embedding_function"] = embed_fn
    return client.get_or_create_collection(**kwargs)


def retrieve_similar_scripts(topic: str, niche: str, k: int = 5) -> list[str]:
    """
    Find the k most stylistically similar scripts to the given topic+niche.
    Returns list of document strings (rich text representations of scripts).
    """
    try:
        collection = _collection("viral_scripts")
        count = collection.count()
        if count == 0:
            return []

        k = min(k, count)
        results = collection.query(
            query_texts=[f"{topic} {niche}"],
            n_results=k,
            where={"niche": niche} if niche else None,
        )
        return results.get("documents", [[]])[0]
    except Exception as e:
        logger.warning(f"[Retriever] viral_scripts query failed: {e}")
        return []


def retrieve_top_hooks(niche: str, k: int = 10) -> list[str]:
    """
    Retrieve the top k hook texts for the given niche, ranked by virality.
    Returns list of hook strings.
    """
    try:
        collection = _collection("viral_hooks")
        count = collection.count()
        if count == 0:
            return _fallback_hooks(niche)

        k = min(k, count)
        results = collection.query(
            query_texts=[f"viral hook {niche} tiktok"],
            n_results=k,
            where={"niche": niche} if niche else None,
        )
        docs = results.get("documents", [[]])[0]
        return docs if docs else _fallback_hooks(niche)
    except Exception as e:
        logger.warning(f"[Retriever] viral_hooks query failed: {e}")
        return _fallback_hooks(niche)


def retrieve_patterns(niche: str) -> dict:
    """
    Retrieve viral pattern data for the given niche.
    Falls back to DB query if ChromaDB collection is empty.
    """
    try:
        collection = _collection("viral_patterns")
        count = collection.count()
        if count > 0:
            results = collection.query(
                query_texts=[niche],
                n_results=1,
                where={"niche": niche} if niche else None,
            )
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            if docs:
                return {"text": docs[0], "meta": metas[0] if metas else {}}
    except Exception as e:
        logger.warning(f"[Retriever] viral_patterns query failed: {e}")

    # Fallback: direct DB query
    return _patterns_from_db(niche)


def _patterns_from_db(niche: str) -> dict:
    try:
        from database.connection import get_session
        from database.models import ViralPattern
        db = get_session()
        try:
            p = db.query(ViralPattern).filter(ViralPattern.niche == niche).first()
            if p:
                return {
                    "hook_templates":   p.hook_templates or [],
                    "scene_types":      p.scene_types or [],
                    "cta_phrases":      p.cta_phrases or [],
                    "hashtag_clusters": p.hashtag_clusters or [],
                    "avg_duration_s":   p.avg_duration_s or 30,
                }
        finally:
            db.close()
    except Exception:
        pass
    return {}


def _fallback_hooks(niche: str) -> list[str]:
    """Hardcoded hook templates per niche when DB is empty."""
    hooks = {
        "health":    ["Bạn có biết N thói quen này đang hại sức khỏe?", "Bí quyết sống khỏe mà ít ai biết"],
        "fitness":   ["N bài tập đốt mỡ cực nhanh tại nhà", "Tại sao bạn tập mãi mà không giảm cân?"],
        "lifestyle": ["N thói quen của người thành công", "Cách thay đổi cuộc sống chỉ trong N ngày"],
        "finance":   ["N sai lầm tài chính người trẻ hay mắc", "Cách tiết kiệm N triệu mỗi tháng"],
        "food":      ["N món ăn vừa ngon vừa tốt cho sức khỏe", "Bí quyết nấu ăn ngon mà ít calo"],
    }
    return hooks.get(niche, ["Bạn có biết điều này chưa?", "Bí quyết mà ít người biết"])
