import React, { useState, useEffect, useMemo, useRef } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import {
  Layers3,
  FolderOpen,
  Undo2,
  Redo2,
  Download,
  History,
  LoaderCircle,
  Check,
  PanelLeftClose,
  PanelLeftOpen,
  Lightbulb,
  X,
  PanelRightClose,
  PanelRightOpen,
} from "lucide-react";
import {
  api,
  setToken,
  Button,
  Drawer,
  uid,
  applyPreview,
  Field,
} from "./workspace-ui.jsx";
import { WorkspaceDiagram } from "./workspace-diagram.jsx";
import {
  DocumentPanel,
  EntityPanel,
  Suggestions,
  TopicPanel,
  NoteEditor,
} from "./workspace-panels.jsx";
import { StartPanel, HistoryPanel } from "./workspace-drawers.jsx";
import { ReviewDiagnostics } from "./review-diagnostics.jsx";
import { pollJob } from "./workbench-api.js";
import { readableText } from "./review-labels.js";
import { reviewProgress } from "./review-status.js";
import "./workspace.css";
import { useModelSettings, ModelSettings } from "./model-settings.jsx";
import {
  ChangePreview,
  TidPanel,
  AssumptionsPanel,
  AssistantPanel,
} from "./engineering-panels.jsx";

function Workspace({
  project,
  commit,
  busy,
  error,
  onError,
  history,
  onHistoryClose,
  onEditing,
  onContextChange,
}) {
  const [selection, setSelection] = useState(null),
    [sourceId, setSourceId] = useState(null),
    [topicId, setTopicId] = useState(null),
    [draft, setDraft] = useState(null),
    [noteOpen, setNoteOpen] = useState(false),
    [markers, setMarkers] = useState(true),
    [left, setLeft] = useState(() => window.innerWidth >= 900),
    [right, setRight] = useState(() => window.innerWidth >= 560),
    [widths, setWidths] = useState([290, 360]),
    [focusMode, setFocusMode] = useState("");
  const draftVersion = useRef(null);
  useEffect(() => {
    const editing = !!draft || noteOpen;
    onEditing(editing);
    if (editing && draftVersion.current === null)
      draftVersion.current = project.version;
    if (!editing) draftVersion.current = null;
  }, [!!draft, noteOpen, project.version, onEditing]);
  const save = async (...args) => {
    if (
      draftVersion.current !== null &&
      draftVersion.current !== project.version
    ) {
      onError(
        "Düzenleme sırasında çalışma güncellendi. Vazgeç ile taslağı kapatıp güncel öğeyi tekrar düzenleyin.",
      );
      return false;
    }
    return commit(...args);
  };
  const architecture = project.state.architecture,
    active = project.topics.find((t) => t.id === topicId);
  const object = selection
    ? architecture[
        selection.kind === "component" ? "components" : "connections"
      ].find((o) => o.id === selection.id)
    : null;
  const changes = useMemo(
    () =>
      !draft
        ? []
        : draft.mode === "proposal"
          ? draft.changes
          : [
              {
                kind: draft.kind,
                id: draft.value.id,
                action:
                  draft.mode === "remove"
                    ? "remove"
                    : draft.original
                      ? "update"
                      : "add",
                value: draft.value,
              },
            ],
    [draft],
  );
  const shown = useMemo(
    () => applyPreview(architecture, changes),
    [architecture, changes],
  );
  const safe = (fn) => {
    if (draft || noteOpen) {
      onError("Önce açık düzenlemeyi uygulayın veya Vazgeç ile kapatın.");
      return;
    }
    onError("");
    fn();
  };
  const select = (s) =>
    safe(() => {
      setSelection(s);
      onContextChange(s);
      setRight(true);
      setFocusMode("object");
      const o = architecture[
        s.kind === "component" ? "components" : "connections"
      ].find((o) => o.id === s.id);
      if (o?.evidence.length) {
        setSourceId(o.evidence[0].requirement_id);
        setLeft(true);
      }
    });
  const source = (id) => {
    onContextChange({ source_id: id, document: "current" });
    setSourceId(id);
    setLeft(true);
    if (!draft) setFocusMode("source");
  };
  const topic = (id) =>
    safe(() => {
      setTopicId(id);
      setSelection(null);
      setRight(true);
      setFocusMode("topic");
      const t = project.topics.find((t) => t.id === id);
      if (t?.source_ids.length) {
        setSourceId(t.source_ids[0]);
        setLeft(true);
      }
    });
  const edit = (kind, o, value = o) => {
    onError("");
    setDraft({
      mode: "entity",
      kind,
      original: o,
      value: structuredClone(value),
    });
  };
  const add = (kind, params) =>
    safe(() => {
      setRight(true);
      setNoteOpen(false);
      const value =
        kind === "component"
          ? {
              id: uid("component"),
              name: "",
              category: "component",
              description: "",
              evidence: [],
            }
          : {
              id: uid("if"),
              source: params?.source || "",
              target: params?.target || "",
              type: "unknown",
              protocol: "",
              label: "",
              description: "",
              evidence: [],
            };
      setDraft({ mode: "entity", kind, original: null, value });
    });
  const cancel = (removed, applied = false) => {
    if (draft?.mode === "entity" && !removed && (draft.original || applied))
      setSelection({ kind: draft.kind, id: draft.value.id });
    if (removed) setSelection(null);
    setDraft(null);
    onError("");
  };
  let focus =
    focusMode === "topic"
      ? active?.object_ids || []
      : focusMode === "object"
        ? [selection?.id].filter(Boolean)
        : focusMode === "source"
          ? [...architecture.components, ...architecture.connections]
              .filter((o) =>
                o.evidence.some((e) => e.requirement_id === sourceId),
              )
              .map((o) => o.id)
          : [];
  const resize = (side, e) => {
    const start = e.clientX,
      base = widths[side];
    const move = (event) =>
      setWidths((v) =>
        v.map((n, i) =>
          i === side
            ? Math.max(
                230,
                Math.min(
                  500,
                  base + (event.clientX - start) * (side === 0 ? 1 : -1),
                ),
              )
            : n,
        ),
      );
    const end = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
  };
  return (
    <>
      <div className="studio-bar">
        <div className="inline">
          <button
            className="icon-button"
            aria-label={left ? "Belge panelini daralt" : "Belge panelini aç"}
            onClick={() => setLeft(!left)}
          >
            {left ? <PanelLeftClose size={17} /> : <PanelLeftOpen size={17} />}
          </button>
          <span>
            {architecture.components.length} bileşen <i>·</i>{" "}
            {architecture.connections.length} bağlantı
          </span>
        </div>
        <span className="studio-hint">
          Belgeyi gör. Şemayı düzenle. Öneriyi değerlendir.
        </span>
        <button
          className="icon-button"
          aria-label={
            right ? "Düzenleme panelini daralt" : "Düzenleme panelini aç"
          }
          onClick={() => setRight(!right)}
        >
          {right ? <PanelRightClose size={17} /> : <PanelRightOpen size={17} />}
        </button>
      </div>
      <div
        className={`studio ${left ? "" : "document-hidden"} ${right ? "" : "inspector-hidden"}`}
        style={{
          "--document-width": widths[0] + "px",
          "--inspector-width": widths[1] + "px",
        }}
      >
        <div className="document-slot">
          <DocumentPanel
            {...{ project, sourceId }}
            selectedObject={draft?.mode === "entity" ? draft.value : object}
            onSource={source}
            onSelect={select}
            canAttach={
              draft?.mode === "entity" ||
              (draft?.mode === "proposal" && draft.sourceTarget != null)
            }
            onAttach={(ev) =>
              setDraft((d) => {
                const addEvidence = (o) => ({
                  ...o,
                  evidence: [
                    ...(o.evidence || []).filter(
                      (e) => e.requirement_id !== ev.requirement_id,
                    ),
                    ev,
                  ],
                });
                if (d.mode === "entity")
                  return { ...d, value: addEvidence(d.value) };
                return {
                  ...d,
                  changes: d.changes.map((c, i) => {
                    if (i !== d.sourceTarget) return c;
                    const old = architecture[
                      c.kind === "component" ? "components" : "connections"
                    ].find((o) => o.id === c.id);
                    return {
                      ...c,
                      value: addEvidence({ ...old, ...c.value, id: c.id }),
                    };
                  }),
                };
              })
            }
          />
        </div>
        <div
          className="panel-resizer document-resizer"
          role="separator"
          aria-label="Belge paneli genişliği"
          aria-valuenow={widths[0]}
          aria-valuemin={230}
          aria-valuemax={500}
          tabIndex={0}
          onPointerDown={(e) => resize(0, e)}
          onKeyDown={(e) => {
            if (["ArrowLeft", "ArrowRight"].includes(e.key)) {
              e.preventDefault();
              setWidths(([l, r]) => [
                Math.max(
                  230,
                  Math.min(500, l + (e.key === "ArrowRight" ? 20 : -20)),
                ),
                r,
              ]);
            }
          }}
        />
        <ReactFlowProvider>
          <WorkspaceDiagram
            {...{ project, selection, commit, busy, markers }}
            architecture={shown}
            focus={focus}
            focusKey={
              focusMode +
              ":" +
              (focusMode === "topic"
                ? topicId
                : focusMode === "source"
                  ? sourceId
                  : selection?.id)
            }
            onSelect={select}
            onFinding={topic}
            onNew={add}
            preview={!!draft}
            onMarkers={() => setMarkers(!markers)}
          />
        </ReactFlowProvider>
        <div
          className="panel-resizer inspector-resizer"
          role="separator"
          aria-label="Düzenleme paneli genişliği"
          aria-valuenow={widths[1]}
          aria-valuemin={230}
          aria-valuemax={500}
          tabIndex={0}
          onPointerDown={(e) => resize(1, e)}
          onKeyDown={(e) => {
            if (["ArrowLeft", "ArrowRight"].includes(e.key)) {
              e.preventDefault();
              setWidths(([l, r]) => [
                l,
                Math.max(
                  230,
                  Math.min(500, r + (e.key === "ArrowLeft" ? 20 : -20)),
                ),
              ]);
            }
          }}
        />
        <aside className="work-panel">
          <Suggestions
            project={project}
            activeId={topicId}
            onTopic={topic}
            onNewFinding={() => safe(() => setNoteOpen(true))}
          />
          {error && (
            <div className="banner error" role="alert">
              {error}
              <button
                className="icon-button"
                aria-label="Mesajı kapat"
                onClick={() => onError("")}
              >
                <X size={14} />
              </button>
            </div>
          )}
          {active && (
            <details
              className="active-topic"
              open={!selection || draft?.mode === "proposal"}
            >
              <summary>{active.title}</summary>
              <TopicPanel
                key={active.id}
                {...{ project, draft, setDraft, busy }}
                commit={save}
                topic={active}
                onTopic={topic}
                onSource={source}
                onSelect={select}
                onPickSource={() => setLeft(true)}
                onClose={() => setTopicId(null)}
              />
            </details>
          )}
          {noteOpen ? (
            <NoteEditor
              {...{ project, selection, busy }}
              commit={save}
              onClose={() => setNoteOpen(false)}
            />
          ) : (
            draft?.mode !== "proposal" &&
            (object || draft || !active) && (
              <EntityPanel
                key={draft?.value?.id || selection?.id || "empty"}
                {...{
                  project,
                  selection,
                  object,
                  draft,
                  setDraft,
                  busy,
                }}
                commit={save}
                onEdit={edit}
                onSource={source}
                onCancel={cancel}
                onDelete={(kind, o) =>
                  setDraft({ mode: "remove", kind, original: o, value: o })
                }
                onNewFinding={() => safe(() => setNoteOpen(true))}
              />
            )
          )}
          {!draft &&
            !noteOpen &&
            !!(
              project.state.analysis.missing_information?.length ||
              project.state.analysis.open_questions?.length
            ) && (
              <details className="workspace-assumptions">
                <summary>Açık bilgiler ve sorular</summary>
                {[
                  ...new Set([
                    ...project.state.analysis.missing_information,
                    ...project.state.analysis.open_questions,
                  ]),
                ].map((text, i) => (
                  <p key={i}>{readableText(text, project)}</p>
                ))}
              </details>
            )}
        </aside>
      </div>
      {history && (
        <Drawer title="Çalışmanın geçmişi" onClose={onHistoryClose}>
          <HistoryPanel
            {...{ project }}
            onSelect={(s) => {
              if (["component", "connection"].includes(s.kind)) select(s);
              else if (["source", "requirement"].includes(s.kind)) source(s.id);
              else topic(project.topics.find((t) => t.finding_id === s.id)?.id);
              onHistoryClose();
            }}
          />
        </Drawer>
      )}
    </>
  );
}
export default function App() {
  const [bootstrap, setBootstrap] = useState(null),
    [project, setProject] = useState(null),
    [drawer, setDrawer] = useState(null),
    [busy, setBusy] = useState(false),
    [editing, setEditing] = useState(false),
    [error, setError] = useState(""),
    [job, setJob] = useState(null),
    [retryOnly, setRetryOnly] = useState(false),
    [connectionError, setConnectionError] = useState(""),
    [stopping, setStopping] = useState(false),
    [actor, setActor] = useState(
      () => localStorage.getItem("workbench.actor") || "Mühendis",
    );
  const [preview, setPreview] = useState(null),
    [previewError, setPreviewError] = useState(""),
    [assistantRequest, setAssistantRequest] = useState(null),
    [mainTab, setMainTab] = useState("schema"),
    [assistantOpen, setAssistantOpen] = useState(false),
    [selectionContext, setSelectionContext] = useState(null),
    [settingsOpen, setSettingsOpen] = useState(false);
  const modelSettings = useModelSettings(bootstrap?.profiles);
  const previewResolver = useRef(null);
  const lock = useRef(false);
  const refresh = async () => {
    const b = await api("/bootstrap");
    setToken(b.token);
    setBootstrap(b);
    return b;
  };
  const load = (p) => {
    setProject(p);
    localStorage.setItem("workbench.project", p.id);
    setError("");
  };
  useEffect(() => {
    refresh()
      .then(async (b) => {
        const saved = localStorage.getItem("workbench.project");
        const p = b.projects.find((p) => p.id === saved) || b.projects[0];
        if (p) load(await api("/projects/" + p.id));
        setJob(
          b.jobs.find((j) => ["queued", "running"].includes(j.status)) ||
            b.jobs.find(
              (j) =>
                (j.mode === "review" || j.calls !== undefined) &&
                j.project_id === p?.id,
            ) ||
            null,
        );
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    setSelectionContext(null);
    setAssistantRequest(null);
  }, [project?.id]);
  useEffect(() => localStorage.setItem("workbench.actor", actor), [actor]);
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    return pollJob({
      read: () => api("/jobs/" + job.id),
      onResult: async (j) => {
        if (
          ["completed", "partial"].includes(j.status) &&
          j.project_id &&
          j.mode !== "assistant"
        ) {
          load(await api("/projects/" + j.project_id));
          await refresh();
        }
        setJob(j);
        setConnectionError("");
        if (!["queued", "running"].includes(j.status)) setStopping(false);
      },
      onError: (e) => setConnectionError(e.message),
    });
  }, [job?.id, job?.status]);
  const directCommit = async (action, id, value, reason = "") => {
    if (lock.current) return false;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const p = await api(`/projects/${project.id}/changes`, {
        version: project.version,
        actor: actor.trim() || "Mühendis",
        action,
        id,
        value,
        reason,
      });
      load(p);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      lock.current = false;
      setBusy(false);
    }
  };
  const onCommands = async (
    commands,
    reason = "Mühendis düzenlemesi",
    version = project.version,
  ) => {
    if (lock.current || previewResolver.current) return false;
    lock.current = true;
    setBusy(true);
    setError("");
    setPreviewError("");
    try {
      const result = await api(`/projects/${project.id}/preview`, {
        version,
        commands,
        actor: actor.trim() || "Mühendis",
        reason: reason || "Mühendis düzenlemesi",
      });
      setPreview(result);
      return await new Promise((resolve) => {
        previewResolver.current = resolve;
        lock.current = false;
        setBusy(false);
      });
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      lock.current = false;
      setBusy(false);
    }
  };
  const commit = (action, id, value, reason = "") =>
    ["undo", "redo", "layout"].includes(action)
      ? directCommit(action, id, value, reason)
      : onCommands(
          [{ action, id, value, reason }],
          reason || "Mühendis düzenlemesi",
        );
  const closePreview = (result) => {
    setPreview(null);
    setPreviewError("");
    const resolve = previewResolver.current;
    previewResolver.current = null;
    resolve?.(result);
  };
  const applyChanges = async () => {
    if (project.version !== preview.version) {
      setPreviewError("Proje değişti. Güncel sürümde yeniden önizleyin.");
      return;
    }
    if (
      await directCommit(
        "apply_change_set",
        "",
        { preview_id: preview.id },
        preview.reason,
      )
    )
      closePreview(true);
    else
      setPreviewError(
        "Değişiklikler uygulanamadı. Projeyi yenileyip tekrar önizleyin.",
      );
  };
  const repreview = async (commands, assumption_reviews = {}) => {
    setBusy(true);
    setPreviewError("");
    try {
      setPreview(
        await api(`/projects/${project.id}/preview`, {
          version: preview.version,
          commands,
          assumption_reviews,
          actor: actor.trim() || "Mühendis",
          reason: preview.reason,
        }),
      );
    } catch (e) {
      setPreviewError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const askAssistant = (request) => {
    setAssistantRequest(request);
    if (request?.selection) setSelectionContext(request.selection);
    setAssistantOpen(true);
  };
  const running = job && ["queued", "running"].includes(job.status);
  return (
    <div className="studio-app">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">
            <Layers3 size={23} />
          </span>
          <span>
            Mimari <b>Atölyesi</b>
            <small>Belgeden tasarıma</small>
          </span>
        </div>
        <div className="header-center">
          <span className="project-title">
            {project?.name || "Mühendislik çalışma alanı"}
          </span>
          {project && (
            <span className="save-state">
              {busy ? (
                <LoaderCircle size={13} className="spin" />
              ) : (
                <Check size={13} />
              )}{" "}
              {busy
                ? "Kaydediliyor"
                : editing
                  ? "Önizleme · henüz uygulanmadı"
                  : "Kaydedildi"}
            </span>
          )}
        </div>
        <div className="header-actions">
          <label className="reviewer">
            <span>Mühendis</span>
            <input
              aria-label="Mühendis adı"
              value={actor}
              onChange={(e) => setActor(e.target.value)}
            />
          </label>
          <Button
            icon={FolderOpen}
            disabled={!bootstrap || busy || editing}
            onClick={() => {
              refresh();
              setDrawer("open");
            }}
          >
            Belge aç
          </Button>
          <Button disabled={!bootstrap} onClick={() => setSettingsOpen(true)}>
            Model Ayarları
          </Button>
          {project && (
            <>
              <button
                className="icon-button"
                aria-label="Son işlemi geri al"
                disabled={busy || editing || !project.can_undo}
                onClick={() => commit("undo", "", {})}
              >
                <Undo2 size={18} />
              </button>
              <button
                className="icon-button"
                aria-label="Geri alınan işlemi yinele"
                disabled={busy || editing || !project.can_redo}
                onClick={() => commit("redo", "", {})}
              >
                <Redo2 size={18} />
              </button>
              <button
                className="icon-button"
                aria-label="Geçmişi aç"
                onClick={() => {
                  setMainTab("schema");
                  setDrawer("history");
                }}
              >
                <History size={18} />
              </button>
              <a
                className="icon-button"
                aria-label="Çalışmayı dışa aktar"
                href={`/api/projects/${project.id}/export`}
              >
                <Download size={18} />
              </a>
              <Button
                className="primary"
                icon={Lightbulb}
                disabled={busy || running || editing}
                onClick={() => {
                  setRetryOnly(false);
                  setDrawer("review");
                }}
              >
                Yeni değerlendirme
              </Button>
            </>
          )}
        </div>
      </header>
      {job && job.mode !== "assistant" && (
        <div
          className={"studio-job " + (job.status === "failed" ? "failed" : "")}
          role="status"
        >
          {running && !connectionError && (
            <LoaderCircle className="spin" size={15} />
          )}
          <span>
            {job.mode === "fixture" ? "Çevrimdışı örnek · " : ""}
            {connectionError || job.message}
            <JobProgress job={job} online={!connectionError} />
          </span>
          {running && (
            <Button
              disabled={!!connectionError || stopping}
              onClick={async () => {
                setStopping(true);
                try {
                  await api(`/jobs/${job.id}/cancel`, {});
                } catch (e) {
                  setStopping(false);
                  setConnectionError(e.message);
                }
              }}
            >
              {stopping ? "Durduruluyor…" : "Değerlendirmeyi durdur"}
            </Button>
          )}
          {job.mode === "assistant" && (
            <Button onClick={() => askAssistant(null)}>Yanıtı aç</Button>
          )}
          {(job.mode === "review" || job.calls !== undefined) && (
            <Button onClick={() => setDrawer("diagnostics")}>
              Değerlendirme ayrıntıları
            </Button>
          )}
          {project &&
            ((job.status === "partial" && job.project_id === project.id) ||
              (["failed", "interrupted", "cancelled"].includes(job.status) &&
                job.mode === "review" &&
                job.project_id === project.id)) && (
              <Button
                disabled={busy || editing}
                onClick={() => {
                  setRetryOnly(!!job.can_retry_missing);
                  setDrawer("review");
                }}
              >
                {job.can_retry_missing
                  ? "Eksik bölümleri yeniden dene"
                  : "Değerlendirmeyi yeniden dene"}
              </Button>
            )}
          {!running && (
            <button
              className="icon-button"
              aria-label="Analiz mesajını kapat"
              onClick={() => setJob(null)}
            >
              <X size={15} />
            </button>
          )}
        </div>
      )}
      {project ? (
        <>
          <nav
            className="main-tabs"
            aria-label="Çalışma alanları"
            role="tablist"
          >
            {[
              ["schema", "Şema"],
              ["tid", "TİD"],
              ["assumptions", "Varsayımlar"],
            ].map(([id, label]) => (
              <button
                key={id}
                id={"tab-" + id}
                role="tab"
                aria-selected={mainTab === id}
                aria-controls={"panel-" + id}
                onClick={() => setMainTab(id)}
              >
                {label}
                {id === "assumptions" && (
                  <span>
                    {
                      project.state.assumption_records.filter(
                        (r) =>
                          r.status === "pending" ||
                          r.status === "waiting" ||
                          r.stale,
                      ).length
                    }
                  </span>
                )}
              </button>
            ))}
          </nav>
          {error && mainTab !== "schema" && (
            <p className="banner error" role="alert">
              {readableText(error, project)}
            </p>
          )}
          <div
            className="main-tab-panel schema-panel"
            id="panel-schema"
            role="tabpanel"
            aria-labelledby="tab-schema"
            hidden={mainTab !== "schema"}
          >
            <Workspace
              key={project.id}
              {...{ project, commit, busy, error }}
              onError={setError}
              onContextChange={setSelectionContext}
              onEditing={setEditing}
              history={drawer === "history"}
              onHistoryClose={() => setDrawer(null)}
            />
          </div>
          <div
            className="main-tab-panel"
            id="panel-tid"
            role="tabpanel"
            aria-labelledby="tab-tid"
            hidden={mainTab !== "tid"}
          >
            <TidPanel
              key={project.id}
              {...{ project, busy, onCommands }}
              onAssistant={askAssistant}
              onContextChange={setSelectionContext}
            />
          </div>
          <div
            className="main-tab-panel"
            id="panel-assumptions"
            role="tabpanel"
            aria-labelledby="tab-assumptions"
            hidden={mainTab !== "assumptions"}
          >
            <AssumptionsPanel
              key={project.id}
              {...{ project, busy, onCommands }}
              onAssistant={askAssistant}
            />
          </div>
          {bootstrap && (
            <AssistantPanel
              key={project.id}
              {...{
                project,
                bootstrap,
                actor,
                job,
                busy,
                onCommands,
                modelSettings,
                connectionError,
              }}
              onJob={setJob}
              open={assistantOpen}
              onOpenChange={setAssistantOpen}
              request={assistantRequest}
              onRequestHandled={() => setAssistantRequest(null)}
              context={selectionContext}
              onClearContext={() => setSelectionContext(null)}
            />
          )}
        </>
      ) : (
        <main className="welcome">
          <div className="welcome-copy">
            <span className="eyebrow">MÜHENDİSLİK ÇALIŞMA ALANI</span>
            <h1>
              Belgeni aç.
              <br />
              Tasarımı birlikte geliştir.
            </h1>
            <p>
              Kaynağı gör, şemayı düzenle, yapay zekâ önerilerini kendi
              kararınla uygula.
            </p>
            {error && <p role="alert">{error}</p>}
            <Button
              className="primary"
              icon={FolderOpen}
              disabled={!bootstrap}
              onClick={() => setDrawer("open")}
            >
              Belge veya çalışma aç
            </Button>
          </div>
          <div className="welcome-illustration">
            <Layers3 size={70} />
            <p>Kaynak · Mimari · Mühendis kararı</p>
          </div>
        </main>
      )}
      {preview && (
        <Drawer
          title="Değişiklik önizlemesi"
          className="centered-dialog preview-dialog"
          onClose={() => {
            if (!busy) closePreview(false);
          }}
        >
          <ChangePreview
            key={preview.id}
            {...{ preview, project, busy }}
            error={previewError}
            onApply={applyChanges}
            onCancel={() => closePreview(false)}
            onRepreview={repreview}
          />
        </Drawer>
      )}
      {["open", "review"].includes(drawer) && bootstrap && (
        <Drawer
          title={
            drawer === "review"
              ? "Güncel tasarımı değerlendir"
              : "Belge veya çalışma aç"
          }
          onClose={() => setDrawer(null)}
        >
          <StartPanel
            {...{ bootstrap, project, modelSettings }}
            onModelSettings={() => setSettingsOpen(true)}
            reevaluate={drawer === "review"}
            retryJob={drawer === "review" && retryOnly ? job : null}
            onClose={() => setDrawer(null)}
            onProject={(p) => {
              load(p);
              refresh();
            }}
            onJob={setJob}
          />
        </Drawer>
      )}
      {settingsOpen && bootstrap && (
        <Drawer
          title="Model Ayarları"
          className="centered-dialog settings-dialog"
          onClose={() => setSettingsOpen(false)}
        >
          <ModelSettings
            profiles={bootstrap.profiles}
            modelSettings={modelSettings}
            onClose={() => setSettingsOpen(false)}
          />
        </Drawer>
      )}
      {drawer === "diagnostics" && job && (
        <Drawer
          title="Değerlendirme ayrıntıları"
          onClose={() => setDrawer(null)}
        >
          <ReviewDiagnostics job={job} />
        </Drawer>
      )}
    </div>
  );
}

function JobProgress({ job, online }) {
  const [clock, setClock] = useState(Date.now());
  const active = ["queued", "running"].includes(job.status);
  useEffect(() => {
    if (!active || !online) return;
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active, online]);
  if (!online)
    return (
      <small className="job-progress">
        Sunucuya ulaşılamıyor; değerlendirmenin devam ettiği doğrulanamadı.
      </small>
    );
  // Old/interrupted jobs have no reliable finish time; do not show time since creation as duration.
  if (!active && !job.finished_at) return null;
  const start = Date.parse(job.started_at || job.created);
  const end = job.finished_at ? Date.parse(job.finished_at) : clock;
  const seconds = Math.max(0, Math.floor((end - start) / 1000));
  const duration = (n) =>
    `${Math.floor(n / 60)}:${String(n % 60).padStart(2, "0")}`;
  return (
    <small className="job-progress">
      {reviewProgress(job) ? `${reviewProgress(job)} · ` : ""}
      {active ? "Geçen süre" : "Süre"}: {duration(seconds)}
      {active && job.timeout
        ? ` · Toplam süre sınırı: ${duration(job.timeout)}`
        : ""}
    </small>
  );
}
