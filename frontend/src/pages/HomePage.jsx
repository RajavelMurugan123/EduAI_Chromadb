import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { logout } from "../api/auth";
import { listVideos } from "../api/videos";
import { globalSearch } from "../api/search";
import { useNavigate } from "react-router-dom";

export default function HomePage() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [videos, setVideos] = useState([]);
  const [allVideos, setAllVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [activeCategory, setActiveCategory] = useState(null);

  useEffect(() => {
    listVideos()
      .then((data) => {
        setAllVideos(data);
        setVideos(data);
      })
      .finally(() => setLoading(false));
  }, []);

  function handleLogout() {
    logout();
    setUser(null);
    navigate("/login");
  }

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) { setSearchResults(null); return; }
    setSearching(true);
    try {
      setSearchResults(await globalSearch(query));
    } finally {
      setSearching(false);
    }
  }

  function clearSearch() {
    setQuery("");
    setSearchResults(null);
  }

  function openVideoAt(videoId, timestamp) {
    navigate(`/watch/${videoId}?t=${timestamp}`);
  }

  function selectCategory(category) {
    setActiveCategory(category);
    setSearchResults(null);
    if (category === null) {
      setVideos(allVideos);
    } else {
      setVideos(allVideos.filter((v) => v.category === category));
    }
  }

  const categories = [...new Set(allVideos.map((v) => v.category))].filter(Boolean).sort();

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Welcome back, {user?.name}</h1>
          <p className="page-subtitle">Browse courses or search across everything you have access to.</p>
        </div>
        <button className="btn" onClick={handleLogout}>Log out</button>
      </div>

      <form onSubmit={handleSearch} className="search-bar" style={{ marginBottom: 20 }}>
        <input
          className="input"
          type="text"
          placeholder="Search all courses, e.g. loops"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn btn-primary" type="submit" disabled={searching}>
          {searching ? "Searching..." : "Search"}
        </button>
        {searchResults && <button className="btn" type="button" onClick={clearSearch}>Clear</button>}
      </form>

      {!searchResults && categories.length > 0 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 24 }}>
          <button
            className="btn btn-sm"
            style={activeCategory === null ? { background: "var(--color-primary)", color: "white", borderColor: "var(--color-primary)" } : {}}
            onClick={() => selectCategory(null)}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              className="btn btn-sm"
              style={activeCategory === cat ? { background: "var(--color-primary)", color: "white", borderColor: "var(--color-primary)" } : {}}
              onClick={() => selectCategory(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {searchResults && (
        <div style={{ marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, marginBottom: 14 }}>Search results</h3>
          {searchResults.length === 0 && <p style={{ color: "var(--color-text-secondary)" }}>No matches found.</p>}
          <div className="video-grid">
            {searchResults.map((r) => (
              <div
                key={r.video_id}
                className="video-card"
                onClick={() => openVideoAt(r.video_id, r.best_match_timestamp)}
              >
                <div className="video-thumb">▶</div>
                <div className="video-card-body">
                  <p className="video-card-title">{r.title}</p>
                  <p className="video-card-meta">{r.category}</p>
                  <p style={{ fontSize: 12, fontStyle: "italic", color: "var(--color-text-secondary)", margin: "6px 0" }}>"{r.matched_text}"</p>
                  <p style={{ fontSize: 12, color: "var(--color-primary)", fontWeight: 600 }}>
                    Jump to {Math.floor(r.best_match_timestamp / 60)}:{String(Math.floor(r.best_match_timestamp % 60)).padStart(2, "0")}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!searchResults && (
        <>
          {loading && <p>Loading courses...</p>}
          {!loading && videos.length === 0 && (
            <div className="empty-state">
              <h3>No courses yet</h3>
              <p>Once an admin uploads a video, it will appear here automatically.</p>
            </div>
          )}
          <div className="video-grid">
            {videos.map((v) => (
              <div key={v.id} className="video-card" onClick={() => navigate(`/watch/${v.id}`)}>
                <div className="video-thumb">▶</div>
                <div className="video-card-body">
                  <p className="video-card-title">{v.title}</p>
                  <p className="video-card-meta">{v.category}</p>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}