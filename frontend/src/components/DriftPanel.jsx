import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../api";

function Diff({ patch }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-md bg-ink p-3 font-mono text-xs leading-relaxed">
      {patch.split("\n").map((line, i) => {
        const cls = line.startsWith("+") && !line.startsWith("+++")
          ? "text-green-300"
          : line.startsWith("-") && !line.startsWith("---")
            ? "text-red-300"
            : line.startsWith("@@")
              ? "text-sky-300"
              : "text-white/70";
        return <div key={i} className={cls}>{line || " "}</div>;
      })}
    </pre>
  );
}

function FindingCard({ f }) {
  const confirmed = f.severity === "confirmed";
  return (
    <li className="rounded-lg border border-line bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${confirmed ? "bg-verified/10 text-verified" : "bg-caution/10 text-caution"}`}>
          {confirmed ? "Confirmed against the repo" : "Needs your judgement"}
        </span>
        <span className="text-xs text-muted">README line {f.line}</span>
        <span className="ml-auto text-xs">
          {f.fix_status === "fixed" ? (
            <span className="text-verified">Fixed in patch ({f.fix_source === "ai" ? "Gemma, verified by code" : "rule-based"})</span>
          ) : (
            <span className="text-caution">No safe automatic fix</span>
          )}
        </span>
      </div>
      <h3 className="mt-2 font-display text-base font-extrabold">{f.title}</h3>
      <pre className="mt-2 overflow-x-auto rounded bg-paper p-2 font-mono text-xs">{f.text}</pre>
      <p className="mt-2 text-sm">{f.evidence}</p>
      {f.suggestion && <p className="mt-1 text-sm text-muted">{f.suggestion}</p>}
      {f.ai_note && <p className="mt-1 text-sm text-muted">Gemma: {f.ai_note}</p>}
    </li>
  );
}

export default function DriftPanel() {
  const [repo, setRepo] = useState("");
  const [state, setState] = useState({ loading: false, error: "", data: null });
  const [copied, setCopied] = useState(false);

  const [cmp, setCmp] = useState({ snippet: "", path: "", loading: false, error: "", data: null });

  async function run(e) {
    e.preventDefault();
    setState({ loading: true, error: "", data: null });
    try {
      setState({ loading: false, error: "", data: await api.docsDrift(repo) });
    } catch (err) {
      setState({ loading: false, error: err.message, data: null });
    }
  }

  async function compare(e) {
    e.preventDefault();
    setCmp((c) => ({ ...c, loading: true, error: "", data: null }));
    try {
      const data = await api.docsCompare({ repo, doc_snippet: cmp.snippet, source_path: cmp.path });
      setCmp((c) => ({ ...c, loading: false, data }));
    } catch (err) {
      setCmp((c) => ({ ...c, loading: false, error: err.message }));
    }
  }

  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked */
    }
  }

  const d = state.data;

  return (
    <div className="space-y-8">
      <section>
        <p className="mb-3 max-w-2xl text-muted">
          Paste a repository you want to contribute to. We check what its README tells you to run or open against the real files, then Gemma drafts a fix that code re-checks.
        </p>
        <form onSubmit={run} className="flex flex-col gap-2 sm:flex-row">
          <label htmlFor="repo" className="sr-only">Repository</label>
          <input id="repo" className="input sm:max-w-md" placeholder="owner/name or https://github.com/owner/name" value={repo} onChange={(e) => setRepo(e.target.value)} />
          <button className="btn-primary" disabled={state.loading || repo.trim().length < 3}>
            {state.loading ? "Checking…" : "Check README"}
          </button>
        </form>
        {state.error && <p className="mt-4 rounded-md border border-alert/40 bg-white p-4 text-sm text-alert">{state.error}</p>}
      </section>

      {d && (
        <section className="space-y-4" aria-live="polite">
          <div className="rounded-lg border border-line bg-white p-5">
            <h2 className="font-display text-xl font-extrabold">{d.repo}</h2>
            <p className="mt-1 text-sm text-muted">
              Checked {d.readme_path} against {d.files_checked.toLocaleString()} files on branch {d.default_branch}.
              {d.tree_truncated && " The repository is very large, so some files were not listed."}
            </p>
            <p className="mt-3 text-base">
              {d.summary.total === 0
                ? "No drift found. Every command, file and link we could check exists."
                : `${d.summary.total} possible problem${d.summary.total === 1 ? "" : "s"}: ${d.summary.confirmed} confirmed, ${d.summary.uncertain} to judge yourself. ${d.summary.fixed_in_patch} fixed in the patch below.`}
            </p>
            {d.summary.ai_error && (
              <p className="mt-2 text-sm text-caution">Gemma was unavailable ({d.summary.ai_error}). Showing rule-based fixes only.</p>
            )}
          </div>

          {d.findings.length > 0 && (
            <ul className="space-y-3">
              {d.findings.map((f) => <FindingCard key={f.id} f={f} />)}
            </ul>
          )}

          {d.patch && (
            <div className="rounded-lg border border-line bg-white p-5">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="font-display text-lg font-extrabold">Suggested patch for review</h3>
                <button className="btn-quiet" onClick={() => copy(d.patch)}>{copied ? "Copied" : "Copy patch"}</button>
              </div>
              <Diff patch={d.patch} />
              <p className="mt-3 text-xs text-muted">Apply with `git apply` after reading it. Nothing is changed in the repository automatically.</p>
            </div>
          )}
        </section>
      )}

      <details className="rounded-lg border border-line bg-white p-5">
        <summary className="cursor-pointer font-semibold">Compare a doc example with a source file (AI, unverified)</summary>
        <form onSubmit={compare} className="mt-4 space-y-3">
          <p className="text-sm text-muted">Uses the repository above. Paste the documentation text and the path of the code file it describes.</p>
          <textarea className="input h-28 font-mono text-xs" placeholder="Paste a README instruction or API example" value={cmp.snippet} onChange={(e) => setCmp({ ...cmp, snippet: e.target.value })} />
          <input className="input" placeholder="Source file path, for example src/server.js" value={cmp.path} onChange={(e) => setCmp({ ...cmp, path: e.target.value })} />
          <button className="btn-primary" disabled={cmp.loading || !repo.trim() || cmp.snippet.length < 5 || !cmp.path.trim()}>
            {cmp.loading ? "Gemma is reading…" : "Compare with Gemma"}
          </button>
        </form>
        {cmp.error && <p className="mt-3 text-sm text-alert">{cmp.error}</p>}
        {cmp.data && (
          <div className="mt-4 rounded-md border border-line p-4">
            <div className="md text-sm"><ReactMarkdown>{cmp.data.analysis}</ReactMarkdown></div>
            <p className="mt-3 text-xs text-caution">{cmp.data.note}</p>
          </div>
        )}
      </details>
    </div>
  );
}
