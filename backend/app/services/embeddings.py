import json
from sentence_transformers import SentenceTransformer

_model = None


def get_embedding_model():
    global _model
    if _model is None:
        # Small, fast, good general-purpose embedding model. Runs on CPU fine.
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embedding_to_json(vector: list[float]) -> str:
    return json.dumps(vector)


def embedding_from_json(raw: str) -> list[float]:
    return json.loads(raw)