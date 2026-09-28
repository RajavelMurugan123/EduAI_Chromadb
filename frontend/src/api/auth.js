import api from "./client";

export async function login(email, password) {
  const response = await api.post("/auth/login", { email, password });
  const { access_token, role } = response.data;
  localStorage.setItem("token", access_token);
  localStorage.setItem("role", role);
  return { token: access_token, role };
}

export function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("role");
}

export async function getMyProfile() {
  const response = await api.get("/users/me");
  return response.data;
}

export async function listUsers() {
  const response = await api.get("/users");
  return response.data;
}

export async function createUser(payload) {
  const response = await api.post("/users", payload);
  return response.data;
}

export async function deleteUser(userId) {
  await api.delete(`/users/${userId}`);
}