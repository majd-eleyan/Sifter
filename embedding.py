"""تحويل النص لأرقام (vector من 384 رقم). الموديل بيتحمّل مرة وحدة بس."""
from functools import lru_cache

from config import EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL)


def embed_texts(texts):
    return get_model().encode(texts, normalize_embeddings=True).tolist()


def embed_one(text):
    return embed_texts([text])[0]


def to_vector(vec):
    """قائمة أرقام ← نص بصيغة pgvector:  [0.1,0.2,...]"""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
