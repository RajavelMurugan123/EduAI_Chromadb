import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { logout } from "../api/auth";

const NAV_ITEMS = [
  { path: "/admin", label: "Videos", icon: "▶" },
  { path: "/admin/users", label: "Users", icon: "◐" },
];

export default function AdminSidebar() {
  const location = useLocation();
  const { user, setUser } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    setUser(null);
    navigate("/login");
  }

  const initials = user?.name?.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="sidebar">
      <div className="sidebar-brand">
        <span className="navbar-brand-mark">E</span>
        <span>EduAI</span>
      </div>

      <div className="sidebar-section-label">Manage</div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`sidebar-link ${location.pathname === item.path ? "active" : ""}`}
          >
            <span className="sidebar-link-icon">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>

      <Link to="/" className="sidebar-link sidebar-link-muted" style={{ marginTop: "auto" }}>
        <span className="sidebar-link-icon">←</span>
        Back to learner view
      </Link>

      <div className="sidebar-footer">
        <div className="navbar-avatar" style={{ width: 34, height: 34 }}>{initials}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="sidebar-user-name">{user?.name}</div>
          <div className="sidebar-user-role">{user?.role}</div>
        </div>
        <button className="btn btn-sm" onClick={handleLogout} title="Log out">⏻</button>
      </div>
    </div>
  );
}