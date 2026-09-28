import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getQuiz, submitQuiz } from "../api/quiz";
import api from "../api/client";

export default function QuizPage() {
  const { videoId } = useParams();
  const navigate = useNavigate();

  const [video, setVideo] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get(`/videos/${videoId}`).then((res) => setVideo(res.data));
  }, [videoId]);

  useEffect(() => {
    getQuiz(videoId)
      .then(setQuestions)
      .catch((err) => setError(err.response?.data?.detail || "Couldn't load quiz."))
      .finally(() => setLoading(false));
  }, [videoId]);

  function selectAnswer(questionId, optionIndex) {
    setAnswers((prev) => ({ ...prev, [questionId]: optionIndex }));
  }

  function goNext() {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      handleSubmit();
    }
  }

  async function handleSubmit() {
    setSubmitting(true);
    try {
      const data = await submitQuiz(videoId, answers);
      setResult(data);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="page">Loading quiz...</div>;
  if (error) return <div className="page"><p className="error-text">{error}</p></div>;
  if (questions.length === 0) return <div className="page">No quiz available for this video yet.</div>;

  if (result) {
    return (
      <div className="page" style={{ maxWidth: 560 }}>
        <div className="card card-pad" style={{ textAlign: "center" }}>
          <p className="section-label">Quiz complete</p>
          <h2 style={{ fontSize: 32, margin: "8px 0" }}>{result.score} / {result.total}</h2>
          <p style={{ color: "var(--color-text-secondary)", marginBottom: 20 }}>
            {result.score === result.total ? "Perfect score!" : "Nice work — keep going."}
          </p>
          <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
            <button className="btn" onClick={() => navigate("/quizzes")}>Back to quizzes</button>
            <button className="btn btn-primary" onClick={() => navigate(`/watch/${videoId}`)}>Watch video</button>
          </div>
        </div>
      </div>
    );
  }

  const q = questions[currentIndex];
  const selected = answers[q.id];

  return (
    <div className="page" style={{ maxWidth: 560 }}>
      <button className="btn" onClick={() => navigate(-1)} style={{ marginBottom: 16 }}>&larr; Back</button>

      <div className="card card-pad">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-primary)" }}>{video?.title}</span>
          <span style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>Question {currentIndex + 1} of {questions.length}</span>
        </div>

        <div style={{ display: "flex", gap: 3, marginBottom: 20 }}>
          {questions.map((_, i) => (
            <div key={i} style={{ flex: 1, height: 4, borderRadius: 2, background: i <= currentIndex ? "var(--color-success)" : "var(--color-border)" }} />
          ))}
        </div>

        <div style={{ fontSize: 16, marginBottom: 16 }}>{q.question}</div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
          {q.options.map((opt, i) => (
            <button
              key={i}
              onClick={() => selectAnswer(q.id, i)}
              style={{
                textAlign: "left",
                padding: "12px 14px",
                borderRadius: 8,
                border: selected === i ? "1.5px solid var(--color-primary)" : "1px solid var(--color-border)",
                background: selected === i ? "var(--color-primary-light)" : "var(--color-surface)",
                color: selected === i ? "var(--color-primary)" : "var(--color-text)",
                fontSize: 14,
                fontWeight: selected === i ? 600 : 400,
                cursor: "pointer",
              }}
            >
              {opt}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          {q.timestamp != null ? (
            <span
              style={{ fontSize: 13, color: "var(--color-text-muted)", cursor: "pointer" }}
              onClick={() => navigate(`/watch/${videoId}?t=${q.timestamp}`)}
            >
              Jump to {Math.floor(q.timestamp / 60)}:{String(Math.floor(q.timestamp % 60)).padStart(2, "0")} in video ↗
            </span>
          ) : <span />}
          <button className="btn btn-primary" onClick={goNext} disabled={selected === undefined || submitting}>
            {currentIndex < questions.length - 1 ? "Next question" : (submitting ? "Submitting..." : "Finish quiz")}
          </button>
        </div>
      </div>
    </div>
  );
}