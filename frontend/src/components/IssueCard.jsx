import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../api";

function Check({ state, children }) {
  const color = state === "ok" ? "text-verified" : state === "warn" ? "text-caution" : "text-alert";
  const icon = state === "ok" ? "✓" : state === "warn" ? "?" : "✕";
  return (
    <li className={`flex items-center gap-1.5 ${color}`}>
      <span aria-hidden className="font-bold">{icon}</span>
      <span className="text-ink">{children}</span>
    </li>
  );
}

function Readiness({ r }) {
  const d = r.days_since_update;
  return (
    <ul className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2" aria-label="Checks done on GitHub">
      <Check state="ok">Open</Check>
      <Check state={r.unassigned ? "ok" : "bad"}>{r.unassigned ? "Not assigned" : "Assigned to someone"}</Check>
      <Check state={r.pr_status === "none" ? "ok" : r.pr_status === "open" ? "bad" : "warn"}>
        {r.pr_status === "none" ? "No open pull request" : r.pr_status === "open" ? "Open pull request exists" : "PR check unavailable"}
      </Check>
      <Check state={r.claim_status === "none" ? "ok" : r.claim_status === "found" ? "warn" : "warn"}>
        {r.claim_status === "none"
          ? "No one has claimed it"
          : r.claim_status === "found"
            ? `${r.claim_by || "Someone"} may have claimed it`
            : "Comments not checked"}
      </Check>
      <Check state={d == null ? "warn" : d <= 60 ? "ok" : "warn"}>{d == null ? "Activity unknown" : `Updated ${d} day${d === 1 ? "" : "s"} ago`}</Check>
    </ul>
  );
}

function Breakdown({ items }) {
  return (
    <ul className="space-y-1.5">
      {items.map((b) => (
        <li key={b.key} className="grid grid-cols-[110px_1fr_48px] items-center gap-3 text-sm">
          <span>{b.label}</span>
          <span className="h-2 overflow-hidden rounded-full bg-paper" title={b.detail}>
            <span className="block h-full bg-signal" style={{ width: `${(b.points / b.max) * 100}%` }} />
          </span>
          <span className="text-right font-mono text-xs">{b.points}/{b.max}</span>
        </li>
      ))}
    </ul>
  );
}

export default function IssueCard({ issue, profile }) {
  const [showWhy, setShowWhy] = useState(false);
  const [ai, setAi] = useState({ loading: false, text: "", error: "" });

  async function explain() {
    setAi({ loading: true, text: "", error: "" });
    try {
      const res = await api.explainIssue(issue, profile);
      setAi({ loading: false, text: res.markdown, error: "" });
    } catch (e) {
      setAi({ loading: false, text: "", error: e.message });
    }
  }

  const sample = issue.id < 0;

  return (
    <article className="rounded-lg border border-line bg-white p-5">
      <div className="flex items-start gap-4">
        <div className="shrink-0 text-center" aria-label={`Match score ${issue.score} out of 100`}>
          <div className="font-display text-4xl font-extrabold leading-none">{issue.score}</div>
          <div className="mt-1 text-xs text-muted">of 100</div>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm text-muted">
            {issue.repo}
            {issue.repo_info?.stars != null && ` · ${issue.repo_info.stars.toLocaleString()} stars`}
            {issue.language && ` · ${issue.language}`}
          </p>
          <h3 className="font-display text-lg font-extrabold leading-snug">
            {sample ? (
              issue.title
            ) : (
              <a className="hover:text-signal hover:underline" href={issue.url} target="_blank" rel="noreferrer">
                {issue.title} <span className="font-sans text-sm font-normal text-muted">#{issue.number}</span>
              </a>
            )}
          </h3>
          {issue.labels.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {issue.labels.slice(0, 6).map((l) => (
                <li key={l} className="rounded-full bg-paper px-2.5 py-0.5 text-xs">{l}</li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {sample && <p className="mt-3 text-sm text-caution">Sample data, not a real GitHub issue.</p>}

      <div className="mt-4 border-t border-line pt-4">
        <p className="mb-2 text-sm font-semibold">Checked on GitHub</p>
        <Readiness r={issue.readiness} />
      </div>

      {issue.reasons.length > 0 && (
        <p className="mt-4 text-sm">
          <span className="font-semibold">Why it matches: </span>
          {issue.reasons.join(". ")}.
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <button className="btn-quiet" onClick={() => setShowWhy((v) => !v)} aria-expanded={showWhy}>
          {showWhy ? "Hide score" : "How is this scored?"}
        </button>
        <button className="btn-primary" onClick={explain} disabled={ai.loading}>
          {ai.loading ? "Gemma is thinking…" : ai.text ? "Explain again" : "Explain with Gemma"}
        </button>
      </div>

      {showWhy && (
        <div className="mt-4 rounded-md bg-paper p-4">
          <Breakdown items={issue.breakdown} />
          <p className="mt-3 text-xs text-muted">Calculated by fixed rules from GitHub data. The AI model does not change this number.</p>
        </div>
      )}

      {ai.error && <p className="mt-4 rounded-md border border-alert/40 p-3 text-sm text-alert">{ai.error}</p>}
      {ai.text && (
        <div className="mt-4 rounded-md border border-line p-4">
          <div className="md text-sm">
            <ReactMarkdown>{ai.text}</ReactMarkdown>
          </div>
          <p className="mt-3 text-xs text-muted">Written by a local Gemma model from the facts above. Check details before you start.</p>
        </div>
      )}
    </article>
  );
}
