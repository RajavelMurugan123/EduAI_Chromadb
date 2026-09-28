import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { videoSearch } from "../api/search";
import { getVideoChapters } from "../api/videos";
import {
  streamChatMessage,
  clearChatHistory,
  getVideoSummary,
  getRelatedVideos,
  getSuggestedQuestions,
} from "../api/chat";
import api from "../api/client";

const STATIC_CHIPS = [
  { label: "Summarise the video", action: "summary" },
  { label: "Recommend related content", action: "related" },
];

export default function WatchPage() {
  const { videoId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const videoRef = useRef(null);
  const chatEndRef = useRef(null);

  const [video, setVideo] = useState(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);

  const [chapters, setChapters] = useState([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [chaptersExpanded, setChaptersExpanded] = useState(true);

  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [dynamicChips, setDynamicChips] = useState([]);

  useEffect(() => { api.get(`/videos/${videoId}`).then((res) => setVideo(res.data)); }, [videoId]);

  useEffect(() => {
    const t = searchParams.get("t");
    if (t && videoRef.current) videoRef.current.currentTime = parseFloat(t);
  }, [video, searchParams]);

  useEffect(() => {
    setChatMessages([]);
    setHistoryLoaded(true);
  }, [videoId]);

  useEffect(() => {
    if (!videoId) return;
    getSuggestedQuestions(videoId)
      .then((data) => setDynamicChips((data.questions || []).map((q) => ({ label: q, action: "chat", message: q }))))
      .catch(() => setDynamicChips([]));
  }, [videoId]);

  useEffect(() => {
    if (!videoId) return;
    getVideoChapters(videoId).then(setChapters).catch(() => setChapters([]));
  }, [videoId]);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chatMessages]);

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setSearched(true);
    try {
      setResults(await videoSearch(query, videoId));
    } finally {
      setSearching(false);
    }
  }

  function jumpTo(seconds) {
    if (videoRef.current) { videoRef.current.currentTime = seconds; videoRef.current.play(); }
  }

  function formatTime(s) { return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`; }

  async function sendQuestion(message) {
    setChatMessages((prev) => [...prev, { role: "user", text: message }]);
    setChatLoading(true);
    setChatMessages((prev) => [...prev, { role: "assistant", text: "", streaming: true, timestamps: [] }]);

    try {
      const currentTime = videoRef.current?.currentTime || 0;
      await streamChatMessage(videoId, message, currentTime, {
        onMeta: (timestamps) => {
          setChatMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = { ...next[next.length - 1], timestamps };
            return next;
          });
        },
        onChunk: (chunk) => {
          setChatMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, text: last.text + chunk };
            return next;
          });
        },
      });
      setChatMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { ...next[next.length - 1], streaming: false };
        return next;
      });
    } catch {
      setChatMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { role: "assistant", text: "Sorry, I couldn't answer that. Try again.", error: true };
        return next;
      });
    } finally {
      setChatLoading(false);
    }
  }

  async function handleChip(chip) {
    if (chip.action === "chat") { await sendQuestion(chip.message); return; }
    setChatMessages((prev) => [...prev, { role: "user", text: chip.label }]);
    setChatLoading(true);
    try {
      if (chip.action === "summary") {
        const data = await getVideoSummary(videoId);
        setChatMessages((prev) => [...prev, { role: "assistant", text: data.summary }]);
      } else if (chip.action === "related") {
        const data = await getRelatedVideos(videoId);
        setChatMessages((prev) => [...prev, data.length === 0
          ? { role: "assistant", text: "No related videos found yet." }
          : { role: "assistant", text: "Here's what's related:", relatedVideos: data }
        ]);
      }
    } catch {
      setChatMessages((prev) => [...prev, { role: "assistant", text: "Something went wrong.", error: true }]);
    } finally { setChatLoading(false); }
  }

  async function handleChatSend(e) {
    e.preventDefault();
    const message = chatInput.trim();
    if (!message) return;
    setChatInput("");

    const normalized = message.toLowerCase();

    if (normalized.includes("summar")) {
      await handleChip({ label: message, action: "summary" });
    } else if (normalized.includes("related") || normalized.includes("recommend")) {
      await handleChip({ label: message, action: "related" });
    } else {
      await sendQuestion(message);
    }
  }

  async function handleClearChat() {
    await clearChatHistory(videoId);
    setChatMessages([]);
  }

  if (!video) return <div className="page">Loading...</div>;

  const allChips = [...STATIC_CHIPS, ...dynamicChips];
  const maxScore = results.length ? Math.max(...results.map((r) => r.score)) : 1;
  const activeChapterIndex = chapters.reduce((activeIdx, ch, i) => (ch.start_time <= currentTime ? i : activeIdx), -1);

  return (
    <div className="page">
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button className="btn" onClick={() => navigate("/")}>&larr; Back to browse</button>
        <button className="btn btn-primary" onClick={() => navigate(`/watch/${videoId}/quiz`)}>Take quiz</button>
      </div>

      <div className="watch-layout">
        <div>
          <video
            ref={videoRef}
            src={`http://localhost:8000${video.file_url}`}
            controls
            className="video-player"
            onTimeUpdate={(e) => setCurrentTime(e.target.currentTime)}
          />
          <h2 style={{ margin: "16px 0 2px" }}>{video.title}</h2>
          <p style={{ color: "var(--color-text-secondary)", margin: "0 0 16px" }}>{video.category}</p>

          <form onSubmit={handleSearch} className="search-bar" style={{ marginBottom: 4 }}>
            <input className="input" placeholder="Search this video, e.g. for loop" value={query} onChange={(e) => setQuery(e.target.value)} />
            <button className="btn btn-primary" type="submit" disabled={searching}>{searching ? "Searching..." : "Search"}</button>
          </form>

          {searched && !searching && (
            <div className="search-results-list" style={{ marginBottom: 20 }}>
              {results.length === 0 ? (
                <div className="search-results-empty">No relevant moments found for "{query}".</div>
              ) : (
                results.map((r, i) => (
                  <div key={i} className="search-result-card" onClick={() => jumpTo(r.start_time)}>
                    <div className="search-result-time">{formatTime(r.start_time)}</div>
                    <div className="search-result-text">"{r.text}"</div>
                    <div className="search-result-score" title={`Relevance: ${Math.round(r.score * 100)}%`}>
                      <div className="search-result-score-fill" style={{ width: `${(r.score / maxScore) * 100}%` }} />
                    </div>
                    <div className="search-result-jump">Jump →</div>
                  </div>
                ))
              )}
            </div>
          )}

          {chapters.length > 0 && (
            <div className="card card-pad chapters-card">
              <div className="chapters-header" onClick={() => setChaptersExpanded(!chaptersExpanded)}>
                <span className="chapters-header-title">Key moments</span>
                <svg className={`chapters-chevron ${chaptersExpanded ? "" : "collapsed"}`} width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>

              {chaptersExpanded && (
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  {chapters.map((ch, i) => (
                    <div
                      key={ch.id}
                      className={`chapter-row-yt ${i === activeChapterIndex ? "active" : ""}`}
                      onClick={() => jumpTo(ch.start_time)}
                    >
                      <div className="chapter-thumb">
                        <span className="chapter-thumb-time">{formatTime(ch.start_time)}</span>
                      </div>
                      <div className="chapter-info">
                        <div className="chapter-info-time">{formatTime(ch.start_time)}</div>
                        <div className="chapter-info-title">{ch.title}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="card card-pad chat-panel">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <h3 style={{ margin: 0, fontSize: 15 }}>Ask about this video</h3>
            {chatMessages.length > 0 && (
              <button className="btn btn-sm" onClick={handleClearChat}>Clear chat</button>
            )}
          </div>

          <div className="chat-messages">
            {historyLoaded && chatMessages.length === 0 && (
              <div>
                <p style={{ color: "var(--color-text-secondary)", fontSize: 13 }}>
                  Curious about what you're watching? Ask below, or try one of these:
                </p>
                {allChips.map((chip, i) => (
                  <button key={i} className="chip" onClick={() => handleChip(chip)}>{chip.label}</button>
                ))}
              </div>
            )}

            {chatMessages.map((m, i) => (
              <div key={i} className={`chat-bubble ${m.role}${m.error ? " error" : ""}`}>
                {m.role === "assistant" ? (
                  <>
                    <ReactMarkdown>{m.text || " "}</ReactMarkdown>
                    {m.streaming && <span className="typing-cursor" />}
                  </>
                ) : m.text}

                {!m.streaming && m.timestamps && m.timestamps.length > 0 && (
                  <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {m.timestamps.map((t, idx) => (
                      <span key={idx} className="timestamp-chip" onClick={() => jumpTo(t)}>{formatTime(t)}</span>
                    ))}
                  </div>
                )}

                {m.relatedVideos && (
                  <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
                    {m.relatedVideos.map((rv) => (
                      <div key={rv.video_id} className="card card-pad" style={{ padding: 10, cursor: "pointer" }} onClick={() => navigate(`/watch/${rv.video_id}`)}>
                        <strong style={{ fontSize: 13 }}>{rv.title}</strong>
                        <p style={{ margin: 0, fontSize: 12, color: "var(--color-text-secondary)" }}>{rv.category}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          <form onSubmit={handleChatSend} className="search-bar" style={{ marginTop: 12 }}>
            <input className="input" placeholder="Ask a question..." value={chatInput} onChange={(e) => setChatInput(e.target.value)} disabled={chatLoading} />
            <button className="btn btn-primary" type="submit" disabled={chatLoading}>Send</button>
          </form>
        </div>
      </div>
    </div>
  );
}