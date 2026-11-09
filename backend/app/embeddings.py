from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding

from .config import get_settings


@lru_cache
def _model() -> TextEmbedding:
    # Downloads the ONNX model (~130 MB) on first use, then runs locally on CPU.
    return TextEmbedding(model_name=get_settings().embedding_model)


def embed_documents(texts: list[str]) -> list[np.ndarray]:
    return list(_model().passage_embed(texts))


def embed_query(text: str) -> np.ndarray:
    # BGE models embed queries with an instruction prefix; query_embed handles that.
    return next(iter(_model().query_embed(text)))
