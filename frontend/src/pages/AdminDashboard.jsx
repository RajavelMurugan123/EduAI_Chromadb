import { useEffect, useState } from "react";
import AdminLayout from "../components/AdminLayout";
import { adminListAllVideos, uploadVideo, deleteVideo, updateVideo, reuploadVideo } from "../api/videos";

export default function AdminDashboard() {
  const [videos, setVideos] = useState([]);
  const [form, setForm] = useState({ title: "", description: "", category: "", file: null });
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ title: "", category: "", description: "" });
  const [reuploadFileByVideo, setReuploadFileByVideo] = useState({});

  async function refresh() {
    setVideos(await adminListAllVideos());
  }

  useEffect(() => { refresh(); }, []);

  async function handleUpload(e) {
    e.preventDefault();
    setError("");
    if (!form.title || !form.file) {
      setError("Title and a video file are required.");
      return;
    }
    setUploading(true);
    try {
      await uploadVideo(form);
      setForm({ title: "", description: "", category: "", file: null });
      e.target.reset();
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id) {
    await deleteVideo(id);
    refresh();
  }

  function startEdit(v) {
    setEditingId(v.id);
    setEditForm({ title: v.title, category: v.category, description: v.description || "" });
  }

  function cancelEdit() {
    setEditingId(null);
  }

  async function saveEdit(id) {
    await updateVideo(id, editForm);
    setEditingId(null);
    refresh();
  }

  async function handleReupload(id) {
    const file = reuploadFileByVideo[id];
    if (!file) return;
    await reuploadVideo(id, file);
    setReuploadFileByVideo((prev) => ({ ...prev, [id]: null }));
    refresh();
  }

  const readyCount = videos.filter((v) => v.status === "ready").length;
  const processingCount = videos.filter((v) => v.status === "processing" || v.status === "uploading").length;
  const failedCount = videos.filter((v) => v.status === "failed").length;

  return (
    <AdminLayout>
      <div className="page">
        <div className="page-header">
          <div>
            <h1 className="page-title">Videos</h1>
            <p className="page-subtitle">Upload course content — any format, processed automatically.</p>
          </div>
        </div>

        <div className="stat-grid">
          <div className="stat-card">
            <p className="stat-label">Total videos</p>
            <p className="stat-value">{videos.length}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Ready</p>
            <p className="stat-value" style={{ color: "var(--color-success)" }}>{readyCount}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Processing</p>
            <p className="stat-value" style={{ color: "var(--color-warning)" }}>{processingCount}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Failed</p>
            <p className="stat-value" style={{ color: "var(--color-danger)" }}>{failedCount}</p>
          </div>
        </div>

        <div className="card card-pad" style={{ marginBottom: 24 }}>
          <p className="section-label" style={{ marginBottom: 16 }}>Upload a new video</p>
          <form onSubmit={handleUpload} className="form-row">
            <input className="input" placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <input className="input" placeholder="Category (optional — AI detects it if left blank)" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
            <input className="input" placeholder="Description (optional)" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <input type="file" accept="video/*" onChange={(e) => setForm({ ...form, file: e.target.files[0] })} />
            <button className="btn btn-primary" type="submit" disabled={uploading}>
              {uploading ? "Uploading..." : "+ Upload video"}
            </button>
          </form>
          {error && <p className="error-text" style={{ margin: 0 }}>{error}</p>}
        </div>

        <div className="card">
          {videos.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">▶</div>
              <h3>Upload your first video</h3>
              <p>Videos you upload appear here and on the learner Home page once processing finishes.</p>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr><th>Title</th><th>Category</th><th>Status</th><th></th></tr>
              </thead>
              <tbody>
                {videos.map((v) => (
                  editingId === v.id ? (
                    <tr key={v.id}>
                      <td colSpan={4} style={{ padding: 16 }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                          <div className="form-row" style={{ marginBottom: 0 }}>
                            <input className="input" placeholder="Title" value={editForm.title} onChange={(e) => setEditForm({ ...editForm, title: e.target.value })} />
                            <input className="input" placeholder="Category" value={editForm.category} onChange={(e) => setEditForm({ ...editForm, category: e.target.value })} />
                            <input className="input" placeholder="Description" value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} />
                          </div>
                          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                            <span style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>Replace video file:</span>
                            <input
                              type="file"
                              accept="video/*"
                              onChange={(e) => setReuploadFileByVideo((prev) => ({ ...prev, [v.id]: e.target.files[0] }))}
                            />
                            <button className="btn btn-sm" onClick={() => handleReupload(v.id)} disabled={!reuploadFileByVideo[v.id]}>
                              Replace &amp; reprocess
                            </button>
                          </div>
                          <div style={{ display: "flex", gap: 8 }}>
                            <button className="btn btn-primary btn-sm" onClick={() => saveEdit(v.id)}>Save changes</button>
                            <button className="btn btn-sm" onClick={cancelEdit}>Cancel</button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    <tr key={v.id}>
                      <td style={{ fontWeight: 600 }}>{v.title}</td>
                      <td>{v.category || "—"}</td>
                      <td><span className={`badge badge-${v.status}`}>{v.status}</span></td>
                      <td style={{ textAlign: "right", display: "flex", gap: 8, justifyContent: "flex-end" }}>
                        <button className="btn btn-sm" onClick={() => startEdit(v)}>Edit</button>
                        <button className="btn btn-danger btn-sm" onClick={() => handleDelete(v.id)}>Delete</button>
                      </td>
                    </tr>
                  )
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </AdminLayout>
  );
}