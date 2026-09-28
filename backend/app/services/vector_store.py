import os
import chromadb

_client = None
_collection = None

# Absolute path, anchored to this file's own location, so it's identical
# no matter which folder uvicorn or Celery happened to be launched from.
CHROMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "chroma_data")


def get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _client.get_or_create_collection(name="transcript_segments")
    return _collection


def add_segment(segment_id: str, video_id: str, embedding: list[float], text: str, start_time: float, end_time: float):
    collection = get_collection()
    collection.add(
        ids=[segment_id],
        embeddings=[embedding],
        documents=[text],
        metadatas=[{"video_id": video_id, "start_time": start_time, "end_time": end_time}],
    )


def query_segments(query_embedding: list[float], video_id: str | None = None, top_k: int = 10):
    collection = get_collection()
    where_filter = {"video_id": video_id} if video_id else None
    return collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where_filter,
    )


def delete_video_segments(video_id: str):
    collection = get_collection()
    collection.delete(where={"video_id": video_id})