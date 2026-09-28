import api from "./client";

export async function globalSearch(query) {
  const response = await api.get("/search", { params: { q: query } });
  return response.data;
}

export async function videoSearch(query, videoId) {
  const response = await api.get("/search", { params: { q: query, video_id: videoId } });
  return response.data;
}