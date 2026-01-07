import os
import re
import json
import time
import hashlib
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

import requests
import chromadb
from sentence_transformers import SentenceTransformer

from mcp.server.fastmcp import FastMCP


# ----------------------------
# Config
# ----------------------------

BUNDLE_NAME = "python-genai-docs"
CACHE_DIR_NAME = ".cache"

SOURCES = [
    {
        "id": "codegen_instructions",
        "type": "md",
        "url": "https://raw.githubusercontent.com/googleapis/python-genai/refs/heads/main/codegen_instructions.md",
        "title": "python-genai: codegen_instructions.md",
    },
    {
        "id": "readme",
        "type": "md",
        "url": "https://raw.githubusercontent.com/googleapis/python-genai/refs/heads/main/README.md",
        "title": "python-genai: README.md",
    },
    {
        "id": "genai_html",
        "type": "html",
        "url": "https://raw.githubusercontent.com/googleapis/python-genai/refs/heads/main/docs/genai.html",
        "title": "python-genai: docs/genai.html",
    },
]

# Embedding model (local)
DEFAULT_EMBED_MODEL = os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2")

# Pandoc settings
PANDOC_FROM = "html"
PANDOC_TO = "gfm"
PANDOC_EXTRA_ARGS = ["--wrap=none"]  # keep long lines; easier chunking


mcp = FastMCP(
    "Google Gemini Python SDK Documentation RAG", 
    json_response=True,
    instructions="""
        Provides search over the official Gemini SDK for Python (python-genai) documentation.
        This server is for questions about the Python client library, SDK APIs, and usage examples.
        Do NOT use for generic generative AI concepts or other Google AI products.
    """    
    )

mcp = FastMCP()

# ----------------------------
# Utilities
# ----------------------------

def _base_dir() -> str:
    return os.path.dirname(__file__)

