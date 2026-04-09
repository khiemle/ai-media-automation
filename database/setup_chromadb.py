"""
Initialize ChromaDB persistent client and create the 3 required collections.
Run once: python database/setup_chromadb.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "pipeline.env", override=False)
load_dotenv(Path(__file__).parent.parent / "console" / ".env", override=False)

CHROMA_DB_PATH  = os.environ.get("CHROMA_DB_PATH", "./chroma_db")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "keepitreal/vietnamese-sbert")

COLLECTIONS = {
    "viral_scripts":  "Full generated script JSON — used to find stylistically similar scripts",
    "viral_hooks":    "First-line hook text from scraped TikTok videos — used to retrieve top hooks",
    "viral_patterns": "Extracted niche/region trend patterns — used to enrich prompts",
}


def _get_embed_fn():
    """Load sentence-transformer embedding function (must match retriever/indexer)."""
    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    except Exception:
        try:
            from chromadb.utils.embedding_functions.sentence_transformer_embedding_function import SentenceTransformerEmbeddingFunction
            return SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        except Exception as e:
            print(f"Warning: could not load sentence-transformers ({e}), using default embeddings")
            return None


def get_client():
    import chromadb
    return chromadb.PersistentClient(path=CHROMA_DB_PATH)


def setup():
    """Create all 3 ChromaDB collections if they don't already exist."""
    client   = get_client()
    embed_fn = _get_embed_fn()
    existing = {col.name for col in client.list_collections()}

    for name, description in COLLECTIONS.items():
        kwargs = {"name": name, "metadata": {"description": description, "hnsw:space": "cosine"}}
        if embed_fn:
            kwargs["embedding_function"] = embed_fn
        if name not in existing:
            client.create_collection(**kwargs)
            print(f"✅  Created collection: {name}")
        else:
            print(f"   Collection already exists: {name}")

    print(f"\nChromaDB ready at: {CHROMA_DB_PATH}")
    print(f"Collections: {[col.name for col in client.list_collections()]}")
    return client


if __name__ == "__main__":
    setup()
