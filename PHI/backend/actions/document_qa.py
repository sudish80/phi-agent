"""Document Q&A (RAG) module for J.A.R.V.I.S.

Ask questions against uploaded PDFs/DOCs using vector search + LLM.
"""

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Optional, List, Dict

from backend.shared.config import settings

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent / "static" / "documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


async def ingest_document(file_path: str) -> str:
    """Ingest a document (PDF, DOCX, TXT) into vector memory for Q&A."""
    full = os.path.abspath(os.path.expanduser(file_path))
    if not os.path.exists(full):
        return f"File not found: {full}"

    ext = Path(full).suffix.lower()
    text = ""

    loop = asyncio.get_event_loop()

    def _extract():
        nonlocal text
        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(full)
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
            except ImportError:
                return "PDF requires PyMuPDF"
        elif ext == ".docx":
            try:
                import docx
                d = docx.Document(full)
                text = "\n".join(p.text for p in d.paragraphs)
            except ImportError:
                return "DOCX requires python-docx"
        elif ext == ".txt":
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        else:
            return f"Unsupported format: {ext}"
        return None

    err = await loop.run_in_executor(None, _extract)
    if err:
        return err
    if not text.strip():
        return "No text could be extracted from the document."

    chunks = _chunk_text(text)
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return "Document Q&A requires sentence-transformers"

    loop2 = asyncio.get_event_loop()

    def _embed_and_store():
        model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = model.encode(chunks, show_progress_bar=False)

        try:
            import chromadb
            client = chromadb.Client()
            collection = client.get_or_create_collection(
                f"doc_qa_{uuid.uuid4().hex[:8]}"
            )
            ids = [f"chunk_{i}" for i in range(len(chunks))]
            collection.add(
                documents=chunks,
                embeddings=embeddings.tolist(),
                ids=ids,
            )
            return collection.name
        except ImportError:
            return "Document Q&A requires chromadb"

    col_name = await loop2.run_in_executor(None, _embed_and_store)
    return (f"Document ingested: {os.path.basename(full)} "
            f"({len(chunks)} chunks, {len(text)} chars) "
            f"Collection: {col_name}")


async def ask_document(collection_name: str, question: str) -> str:
    """Ask a question against an ingested document collection."""
    try:
        from sentence_transformers import SentenceTransformer
        import chromadb
    except ImportError:
        return "Document Q&A requires sentence-transformers and chromadb"

    loop = asyncio.get_event_loop()

    def _query():
        client = chromadb.Client()
        try:
            collection = client.get_collection(collection_name)
        except ValueError:
            return f"Collection '{collection_name}' not found."

        model = SentenceTransformer("all-MiniLM-L6-v2")
        q_embed = model.encode([question]).tolist()
        results = collection.query(query_embeddings=q_embed, n_results=3)
        contexts = results["documents"][0] if results["documents"] else []
        if not contexts:
            return "No relevant content found."
        return "\n\n".join(f"[{i+1}] {c[:2000]}" for i, c in enumerate(contexts))

    context = await loop.run_in_executor(None, _query)
    if context.startswith("Collection") or context.startswith("No relevant"):
        return context

    try:
        from backend.shared.llm_client import LLMClient, LLMConfig, LLMProvider
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4",
            api_key=settings.openai_api_key,
        )
        client = LLMClient.create(config)
        response = await client.generate([
            {"role": "system",
             "content": "Answer based on the provided context. If unsure, say so."},
            {"role": "user",
             "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ])
        return (f"**Answer:**\n{response.content}\n\n"
                f"**Sources:**\n{context[:1000]}")
    except Exception as e:
        return f"Q&A error: {e}"


async def list_collections() -> str:
    """List all document Q&A collections."""
    try:
        import chromadb
    except ImportError:
        return "chromadb not installed"

    loop = asyncio.get_event_loop()

    def _list():
        client = chromadb.Client()
        cols = client.list_collections()
        if not cols:
            return "No document collections. Use ingest_document first."
        lines = [f"**{len(cols)} Collection(s)**"]
        for c in cols:
            lines.append(f"  - {c.name}")
        return "\n".join(lines)

    return await loop.run_in_executor(None, _list)


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks for embedding."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks or [text]