def _cache_dir() -> str:
    d = os.path.join(_base_dir(), CACHE_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d

def _paths() -> Dict[str, str]:
    base = _cache_dir()
    raw_dir = os.path.join(base, "raw")
    norm_dir = os.path.join(base, "normalized")
    chroma_dir = os.path.join(base, "chroma")

    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(norm_dir, exist_ok=True)
    os.makedirs(chroma_dir, exist_ok=True)

    return {
        "base": base,
        "raw_dir": raw_dir,
        "norm_dir": norm_dir,
        "chroma_dir": chroma_dir,
        "meta_json": os.path.join(base, "meta.json"),
    }

def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def _write_bytes(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)

def _fetch(url: str) -> bytes:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content

def _pandoc_available() -> bool:
    try:
        subprocess.run(["pandoc", "--version"], check=True, capture_output=True, text=True)
        return True
    except Exception:
        return False

def _convert_html_to_md_with_pandoc(html_bytes: bytes) -> str:
    """
    Convert HTML bytes to GitHub-flavored Markdown using pandoc.
    """
    if not _pandoc_available():
        raise RuntimeError("Pandoc not found on PATH. Install pandoc or adjust PATH.")

    proc = subprocess.run(
        ["pandoc", "-f", PANDOC_FROM, "-t", PANDOC_TO, *PANDOC_EXTRA_ARGS],
        input=html_bytes,
        capture_output=True,
        check=True,
    )
    md = proc.stdout.decode("utf-8", errors="ignore")
    return md

def _normalize_markdown(md: str) -> str:
    """
    Light cleanup:
    - normalize line endings
    - collapse excessive blank lines
    - trim trailing whitespace
    """
    md = md.replace("\r\n", "\n").replace("\r", "\n")
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{4,}", "\n\n\n", md)
    return md.strip() + "\n"

def _split_heading_blocks(text: str) -> List[str]:
    """
    Split on markdown headings (lines starting with #).
    Keeps headings with the content that follows.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Split before a heading line
    parts = re.split(r"\n(?=#{1,6}\s)", text)
    return [p.strip() for p in parts if p.strip()]

def _first_heading_title(block: str) -> str:
    first_line = block.split("\n", 1)[0].strip()
    m = re.match(r"^(#{1,6})\s+(.*)$", first_line)
    return (m.group(2).strip() if m else "Docs")

def _chunk_by_heading(text: str, max_chars: int = 5000) -> List[Dict[str, Any]]:
    """
    Chunk by headings, then pack adjacent blocks until max_chars is reached.
    Char-based chunking is a decent proxy; works well with docs.
    """
    blocks = _split_heading_blocks(text)
    chunks: List[Dict[str, Any]] = []

    buf = ""
    buf_title = ""

    def flush():
        nonlocal buf, buf_title
        if buf.strip():
            chunks.append({"title": buf_title or "Docs", "text": buf.strip()})
        buf = ""
        buf_title = ""

    for block in blocks:
        block_title = _first_heading_title(block)
        if not buf:
            buf_title = block_title

        # If adding the block would exceed max, flush and start a new chunk
        if len(buf) + len(block) + 2 > max_chars:
            flush()
            buf_title = block_title

        buf = (buf + "\n\n" + block).strip()

    flush()
    return chunks

def _bundle_key() -> str:
    # stable identifier for the bundle; change if you want to force a fresh collection name
    joined = "|".join([s["url"] for s in SOURCES])
    return hashlib.md5(joined.encode("utf-8")).hexdigest()

def _get_collection() -> chromadb.api.models.Collection.Collection:
    p = _paths()
    client = chromadb.PersistentClient(path=p["chroma_dir"])
    name = f"{BUNDLE_NAME}_{_bundle_key()}"
    return client.get_or_create_collection(name=name)

def _load_meta() -> Dict[str, Any]:
    meta_path = _paths()["meta_json"]
    if not os.path.exists(meta_path):
        return {"bundle": BUNDLE_NAME, "sources": {}, "last_indexed_at": None}
    try:
        return json.load(open(meta_path, "r", encoding="utf-8"))
    except Exception:
        return {"bundle": BUNDLE_NAME, "sources": {}, "last_indexed_at": None}

def _save_meta(meta: Dict[str, Any]) -> None:
    meta_path = _paths()["meta_json"]
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

def _source_raw_path(source_id: str, ext: str) -> str:
    p = _paths()
    return os.path.join(p["raw_dir"], f"{source_id}.{ext}")

def _source_norm_path(source_id: str) -> str:
    p = _paths()
    return os.path.join(p["norm_dir"], f"{source_id}.md")

def _clear_collection(collection) -> None:
    try:
        count = collection.count()
    except Exception:
        count = 0
    if count <= 0:
        return

    # Delete ids in batches
    offset = 0
    all_ids: List[str] = []
    while True:
        batch = collection.get(limit=500, offset=offset, include=[])
        ids = batch.get("ids", [])
        if not ids:
            break
        all_ids.extend(ids)
        offset += len(ids)

    if all_ids:
        collection.delete(ids=all_ids)


# ----------------------------
# Ingestion + Indexing
# ----------------------------

@dataclass
class NormalizedDoc:
    source_id: str
    source_title: str
    source_url: str
    text: str
    sha256: str  # of raw bytes


def _ingest_sources() -> Tuple[List[NormalizedDoc], Dict[str, Any]]:
    """
    Fetch all sources, cache raw, normalize to markdown, cache normalized.
    Returns (normalized_docs, meta_update_info).
    """
    p = _paths()
    meta = _load_meta()
    meta_sources = meta.get("sources", {}) or {}

    normalized_docs: List[NormalizedDoc] = []
    any_changed = False

    for s in SOURCES:
        raw_bytes = _fetch(s["url"])
        raw_sha = _sha256_bytes(raw_bytes)

        prev_sha = meta_sources.get(s["id"], {}).get("sha256")
        changed = (prev_sha != raw_sha)
        any_changed = any_changed or changed

        # cache raw
        raw_ext = "html" if s["type"] == "html" else "md"
        raw_path = _source_raw_path(s["id"], raw_ext)
        _write_bytes(raw_path, raw_bytes)

        # normalize
        if s["type"] == "md":
            md = raw_bytes.decode("utf-8", errors="ignore")
            md = _normalize_markdown(md)
        else:
            md = _convert_html_to_md_with_pandoc(raw_bytes)
            md = _normalize_markdown(md)

        norm_path = _source_norm_path(s["id"])
        _write_text(norm_path, md)

        normalized_docs.append(
            NormalizedDoc(
                source_id=s["id"],
                source_title=s["title"],
                source_url=s["url"],
                text=md,
                sha256=raw_sha,
            )
        )

        meta_sources[s["id"]] = {
            "url": s["url"],
            "sha256": raw_sha,
            "raw_path": raw_path,
            "normalized_path": norm_path,
            "type": s["type"],
            "title": s["title"],
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    meta["sources"] = meta_sources
    meta_update = {"any_changed": any_changed, "meta": meta}
    return normalized_docs, meta_update


def _ensure_index(force: bool = False) -> Dict[str, Any]:
    """
    Re-index if any source hash changed, or if force=True, or if collection empty.
    """
    docs, meta_update = _ingest_sources()
    meta = meta_update["meta"]
    any_changed = meta_update["any_changed"]

    collection = _get_collection()
    try:
        existing_count = collection.count()
    except Exception:
        existing_count = 0

    if not force and not any_changed and existing_count > 0:
        return {
            "reindexed": False,
            "chunk_count": existing_count,
            "last_indexed_at": meta.get("last_indexed_at"),
            "sources": meta.get("sources", {}),
        }

    # rebuild
    _clear_collection(collection)

    embedder = SentenceTransformer(DEFAULT_EMBED_MODEL)

    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    chunk_total = 0
    for d in docs:
        chunks = _chunk_by_heading(d.text, max_chars=5000)
        for i, ch in enumerate(chunks):
            chunk_id = f"{d.source_id}__chunk_{i}"
            ids.append(chunk_id)
            documents.append(ch["text"])
            metadatas.append({
                "source_id": d.source_id,
                "source_title": d.source_title,
                "source_url": d.source_url,
                "heading": ch["title"],
                "chunk_index": i,
            })
        chunk_total += len(chunks)

    # embed + add
    embeddings = embedder.encode(documents, normalize_embeddings=True).tolist()
    collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    meta["last_indexed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_meta(meta)

    return {
        "reindexed": True,
        "chunk_count": chunk_total,
        "last_indexed_at": meta["last_indexed_at"],
        "sources": meta.get("sources", {}),
    }


# ----------------------------
# MCP Tools
# ----------------------------

@mcp.tool()
def gemini_python_sdk_docs_status() -> Dict[str, Any]:
    """
    Return indexing status, source hashes, and chunk counts.
    """
    meta = _load_meta()
    collection = _get_collection()
    try:
        count = collection.count()
    except Exception:
        count = 0

    return {
        "bundle": BUNDLE_NAME,
        "chunk_count": count,
        "last_indexed_at": meta.get("last_indexed_at"),
        "sources": meta.get("sources", {}),
        "pandoc_available": _pandoc_available(),
        "embed_model": DEFAULT_EMBED_MODEL,
    }


@mcp.tool()
def gemini_python_sdk_docs_reindex(force: bool = False) -> Dict[str, Any]:
    """
    Force or refresh the index if sources changed.
    """
    return _ensure_index(force=force)


@mcp.tool()
def gemini_python_sdk_docs_search(query: str, k: int = 6, sources: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Search the official Gemini SDK for Python documentation (python-genai library).

    Use this tool ONLY for:
    - Gemini SDK / python-genai client library questions
    - Code usage, APIs, classes, functions, examples
    - NOT for generic genAI concepts, Vertex AI, or non-SDK Gemini products

    Optionally filter by sources (list of source_id values).
    """
    index_info = _ensure_index(force=False)
    collection = _get_collection()

    embedder = SentenceTransformer(DEFAULT_EMBED_MODEL)
    q_emb = embedder.encode([query], normalize_embeddings=True).tolist()[0]

    # Pull more than k first if filtering, then filter down.
    n = max(1, min(20, max(k, 6)))

    res = collection.query(
        query_embeddings=[q_emb],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )

    results = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        if sources and meta.get("source_id") not in set(sources):
            continue
        results.append({
            "source_id": meta.get("source_id"),
            "source_title": meta.get("source_title"),
            "source_url": meta.get("source_url"),
            "heading": meta.get("heading"),
            "chunk_index": meta.get("chunk_index"),
            "distance": dist,
            "text": doc,
        })
        if len(results) >= k:
            break

    return {"index": index_info, "results": results}


# ----------------------------
# Entrypoint (STDIO for Roo)
# ----------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
