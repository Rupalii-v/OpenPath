import { useState } from "react";

const LANGUAGES = ["Python", "JavaScript", "TypeScript", "Java", "Go", "Rust", "C++", "C#", "Ruby", "PHP", "Kotlin", "Dart"];

function TagInput({ label, placeholder, values, onChange }) {
  const [text, setText] = useState("");

  function add() {
    const parts = text.split(",").map((s) => s.trim()).filter(Boolean);
    if (parts.length) onChange([...new Set([...values, ...parts])].slice(0, 12));
    setText("");
  }

  return (
    <div>
      <label className="mb-1 block text-sm font-semibold">{label}</label>
      <div className="flex gap-2">
        <input
          className="input"
          value={text}
          placeholder={placeholder}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              add();
            }
          }}
          onBlur={add}
        />
      </div>
      {values.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-2">
          {values.map((v) => (
            <li key={v}>
              <button
                type="button"
                className="chip hover:border-alert"
                onClick={() => onChange(values.filter((x) => x !== v))}
                aria-label={`Remove ${v}`}
              >
                {v} <span aria-hidden>×</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ProfileForm({ profile, onChange, onSubmit, loading }) {
  const set = (patch) => onChange({ ...profile, ...patch });
  const toggleLang = (l) =>
    set({ languages: profile.languages.includes(l) ? profile.languages.filter((x) => x !== l) : [...profile.languages, l].slice(0, 3) });
  const ready = profile.skills.length > 0 || profile.languages.length > 0;

  return (
    <form
      className="h-fit space-y-5 rounded-lg border border-line bg-white p-5"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <h2 className="font-display text-xl font-extrabold">Your profile</h2>

      <fieldset>
        <legend className="mb-1 text-sm font-semibold">Languages (up to 3)</legend>
        <div className="flex flex-wrap gap-2">
          {LANGUAGES.map((l) => (
            <button
              type="button"
              key={l}
              aria-pressed={profile.languages.includes(l)}
              onClick={() => toggleLang(l)}
              className={`chip ${profile.languages.includes(l) ? "chip-on" : "hover:border-ink"}`}
            >
              {l}
            </button>
          ))}
        </div>
      </fieldset>

      <TagInput label="Skills" placeholder="react, fastapi, testing" values={profile.skills} onChange={(skills) => set({ skills })} />
      <TagInput label="Interests" placeholder="education, health, games" values={profile.interests} onChange={(interests) => set({ interests })} />

      <div>
        <label htmlFor="level" className="mb-1 block text-sm font-semibold">Experience</label>
        <select id="level" className="input" value={profile.level} onChange={(e) => set({ level: e.target.value })}>
          <option value="beginner">First contribution</option>
          <option value="intermediate">I have contributed before</option>
        </select>
      </div>

      <button className="btn-primary w-full" disabled={!ready || loading}>
        {loading ? "Searching…" : "Find issues I can take"}
      </button>
      {!ready && <p className="text-sm text-muted">Pick a language or add a skill to start.</p>}
    </form>
  );
}
