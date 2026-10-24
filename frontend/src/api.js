async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`/api${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error("Cannot reach the ContribScout backend. Is it running on port 8000?");
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON response */
  }
  if (!res.ok) {
    const detail = data && data.detail;
    const message = Array.isArray(detail)
      ? detail.map((d) => d.msg).join("; ")
      : typeof detail === "string"
        ? detail
        : `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data;
}

const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => request("/health"),
  searchIssues: (profile, limit = 8) => post("/issues/search", { profile, limit }),
  explainIssue: (issue, profile) => post("/issues/explain", { issue, profile }),
  docsDrift: (repo) => post("/docs/drift", { repo }),
  docsCompare: (body) => post("/docs/compare", body),
};
