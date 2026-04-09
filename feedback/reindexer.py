"""
Feedback Reindexer — indexes high-quality scripts into ChromaDB viral_scripts collection.
Removes low-quality entries to keep the vector DB clean.
"""
import logging
import os

logger = logging.getLogger(__name__)

REINDEX_THRESHOLD    = int(os.environ.get("FEEDBACK_REINDEX_THRESHOLD", "70"))
LOW_QUALITY_THRESHOLD = int(os.environ.get("FEEDBACK_LOW_QUALITY_THRESHOLD", "40"))


def reindex_top_performers() -> dict:
    """
    1. Query scripts with quality_score >= REINDEX_THRESHOLD → upsert to viral_scripts
    2. Remove scripts with quality_score < LOW_QUALITY_THRESHOLD from viral_scripts
    Returns summary dict.
    """
    from database.connection import get_session
    from database.models import GeneratedScript
    from vector_db.indexer import index_script

    db = get_session()
    try:
        # High performers → add to ChromaDB
        high_quality = db.query(GeneratedScript).filter(
            GeneratedScript.quality_score >= REINDEX_THRESHOLD,
        ).all()

        indexed = 0
        for script in high_quality:
            try:
                index_script(script.id)
                indexed += 1
            except Exception as e:
                logger.warning(f"[Reindexer] Failed to index script {script.id}: {e}")

        # Low performers → remove from ChromaDB
        removed = _remove_low_quality(db)

        summary = {"indexed": indexed, "removed": removed, "threshold": REINDEX_THRESHOLD}
        logger.info(f"[Reindexer] {summary}")
        return summary
    finally:
        db.close()


def _remove_low_quality(db) -> int:
    """Remove low-quality scripts from the viral_scripts ChromaDB collection."""
    from database.models import GeneratedScript

    low_quality = db.query(GeneratedScript).filter(
        GeneratedScript.quality_score.isnot(None),
        GeneratedScript.quality_score < LOW_QUALITY_THRESHOLD,
    ).all()

    if not low_quality:
        return 0

    try:
        from database.setup_chromadb import get_client
        client = get_client()
        collection = client.get_collection("viral_scripts")
        ids_to_remove = [str(s.id) for s in low_quality]
        # Only remove IDs that exist in the collection
        existing = collection.get(ids=ids_to_remove)
        existing_ids = existing.get("ids", [])
        if existing_ids:
            collection.delete(ids=existing_ids)
        logger.info(f"[Reindexer] Removed {len(existing_ids)} low-quality entries from viral_scripts")
        return len(existing_ids)
    except Exception as e:
        logger.warning(f"[Reindexer] ChromaDB removal failed: {e}")
        return 0
