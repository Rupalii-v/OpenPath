function Item({ ok, label, hint }) {
  return (
    <li className="flex items-center gap-2" title={hint}>
      <span aria-hidden className={`h-2.5 w-2.5 rounded-full ${ok === true ? "bg-verified" : ok === false ? "bg-alert" : "bg-line"}`} />
      <span>{label}</span>
    </li>
  );
}

export default function StatusBar({ health }) {
  if (!health) return <p className="mt-4 text-sm text-muted">Checking backend…</p>;
  if (health.error) {
    return <p className="mt-4 text-sm text-alert">{health.error}</p>;
  }
  const { github, ollama } = health;
  const model = ollama.model;
  return (
    <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted">
      <Item
        ok={github.token_configured}
        label={github.token_configured ? "GitHub token set" : "No GitHub token (60 requests/hour)"}
        hint="Add GITHUB_TOKEN to backend/.env"
      />
      {github.rate_limit && (
        <Item ok={github.rate_limit.remaining > 5} label={`${github.rate_limit.remaining}/${github.rate_limit.limit} GitHub requests left`} />
      )}
      <Item
        ok={ollama.reachable && ollama.installed}
        label={
          !ollama.reachable
            ? "Ollama not running"
            : ollama.installed
              ? `Local model: ${model}`
              : `Model ${model} not installed`
        }
        hint={!ollama.reachable ? "Run: ollama serve" : !ollama.installed ? `Run: ollama pull ${model}` : "Runs on this machine"}
      />
    </ul>
  );
}
