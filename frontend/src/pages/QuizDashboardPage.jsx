import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getQuizDashboard } from "../api/quiz";

function ringColor(score, total) {
  if (score == null) return "var(--color-border)";
  const pct = score / total;
  if (pct === 1) return "#d85a30";
  if (pct >= 0.6) return "var(--color-success)";
  return "var(--color-primary)";
}

function ProgressRing({ score, total }) {
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const pct = score != null && total ? score / total : 0;
  const offset = circumference * (1 - pct);
  const color = ringColor(score, total);

  return (
    <svg width="64" height="64" viewBox="0 0 64 64">
      <circle cx="32" cy="32" r={radius} fill="none" stroke="var(--color-border)" strokeWidth="6" />
      {score != null && (
        <circle
          cx="32" cy="32" r={radius} fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          transform="rotate(-90 32 32)"
        />
      )}
      <text x="32" y="37" textAnchor="middle" fontSize="15" fontWeight="700" fill={score != null ? "var(--color-text)" : "var(--color-text-muted)"}>
        {score != null ? `${score}/${total}` : "--"}
      </text>
    </svg>
  );
}

export default function QuizDashboardPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    getQuizDashboard().then(setItems).finally(() => setLoading(false));
  }, []);

  function statusLabel(item) {
    if (item.best_score == null) return "Not attempted";
    if (item.best_score === item.total_questions) return "Perfect score";
    return "Best score";
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Quizzes</h1>
          <p className="page-subtitle">Test what you've learned from each video.</p>
        </div>
      </div>

      {loading && <p>Loading...</p>}

      {!loading && items.length === 0 && (
        <div className="empty-state">
          <h3>No quizzes yet</h3>
          <p>Quizzes are generated automatically once videos are available.</p>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 14 }}>
        {items.map((item) => (
          <div
            key={item.video_id}
            className="card card-pad"
            style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, cursor: "pointer" }}
            onClick={() => navigate(`/watch/${item.video_id}/quiz`)}
          >
            <ProgressRing score={item.best_score} total={item.total_questions} />
            <div style={{ fontSize: 13, fontWeight: 600, textAlign: "center" }}>{item.title}</div>
            <div style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>{statusLabel(item)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}