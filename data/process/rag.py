"""Nexova sales knowledge base: chunking, embedding and indexing (Milestone 7).

Two of the four RAG entry points live here:

- ``setup()``  reads docs/company-knowledge-base/, splits each document into semantic
  chunks and upserts them into the Qdrant collection ``nexova_knowledge``.
- ``embed()``  turns one text into a vector with the dedicated embeddings model. The same
  function embeds chunks here and the SDR's question in data/pipelines/rag.py.

Run from the repo root:  uv run python -m data.process.rag
"""
from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(os.environ.get("RAG_REPO_ROOT", Path(__file__).resolve().parents[2]))
load_dotenv(REPO_ROOT / ".env")

# --- Values fixed by company-BRIEFING.md (Milestone 7) ----------------------------------
COMPANY = "nexova"
COLLECTION = "nexova_knowledge"
KNOWLEDGE_BASE_DIR = REPO_ROOT / "docs" / "company-knowledge-base"
SOURCE_FILES = {
    "nexova-service-lines.en.md": "service-lines",
    "nexova-pricing-model.en.md": "pricing-model",
    "nexova-hiring-process-sla.en.md": "hiring-process-sla",
    "nexova-objection-handling.en.md": "objection-handling",
}

# --- Chunking limit (characters). See docs/rag/rag-design.md for why. -------------------
MAX_CHUNK_CHARS = 1400   # a unit above this is split between whole lines, never mid-line

# Deterministic point ids: same document + section + chunk_index -> same id on every run.
_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://nexova.example/knowledge")


@dataclass(frozen=True)
class Chunk:
    source_document: str
    section: str
    chunk_index: int
    text: str
    language: str = "en"

    @property
    def point_id(self) -> str:
        key = f"{COMPANY}|{self.source_document}|{self.section}|{self.chunk_index}"
        return str(uuid.uuid5(_ID_NAMESPACE, key))

    @property
    def embedding_text(self) -> str:
        """What gets embedded: the section path gives short chunks their topic back."""
        return f"{self.source_document.replace('-', ' ')}: {self.section}\n\n{self.text}"

    def payload(self) -> dict:
        return {
            "company": COMPANY,
            "source_document": self.source_document,
            "section": self.section,
            "language": self.language,
            "chunk_index": self.chunk_index,
            "text": self.text,
        }


# ======================================================================================
# Clients (configured from .env; see .env.example "RAG knowledge base")
# ======================================================================================
@lru_cache(maxsize=1)
def get_qdrant_client():
    from qdrant_client import QdrantClient

    url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    return QdrantClient(url=url, api_key=os.environ.get("QDRANT_API_KEY") or None, timeout=30)


@lru_cache(maxsize=1)
def _embeddings_client():
    from openai import OpenAI

    return OpenAI(
        base_url=os.environ.get("RAG_EMBED_BASE_URL") or os.environ["RAG_BASE_URL"],
        api_key=os.environ.get("RAG_EMBED_API_KEY") or os.environ["RAG_API_KEY"],
    )


def embedding_model() -> str:
    model = os.environ.get("RAG_EMBED_MODEL")
    if not model:
        raise RuntimeError("Set RAG_EMBED_MODEL in .env (the embeddings model id).")
    if model == os.environ.get("RAG_GEN_MODEL"):
        raise RuntimeError("RAG_EMBED_MODEL must be a dedicated embeddings model, not the generation model.")
    return model


# ======================================================================================
# embed()
# ======================================================================================
def _normalise(text: str) -> str:
    """Collapse whitespace so index-time and query-time text are embedded the same way."""
    return re.sub(r"\s+", " ", text).strip()


def embed(text: str) -> list[float]:
    """Vector for one text, from the dedicated embeddings model (never the generation model)."""
    response = _embeddings_client().embeddings.create(model=embedding_model(), input=_normalise(text))
    return list(response.data[0].embedding)


# ======================================================================================
# Chunking
# ======================================================================================
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def _blocks(lines: list[str]) -> list[str]:
    """Group lines into blocks separated by blank lines. A table, a list or a paragraph is
    one block, so splitting between blocks never cuts a rule or a condition in half."""
    blocks, current = [], []
    for line in lines:
        if line.strip():
            current.append(line.rstrip())
        elif current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def split_markdown(markdown: str) -> tuple[str, list[tuple[str, list[str]]]]:
    """Return (document title, [(section path, body lines)]) split at ## and ### headings.

    The section path is "H2" or "H2 › H3". Text before the first ## is the "Overview".
    Headings inside fenced code blocks are ignored.
    """
    title, h2, h3 = "", None, None
    sections: list[tuple[str, list[str]]] = []
    body: list[str] = []
    in_fence = False

    def flush():
        if any(line.strip() for line in body):
            path = h2 or "Overview"
            if h3:
                path = f"{path} › {h3}"
            sections.append((path, list(body)))
        body.clear()

    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else _HEADING.match(line)
        if not match:
            body.append(line)
            continue
        level, text = len(match.group(1)), match.group(2).strip()
        if level == 1:
            flush()
            title = title or text
        elif level == 2:
            flush()
            h2, h3 = text, None
        elif level == 3:
            flush()
            h3 = text
        else:  # #### and deeper stay inside their section, as bold lines
            body.append(f"**{text}**")
    flush()
    return title, sections


_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.*)")
_QUOTE = re.compile(r'^\s*["“](.+?)["”]\s*$')


