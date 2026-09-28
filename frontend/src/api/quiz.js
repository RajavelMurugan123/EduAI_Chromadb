import api from "./client";

export async function getQuiz(videoId) {
  const response = await api.get(`/videos/${videoId}/quiz`);
  return response.data;
}

export async function submitQuiz(videoId, answers) {
  const response = await api.post(`/videos/${videoId}/quiz/submit`, { answers });
  return response.data;
}

export async function getQuizDashboard() {
  const response = await api.get("/videos/quizzes/dashboard");
  return response.data;
}