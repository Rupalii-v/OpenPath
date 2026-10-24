import { useEffect, useState } from "react";
import { api } from "./api";
import StatusBar from "./components/StatusBar";
import ProfileForm from "./components/ProfileForm";
import IssueCard from "./components/IssueCard";
import DriftPanel from "./components/DriftPanel";

const DEFAULT_PROFILE = { skills: [], languages: [], interests: [], level: "beginner" };

function loadProfile() {
  try {
    const raw = localStorage.getItem("contribscout.profile");
    return raw ? { ...DEFAULT_PROFILE, ...JSON.parse(raw) } : DEFAULT_PROFILE;
  } catch {
    return DEFAULT_PROFILE;
  }
}

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
      /* storage unavailable */
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
    <div className="mx-auto max-w-5xl px-4 pb-16">
      <header className="pt-8 pb-6">
        <h1 className="font-display text-4xl font-extrabold tracking-tight sm:text-5xl">ContribScout AI</h1>
        <p className="mt-2 max-w-xl text-lg text-muted">
          Find an issue you can actually take. Understand it. Check that the docs still match the code.
        </p>
        <StatusBar health={health} />
      </header>

      <nav className="mb-6 flex gap-1 border-b border-line" role="tablist">
        {[
          ["issues", "Find an issue"],
          ["docs", "Check documentation"],
        ].map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-semibold ${
              tab === id ? "border-signal text-ink" : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "issues" ? (
        <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
          <ProfileForm profile={profile} onChange={setProfile} onSubmit={search} loading={loading} />
          <section aria-live="polite">
            {error && <p className="rounded-md border border-alert/40 bg-white p-4 text-sm text-alert">{error}</p>}
            {loading && <p className="p-4 text-muted">Searching GitHub and checking each issue is really free…</p>}
            {!loading && !error && !result && (
              <p className="rounded-md border border-dashed border-line p-6 text-muted">
                Add your skills and languages, then search. Every result shows what was checked on GitHub before it was recommended.
              </p>
            )}
            {result && !loading && (
              <>
                {result.warning && (
                  <p className="mb-4 rounded-md border border-caution/50 bg-white p-4 text-sm text-caution">{result.warning}</p>
                )}
                <p className="mb-3 text-sm text-muted">
                  {result.stats.fetched} issues found, {result.stats.excluded} removed after checking, showing {result.stats.returned}.
                </p>
                {result.issues.length === 0 && (
                  <p className="rounded-md border border-line bg-white p-4">
                    No ready-to-take issues matched. Try another language or add more skills.
                  </p>
                )}
                <div className="space-y-4">
                  {result.issues.map((issue) => (
                    <IssueCard key={issue.id} issue={issue} profile={profile} />
                  ))}
                </div>
                {result.filtered_out.length > 0 && (
                  <details className="mt-6 rounded-md border border-line bg-white p-4 text-sm">
                    <summary className="cursor-pointer font-semibold">
                      Removed because they were not ready ({result.filtered_out.length})
                    </summary>
                    <ul className="mt-3 space-y-2">
                      {result.filtered_out.map((f) => (
                        <li key={f.url}>
                          <a className="text-signal underline" href={f.url} target="_blank" rel="noreferrer">
                            {f.repo}: {f.title}
                          </a>
                          <span className="block text-muted">{f.reasons.join(", ")}</span>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </>
            )}
          </section>
        </div>
      ) : (
        <DriftPanel />
      )}
    </div>
  );
}
