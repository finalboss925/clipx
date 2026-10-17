import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUpRight,
  ArrowRight,
  Plus,
  Clapperboard,
  LayoutGrid,
  Palette,
  Settings,
  Link,
  Upload,
  ChevronDown,
  ChevronRight,
  Play,
  Download,
  Scissors,
  Search,
  X,
  Check,
  Loader2,
  ArrowLeft,
  RefreshCw,
  Film,
  FolderOpen,
  AudioLines,
  Monitor,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Github,
  Clock,
  MoreHorizontal,
  Sparkles,
} from "lucide-react";
import {
  api,
  defaults,
  styles,
  time,
  type Project,
  type Options,
  type Clip,
  type Brand,
  type Word,
} from "./types";
import "./style.css";

function App() {
  const [projects, setProjects] = useState<Project[]>([]),
    [selected, setSelected] = useState<string | null>(null),
    [page, setPage] = useState("studio"),
    [error, setError] = useState(""),
    [search, setSearch] = useState(""),
    [modal, setModal] = useState(false),
    [activeClip, setActiveClip] = useState<Clip | null>(null);
  const refresh = async () => {
    try {
      setProjects(await api<Project[]>("/projects"));
    } catch (e) {
      setError(String(e));
    }
  };
  useEffect(() => {
    refresh();
    const key = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setModal(true);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [selected, page]);
  const project = projects.find((p) => p.id === selected);
  useEffect(() => {
    if (!selected) return;
    const events = new EventSource("/api/projects/" + selected + "/events");
    events.onmessage = (event) => {
      refresh();
      const jobs = JSON.parse(event.data);
      if (
        jobs.length &&
        jobs.every((j: { status: string }) =>
          ["complete", "failed"].includes(j.status),
        )
      )
        events.close();
    };
    events.onerror = () => {};
    return () => events.close();
  }, [selected]);
  useEffect(() => {
    const interval = setInterval(() => {
      if (
        projects.some(
          (p) =>
            p.status === "processing" ||
            p.status === "queued" ||
            p.jobs.some((j) =>
              ["queued", "running", "retrying"].includes(j.status),
            ),
        )
      )
        refresh();
    }, 4000);
    return () => clearInterval(interval);
  }, [projects]);
  const clips = projects.flatMap((p) => p.clips),
    filtered = projects.filter((p) =>
      p.title.toLowerCase().includes(search.toLowerCase()),
    );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="logo"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("studio");
            setSelected(null);
          }}
        >
          <span className="logo-mark">
            <Scissors size={20} />
          </span>
          clip<span className="logo-x">x</span>
          <span className="beta">BETA</span>
        </a>
        <button className="new-project" onClick={() => setModal(true)}>
          <Plus size={17} /> New project <span>⌘ K</span>
        </button>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          <button
            className={page === "studio" ? "active" : ""}
            onClick={() => {
              setPage("studio");
              setSelected(null);
            }}
          >
            <LayoutGrid size={18} />
            Overview
          </button>
          <button
            className={page === "clips" ? "active" : ""}
            onClick={() => {
              setPage("clips");
              setSelected(null);
            }}
          >
            <Clapperboard size={18} />
            All clips <span className="nav-count">{clips.length}</span>
          </button>
          <button
            className={page === "brand" ? "active" : ""}
            onClick={() => {
              setPage("brand");
              setSelected(null);
            }}
          >
            <Palette size={18} />
            Brand kit
          </button>
        </nav>
        <div className="sidebar-projects">
          <div className="nav-label">
            RECENT PROJECTS{" "}
            <button aria-label="New project" onClick={() => setModal(true)}>
              <Plus size={14} />
            </button>
          </div>
          {projects.slice(0, 4).map((p) => (
            <button
              key={p.id}
              onClick={() => {
                setSelected(p.id);
                setPage("studio");
              }}
            >
              <span className="project-dot" />
              {p.title}
              <ChevronRight size={12} />
            </button>
          ))}
          {!projects.length && <p>Your next big moment starts here.</p>}
        </div>
        <div className="local-card">
          <span className="local-dot" />
          Made to stay local
          <p>
            Your videos. Your machine.
            <br />
            Your creative freedom.
          </p>
          <a href="https://github.com" target="_blank" rel="noreferrer">
            Open source, always <ArrowUpRight size={13} />
          </a>
        </div>
        <button className="profile" onClick={() => setPage("settings")}>
          <div className="avatar">C</div>
          <div>
            <strong>Creator workspace</strong>
            <small>Local workspace</small>
          </div>
          <Settings size={16} />
        </button>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            Workspace <ChevronRight size={13} />
            <span>
              {page === "brand"
                ? "Brand kit"
                : page === "clips"
                  ? "All clips"
                  : page === "settings"
                    ? "Settings"
                    : project
                      ? "Project"
                      : "Overview"}
            </span>
          </div>
          <div className="top-actions">
            <span className="private-pill">
              <span /> Local processing
            </span>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
            >
              API docs <ArrowUpRight size={13} />
            </a>
            <div className="avatar small">C</div>
          </div>
        </header>
        <main>
          {error && (
            <div role="alert" className="error">
              <AlertCircle size={17} />
              {error}
              <button onClick={() => setError("")} aria-label="Dismiss">
                <X size={16} />
              </button>
            </div>
          )}
          {page === "brand" ? (
            <BrandKit onError={setError} />
          ) : page === "settings" ? (
            <SettingsPage />
          ) : project ? (
            <ProjectView
              project={project}
              onBack={() => setSelected(null)}
              onEdit={setActiveClip}
              refresh={refresh}
              onError={setError}
            />
          ) : page === "clips" ? (
            <>
              <div className="page-heading">
                <div className="eyebrow">THE CUTTING ROOM</div>
                <h1>All your best moments.</h1>
                <p>Every clip, one place. Ready for its next audience.</p>
              </div>
              {clips.length ? (
                <div className="clip-grid">
                  {clips.map((c) => (
                    <ClipCard
                      key={c.id}
                      clip={c}
                      provider={
                        projects.find((p) => p.id === c.project_id)?.options
                          .provider || "local"
                      }
                      onEdit={() => setActiveClip(c)}
                    />
                  ))}
                </div>
              ) : (
                <Empty onNew={() => setModal(true)} />
              )}
            </>
          ) : (
            <>
              <div className="heading-row">
                <div className="page-heading">
                  <div className="eyebrow">
                    <span /> YOUR CREATIVE SHORTCUT
                  </div>
                  <h1>
                    Long videos.
                    <br className="mobile-break" /> <span>Big moments.</span>
                  </h1>
                  <p>
                    Find the good parts. Make them impossible to scroll past.
                  </p>
                </div>
                <div className="date-note">
                  YOUR NEXT CHAPTER
                  <br />
                  <span>Starts with a clip ↗</span>
                </div>
              </div>
              <div className="hero-grid">
                <div className="import-panel">
                  <div className="section-kicker">
                    <span className="step">01</span> START WITH YOUR VIDEO
                  </div>
                  <h2>One video. A world of possibilities.</h2>
                  <p>
                    Drop a podcast, interview, or that three-hour deep dive.
                  </p>
                  <QuickImport
                    onCreated={(id) => {
                      setSelected(id);
                      refresh();
                    }}
                    onAdvanced={() => setModal(true)}
                    onError={setError}
                  />
                  <div className="import-foot">
                    <span>
                      <Check size={13} /> No watermarks
                    </span>
                    <span>
                      <Check size={13} /> Yours to keep
                    </span>
                    <button onClick={() => setModal(true)}>
                      Customize settings <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
                <div className="feature-panel">
                  <div className="feature-top">
                    <span className="pill">LESS EDITING. MORE CREATING.</span>
                    <Sparkles size={20} />
                  </div>
                  <h2>
                    Your next great clip
                    <br />
                    is already in there.
                  </h2>
                  <div className="mini-film">
                    <div className="film-line" />
                    <div className="film-line second" />
                    <div className="film-line third" />
                    <div className="frame-corner tl" />
                    <div className="frame-corner tr" />
                    <div className="frame-corner bl" />
                    <div className="frame-corner br" />
                    <div className="mini-caption">
                      make every
                      <br />
                      <span>moment count.</span>
                    </div>
                    <span className="mini-time">00:15 / 00:30</span>
                    <span className="mini-ratio">9:16</span>
                  </div>
                  <div className="feature-bottom">
                    <span>
                      <AudioLines size={14} /> Word-perfect captions
                    </span>
                    <span>
                      <Monitor size={14} /> Smart reframing
                    </span>
                  </div>
                </div>
              </div>
              <div className="stats-row">
                <Stat
                  icon={<FolderOpen size={18} />}
                  value={String(projects.length).padStart(2, "0")}
                  label="Total projects"
                />
                <Stat
                  icon={<Clapperboard size={18} />}
                  value={String(clips.length).padStart(2, "0")}
                  label="Clips created"
                />
                <Stat
                  icon={<Clock size={18} />}
                  value={`${Math.round(projects.reduce((n, p) => n + p.duration, 0) / 60)}`}
                  suffix="min"
                  label="Video processed"
                />
                <div className="stats-note">
                  <span className="tiny-star">✳</span>
                  <div>
                    Big ideas. Small clips.
                    <br />
                    <span>All the tools to make them yours.</span>
                  </div>
                </div>
              </div>
              <section className="projects-section">
                <div className="section-heading">
                  <div>
                    <h2>
                      Your projects <span>{projects.length}</span>
                    </h2>
                    <p>A little less footage. A lot more potential.</p>
                  </div>
                  <div className="project-tools">
                    <label className="search">
                      <Search size={15} />
                      <input
                        aria-label="Search projects"
                        placeholder="Search projects..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                    </label>
                    <button
                      className="sort-button"
                      onClick={() => setProjects([...projects].reverse())}
                    >
                      Date created <ChevronDown size={14} />
                    </button>
                    <button
                      className="icon-button"
                      aria-label="Refresh projects"
                      onClick={refresh}
                    >
                      <RefreshCw size={16} />
                    </button>
                  </div>
                </div>
                {filtered.length ? (
                  <div className="project-grid">
                    {filtered.map((p, i) => (
                      <button
                        className="project-card"
                        key={p.id}
                        onClick={() => setSelected(p.id)}
                      >
                        <div className="project-image">
                          <img
                            src={p.poster_url}
                            alt=""
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                            }}
                          />
                          <span className={"status " + p.status}>
                            <span />
                            {p.status === "complete"
                              ? "Ready to clip"
                              : p.status === "failed"
                                ? "Needs attention"
                                : "Processing"}
                          </span>
                          <span className="duration">{time(p.duration)}</span>
                          <div className="project-play">
                            <Play size={22} fill="currentColor" />
                          </div>
                        </div>
                        <div className="project-info">
                          <div className="project-type">
                            {p.options.aspect} ·{" "}
                            {p.options.provider === "local"
                              ? "LOCAL WORKFLOW"
                              : "AI CLIPS"}
                          </div>
                          <h3>{p.title}</h3>
                          <div className="project-meta">
                            <span>
                              {p.clips.length} clips{" "}
                              <span className="dot-sep">·</span>{" "}
                              {new Date(p.created_at).toLocaleDateString(
                                undefined,
                                { month: "short", day: "numeric" },
                              )}
                            </span>
                            <ArrowUpRight size={17} />
                          </div>
                        </div>
                      </button>
                    ))}
                    <button
                      className="add-project-card"
                      onClick={() => setModal(true)}
                    >
                      <span>
                        <Plus size={24} />
                      </span>
                      <strong>Something worth sharing?</strong>
                      <p>Let’s find your next great moment.</p>
                      <small>
                        Create a project <ArrowRight size={13} />
                      </small>
                    </button>
                  </div>
                ) : (
                  <Empty onNew={() => setModal(true)} />
                )}
              </section>
              <footer className="main-footer">
                <span>
                  <span className="footer-mark">✳</span> Made for creators.
                  Built in the open.
                </span>
                <span>
                  Your footage stays yours. <span className="local-dot" />
                </span>
              </footer>
            </>
          )}
        </main>
      </div>
      {modal && (
        <ImportModal
          onClose={() => setModal(false)}
          onCreated={(id) => {
            setModal(false);
            setSelected(id);
            setPage("studio");
            refresh();
          }}
          onError={setError}
        />
      )}{" "}
      {activeClip && (
        <Editor
          clip={activeClip}
          project={projects.find((p) => p.id === activeClip.project_id)!}
          onClose={() => setActiveClip(null)}
          onSaved={() => {
            setActiveClip(null);
            refresh();
          }}
          onError={setError}
        />
      )}
    </div>
  );
}
function Stat({
  icon,
  value,
  label,
  suffix,
}: {
  icon: React.ReactNode;
  value: string;
  label: string;
  suffix?: string;
}) {
  return (
    <div className="stat">
      <span className="stat-icon">{icon}</span>
      <div>
        <strong>
          {value}
          <small>{suffix}</small>
        </strong>
        <span>{label}</span>
      </div>
    </div>
  );
}
function Empty({ onNew }: { onNew: () => void }) {
  return (
    <div className="empty">
      <Film size={32} />
      <h3>Your next great moment starts here.</h3>
      <p>Import a video to create your first clips.</p>
      <button className="primary" onClick={onNew}>
        <Plus size={16} />
        Create a project
      </button>
    </div>
  );
}
function QuickImport({
  onCreated,
  onAdvanced,
  onError,
}: {
  onCreated: (id: string) => void;
  onAdvanced: () => void;
  onError: (s: string) => void;
}) {
  const [url, setUrl] = useState(""),
    [busy, setBusy] = useState(false),
    [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const upload = async (file: File) => {
    setBusy(true);
    try {
      const data = new FormData();
      data.append("file", file);
      const brand = await api<Brand>("/brand");
      data.append("options", JSON.stringify({ ...defaults, brand }));
      const p = await api<{ id: string }>("/projects/upload", {
        method: "POST",
        body: data,
      });
      onCreated(p.id);
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  };
  const submit = async () => {
    if (!url.trim()) return;
    setBusy(true);
    try {
      const p = await api<{ id: string }>("/projects/url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          options: { ...defaults, brand: await api<Brand>("/brand") },
        }),
      });
      onCreated(p.id);
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="url-input">
        <Link size={17} />
        <input
          aria-label="Video URL"
          placeholder="Paste a YouTube or video link..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
        />
        <button disabled={busy || !url.trim()} onClick={submit}>
          {busy ? (
            <Loader2 size={16} className="spin" />
          ) : (
            <>
              Get clips <ArrowRight size={15} />
            </>
          )}
        </button>
      </div>
      <div className="or-divider">
        <span />
        or bring your own
        <span />
      </div>
      <button
        className={"dropzone " + (drag ? "drag" : "")}
        disabled={busy}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]);
        }}
      >
        <span className="upload-icon">
          <Upload size={21} />
        </span>
        <strong>
          {busy ? (
            "Uploading your video..."
          ) : (
            <>
              Drag & drop your video <span>or browse files</span>
            </>
          )}
        </strong>
        <small>MP4, MOV, MKV, WEBM · Up to 4 GB</small>
      </button>
      <input
        hidden
        ref={input}
        type="file"
        accept="video/*,.mkv"
        onChange={(e) => {
          if (e.target.files?.[0]) upload(e.target.files[0]);
        }}
      />
    </>
  );
}
function ImportModal({
  onClose,
  onCreated,
  onError,
}: {
  onClose: () => void;
  onCreated: (id: string) => void;
  onError: (s: string) => void;
}) {
  const [o, setO] = useState<Options>(structuredClone(defaults)),
    [file, setFile] = useState<File | null>(null),
    [url, setUrl] = useState(""),
    [busy, setBusy] = useState(false),
    [duration, setDuration] = useState(0);
  useEffect(() => {
    api<Brand>("/brand")
      .then((brand) => setO((v) => ({ ...v, brand })))
      .catch(() => {});
  }, []);
  const choose = (f: File) => {
    setFile(f);
    const v = document.createElement("video");
    const object = URL.createObjectURL(f);
    v.preload = "metadata";
    v.onloadedmetadata = () => {
      setDuration(v.duration);
      URL.revokeObjectURL(object);
    };
    v.onerror = () => URL.revokeObjectURL(object);
    v.src = object;
  };
  const submit = async () => {
    setBusy(true);
    try {
      let p: { id: string };
      if (file) {
        const d = new FormData();
        d.append("file", file);
        d.append("options", JSON.stringify(o));
        p = await api("/projects/upload", { method: "POST", body: d });
      } else {
        p = await api("/projects/url", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url, options: o }),
        });
      }
      onCreated(p.id);
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  };
  const set = (k: keyof Options, v: unknown) => setO({ ...o, [k]: v });
  const est =
    (o.transcription === "openai" ? (duration / 60) * 0.006 : 0) +
    (o.provider !== "local"
      ? ((duration / 60) * 550 * 0.15 + o.clip_count * 650 * 0.6) / 1e6
      : 0);
  return (
    <div className="modal-backdrop">
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="Create project"
      >
        <div className="modal-header">
          <div>
            <div className="eyebrow">LET’S MAKE THE CUT</div>
            <h2>Create a project</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close">
            <X size={20} />
          </button>
        </div>
        <label className="field">
          Video link
          <input
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setFile(null);
            }}
            placeholder="https://www.youtube.com/watch?v=..."
          />
        </label>
        <label className="file-field">
          <Upload size={20} />
          {file ? file.name : "Or choose a video file"}
          <input
            type="file"
            accept="video/*,.mkv"
            onChange={(e) => {
              if (e.target.files?.[0]) choose(e.target.files[0]);
            }}
          />
        </label>
        <div className="form-grid">
          <label className="field">
            Minimum length
            <select
              value={o.min_length}
              onChange={(e) => set("min_length", +e.target.value)}
            >
              {[15, 30, 45, 60].map((n) => (
                <option key={n} value={n}>
                  {n} seconds
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Maximum length
            <select
              value={o.max_length}
              onChange={(e) => set("max_length", +e.target.value)}
            >
              {[30, 45, 60, 90].map((n) => (
                <option key={n} value={n}>
                  {n} seconds
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Number of clips
            <input
              type="number"
              min="1"
              max="20"
              value={o.clip_count}
              onChange={(e) => set("clip_count", +e.target.value)}
            />
          </label>
          <label className="field">
            Aspect ratio
            <select
              value={o.aspect}
              onChange={(e) => set("aspect", e.target.value)}
            >
              {["9:16", "1:1", "16:9"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Caption style
            <select
              value={o.caption_style}
              onChange={(e) => set("caption_style", e.target.value)}
            >
              {styles.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Language
            <select
              value={o.language}
              onChange={(e) => set("language", e.target.value)}
            >
              {[
                ["auto", "Auto detect"],
                ["en", "English"],
                ["es", "Spanish"],
                ["fr", "French"],
                ["de", "German"],
                ["pt", "Portuguese"],
                ["ar", "Arabic"],
                ["hi", "Hindi"],
                ["zh", "Chinese"],
                ["ja", "Japanese"],
                ["yo", "Yoruba"],
              ].map(([v, s]) => (
                <option key={v} value={v}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Find moments with
            <select
              value={o.provider}
              onChange={(e) => set("provider", e.target.value)}
            >
              <option value="local">Local heuristic · free</option>
              <option value="openai">OpenAI · API key required</option>
              <option value="anthropic">Anthropic · API key required</option>
            </select>
          </label>
          <label className="field">
            Transcription
            <select
              value={o.transcription}
              onChange={(e) => set("transcription", e.target.value)}
            >
              <option value="local">Local Whisper</option>
              <option value="openai">OpenAI audio API</option>
            </select>
          </label>
          <label className="field">
            Layout
            <select
              value={o.layout}
              onChange={(e) => set("layout", e.target.value)}
            >
              <option value="face">Track primary face</option>
              <option value="center">Center crop</option>
              <option value="split">Content + face split</option>
            </select>
          </label>
          <label className="toggle-field">
            <input
              type="checkbox"
              checked={o.cleanup}
              onChange={(e) => set("cleanup", e.target.checked)}
            />
            <span>
              Remove pauses & fillers
              <small>Keep audio and captions in sync</small>
            </span>
          </label>
        </div>
        <div className="estimate">
          <span>
            Estimated API cost {duration > 0 ? `for ${time(duration)}` : ""}
          </span>
          <strong>
            {o.provider === "local" && o.transcription === "local"
              ? "$0.00"
              : duration > 0
                ? `~$${est.toFixed(3)}`
                : "Calculated after ingest"}
          </strong>
          <small>
            Budget estimate using configurable default rates. Local processing
            is free.{" "}
            {o.transcription === "openai"
              ? "Audio will be sent to OpenAI."
              : "LLM analysis sends transcript text only."}
          </small>
        </div>
        <button
          className="primary wide"
          disabled={
            busy ||
            (!file && !url) ||
            o.min_length > o.max_length ||
            o.clip_count < 1 ||
            o.clip_count > 20
          }
          onClick={submit}
        >
          {busy ? (
            <Loader2 size={17} className="spin" />
          ) : (
            <Sparkles size={17} />
          )}{" "}
          {busy ? "Uploading..." : "Find my best moments"}
          <ArrowRight size={17} />
        </button>
      </section>
    </div>
  );
}
function ClipCard({
  clip: c,
  provider,
  onEdit,
}: {
  clip: Clip;
  provider: string;
  onEdit: () => void;
}) {
  return (
    <article className="clip-card">
      <div className="clip-video">
        {c.video_url ? (
          <video
            controls
            preload="metadata"
            poster={c.thumbnail_url || undefined}
            src={c.video_url}
          />
        ) : (
          <div className="render-placeholder">
            <Film size={30} />
            <span>Ready to render</span>
          </div>
        )}
        <span className="clip-score">
          {c.total > 0 ? Math.round(c.total) : "—"}
          <small>{provider === "local" ? "HEURISTIC" : "VIRALITY"}</small>
        </span>
      </div>
      <div className="clip-info">
        <span className="project-type">
          {time(c.start)} – {time(c.end)} · {Math.round(c.end - c.start)} SEC
        </span>
        <h3>{c.title}</h3>
        <p>{c.reason}</p>
        <div className="clip-actions">
          <button onClick={onEdit}>
            <Scissors size={14} /> Edit clip
          </button>
          {c.video_url && (
            <a href={c.video_url + "?download=true"}>
              <Download size={14} /> MP4
            </a>
          )}
          {c.srt_url && <a href={c.srt_url}>SRT</a>}
        </div>
      </div>
    </article>
  );
}
function ProjectView({
  project: p,
  onBack,
  onEdit,
  refresh,
  onError,
}: {
  project: Project;
  onBack: () => void;
  onEdit: (c: Clip) => void;
  refresh: () => void;
  onError: (s: string) => void;
}) {
  const [q, setQ] = useState(""),
    [words, setWords] = useState<Word[]>([]),
    [finding, setFinding] = useState(false);
  const job = p.jobs.find((j) => j.kind === "pipeline"),
    busy = job && ["running", "queued", "retrying"].includes(job.status);
  const find = async () => {
    setFinding(true);
    try {
      setWords(
        (
          await api<{ words: Word[] }>(
            `/projects/${p.id}/transcript?q=${encodeURIComponent(q)}`,
          )
        ).words,
      );
    } catch (e) {
      onError(String(e));
    } finally {
      setFinding(false);
    }
  };
  const custom = async (w: Word) => {
    try {
      const c = await api<Clip>(`/projects/${p.id}/clips`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start: w.start,
          end: Math.min(p.duration, w.start + 30),
          title: `Custom clip · ${q}`,
          caption_style: p.options.caption_style,
          offset: 0,
          deleted_words: [],
        }),
      });
      await refresh();
      onEdit(c);
    } catch (e) {
      onError(String(e));
    }
  };
  return (
    <>
      <button className="back" onClick={onBack}>
        <ArrowLeft size={15} /> All projects
      </button>
      <div className="section-heading project-heading">
        <div>
          <div className="eyebrow">YOUR CUTTING ROOM</div>
          <h1>{p.title}</h1>
          <p>
            {time(p.duration)} source · {p.options.aspect} ·{" "}
            {p.options.provider === "local"
              ? "Local heuristic selection"
              : p.options.provider + " analysis"}{" "}
            · Estimated API cost ${p.cost.estimated_usd.toFixed(3)}
          </p>
        </div>
        {p.clips.some((c) => c.video_url) && (
          <a className="primary" href={`/api/projects/${p.id}/download`}>
            <Download size={16} />
            Download all
          </a>
        )}
      </div>
      {job && (
        <div
          className={
            "progress-panel " + (job.status === "failed" ? "failed" : "")
          }
        >
          <div>
            <span>
              {job.status === "complete" ? (
                <CheckCircle2 size={18} />
              ) : busy ? (
                <Loader2 size={18} className="spin" />
              ) : (
                <AlertCircle size={18} />
              )}{" "}
              {job.status === "complete"
                ? "Your clips are ready"
                : job.status === "failed"
                  ? "Processing paused"
                  : `Working on ${job.stage}...`}
            </span>
            <strong>{Math.round(job.progress)}%</strong>
          </div>
          <div className="progress-track">
            <i style={{ width: job.progress + "%" }} />
          </div>
          <div className="stages">
            {[
              "Ingest",
              "Transcribe",
              "Segment",
              "Candidates",
              "Cleanup",
              "Reframe",
              "Captions",
              "Export",
            ].map((s, i) => (
              <span
                key={s}
                className={job.progress >= (i / 8) * 100 ? "done" : ""}
              >
                {s}
              </span>
            ))}
          </div>
          {job.error && <p>{job.error}</p>}
          {job.status === "failed" && (
            <button
              className="secondary"
              onClick={async () => {
                try {
                  await api(`/jobs/${job.id}/retry`, { method: "POST" });
                  refresh();
                } catch (e) {
                  onError(String(e));
                }
              }}
            >
              <RefreshCw size={14} />
              Resume from checkpoint
            </button>
          )}
        </div>
      )}
      {p.jobs
        .filter((j) => j.kind === "render" && j.status !== "complete")
        .map((j) => (
          <div key={j.id} className="notice">
            {j.status === "failed" ? (
              <AlertCircle size={16} />
            ) : (
              <Loader2 size={16} className="spin" />
            )}{" "}
            Render {j.status}:{" "}
            {j.error || "Your original export remains available."}
            {j.status === "failed" && (
              <button
                onClick={async () => {
                  try {
                    await api(`/jobs/${j.id}/retry`, { method: "POST" });
                    refresh();
                  } catch (e) {
                    onError(String(e));
                  }
                }}
              >
                Retry
              </button>
            )}
          </div>
        ))}
      <div className="section-heading">
        <h2>
          Selected moments <span className="count">{p.clips.length}</span>
        </h2>
        <span className="muted">
          Ranked by{" "}
          {p.options.provider === "local"
            ? "heuristic score"
            : "editorial score"}
        </span>
      </div>
      <div className="clip-grid">
        {p.clips.map((c) => (
          <ClipCard
            key={c.id}
            clip={c}
            provider={p.options.provider}
            onEdit={() => onEdit(c)}
          />
        ))}
      </div>
      {!p.clips.length && (
        <div className="empty">
          <AudioLines size={32} />
          <h3>{busy ? "Finding the moments that matter." : "No clips yet."}</h3>
          <p>
            {busy
              ? "This page updates as each stage completes."
              : "Check your project status above."}
          </p>
        </div>
      )}
      <section className="transcript-search">
        <div>
          <h2>Find your own moment.</h2>
          <p>Search the transcript and turn a quote into a custom clip.</p>
        </div>
        <div className="url-input">
          <Search size={17} />
          <input
            value={q}
            aria-label="Search transcript"
            placeholder="Search a word or phrase..."
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") find();
            }}
          />
          <button disabled={!q || finding} onClick={find}>
            {finding ? <Loader2 size={15} className="spin" /> : "Search"}
          </button>
        </div>
        {words.map((w) => (
          <button
            className="search-hit"
            key={w.index}
            onClick={() => custom(w)}
          >
            <span>{time(w.start)}</span>
            <strong>{w.text}</strong>Create clip <Plus size={14} />
          </button>
        ))}
      </section>
    </>
  );
}
function SettingsPage() {
  return (
    <>
      <div className="page-heading">
        <div className="eyebrow">YOUR WORKSPACE</div>
        <h1>Local by design.</h1>
        <p>Everything you need to make ClipX your own.</p>
      </div>
      <div className="settings-panel">
        <h2>Processing & providers</h2>
        <p>
          Configure Whisper models, OpenAI or Anthropic keys, and API cost rates
          in your server’s <code>.env</code> file. Restart the API and worker
          after making changes.
        </p>
        <p>
          Local selection uses sentence heuristics. Face tracking follows the
          stable primary visible face; active-speaker diarization is not
          enabled.
        </p>
        <a
          className="secondary"
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
        >
          Explore API documentation <ExternalLink size={15} />
        </a>
        <h2>Publishing</h2>
        <p>
          Direct publishing is disabled. Export your MP4 and upload it to
          YouTube Shorts, Reels or TikTok. Use only footage you have rights to
          process.
        </p>
      </div>
    </>
  );
}
function BrandKit({ onError }: { onError: (s: string) => void }) {
  const [brand, setBrand] = useState<Brand>(defaults.brand),
    [saved, setSaved] = useState(false),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    api<Brand>("/brand")
      .then(setBrand)
      .catch((e) => onError(String(e)));
  }, []);
  const save = async () => {
    setBusy(true);
    try {
      await api("/brand", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(brand),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  };
  const media = async (kind: "intro" | "outro", file: File) => {
    const f = new FormData();
    f.append("file", file);
    try {
      const r = await api<Record<string, string>>("/brand/media/" + kind, {
        method: "POST",
        body: f,
      });
      setBrand({ ...brand, [kind]: r[kind] });
    } catch (e) {
      onError(String(e));
    }
  };
  const logo = async (file: File) => {
    const f = new FormData();
    f.append("file", file);
    try {
      const r = await api<{ logo: string }>("/brand/logo", {
        method: "POST",
        body: f,
      });
      setBrand({ ...brand, logo: r.logo });
    } catch (e) {
      onError(String(e));
    }
  };
  return (
    <>
      <div className="page-heading">
        <div className="eyebrow">MAKE IT UNMISTAKABLY YOURS</div>
        <h1>Your signature style.</h1>
        <p>One consistent look, from your first clip to your next thousand.</p>
      </div>
      <div className="brand-grid">
        <section className="settings-panel">
          <h2>Brand essentials</h2>
          <label className="field">
            Brand name
            <input
              value={brand.name}
              onChange={(e) => setBrand({ ...brand, name: e.target.value })}
            />
          </label>
          <label className="field">
            Caption font
            <select
              value={brand.font}
              onChange={(e) =>
                setBrand({ ...brand, font: e.target.value as Brand["font"] })
              }
            >
              {["DejaVu Sans", "Liberation Sans", "Arial"].map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
          </label>
          <div className="form-grid">
            <label className="field">
              Highlight color
              <input
                type="color"
                value={brand.color}
                onChange={(e) => setBrand({ ...brand, color: e.target.value })}
              />
            </label>
            <label className="field">
              Text color
              <input
                type="color"
                value={brand.text_color}
                onChange={(e) =>
                  setBrand({ ...brand, text_color: e.target.value })
                }
              />
            </label>
          </div>
          <label className="file-field">
            <Upload size={19} />
            {brand.logo ? "Replace brand logo" : "Upload a brand logo"}
            <input
              type="file"
              accept="image/png,image/jpeg"
              onChange={(e) => {
                if (e.target.files?.[0]) logo(e.target.files[0]);
              }}
            />
          </label>
          {brand.logo && (
            <button
              className="text-button"
              onClick={() => setBrand({ ...brand, logo: null })}
            >
              Remove logo
            </button>
          )}
          <label className="field">
            Caption emoji
            <select
              value={brand.emoji || ""}
              onChange={(e) => setBrand({ ...brand, emoji: e.target.value })}
            >
              {["", "🔥", "💡", "✨", "👏"].map((s) => (
                <option key={s} value={s}>
                  {s || "None"}
                </option>
              ))}
            </select>
          </label>
          <div className="form-grid">
            {(["intro", "outro"] as const).map((kind) => (
              <div key={kind}>
                <label className="file-field">
                  <Film size={16} />
                  {brand[kind] ? "Replace " + kind : "Add " + kind}
                  <input
                    type="file"
                    accept="video/*"
                    onChange={(e) => {
                      if (e.target.files?.[0]) media(kind, e.target.files[0]);
                    }}
                  />
                </label>
                {brand[kind] && (
                  <button
                    className="text-button"
                    onClick={() => setBrand({ ...brand, [kind]: null })}
                  >
                    Remove {kind}
                  </button>
                )}
              </div>
            ))}
          </div>
          <p className="muted">
            Optional intro/outro: video with audio, up to 15 seconds and 100 MB.
            Saved settings apply to new projects. PNG/JPEG logos, up to 5 MB.
          </p>
          <button className="primary" disabled={busy} onClick={save}>
            {saved ? <Check size={16} /> : <Palette size={16} />}{" "}
            {saved ? "Brand kit saved" : "Save brand kit"}
          </button>
        </section>
        <div className="brand-preview">
          <span>CAPTION PREVIEW</span>
          <div className="brand-video">
            {brand.logo && (
              <img src={"/api/brand/logo/" + brand.logo} alt="Brand logo" />
            )}
            <div className="preview-orbit" />
            <h2
              style={{
                fontFamily: brand.font + ", sans-serif",
                color: brand.text_color,
              }}
            >
              A little more
              <br />
              <strong style={{ color: brand.color }}>you.</strong>
            </h2>
            <p>YOUR STORY. YOUR STYLE.</p>
          </div>
          <small>
            Preview is illustrative. Final captions are rendered with FFmpeg.
          </small>
        </div>
      </div>
    </>
  );
}
function Editor({
  clip,
  project,
  onClose,
  onSaved,
  onError,
}: {
  clip: Clip;
  project: Project;
  onClose: () => void;
  onSaved: () => void;
  onError: (s: string) => void;
}) {
  const [c, setC] = useState({ ...clip }),
    [words, setWords] = useState<Word[]>([]),
    [busy, setBusy] = useState(false),
    [cursor, setCursor] = useState(clip.start);
  const video = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    api<{ words: Word[] }>(`/projects/${clip.project_id}/transcript`)
      .then((t) => setWords(t.words))
      .catch((e) => onError(String(e)));
  }, [clip.project_id]);
  const seek = (t: number) => {
    if (video.current) video.current.currentTime = t;
    setCursor(t);
  };
  const toggle = (index: number) =>
    setC({
      ...c,
      deleted_words: c.deleted_words.includes(index)
        ? c.deleted_words.filter((i) => i !== index)
        : [...c.deleted_words, index],
    });
  const render = async () => {
    setBusy(true);
    try {
      const body = {
        start: c.start,
        end: c.end,
        title: c.title,
        caption_style: c.caption_style,
        offset: c.offset,
        deleted_words: c.deleted_words,
      };
      await api(`/clips/${c.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      await api(`/clips/${c.id}/renders`, { method: "POST" });
      onSaved();
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal-backdrop editor-backdrop">
      <section
        className="editor"
        role="dialog"
        aria-modal="true"
        aria-label="Clip editor"
      >
        <div className="editor-header">
          <div>
            <span className="eyebrow">THE FINAL CUT</span>
            <h2>Edit your moment</h2>
          </div>
          <div>
            <button
              className="primary"
              disabled={busy || c.end <= c.start}
              onClick={render}
            >
              {busy ? (
                <Loader2 size={16} className="spin" />
              ) : (
                <Clapperboard size={16} />
              )}
              Save & re-render
            </button>
            <button
              className="icon-button"
              onClick={onClose}
              aria-label="Close editor"
            >
              <X size={21} />
            </button>
          </div>
        </div>
        <div className="editor-grid">
          <div className="editor-preview">
            <video
              controls
              ref={video}
              src={`/api/projects/${clip.project_id}/source`}
              onLoadedMetadata={() => seek(c.start)}
              onTimeUpdate={() => {
                const t = video.current?.currentTime || 0;
                setCursor(t);
                if (t >= c.end && video.current && !video.current.paused) {
                  video.current.pause();
                  seek(c.start);
                }
              }}
            />
            <div className="editor-preview-note">
              Source preview · edits appear in the new render
            </div>
            <div className="timeline">
              <div>
                <span>{time(c.start)}</span>
                <span>{time(cursor)}</span>
                <span>{time(c.end)}</span>
              </div>
              <div className="waveform">
                {Array.from({ length: 70 }, (_, i) => (
                  <i
                    key={i}
                    style={{
                      height: 15 + (Math.sin(i * 2.1) + 1) * 18 + "px",
                      opacity:
                        (i / 70) * project.duration >= c.start &&
                        (i / 70) * project.duration <= c.end
                          ? 1
                          : 0.2,
                    }}
                  />
                ))}
              </div>
              <label className="trim-label">
                Start handle
                <input
                  aria-label="Trim start handle"
                  type="range"
                  min="0"
                  max={project.duration}
                  step="0.05"
                  value={c.start}
                  onChange={(e) => {
                    const start = Math.min(+e.target.value, c.end - 0.2);
                    setC({ ...c, start });
                    seek(start);
                  }}
                />
              </label>
              <label className="trim-label">
                End handle
                <input
                  aria-label="Trim end handle"
                  type="range"
                  min="0"
                  max={project.duration}
                  step="0.05"
                  value={c.end}
                  onChange={(e) =>
                    setC({
                      ...c,
                      end: Math.max(+e.target.value, c.start + 0.2),
                    })
                  }
                />
              </label>
              <div className="form-grid">
                <label className="field">
                  In (seconds)
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    max={c.end - 0.2}
                    value={c.start}
                    onChange={(e) => setC({ ...c, start: +e.target.value })}
                  />
                </label>
                <label className="field">
                  Out (seconds)
                  <input
                    type="number"
                    step="0.05"
                    min={c.start + 0.2}
                    max={Math.min(project.duration, c.start + 90)}
                    value={c.end}
                    onChange={(e) => setC({ ...c, end: +e.target.value })}
                  />
                </label>
              </div>
            </div>
          </div>
          <div className="editor-controls">
            <label className="field">
              Clip title
              <input
                value={c.title}
                maxLength={140}
                onChange={(e) => setC({ ...c, title: e.target.value })}
              />
            </label>
            <label className="field">
              Caption style
              <select
                value={c.caption_style}
                onChange={(e) => setC({ ...c, caption_style: e.target.value })}
              >
                {styles.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Reframe offset <span>{c.offset.toFixed(2)}</span>
              <input
                type="range"
                min="-1"
                max="1"
                step="0.01"
                value={c.offset}
                onChange={(e) => setC({ ...c, offset: +e.target.value })}
              />
            </label>
            <div className="transcript-editor">
              <div>
                <h3>Edit with words</h3>
                <span>{c.deleted_words.length} removed</span>
              </div>
              <p>
                Click a word to remove or restore it. Audio, video and captions
                are cut together.
              </p>
              <div className="words">
                {words
                  .filter((w) => w.start >= c.start && w.end <= c.end)
                  .map((w) => (
                    <button
                      key={w.index}
                      className={
                        c.deleted_words.includes(w.index)
                          ? "deleted"
                          : cursor >= w.start && cursor < w.end
                            ? "spoken"
                            : ""
                      }
                      onClick={() => toggle(w.index)}
                      onDoubleClick={() => seek(w.start)}
                      title={`${time(w.start)} · click to remove / restore`}
                    >
                      {w.text}
                    </button>
                  ))}
              </div>
              <button
                className="text-button"
                onClick={() => setC({ ...c, deleted_words: [] })}
              >
                Restore all words
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
