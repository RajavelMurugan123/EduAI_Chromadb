import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import HomePage from "./pages/HomePage";
import WatchPage from "./pages/WatchPage";
import QuizDashboardPage from "./pages/QuizDashboardPage";
import QuizPage from "./pages/QuizPage";
import AdminUsersPage from "./pages/AdminUsersPage";
import AdminDashboard from "./pages/AdminDashboard";
import "./styles.css";

function TopNavbar() {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return null;

  const initials = user.name?.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="navbar">
      <div className="navbar-left">
        <Link to="/" className="navbar-brand">
          <span className="navbar-brand-mark">E</span>
          EduAI
        </Link>
        <div className="navbar-links">
          <Link to="/" className={location.pathname === "/" ? "active" : ""}>Browse</Link>
          <Link to="/quizzes" className={location.pathname === "/quizzes" ? "active" : ""}>Quizzes</Link>
        </div>
      </div>
      <div className="navbar-avatar">{initials}</div>
    </div>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedRoute><><TopNavbar /><HomePage /></></ProtectedRoute>} />
      <Route path="/watch/:videoId" element={<ProtectedRoute><><TopNavbar /><WatchPage /></></ProtectedRoute>} />
      <Route path="/watch/:videoId/quiz" element={<ProtectedRoute><><TopNavbar /><QuizPage /></></ProtectedRoute>} />
      <Route path="/quizzes" element={<ProtectedRoute><><TopNavbar /><QuizDashboardPage /></></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute allowedRoles={["admin"]}><AdminDashboard /></ProtectedRoute>} />
      <Route path="/admin/users" element={<ProtectedRoute allowedRoles={["admin"]}><AdminUsersPage /></ProtectedRoute>} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}