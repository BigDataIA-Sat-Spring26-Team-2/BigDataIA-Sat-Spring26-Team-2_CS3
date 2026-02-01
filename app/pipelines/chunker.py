from __future__ import annotations

from dataclasses import dataclass
from typing import List
import hashlib


@dataclass
class TextChunk:
    chunk_index: int
    text: str
    content_hash: str
    word_count: int


def chunk_text(text: str, chunk_size_words: int = 350, overlap_words: int = 50) -> List[TextChunk]:
    words = text.split()
    if not words:
        return []

    chunks: List[TextChunk] = []
    start = 0
    idx = 0

    while start < len(words):
        end = min(start + chunk_size_words, len(words))
        chunk_words = words[start:end]
        chunk_str = " ".join(chunk_words)

        h = hashlib.sha256(chunk_str.encode("utf-8")).hexdigest()

        chunks.append(
            TextChunk(
                chunk_index=idx,
                text=chunk_str,
                content_hash=h,
                word_count=len(chunk_words),
            )
        )

        idx += 1
        start = end - overlap_words
        if start < 0:
            start = 0
        if end == len(words):
            break

    return chunks
