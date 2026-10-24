import { useEffect, useState } from "react";
import { api } from "./api";
import StatusBar from "./components/StatusBar";
import ProfileForm from "./components/ProfileForm";
import IssueCard from "./components/IssueCard";
import DriftPanel from "./components/DriftPanel";

const DEFAULT_PROFILE = {
  skills: [],
  languages: [],
  interests: [],
  level: "beginner",
};

function loadProfile() {
  try {
    const raw = localStorage.getItem("contribscout.profile");
    return raw ? { ...DEFAULT_PROFILE, ...JSON.parse(raw) } : DEFAULT_PROFILE;
  } catch {
    return DEFAULT_PROFILE;
  }
}

const navItems = [
  { id: "issues", icon: "⌕", label: "Discover issues" },
  { id: "docs", icon: "▤", label: "Docs drift" },
];

export default function App() {
  const [tab, setTab] = useState("issues");
  const [profile, setProfile] = useState(loadProfile);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setHealth({ error: e.message }));
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("contribscout.profile", JSON.stringify(profile));
    } catch {
      // Storage may be unavailable.
    }
  }, [profile]);

  async function search() {
    setLoading(true);
    setError("");
    try {
      setResult(await api.searchIssues(profile, 8));
    } catch (e) {
      setError(e.message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="op-shell">
      <aside className="op-sidebar">
        <a className="op-brand" href="#" onClick={() => setTab("issues")}>
          <span className="op-brand-mark">o</span>
          <span>
            <strong>openpath</strong>
            <small>YOUR OPEN SOURCE JOURNEY</small>
          </span>
        </a>

        <div className="op-side-label">WORKSPACE</div>
        <nav className="op-nav" aria-label="Main navigation">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setTab(item.id)}
              className={`op-nav-item ${tab === item.id ? "active" : ""}`}
            >
              <span className="op-nav-icon">{item.icon}</span>
              {item.label}
              {tab === item.id && <span className="op-nav-dot" />}
            </button>
          ))}
        </nav>

        <div className="op-sidebar-bottom">
          <div className="op-side-label">YOUR MISSION</div>
          <div className="op-mission">
            <span className="op-mission-icon">✳</span>
            <strong>Your first contribution</strong>
            <p>Small steps. Real impact. Start with one issue.</p>
            <button onClick={() => setTab("issues")}>Explore issues ↗</button>
          </div>
          <p className="op-version">OPENPATH · BUILT FOR CONTRIBUTORS</p>
        </div>
      </aside>

      <main className="op-main">
        <header className="op-topbar">
          <div className="op-breadcrumb">
            Workspace <span>/</span>{" "}
            {tab === "issues" ? "Discover issues" : "Documentation drift"}
          </div>
          <div className="op-topbar-right">
            <span className="op-status-dot" />
            <span>Local AI workspace</span>
            <span className="op-avatar">O</span>
          </div>
        </header>

        <div className="op-content">
          <div className="op-eyebrow">
            <span className="op-eyebrow-line" />
            YOUR NEXT CHAPTER STARTS HERE
          </div>

          <h1 className="op-hero-title">
            {tab === "issues" ? (
              <>Find your <span>first issue.</span></>
            ) : (
              <>Keep your docs <span>in sync.</span></>
            )}
          </h1>

          <p className="op-hero-description">
            {tab === "issues"
              ? "Discover meaningful open-source issues that match your skills. Understand the code, find your path, and make your first contribution."
              : "Find documentation that has drifted from your codebase and review suggested fixes with AI assistance."}
          </p>

          <div className="op-statusbar">
            <StatusBar health={health} />
          </div>

          <div className="op-tab-switch">
            <button
              className={tab === "issues" ? "selected" : ""}
              onClick={() => setTab("issues")}
            >
              <span>⌕</span> Discover issues
            </button>
            <button
              className={tab === "docs" ? "selected" : ""}
              onClick={() => setTab("docs")}
            >
              <span>▤</span> Docs drift
            </button>
          </div>

          {tab === "issues" ? (
            <>
              <section className="op-search-panel">
                <div className="op-search-heading">
                  <div>
                    <h2>Find an issue worth solving</h2>
                    <p>Tell us what you know. We'll help you find where to start.</p>
                  </div>
                  <span className="op-ai-badge">✦ AI-ASSISTED</span>
                </div>

                <div className="op-search-layout">
                  <div className="op-profile-area">
                    <ProfileForm
                      profile={profile}
                      onChange={setProfile}
                      onSubmit={search}
                      loading={loading}
                    />
                  </div>
                  <div className="op-results-area" aria-live="polite">
                    <div className="op-results-heading">
                      <div>
                        <h2>Your discoveries</h2>
                        <p>Issues checked for contribution readiness</p>
                      </div>
                      {result && !loading && (
                        <span className="op-count">{result.stats.returned} found</span>
                      )}
                    </div>

                    {error && (
                      <div className="op-message op-error">
                        <strong>Something went wrong</strong>
                        <p>{error}</p>
                      </div>
                    )}

                    {loading && (
                      <div className="op-empty-state">
                        <span className="op-loading-orb">✦</span>
                        <h3>Finding your path…</h3>
                        <p>Searching GitHub and checking issue readiness.</p>
                      </div>
                    )}

                    {!loading && !error && !result && (
                      <div className="op-empty-state">
                        <span className="op-empty-icon">⌕</span>
                        <h3>Your next contribution is out there.</h3>
                        <p>
                          Add your skills and languages in the panel, then start
                          your search. We'll check each issue before recommending it.
                        </p>
                        <div className="op-hint-chips">
                          <span>Beginner-friendly</span>
                          <span>Verified status</span>
                          <span>Skill matched</span>
                        </div>
                      </div>
                    )}

                    {result && !loading && (
                      <>
                        {result.warning && (
                          <div className="op-message op-warning">{result.warning}</div>
                        )}
                        <div className="op-result-summary">
                          <span>{result.stats.fetched} fetched</span>
                          <span>{result.stats.excluded} filtered out</span>
                          <span>{result.stats.returned} recommended</span>
                        </div>

                        {result.issues.length === 0 && (
                          <div className="op-empty-state">
                            <h3>No matching issues yet</h3>
                            <p>Try adding another language or skill to your profile.</p>
                          </div>
                        )}

                        <div className="op-issue-list">
                          {result.issues.map((issue) => (
                            <IssueCard key={issue.id} issue={issue} profile={profile} />
                          ))}
                        </div>

                        {result.filtered_out.length > 0 && (
                          <details className="op-filtered">
                            <summary>
                              View {result.filtered_out.length} issues excluded by checks
                            </summary>
                            <ul>
                              {result.filtered_out.map((item) => (
                                <li key={item.url}>
                                  <a href={item.url} target="_blank" rel="noreferrer">
                                    {item.repo}: {item.title}
                                  </a>
                                  <p>{item.reasons.join(", ")}</p>
                                </li>
                              ))}
                            </ul>
                          </details>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </section>

              <section className="op-roadmap">
                <div>
                  <span className="op-roadmap-icon">01</span>
                  <div>
                    <strong>Discover</strong>
                    <p>Find an issue that matches your skills.</p>
                  </div>
                </div>
                <span className="op-roadmap-arrow">→</span>
                <div>
                  <span className="op-roadmap-icon">02</span>
                  <div>
                    <strong>Understand</strong>
                    <p>Use AI to understand the problem and code.</p>
                  </div>
                </div>
                <span className="op-roadmap-arrow">→</span>
                <div>
                  <span className="op-roadmap-icon">03</span>
                  <div>
                    <strong>Contribute</strong>
                    <p>Make your first meaningful pull request.</p>
                  </div>
                </div>
              </section>
            </>
          ) : (
            <section className="op-search-panel op-docs-panel">
              <div className="op-search-heading">
                <div>
                  <h2>Documentation drift detector</h2>
                  <p>Check whether your project documentation still matches the code.</p>
                </div>
                <span className="op-ai-badge">✦ DOCS CHECK</span>
              </div>
              <DriftPanel />
            </section>
          )}

          <footer className="op-footer">
            <span>OPENPATH</span>
            <span>Make your first open-source contribution count.</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
