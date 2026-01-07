import os
import re
import json
import hashlib
from typing import List, Dict, Any

import requests
import chromadb
from sentence_transformers import SentenceTransformer

from mcp.server.fastmcp import FastMCP

DOC_URL_DEFAULT = "https://docs.streamlit.io/llms-full.txt"
ADK_DOC_URL_DEFAULT = "https://raw.githubusercontent.com/google/adk-python/refs/heads/main/llms-full.txt"
APP_NAME = "streamlit-docs-rag"

mcp = FastMCP("Streamlit Docs RAG (local)", json_response=True)

def _cache_dir() -> str:
    d = os.path.join(os.path.dirname(__file__), ".cache")
    os.makedirs(d, exist_ok=True)
    return d

def _data_paths() -> Dict[str, str]:
    base = _cache_dir()
    return {
        "raw": os.path.join(base, "llms-full.txt"),
        "meta": os.path.join(base, "meta.json"),
        "chroma": os.path.join(base, "chroma"),
    }

def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _fetch_doc(doc_url: str) -> bytes:
    r = requests.get(doc_url, timeout=60)
    r.raise_for_status()
    return r.content

def _load_or_refresh_raw(doc_url: str) -> Dict[str, Any]:
    paths = _data_paths()
    meta_path = paths["meta"]

    raw_bytes = _fetch_doc(doc_url)
    new_hash = _sha256_bytes(raw_bytes)

    meta = {"doc_url": doc_url, "sha256": None}
    if os.path.exists(meta_path):
        try:
            meta = json.load(open(meta_path, "r", encoding="utf-8"))
        except Exception:
            meta = {"doc_url": doc_url, "sha256": None}

    changed = meta.get("sha256") != new_hash

    # Always write latest raw (so your cache is consistent)
    with open(paths["raw"], "wb") as f:
        f.write(raw_bytes)

    meta = {"doc_url": doc_url, "sha256": new_hash}
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)

    return {"changed": changed, "sha256": new_hash, "raw_path": paths["raw"]}

def _chunk_markdown(text: str, max_chars: int = 3500) -> List[Dict[str, str]]:
    """
    Simple chunker:
    - splits on headings
    - then packs into ~max_chars chunks while keeping headings with content
    """
    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Split into heading blocks
    parts = re.split(r"\n(?=#+\s)", text)
    blocks = [p.strip() for p in parts if p.strip()]

    chunks: List[Dict[str, str]] = []
    buf = ""
    title = ""

    def flush():
        nonlocal buf, title
        if buf.strip():
            chunks.append({"title": title.strip() or "Streamlit Docs", "text": buf.strip()})
        buf = ""
        title = ""

    for block in blocks:
        # Identify the first heading as title
        m = re.match(r"^(#+)\s+(.*)$", block.split("\n", 1)[0].strip())
        block_title = m.group(2).strip() if m else "Streamlit Docs"

        # Start a new chunk if needed
        if not buf:
            title = block_title

        if len(buf) + len(block) + 2 > max_chars:
            flush()
            title = block_title

        buf = (buf + "\n\n" + block).strip()

    flush()
    return chunks

def _get_collection(doc_url: str):
    paths = _data_paths()
    client = chromadb.PersistentClient(path=paths["chroma"])
    # Make collection name stable per URL (supports multiple doc sources later)
    name = "streamlit_llms_full_" + hashlib.md5(doc_url.encode("utf-8")).hexdigest()
    return client.get_or_create_collection(name=name)

def _ensure_index(doc_url: str) -> Dict[str, Any]:
    refresh = _load_or_refresh_raw(doc_url)
    paths = _data_paths()

    collection = _get_collection(doc_url)
    # If doc changed OR collection empty -> rebuild
    existing_count = 0
    try:
        existing_count = collection.count()
    except Exception:
        existing_count = 0

    if (not refresh["changed"]) and existing_count > 0:
        return {"reindexed": False, "count": existing_count, "sha256": refresh["sha256"]}

    # Rebuild
    raw_text = open(paths["raw"], "r", encoding="utf-8", errors="ignore").read()
    chunks = _chunk_markdown(raw_text)

    # Clear collection (Chroma doesn't have "truncate" consistently across versions; easiest: delete+recreate)
    # We'll delete by ids if any exist.
    try:
        if existing_count > 0:
            # Pull all ids in batches
            all_ids = []
            offset = 0
            while True:
                batch = collection.get(limit=500, offset=offset, include=[])
                ids = batch.get("ids", [])
                if not ids:
                    break
                all_ids.extend(ids)
                offset += len(ids)
            if all_ids:
                collection.delete(ids=all_ids)
    except Exception:
        pass

    embedder = SentenceTransformer(os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2"))

    ids = []
    documents = []
    metadatas = []

    for i, ch in enumerate(chunks):
        ids.append(f"chunk_{i}")
        documents.append(ch["text"])
        metadatas.append({"title": ch["title"], "chunk_index": i})

    embeddings = embedder.encode(documents, normalize_embeddings=True).tolist()
    collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    return {"reindexed": True, "count": len(ids), "sha256": refresh["sha256"]}

@mcp.tool()
def streamlit_docs_search(query: str, k: int = 6, doc_url: str = DOC_URL_DEFAULT) -> Dict[str, Any]:
    """
    Search Streamlit documentation (llms-full.txt) using embeddings.
    Returns the top-k relevant chunks with titles and text excerpts.
    """
    info = _ensure_index(doc_url)
    collection = _get_collection(doc_url)

    embedder = SentenceTransformer(os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2"))
    q_emb = embedder.encode([query], normalize_embeddings=True).tolist()[0]

    res = collection.query(query_embeddings=[q_emb], n_results=max(1, min(k, 12)), include=["documents", "metadatas", "distances"])
    out = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({
            "title": meta.get("title"),
            "chunk_index": meta.get("chunk_index"),
            "distance": dist,
            "text": doc
        })

    return {"index": info, "results": out}

@mcp.tool()
def gemini_adk_docs_search(query: str, k: int = 6, doc_url: str = ADK_DOC_URL_DEFAULT):
    """
    Search Gemini ADK (adk-python) documentation (llms-full.txt) using embeddings.
    Returns the top-k relevant chunks with titles and text excerpts.
    """
    info = _ensure_index(doc_url)
    collection = _get_collection(doc_url)

    embedder = SentenceTransformer(os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2"))
    q_emb = embedder.encode([query], normalize_embeddings=True).tolist()[0]

    res = collection.query(
        query_embeddings=[q_emb],
        n_results=max(1, min(k, 12)),
        include=["documents", "metadatas", "distances"],
    )

    out = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({
            "title": meta.get("title"),
            "chunk_index": meta.get("chunk_index"),
            "distance": dist,
            "text": doc
        })

    return {"index": info, "results": out}


if __name__ == "__main__":
    # Run as STDIO server for Roo
    mcp.run(transport="stdio")