def _unit_label(block: str) -> str | None:
    """Name of a semantic unit from its first line, or None if it has no label:
    '1. Executive headhunting: ...' -> 'Executive headhunting'; 'Corporate training:' ->
    'Corporate training'; a quoted objection line -> the objection itself."""
    first = block.splitlines()[0].strip()
    quote = _QUOTE.match(first)
    if quote:
        return quote.group(1).strip()
    numbered = _NUMBERED.match(first)
    if numbered:
        first = numbered.group(1)
    if ":" in first:
        label = first.split(":", 1)[0].strip()
        if 0 < len(label) <= 80 and (numbered or first.rstrip().endswith(":")):
            return label
    return None


def _split_long(text: str) -> list[str]:
    """A unit longer than MAX_CHUNK_CHARS is split between whole lines (list items stay whole)."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    pieces, current = [], ""
    for line in text.splitlines():
        starts_item = re.match(r"^\s*([-*]|\d+[.)])\s", line) or not current
        if current and starts_item and len(current) + len(line) > MAX_CHUNK_CHARS:
            pieces.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    return pieces + [current] if current else pieces


def chunk_document(markdown: str, source_document: str, language: str = "en") -> list[Chunk]:
    """Semantic chunks for one document.

    1. Split at ## / ### headings (text before the first ## belongs to the # title).
    2. Inside each section, every blank-line-separated block is one semantic unit: a
       numbered service line, a labelled pricing list, an objection with its response,
       a policy paragraph. Units are never cut, so no rule loses its condition.
    3. A lead-in line ending in ':' ("Committed delivery times by search type:") is
       joined to the block it introduces.
    4. The unit's own label (service line, pricing block, objection) becomes the section
       name; unlabelled paragraphs keep the heading's name. chunk_index counts within it.
    """
    title, sections = split_markdown(markdown)
    chunks: list[Chunk] = []
    counters: dict[str, int] = {}
    for path, lines in sections:
        base = title if path == "Overview" and title else path
        units: list[tuple[str, str]] = []  # (lead-in, block)
        lead_in = ""
        for block in _blocks(lines):
            if block.rstrip().endswith(":") and "\n" not in block.strip():
                lead_in = f"{lead_in}\n{block}" if lead_in else block
                continue
            units.append((lead_in, block))
            lead_in = ""
        if lead_in:
            units.append(("", lead_in))

        for lead, block in units:
            unit = f"{lead}\n{block}" if lead else block
            # The block's own label wins ("1. Executive ... headhunting:"); a lead-in only
            # names an unlabelled block ("Committed delivery times by search type:" + list).
            label = _unit_label(block) or (_unit_label(lead) if lead else None)
            section = f"{base} › {label}" if label and label != base else base
            for piece in _split_long(unit):
                index = counters.get(section, 0)
                counters[section] = index + 1
                chunks.append(Chunk(source_document, section, index, piece, language))
    return chunks


def load_chunks(directory: Path = KNOWLEDGE_BASE_DIR) -> list[Chunk]:
    """Chunks for every BRIEFING source document. Fails loudly if one is missing."""
    missing = [name for name in SOURCE_FILES if not (directory / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing source documents in {directory}: {missing}. Copy them from "
            "00-general-contexts/nexova/ (see company-BRIEFING.md, section 2).")
    chunks: list[Chunk] = []
    for name, slug in SOURCE_FILES.items():
        language = name.split(".")[-2] if name.count(".") >= 2 else "en"
        chunks.extend(chunk_document((directory / name).read_text(encoding="utf-8"), slug, language))
    return chunks


# ======================================================================================
# setup()
# ======================================================================================
def setup(directory: Path = KNOWLEDGE_BASE_DIR) -> dict:
    """Index the knowledge base into Qdrant. Idempotent: deterministic point ids mean a
    re-run overwrites the same points, and points from sections that no longer exist are
    deleted, so the collection always mirrors the documents exactly."""
    from qdrant_client import models

    client = get_qdrant_client()
    chunks = load_chunks(directory)
    vectors = [embed(c.embedding_text) for c in chunks]
    dim = len(vectors[0])

    if client.collection_exists(COLLECTION):
        existing_dim = client.get_collection(COLLECTION).config.params.vectors.size
        if existing_dim != dim:  # embeddings model changed: old vectors are meaningless
            client.delete_collection(COLLECTION)
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            COLLECTION, vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE))
        for field in ("company", "source_document"):
            client.create_payload_index(COLLECTION, field, models.PayloadSchemaType.KEYWORD)

    client.upsert(COLLECTION, points=[
        models.PointStruct(id=c.point_id, vector=v, payload=c.payload()) for c, v in zip(chunks, vectors)
    ], wait=True)

    keep = {c.point_id for c in chunks}
    stale, offset = [], None
    while True:
        points, offset = client.scroll(COLLECTION, limit=256, offset=offset, with_payload=False)
        stale += [p.id for p in points if str(p.id) not in keep]
        if offset is None:
            break
    if stale:
        client.delete(COLLECTION, points_selector=models.PointIdsList(points=stale), wait=True)

    per_document: dict[str, int] = {}
    for c in chunks:
        per_document[c.source_document] = per_document.get(c.source_document, 0) + 1
    return {
        "collection": COLLECTION,
        "points": client.count(COLLECTION, exact=True).count,
        "chunks_per_document": per_document,
        "vector_size": dim,
        "embedding_model": embedding_model(),
        "stale_points_deleted": len(stale),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(setup(), indent=2))
