import { useEffect, useState } from "react";
import AdminLayout from "../components/AdminLayout";
import { listUsers, createUser, deleteUser } from "../api/auth";

export default function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "learner" });
  const [error, setError] = useState("");

  async function refresh() {
    setUsers(await listUsers());
  }

  useEffect(() => { refresh(); }, []);

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    if (!form.name || !form.email || !form.password) {
      setError("Fill in name, email, and password first.");
      return;
    }
    try {
      await createUser(form);
      setForm({ name: "", email: "", password: "", role: "learner" });
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't create that user.");
    }
  }

  async function handleDelete(id) {
    await deleteUser(id);
    refresh();
  }

  const adminCount = users.filter((u) => u.role === "admin").length;
  const instructorCount = users.filter((u) => u.role === "instructor").length;
  const learnerCount = users.filter((u) => u.role === "learner").length;

  return (
    <AdminLayout>
      <div className="page">
        <div className="page-header">
          <div>
            <h1 className="page-title">Users</h1>
            <p className="page-subtitle">Create and manage admin, instructor, and learner accounts.</p>
          </div>
        </div>

        <div className="stat-grid">
          <div className="stat-card">
            <p className="stat-label">Total users</p>
            <p className="stat-value">{users.length}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Admins</p>
            <p className="stat-value stat-accent">{adminCount}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Instructors</p>
            <p className="stat-value">{instructorCount}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Learners</p>
            <p className="stat-value">{learnerCount}</p>
          </div>
        </div>

        <div className="card card-pad" style={{ marginBottom: 24 }}>
          <p className="section-label" style={{ marginBottom: 16 }}>Create a user</p>
          <form onSubmit={handleCreate} className="form-row">
            <input className="input" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input className="input" placeholder="name@company.com" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            <input className="input" type="password" placeholder="Temporary password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <select className="input" style={{ maxWidth: 140 }} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="learner">Learner</option>
              <option value="instructor">Instructor</option>
              <option value="admin">Admin</option>
            </select>
            <button className="btn btn-primary" type="submit">Create user</button>
          </form>
          {error && <p className="error-text" style={{ margin: 0 }}>{error}</p>}
        </div>

        <div className="card">
          <table className="table">
            <thead>
              <tr><th>Name</th><th>Email</th><th>Role</th><th></th></tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 600 }}>{u.name}</td>
                  <td>{u.email}</td>
                  <td><span className={`badge badge-${u.role}`}>{u.role}</span></td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDelete(u.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AdminLayout>
  );
}