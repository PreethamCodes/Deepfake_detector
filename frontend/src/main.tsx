import { lazy, Suspense, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Archive,
  ChevronRight,
  CircleHelp,
  LayoutDashboard,
  Menu,
  PanelLeftClose,
  RefreshCw,
  ScanLine,
  X,
} from "lucide-react";
import { api, type Analysis, type Entry, type Files } from "@/lib/api";
import { Notice } from "@/components/shared";
import { Dashboard, History, About } from "@/pages/Workspace";
import { Upload } from "@/pages/Upload";
import "@fontsource-variable/manrope/wght.css";
import "./styles.css";

const navigation = [
  { id: "dashboard", name: "Dashboard", icon: LayoutDashboard },
  { id: "analyze", name: "Media analysis", icon: ScanLine },
  { id: "history", name: "Investigation history", icon: Archive },
  { id: "about", name: "About SHODHA AI", icon: CircleHelp },
];
const currentRoute = () => location.hash.slice(2) || "dashboard";
const Report = lazy(() =>
  import("@/pages/Report").then((module) => ({ default: module.Report })),
);
const message = (error: unknown) =>
  error instanceof Error ? error.message : "Request failed. Please retry.";
function App() {
  const [route, setRoute] = useState(currentRoute);
  const [menu, setMenu] = useState(false);
  const [page, id, sub = ""] = route.split("/");
  const [revision, refresh] = useState(0);
  const [health, setHealth] = useState("Checking");
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [archiveError, setArchiveError] = useState("");
  const [record, setRecord] = useState<Analysis | null>(null);
  const [reportError, setReportError] = useState("");
  const [draft, setDraft] = useState<Files>({});
  const [last, setLast] = useState<{ id: string; files: Files } | null>(null);
  const [busy, setBusy] = useState(false);
  const [uploadError, setUploadError] = useState("");
  useEffect(() => {
    function change() {
      setRoute(currentRoute());
      setMenu(false);
      window.scrollTo(0, 0);
    }
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    let active = true;
    function check() {
      api
        .health()
        .then((x) => {
          if (active) setHealth(x.status === "ok" ? "Online" : "Offline");
        })
        .catch(() => {
          if (active) setHealth("Offline");
        });
    }
    check();
    const tick = setInterval(check, 30000);
    return () => {
      active = false;
      clearInterval(tick);
    };
  }, [revision]);
  useEffect(() => {
    let active = true;
    if (page === "dashboard" || page === "history") {
      setArchiveError("");
      api
        .history()
        .then((x) => {
          if (active) setEntries(x);
        })
        .catch((e) => {
          if (active) {
            setEntries(null);
            setArchiveError(message(e));
          }
        });
    }
    return () => {
      active = false;
    };
  }, [page, revision]);
  useEffect(() => {
    let active = true;
    if (page === "report" && id) {
      setReportError("");
      api
        .result(id)
        .then((r) => {
          if (active) setRecord(r);
        })
        .catch((e) => {
          if (active) {
            setReportError(message(e));
            setRecord(null);
          }
        });
    }
    return () => {
      active = false;
    };
  }, [page, id, revision]);
  useEffect(() => {
    document.title =
      page === "about"
        ? "About · SHODHA AI"
        : (navigation.find((n) => n.id === page)?.name || "Forensic report") +
          " · SHODHA AI";
  }, [page]);
  async function submit() {
    if (busy) return;
    setBusy(true);
    setUploadError("");
    try {
      const r = await api.submit(draft);
      setRecord(r);
      setLast({ id: r.analysis_id, files: draft });
      setDraft({});
      location.hash = "/report/" + r.analysis_id;
      refresh((x) => x + 1);
    } catch (e) {
      setUploadError(message(e));
    } finally {
      setBusy(false);
    }
  }
  const label =
    navigation.find((n) => n.id === page)?.name ||
    (page === "report" ? "Forensic report" : "Page unavailable");
  return (
    <div className="shell">
      <a
        className="skip"
        href="#main-content"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Skip to content
      </a>
      <aside className={"sidebar " + (menu ? "open" : "")}>
        <a href="#/dashboard" className="brand">
          <img src="/mark.svg" alt="" />
          <span>
            SHODHA<span> AI</span>
          </span>
        </a>
        <nav aria-label="Workspace navigation">
          {navigation.map(({ id, name, icon: Icon }) => (
            <a
              key={id}
              href={"#/" + id}
              aria-current={id === page ? "page" : undefined}
              className={id === page ? "current" : ""}
              onClick={() => setMenu(false)}
            >
              <Icon size={18} />
              {name}
            </a>
          ))}
        </nav>
        <div className="side-foot">
          <PanelLeftClose size={16} />
          <span>Local forensic workspace</span>
        </div>
      </aside>
      <div className="workspace">
        <header>
          <button
            className="menu-toggle icon-button"
            aria-label={menu ? "Close navigation" : "Open navigation"}
            aria-expanded={menu}
            onClick={() => setMenu(!menu)}
          >
            {menu ? <X /> : <Menu />}
          </button>
          <span className="crumb">
            Workspace <ChevronRight size={14} />
            <b>{label}</b>
          </span>
          <div
            className={"connection " + (health === "Online" ? "online" : "")}
          >
            <i />
            API {health.toLowerCase()}
          </div>
          <button
            className="icon-button"
            aria-label="Refresh workspace"
            title="Refresh workspace"
            onClick={() => refresh((x) => x + 1)}
          >
            <RefreshCw size={15} />
          </button>
        </header>
        <main id="main-content" tabIndex={-1}>
          <Suspense fallback={<p role="status">Opening report…</p>}>
            {health === "Offline" && (
              <Notice message="Backend offline. Start the local FastAPI server, then refresh the workspace." />
            )}
            {(page === "dashboard" || page === "history") && archiveError && (
              <Notice message={archiveError} />
            )}
            {page === "dashboard" ? (
              <Dashboard entries={entries} />
            ) : page === "history" ? (
              <History entries={entries} />
            ) : page === "about" ? (
              <About />
            ) : page === "analyze" ? (
              <Upload
                files={draft}
                setFiles={(v) => {
                  setDraft(v);
                  setUploadError("");
                }}
                onAnalyze={submit}
                busy={busy}
                error={uploadError}
              />
            ) : page === "report" && id ? (
              reportError ? (
                <Notice message={reportError} />
              ) : record?.analysis_id === id ? (
                <Report
                  key={id}
                  record={record}
                  files={last?.id === id ? last.files : {}}
                  tab={sub}
                />
              ) : (
                <p role="status">Loading forensic report…</p>
              )
            ) : (
              <p>
                Page unavailable. <a href="#/dashboard">Return to dashboard</a>
              </p>
            )}
          </Suspense>
        </main>
        <footer>
          <Activity size={14} />
          SHODHA AI <span>Uncovering the Truth Behind Digital Media.</span>
        </footer>
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
