import api from "./client";

export async function getChatHistory(videoId) {
  const response = await api.get(`/videos/${videoId}/chat/history`);
  return response.data;
}

export async function clearChatHistory(videoId) {
  await api.delete(`/videos/${videoId}/chat/history`);
}

export async function getVideoSummary(videoId) {
  const response = await api.get(`/videos/${videoId}/summary`);
  return response.data;
}

export async function getRelatedVideos(videoId) {
  const response = await api.get(`/videos/${videoId}/related`);
  return response.data;
}

export async function getSuggestedQuestions(videoId) {
  const response = await api.get(`/videos/${videoId}/suggested-questions`);
  return response.data;
}

/**
 * Streams a chat response. Calls onChunk(text) as tokens arrive,
 * and onMeta(referencedTimestamps) once, before streaming starts.
 */
export async function streamChatMessage(videoId, message, currentTimestamp, { onMeta, onChunk }) {
  const token = localStorage.getItem("token");
  const baseURL = api.defaults.baseURL;

  const response = await fetch(`${baseURL}/videos/${videoId}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message, current_timestamp: currentTimestamp }),
  });

  if (!response.ok || !response.body) {
    throw new Error("Stream request failed");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let metaHandled = false;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    if (!metaHandled) {
      const newlineIndex = buffer.indexOf("\n");
      if (newlineIndex === -1) continue;
      const metaLine = buffer.slice(0, newlineIndex);
      buffer = buffer.slice(newlineIndex + 1);
      metaHandled = true;
      if (metaLine.startsWith("META:")) {
        try {
          const meta = JSON.parse(metaLine.slice(5));
          onMeta?.(meta.referenced_timestamps || []);
        } catch {
          onMeta?.([]);
        }
      }
      if (buffer) {
        onChunk(buffer);
        buffer = "";
      }
      continue;
    }

    if (buffer) {
      onChunk(buffer);
      buffer = "";
    }
  }
}