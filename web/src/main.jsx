import React, {
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
} from "react";
import { createRoot } from "react-dom/client";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  MarkerType,
  useNodesState,
  useReactFlow,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import {
  Layers3,
  FolderOpen,
  Plus,
  ArrowUpRight,
  ArrowRightLeft,
  Check,
  CheckCheck,
  AlertTriangle,
  FileText,
  Network,
  Search,
  X,
  Pencil,
  Trash2,
  Undo2,
  Redo2,
  Download,
  History,
  ChevronRight,
  Link2,
  Lightbulb,
  GitCompareArrows,
  Play,
  LoaderCircle,
  CircleHelp,
  ShieldCheck,
  BookOpen,
  Save,
  Maximize,
  LayoutGrid,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import "@xyflow/react/dist/style.css";
import "./styles.css";

let csrf = "";
async function api(path, body) {
  const r = await fetch("/api" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", "X-Workbench-Token": csrf },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: "Sunucuya ulaşılamadı." }));
    const error = new Error(
      typeof e.detail === "string" ? e.detail : "Alanları kontrol edin.",
    );
    error.status = r.status;
    throw error;
  }
  return r.json();
}
const cats = {
  system: "Sistem",
  subsystem: "Alt sistem",
  component: "Bileşen",
  external: "Dış sistem",
};
const types = {
  data: "Veri",
  control: "Kontrol",
  power: "Güç",
  communication: "Haberleşme",
  mechanical: "Mekanik",
  thermal: "Termal",
  unknown: "Belirtilmemiş",
};
const coverageNames = {
  covered: "Karşılık seçilmiş",
  partially_covered: "Kısmen temsil edilmiş",
  unmapped: "Henüz eşleştirilmemiş",
  not_architectural: "Bağlam / başlık",
};
const decisionNames = {
  approved: "Onaylandı",
  accepted: "Bulgu kabul edildi",
  rejected: "Reddedildi",
  resolved: "Çözüldü olarak işaretlendi",
  merged: "Başka bulguyla birleştirildi",
  needs_review: "İnceleme gerekli",
};
const actions = {
  import: "İlk çıktı açıldı",
  upsert_component: "Bileşen düzenlendi",
  upsert_connection: "Bağlantı düzenlendi",
  delete_component: "Bileşen kaldırıldı",
  delete_connection: "Bağlantı kaldırıldı",
  set_decision: "İnceleme kararı",
  set_coverage: "Kaynak eşleştirmesi",
  set_assumption: "Varsayım düzenlendi",
  add_finding: "Mühendis bulgusu",
  edit_finding: "Bulgu düzenlendi",
  layout: "Şema yerleşimi",
  undo: "Geri alındı",
  redo: "Yinelendi",
};
const loc = (s) =>
  (s?.locations || [])
    .map((x) => x.replace("line:", "Satır ").replace("page:", "Sayfa "))
    .join(", ");
const uid = (p) => p + "_" + crypto.randomUUID().slice(0, 8);
const date = (v) => new Date(v).toLocaleString("tr-TR");
const clone = (x) => JSON.parse(JSON.stringify(x));
function Button({ icon: Icon, children, className = "", ...props }) {
  return (
    <button className={"button " + className} {...props}>
      {Icon && <Icon size={16} />}
      <span>{children}</span>
    </button>
  );
}
function Badge({ tone = "", children }) {
  return <span className={"badge " + tone}>{children}</span>;
}
function Empty({ icon: Icon = BookOpen, title, children }) {
  return (
    <div className="empty">
      <Icon size={30} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function DecisionBadge({ decision }) {
  return (
    <Badge
      tone={
        decision?.stale
          ? "amber"
          : ["approved", "resolved"].includes(decision?.status)
            ? "green"
            : ""
      }
    >
      {decision?.stale
        ? "Yeniden incelenmeli"
        : decisionNames[decision?.status] || "Henüz incelenmedi"}
    </Badge>
  );
}
const ErrorContext = React.createContext("");
function Modal({ title, subtitle, children, onClose, wide = false }) {
  const error = React.useContext(ErrorContext);
  const ref = useRef();
  useEffect(() => {
    const prev = document.activeElement;
    const dialog = ref.current;
    dialog.showModal();
    return () => {
      dialog.close();
      prev?.focus?.();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={"modal " + (wide ? "wide" : "")}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <header>
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Pencereyi kapat"
        >
          <X size={20} />
        </button>
      </header>
      {error && (
        <div className="banner error" role="alert">
          <AlertTriangle size={17} />
          <span>{error}</span>
        </div>
      )}
      {children}
    </dialog>
  );
}
function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span>{label}</span>
      {React.isValidElement(children)
        ? React.cloneElement(children, {
            "aria-label": children.props["aria-label"] || label,
          })
        : children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

function ComponentNode({ data, selected }) {
  return (
    <div
      className={`arch-node ${selected ? "selected" : ""} ${data.dim ? "dim" : ""} ${data.highlight ? "highlight" : ""} ${data.category === "external" ? "external" : ""}`}
    >
      <Handle type="target" position={Position.Top} />
      <Handle type="source" position={Position.Bottom} />
      <div className="node-top">
        <span className="node-icon">
          <Layers3 size={15} />
        </span>
        <span>{cats[data.category]}</span>
        {data.changed && (
          <span className="edit-dot" title="Mühendis düzenlemesi" />
        )}
      </div>
      <strong>{data.name}</strong>
      <div className="node-meta">
        <span>{data.evidenceCount} kaynak</span>
        {data.issueCount > 0 && (
          <span className="node-warning">
            <AlertTriangle size={12} />
            {data.issueCount}
          </span>
        )}
        {data.approved && <CheckCheck size={14} />}
      </div>
    </div>
  );
}
const nodeTypes = { architecture: ComponentNode };
function layout(arch) {
  const g = new dagre.graphlib.Graph({ multigraph: true });
  g.setGraph({
    rankdir: "TB",
    nodesep: 70,
    ranksep: 65,
    marginx: 40,
    marginy: 40,
  });
  g.setDefaultEdgeLabel(() => ({}));
  arch.components.forEach((c) => g.setNode(c.id, { width: 210, height: 100 }));
  arch.connections.forEach((e) => {
    if (g.hasNode(e.source) && g.hasNode(e.target))
      g.setEdge(e.source, e.target, {}, e.id);
  });
  dagre.layout(g);
  return Object.fromEntries(
    arch.components.map((c) => [
      c.id,
      { x: g.node(c.id).x - 105, y: g.node(c.id).y - 50 },
    ]),
  );
}

function Diagram({
  project,
  selection,
  onSelect,
  commit,
  openEditor,
  busy,
  railOpen,
  setRailOpen,
}) {
  const a = project.state.architecture,
    rf = useReactFlow();
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const auto = useMemo(() => layout(a), [project.id, project.version]);
  const selectedSource = selection?.kind === "source" ? selection.id : null;
  const related = useMemo(
    () =>
      new Set(
        [...a.components, ...a.connections]
          .filter((o) =>
            o.evidence.some((e) => e.requirement_id === selectedSource),
          )
          .map((o) => o.id),
      ),
    [a, selectedSource],
  );
  useEffect(() => {
    setNodes(
      a.components.map((c) => ({
        id: c.id,
        type: "architecture",
        position: project.state.positions[c.id] || auto[c.id],
        data: {
          ...c,
          evidenceCount: c.evidence.length,
          issueCount: project.issues.filter((i) => i.object_id === c.id).length,
          changed: !!project.state.provenance["component:" + c.id],
          approved:
            project.state.decisions["component:" + c.id]?.status ===
              "approved" &&
            !project.state.decisions["component:" + c.id]?.stale,
        },
        selected: selection?.kind === "component" && selection.id === c.id,
      })),
    );
  }, [project.id, project.version]);
  const shownNodes = nodes.map((n) => ({
    ...n,
    selected: selection?.kind === "component" && selection.id === n.id,
    data: {
      ...n.data,
      highlight: related.has(n.id),
      dim: !!selectedSource && !related.has(n.id),
    },
  }));
  const ids = new Set(a.components.map((c) => c.id));
  const edges = a.connections
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e) => {
      const selected =
        selection?.kind === "connection" && selection.id === e.id;
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        type: "smoothstep",
        label: e.protocol || types[e.type],
        selected,
        style: {
          stroke: selected
            ? "#087f8c"
            : e.type === "power"
              ? "#bc8640"
              : "#768b9c",
          strokeWidth: selected ? 2.6 : 1.6,
          strokeDasharray: e.type === "power" ? "6 4" : undefined,
          opacity: selectedSource && !related.has(e.id) ? 0.2 : 1,
        },
        labelStyle: { fontSize: 12, fontWeight: 500, fill: "#22394a" },
        labelBgStyle: { fill: selected ? "#dcf4f2" : "#fff", fillOpacity: 1 },
        labelBgPadding: [8, 5],
        labelBgBorderRadius: 5,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: selected
            ? "#087f8c"
            : e.type === "power"
              ? "#bc8640"
              : "#768b9c",
        },
        interactionWidth: 26,
        ariaLabel: `${e.id}: ${e.protocol || types[e.type]}`,
      };
    });
  useEffect(() => {
    const handle = requestAnimationFrame(() =>
      rf.fitView({ padding: 0.2, duration: 250, minZoom: 0.35, maxZoom: 1 }),
    );
    return () => cancelAnimationFrame(handle);
  }, [project.id]);
  return (
    <div className="canvas-area">
      <div className="canvas-toolbar">
        <div className="toolbar-group">
          <button
            className="icon-button"
            aria-label={railOpen ? "Gezgini daralt" : "Gezgini aç"}
            onClick={() => setRailOpen(!railOpen)}
          >
            {railOpen ? (
              <PanelLeftClose size={17} />
            ) : (
              <PanelLeftOpen size={17} />
            )}
          </button>
          <span className="canvas-title">Mimari çalışma alanı</span>
        </div>
        <div className="toolbar-group">
          <Button
            icon={Plus}
            disabled={busy}
            onClick={() => openEditor("component")}
          >
            Bileşen
          </Button>
          <Button
            icon={Link2}
            disabled={busy || a.components.length < 2}
            onClick={() => openEditor("connection")}
          >
            Bağlantı
          </Button>
          <button
            className="icon-button"
            aria-label="Otomatik yerleştir"
            disabled={busy}
            onClick={async () => {
              if (await commit("layout", "", auto, "Otomatik şema yerleşimi"))
                setTimeout(
                  () => rf.fitView({ padding: 0.2, duration: 200 }),
                  50,
                );
            }}
          >
            <LayoutGrid size={17} />
          </button>
          <button
            className="icon-button"
            aria-label="Şemayı ekrana sığdır"
            onClick={() => rf.fitView({ padding: 0.2, duration: 250 })}
          >
            <Maximize size={17} />
          </button>
        </div>
      </div>
      <ReactFlow
        nodes={shownNodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onNodeClick={(_, n) => onSelect({ kind: "component", id: n.id })}
        onEdgeClick={(_, e) => onSelect({ kind: "connection", id: e.id })}
        onConnect={(params) => openEditor("connection", null, params)}
        onNodeDragStop={(_, node) =>
          commit(
            "layout",
            "",
            { [node.id]: node.position },
            "Bileşenin şemadaki konumu değiştirildi",
          )
        }
        nodesDraggable={!busy}
        nodesConnectable={!busy}
        deleteKeyCode={null}
        minZoom={0.15}
        maxZoom={2}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
        onlyRenderVisibleElements={false}
      >
        <Background color="#d6e2e5" gap={22} size={1} />
        <Controls showInteractive={false} />
        <MiniMap nodeColor="#a7bec7" maskColor="#f3f7f8bb" pannable zoomable />
      </ReactFlow>
      <div className="canvas-caption">
        <span>
          <i className="legend-line" />
          Veri / kontrol
        </span>
        <span>
          <i className="legend-line power" />
          Güç
        </span>
        <span>
          {a.connections.length > edges.length
            ? `${a.connections.length - edges.length} bağlantının uç bileşeni eksik; İnceleme bölümüne bakın.`
            : "Blok veya oku seç · Bağlantı için tutamaçları birleştir"}
        </span>
      </div>
    </div>
  );
}

function Evidence({ evidence, sources, onSource }) {
  if (!evidence.length)
    return (
      <div className="notice amber">
        <AlertTriangle size={16} />
        <div>
          <strong>Doküman dayanağı eklenmemiş</strong>
          <p>
            Bu bir mühendislik kararı olabilir. Gerekçesi ile belge desteği ayrı
            tutulur.
          </p>
        </div>
      </div>
    );
  return evidence.map((e, i) => {
    const s = sources.find((s) => s.requirement_id === e.requirement_id);
    const valid =
      !!e.quote &&
      !!s &&
      s.text
        .normalize("NFKC")
        .replace(/\s+/g, " ")
        .includes(e.quote.normalize("NFKC").replace(/\s+/g, " "));
    const idx = s?.text.indexOf(e.quote) ?? -1;
    return (
      <article className="evidence" key={e.requirement_id + i}>
        <div className="evidence-heading">
          <button
            className="text-button"
            onClick={() => onSource(e.requirement_id)}
          >
            <FileText size={14} />
            {loc(s) || "Kaynak bulunamadı"}
            <ArrowUpRight size={13} />
          </button>
          <Badge tone={valid ? "green" : "red"}>
            {valid ? "Alıntı metinde var" : "Alıntıyı kontrol edin"}
          </Badge>
        </div>
        <p>
          {idx >= 0 ? (
            <>
              {s.text.slice(0, idx)}
              <mark>{e.quote}</mark>
              {s.text.slice(idx + e.quote.length)}
            </>
          ) : (
            e.quote || "Alıntı boş"
          )}
        </p>
        <small>{s?.section || "Belge bilgisi"}</small>
      </article>
    );
  });
}

function DecisionForm({ entityKey, project, commit, busy }) {
  const decision = project.state.decisions[entityKey];
  const [status, setStatus] = useState("needs_review"),
    [note, setNote] = useState(""),
    [target, setTarget] = useState("");
  useEffect(() => {
    setStatus(decision?.status || "needs_review");
    setNote("");
    setTarget(decision?.merged_into || "");
  }, [entityKey, project.version]);
  const finding = entityKey.startsWith("finding:");
  const options = finding
    ? ["needs_review", "accepted", "rejected", "resolved", "merged"]
    : ["needs_review", "approved", "rejected"];
  return (
    <div className="decision-box">
      <div className="section-label">
        <ShieldCheck size={15} />
        Mühendis kararı
      </div>
      <DecisionBadge decision={decision} />
      {decision && (
        <div className="decision-record">
          <p>{decision.note}</p>
          <small>
            {decision.actor} · {date(decision.at)}
          </small>
          {decision.stale && (
            <p className="amber-text">{decision.stale_reason}</p>
          )}
        </div>
      )}
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (
            await commit(
              "set_decision",
              entityKey,
              { status, merged_into: target || null },
              note,
            )
          )
            setNote("");
        }}
      >
        <Field label="Karar">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {options.map((x) => (
              <option key={x} value={x}>
                {decisionNames[x]}
              </option>
            ))}
          </select>
        </Field>
        {status === "merged" && (
          <Field label="Birleştirilecek bulgu">
            <select
              required
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              <option value="">Seçin</option>
              {project.state.analysis.findings
                .filter((f) => "finding:" + f.id !== entityKey)
                .map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.id} · {f.title}
                  </option>
                ))}
            </select>
          </Field>
        )}
        <Field label="Karar gerekçesi">
          <textarea
            required
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Bu kararı hangi değerlendirmeye dayanarak veriyorsunuz?"
            rows={3}
          />
        </Field>
        <Button icon={Check} className="primary" disabled={busy}>
          Kararı kaydet
        </Button>
      </form>
    </div>
  );
}

function Inspector({
  project,
  selection,
  onSelect,
  commit,
  openEditor,
  setModal,
  busy,
  selectedIssue,
}) {
  const a = project.state.architecture,
    sources = project.original.source_catalog;
  if (!selection)
    return (
      <aside className="inspector">
        <Empty title="Şemadan bir öğe seç">
          Bileşenin veya bağlantının dayanağını incele; değiştir veya gerekçeli
          kararını kaydet.
        </Empty>
        <div className="inspector-intro">
          <div className="section-label">Üç ayrı kontrol</div>
          <p>
            <b>Şemadaki karşılık</b> · Modelin kurduğu eşleştirme.
          </p>
          <p>
            <b>Otomatik kontrol</b> · Alıntı ve kayıt tutarlılığı.
          </p>
          <p>
            <b>Mühendis kararı</b> · Senin anlam ve tasarım değerlendirmen.
          </p>
        </div>
      </aside>
    );
  if (selection.kind === "source")
    return (
      <SourceInspector
        {...{ project, selection, onSelect, commit, busy, setModal }}
      />
    );
  if (selection.kind === "finding")
    return (
      <FindingInspector
        {...{ project, selection, onSelect, commit, busy, setModal }}
      />
    );
  const field = selection.kind === "component" ? "components" : "connections",
    o = a[field].find((x) => x.id === selection.id);
  if (!o)
    return (
      <aside className="inspector">
        <Empty title="Öğe kaldırıldı">
          Geçmişten geri alabilir veya başka bir öğe seçebilirsin.
        </Empty>
      </aside>
    );
  const edge = selection.kind === "connection",
    name = (id) => a.components.find((c) => c.id === id)?.name || id,
    title = edge ? name(o.source) + " → " + name(o.target) : o.name;
  const issues = project.issues.filter((i) => i.object_id === o.id),
    findings = project.state.analysis.findings.filter(
      (f) =>
        f.related_component_ids.includes(o.id) ||
        f.related_connection_ids.includes(o.id),
    );
  const provenance = project.state.provenance[selection.kind + ":" + o.id];
  return (
    <aside className="inspector">
      <div className="inspector-heading">
        <span className="eyebrow">
          {edge ? "BAĞLANTI" : "BİLEŞEN"} İNCELEMESİ
        </span>
        <h2>{title}</h2>
        <div className="inline">
          <Badge>{edge ? types[o.type] : cats[o.category]}</Badge>
          {edge && <Badge>{o.protocol || "Arayüz belirtilmemiş"}</Badge>}
          <Badge tone={provenance ? "teal" : ""}>
            {provenance ? "Mühendis düzenlemesi" : "Model taslağı"}
          </Badge>
        </div>
        <div className="object-actions">
          <Button
            icon={Pencil}
            disabled={busy}
            onClick={() => openEditor(selection.kind, o)}
          >
            Düzenle
          </Button>
          <Button
            icon={Trash2}
            className="danger-quiet"
            disabled={busy}
            onClick={() =>
              setModal({ type: "delete", kind: selection.kind, object: o })
            }
          >
            Kaldır
          </Button>
        </div>
      </div>
      {selectedIssue && (
        <div className="notice amber">
          <AlertTriangle size={16} />
          <div>
            <strong>{selectedIssue.title}</strong>
            <p>{selectedIssue.suggestion}</p>
            {selectedIssue.source_id && (
              <button
                className="text-button"
                onClick={() =>
                  onSelect({ kind: "source", id: selectedIssue.source_id })
                }
              >
                İlgili kaynağı aç <ArrowUpRight size={14} />
              </button>
            )}
          </div>
        </div>
      )}
      <div className="inspector-section">
        <div className="section-label">
          <Lightbulb size={15} />
          Bu öğe ne anlatıyor?
        </div>
        <p>{o.description || "Açıklama belirtilmemiş."}</p>
        {edge && (
          <p className="muted">
            Gösterilen {types[o.type].toLocaleLowerCase("tr")} akışı:{" "}
            <b>{name(o.source)}</b> → <b>{name(o.target)}</b>. Yön ve arayüzün
            dayanağını aşağıdaki kaynak cümlesiyle karşılaştır.
          </p>
        )}
        {o.category === "external" && (
          <div className="notice amber">
            <div>
              <strong>Sistem sınırı kararı gerekli</strong>
              <p>
                Uzakta çalışmak, tek başına sistem dışında olmak anlamına
                gelmez. Dış sistem sınıfını kaynak kapsamıyla doğrulayın.
              </p>
            </div>
          </div>
        )}
        {provenance && (
          <div className="provenance">
            <strong>
              {provenance.origin === "engineer_added"
                ? "Mühendis tarafından eklendi"
                : "Mühendis tarafından değiştirildi"}
            </strong>
            <p>{provenance.reason}</p>
            <small>
              {provenance.actor} · {date(provenance.at)}
            </small>
          </div>
        )}
      </div>
      <div className="inspector-section">
        <div className="section-label">
          <BookOpen size={15} />
          Kaynak dayanağı <span>{o.evidence.length}</span>
        </div>
        <Evidence
          evidence={o.evidence}
          sources={sources}
          onSource={(id) => onSelect({ kind: "source", id })}
        />
        <p className="micro">
          Metin eşleşmesi, mühendislik doğruluğunun onayı değildir.
        </p>
      </div>
      <div className="inspector-section">
        <div className="section-label">
          <AlertTriangle size={15} />
          Otomatik kontroller
        </div>
        {issues.length ? (
          issues.map((i) => (
            <button
              key={i.key}
              className="issue-mini"
              onClick={() =>
                i.source_id
                  ? onSelect({ kind: "source", id: i.source_id })
                  : openEditor(selection.kind, o)
              }
            >
              <strong>
                {i.source_id &&
                  loc(sources.find((s) => s.requirement_id === i.source_id)) +
                    " · "}
                {i.title}
              </strong>
              <span>{i.suggestion}</span>
              <ChevronRight size={15} />
            </button>
          ))
        ) : (
          <div className="inline muted">
            <Check size={16} />
            Bu nesnede otomatik kayıt sorunu bulunmadı.
          </div>
        )}
      </div>
      {findings.length > 0 && (
        <div className="inspector-section">
          <div className="section-label">
            <MessageSquare size={15} />
            İlgili mühendislik konuları
          </div>
          {findings.map((f) => (
            <button
              key={f.id}
              className="list-link"
              onClick={() => onSelect({ kind: "finding", id: f.id })}
            >
              <span>{f.title}</span>
              <ChevronRight size={15} />
            </button>
          ))}
        </div>
      )}
      <DecisionForm
        entityKey={selection.kind + ":" + o.id}
        {...{ project, commit, busy }}
      />
      <details className="technical">
        <summary>Teknik kimlik</summary>
        <code>{o.id}</code>
      </details>
    </aside>
  );
}

function SourceInspector({
  project,
  selection,
  onSelect,
  commit,
  busy,
  setModal,
}) {
  const s = project.original.source_catalog.find(
    (s) => s.requirement_id === selection.id,
  );
  if (!s) return null;
  const a = project.state.architecture,
    c = a.requirement_coverage.find(
      (c) => c.requirement_id === s.requirement_id,
    );
  const direct = [
    ...a.components.map((o) => ({ ...o, kind: "component" })),
    ...a.connections.map((o) => ({ ...o, kind: "connection" })),
  ].filter((o) =>
    o.evidence.some((e) => e.requirement_id === s.requirement_id),
  );
  const declared = [
    ...(c?.related_component_ids || []).map((id) => ({
      id,
      kind: "component",
    })),
    ...(c?.related_connection_ids || []).map((id) => ({
      id,
      kind: "connection",
    })),
  ];
  const contextual = a.connections
    .filter((e) => direct.some((o) => o.id === e.id))
    .flatMap((e) => [e.source, e.target]);
  const names = (id) =>
    a.components.find((x) => x.id === id)?.name ||
    a.connections.find((x) => x.id === id)?.protocol ||
    id;
  return (
    <aside className="inspector">
      <div className="inspector-heading">
        <span className="eyebrow">KAYNAK İNCELEMESİ</span>
        <h2>{loc(s) || "Kaynak kaydı"}</h2>
        <p className="muted">{s.section || "Belge bilgisi"}</p>
        <Badge>{coverageNames[c?.status] || "Sınıflandırılmamış"}</Badge>
      </div>
      <div className="source-quote">{s.text}</div>
      <div className="notice blue">
        <CircleHelp size={16} />
        <div>
          <strong>Bu durum ne anlama geliyor?</strong>
          <p>
            {c?.status === "not_architectural"
              ? "Bu kayıt başlık veya bağlam olarak sınıflandırılmış."
              : c?.status === "unmapped"
                ? "Bu metin için şemada bir karşılık seçilmemiş."
                : "Bu metne karşılık geldiği düşünülen öğeler seçilmiş. İşlevin doğru uygulandığı veya onaylandığı anlamına gelmez."}
          </p>
        </div>
      </div>
      <div className="inspector-section">
        <div className="section-label">
          Bu kaynağı doğrudan kanıt gösterenler
        </div>
        {direct.length ? (
          direct.map((o) => (
            <button
              className="list-link"
              key={o.id}
              onClick={() => onSelect({ kind: o.kind, id: o.id })}
            >
              <span>{names(o.id)}</span>
              <Badge tone="green">Alıntı bağlı</Badge>
            </button>
          ))
        ) : (
          <p className="muted">Doğrudan dayanak ilişkisi yok.</p>
        )}
      </div>
      <div className="inspector-section">
        <div className="section-label">Kapsama kaydındaki eşleştirmeler</div>
        <p className="muted">{c?.notes || "Açıklama eklenmemiş."}</p>
        {declared.map((o) => (
          <button
            className="list-link"
            key={o.kind + o.id}
            onClick={() => onSelect(o)}
          >
            <span>{names(o.id)}</span>
            <Badge tone={direct.some((d) => d.id === o.id) ? "green" : "amber"}>
              {direct.some((d) => d.id === o.id)
                ? "Kanıt bağlı"
                : "Kanıt bağı yok"}
            </Badge>
          </button>
        ))}
        {!declared.length && <p className="muted">Nesne seçilmemiş.</p>}
        <Button
          icon={Pencil}
          disabled={busy}
          onClick={() => setModal({ type: "coverage", source: s })}
        >
          Eşleştirmeyi düzenle
        </Button>
      </div>
      {contextual.length > 0 && (
        <div className="inspector-section">
          <div className="section-label">
            Bağlantı üzerinden ilgili bileşenler
          </div>
          <p className="micro">
            Uç bileşen ilişkisi, doğrudan kanıtla aynı şey değildir.
          </p>
          <div className="chips">
            {[...new Set(contextual)].map((id) => (
              <button
                key={id}
                onClick={() => onSelect({ kind: "component", id })}
              >
                {names(id)}
              </button>
            ))}
          </div>
        </div>
      )}
      <DecisionForm
        entityKey={"source:" + s.requirement_id}
        {...{ project, commit, busy }}
      />
      <details className="technical">
        <summary>Kaynak kimliği</summary>
        <code>{s.requirement_id}</code>
      </details>
    </aside>
  );
}

function FindingInspector({
  project,
  selection,
  onSelect,
  commit,
  busy,
  setModal,
}) {
  const f = project.state.analysis.findings.find((f) => f.id === selection.id);
  if (!f) return null;
  const a = project.state.architecture;
  return (
    <aside className="inspector">
      <div className="inspector-heading">
        <span className="eyebrow">MÜHENDİSLİK KONUSU · {f.id}</span>
        <h2>{f.title}</h2>
        <Button
          icon={Pencil}
          disabled={busy}
          onClick={() => setModal({ type: "finding", object: f })}
        >
          Bulguyu düzenle
        </Button>
        <div className="inline">
          <Badge tone="amber">
            {
              {
                critical: "Kritik",
                high: "Yüksek",
                medium: "Orta",
                low: "Düşük",
                info: "Bilgi",
              }[f.severity]
            }
          </Badge>
          <Badge>
            {project.state.provenance["finding:" + f.id]
              ? project.state.provenance["finding:" + f.id].origin ===
                "engineer_added"
                ? "Mühendis bulgusu"
                : "Mühendis düzenlemesi"
              : "Model bulgusu"}
          </Badge>
        </div>
      </div>
      <div className="inspector-section">
        <p>{f.description}</p>
        <div className="notice blue">
          <Lightbulb size={16} />
          <div>
            <strong>Önerilen işlem</strong>
            <p>{f.recommended_action || "Kaynakla birlikte değerlendirin."}</p>
          </div>
        </div>
        <p className="micro">
          Öneri tasarım kararı değildir; mühendis tarafından
          değerlendirilmelidir.
        </p>
      </div>
      <div className="inspector-section">
        <div className="section-label">İlgili öğeler</div>
        <div className="chips">
          {f.related_component_ids.map((id) => (
            <button
              key={id}
              onClick={() => onSelect({ kind: "component", id })}
            >
              {a.components.find((c) => c.id === id)?.name ||
                id + " (kaldırılmış)"}
            </button>
          ))}
          {f.related_connection_ids.map((id) => (
            <button
              key={id}
              onClick={() => onSelect({ kind: "connection", id })}
            >
              {id}
            </button>
          ))}
        </div>
      </div>
      <div className="inspector-section">
        <div className="section-label">Dayanak cümleleri</div>
        <Evidence
          evidence={f.evidence}
          sources={project.original.source_catalog}
          onSource={(id) => onSelect({ kind: "source", id })}
        />
      </div>
      <DecisionForm
        entityKey={"finding:" + f.id}
        {...{ project, commit, busy }}
      />
    </aside>
  );
}

function EvidenceEditor({ value, onChange, sources }) {
  return (
    <div className="evidence-editor">
      <div className="section-label">
        <BookOpen size={15} />
        Dayanak cümleleri
      </div>
      <p className="micro">
        Sadece dokümanda bulunan metni alıntılayın. Yeni tasarım kararının
        gerekçesi aşağıda ayrı tutulur.
      </p>
      {value.map((e, i) => (
        <div className="evidence-edit" key={i}>
          <div className="inline spread">
            <strong>
              {loc(sources.find((s) => s.requirement_id === e.requirement_id))}
            </strong>
            <button
              type="button"
              className="icon-button"
              aria-label={"Kanıtı kaldır " + (i + 1)}
              onClick={() => onChange(value.filter((_, j) => i !== j))}
            >
              <X size={15} />
            </button>
          </div>
          <textarea
            aria-label={"Alıntı " + (i + 1)}
            value={e.quote || ""}
            rows={3}
            onChange={(event) =>
              onChange(
                value.map((x, j) =>
                  j === i ? { ...x, quote: event.target.value } : x,
                ),
              )
            }
          />
        </div>
      ))}
      <select
        aria-label="Kaynak dayanağı ekle"
        value=""
        onChange={(e) => {
          const s = sources.find((s) => s.requirement_id === e.target.value);
          if (s)
            onChange([
              ...value,
              { requirement_id: s.requirement_id, quote: s.text },
            ]);
        }}
      >
        <option value="">+ Dokümandan kaynak ekle</option>
        {sources
          .filter(
            (s) => !value.some((e) => e.requirement_id === s.requirement_id),
          )
          .map((s) => (
            <option key={s.requirement_id} value={s.requirement_id}>
              {loc(s)} · {s.text.slice(0, 95)}
            </option>
          ))}
      </select>
    </div>
  );
}

function EntityEditor({ modal, project, commit, onClose, busy }) {
  const kind = modal.kind,
    edge = kind === "connection",
    a = project.state.architecture;
  const [value, setValue] = useState(() =>
    clone(
      modal.object ||
        (edge
          ? {
              id: uid("if"),
              source: modal.params?.source || a.components[0]?.id || "",
              target: modal.params?.target || a.components[1]?.id || "",
              type: "data",
              protocol: "",
              label: "",
              description: "",
              evidence: [],
            }
          : {
              id: uid("component"),
              name: "",
              category: "component",
              description: "",
              evidence: [],
            }),
    ),
  );
  const [reason, setReason] = useState("");
  const set = (k, v) => setValue((x) => ({ ...x, [k]: v }));
  return (
    <Modal
      title={
        (modal.object ? "Düzenle: " : "Yeni ") + (edge ? "bağlantı" : "bileşen")
      }
      subtitle="Kaynak dayanağı ve mühendis gerekçesi birlikte saklanır."
      onClose={onClose}
      wide
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (
            await commit(
              edge ? "upsert_connection" : "upsert_component",
              modal.object?.id || "",
              value,
              reason,
            )
          )
            onClose();
        }}
      >
        <div className="modal-body">
          <div className="form-grid">
            {edge ? (
              <>
                <Field label="Başlangıç bileşeni">
                  <select
                    value={value.source}
                    onChange={(e) => set("source", e.target.value)}
                  >
                    {a.components.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Hedef bileşen">
                  <select
                    value={value.target}
                    onChange={(e) => set("target", e.target.value)}
                  >
                    {a.components.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Bağlantı türü">
                  <select
                    value={value.type}
                    onChange={(e) => set("type", e.target.value)}
                  >
                    {Object.entries(types).map(([v, t]) => (
                      <option key={v} value={v}>
                        {t}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label={
                    value.type === "power"
                      ? "Güç özelliği / arayüz"
                      : "Protokol / arayüz"
                  }
                >
                  <input
                    value={value.protocol || ""}
                    onChange={(e) => set("protocol", e.target.value)}
                    placeholder="Kaynakta belirtilmiyorsa boş bırakın"
                  />
                </Field>
                <Button
                  type="button"
                  icon={ArrowRightLeft}
                  onClick={() =>
                    setValue((v) => ({
                      ...v,
                      source: v.target,
                      target: v.source,
                    }))
                  }
                >
                  Yönü ters çevir
                </Button>
              </>
            ) : (
              <>
                <Field label="Bileşen adı">
                  <input
                    required
                    value={value.name}
                    onChange={(e) => set("name", e.target.value)}
                  />
                </Field>
                <Field label="Sınıf">
                  <select
                    value={value.category}
                    onChange={(e) => set("category", e.target.value)}
                  >
                    {Object.entries(cats).map(([v, t]) => (
                      <option key={v} value={v}>
                        {t}
                      </option>
                    ))}
                  </select>
                </Field>
              </>
            )}
          </div>
          {edge && (
            <Field label="Kısa açıklama / etiket">
              <input
                value={value.label || ""}
                onChange={(e) => set("label", e.target.value)}
              />
            </Field>
          )}
          <Field label="Açıklama">
            <textarea
              value={value.description || ""}
              rows={3}
              onChange={(e) => set("description", e.target.value)}
            />
          </Field>
          <EvidenceEditor
            value={value.evidence}
            onChange={(v) => set("evidence", v)}
            sources={project.original.source_catalog}
          />
          {!value.evidence.length && (
            <div className="notice amber">
              <AlertTriangle size={16} />
              <p>
                Doküman dayanağı olmadan kaydedilebilir. Bu durum görünür kalır
                ve otomatik onay sayılmaz.
              </p>
            </div>
          )}
          <Field label="Değişiklik gerekçesi">
            <textarea
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              placeholder="Ne değişti, neden değişti?"
            />
          </Field>
          <p className="micro">Kalıcı kimlik: {value.id}</p>
        </div>
        <footer>
          <Button type="button" onClick={onClose}>
            Vazgeç
          </Button>
          <Button icon={Save} className="primary" disabled={busy}>
            Değişikliği kaydet
          </Button>
        </footer>
      </form>
    </Modal>
  );
}

function CoverageEditor({ source, project, commit, onClose, busy }) {
  const a = project.state.architecture;
  const [value, setValue] = useState(() =>
    clone(
      a.requirement_coverage.find(
        (c) => c.requirement_id === source.requirement_id,
      ) || {
        requirement_id: source.requirement_id,
        status: "unmapped",
        related_component_ids: [],
        related_connection_ids: [],
        notes: "",
      },
    ),
  );
  const [reason, setReason] = useState("");
  const toggle = (key, id) =>
    setValue((v) => ({
      ...v,
      [key]: v[key].includes(id)
        ? v[key].filter((x) => x !== id)
        : [...v[key], id],
    }));
  const derive = () =>
    setValue((v) => ({
      ...v,
      related_component_ids: a.components
        .filter((c) =>
          c.evidence.some((e) => e.requirement_id === source.requirement_id),
        )
        .map((c) => c.id),
      related_connection_ids: a.connections
        .filter((c) =>
          c.evidence.some((e) => e.requirement_id === source.requirement_id),
        )
        .map((c) => c.id),
    }));
  return (
    <Modal
      title="Kaynağın şemadaki karşılığı"
      subtitle={loc(source)}
      onClose={onClose}
      wide
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (
            await commit("set_coverage", source.requirement_id, value, reason)
          )
            onClose();
        }}
      >
        <div className="modal-body">
          <blockquote>{source.text}</blockquote>
          <Field label="Eşleştirme durumu">
            <select
              value={value.status}
              onChange={(e) => setValue({ ...value, status: e.target.value })}
            >
              {Object.entries(coverageNames).map(([v, t]) => (
                <option value={v} key={v}>
                  {t}
                </option>
              ))}
            </select>
          </Field>
          <div className="notice blue">
            <CircleHelp size={16} />
            <p>
              “Karşılık seçilmiş” mühendis onayı değildir. Bir bağlantının
              uçları olması, bileşenlerin bu cümleyi doğrudan kanıt gösterdiği
              anlamına gelmez.
            </p>
          </div>
          <Button type="button" icon={Link2} onClick={derive}>
            Seçimleri mevcut kanıtlardan getir
          </Button>
          <div className="form-grid checks">
            <div>
              <h3>Bileşenler</h3>
              {a.components.map((c) => (
                <label className="check" key={c.id}>
                  <input
                    type="checkbox"
                    checked={value.related_component_ids.includes(c.id)}
                    onChange={() => toggle("related_component_ids", c.id)}
                  />
                  {c.name}
                </label>
              ))}
            </div>
            <div>
              <h3>Bağlantılar</h3>
              {a.connections.map((c) => (
                <label className="check" key={c.id}>
                  <input
                    type="checkbox"
                    checked={value.related_connection_ids.includes(c.id)}
                    onChange={() => toggle("related_connection_ids", c.id)}
                  />
                  {a.components.find((n) => n.id === c.source)?.name} →{" "}
                  {a.components.find((n) => n.id === c.target)?.name} (
                  {c.protocol || types[c.type]})
                </label>
              ))}
            </div>
          </div>
          <Field label="Kapsama açıklaması">
            <textarea
              value={value.notes || ""}
              onChange={(e) => setValue({ ...value, notes: e.target.value })}
            />
          </Field>
          <Field label="Düzeltme gerekçesi">
            <textarea
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
        </div>
        <footer>
          <Button type="button" onClick={onClose}>
            Vazgeç
          </Button>
          <Button icon={Save} className="primary" disabled={busy}>
            Eşleştirmeyi kaydet
          </Button>
        </footer>
      </form>
    </Modal>
  );
}

function DeleteDialog({ modal, project, commit, onClose, busy }) {
  const [reason, setReason] = useState(""),
    [cascade, setCascade] = useState(false);
  const connected =
    modal.kind === "component"
      ? project.state.architecture.connections.filter((e) =>
          [e.source, e.target].includes(modal.object.id),
        )
      : [];
  return (
    <Modal
      title={
        modal.kind === "component" ? "Bileşeni kaldır" : "Bağlantıyı kaldır"
      }
      subtitle="Çalışma kopyası değişir; ilk model çıktısı ve geçmiş korunur."
      onClose={onClose}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (
            await commit(
              "delete_" + modal.kind,
              modal.object.id,
              { cascade },
              reason,
            )
          )
            onClose();
        }}
      >
        <div className="modal-body">
          <p>
            <strong>
              {modal.object.name || modal.object.label || modal.object.id}
            </strong>{" "}
            çalışma şemasından kaldırılacak.
          </p>
          {connected.length > 0 && (
            <>
              <p>
                {connected.length} bağlantı da kaldırılacak. İlgili kaynak
                eşleştirmeleri güncellenecek; eski bulgular inceleme için
                korunacak.
              </p>
              <label className="check">
                <input
                  type="checkbox"
                  required
                  checked={cascade}
                  onChange={(e) => setCascade(e.target.checked)}
                />
                Bağlantılarıyla birlikte kaldır
              </label>
            </>
          )}
          <Field label="Kaldırma gerekçesi">
            <textarea
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
        </div>
        <footer>
          <Button type="button" onClick={onClose}>
            Vazgeç
          </Button>
          <Button className="danger" icon={Trash2} disabled={busy}>
            Çalışma kopyasından kaldır
          </Button>
        </footer>
      </form>
    </Modal>
  );
}

function FindingEditor({ project, commit, onClose, busy, object }) {
  const [value, setValue] = useState(
      object
        ? clone(object)
        : {
            id: uid("F"),
            severity: "medium",
            type: "other",
            title: "",
            description: "",
            evidence: [],
            related_component_ids: [],
            related_connection_ids: [],
            recommended_action: "",
          },
    ),
    [reason, setReason] = useState("");
  const set = (k, v) => setValue((x) => ({ ...x, [k]: v }));
  return (
    <Modal
      title={object ? "Bulguyu düzenle" : "Mühendis bulgusu ekle"}
      subtitle="Gözlem ve öneriyi kaynak dayanağıyla birlikte kaydet."
      onClose={onClose}
      wide
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (
            await commit(
              object ? "edit_finding" : "add_finding",
              object?.id || "",
              value,
              reason,
            )
          )
            onClose();
        }}
      >
        <div className="modal-body">
          <Field label="Bulgu başlığı">
            <input
              required
              value={value.title}
              onChange={(e) => set("title", e.target.value)}
            />
          </Field>
          <div className="form-grid">
            <Field label="Önem">
              <select
                value={value.severity}
                onChange={(e) => set("severity", e.target.value)}
              >
                {Object.entries({
                  low: "Düşük",
                  medium: "Orta",
                  high: "Yüksek",
                  critical: "Kritik",
                  info: "Bilgi",
                }).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Tür">
              <select
                value={value.type}
                onChange={(e) => set("type", e.target.value)}
              >
                {Object.entries({
                  other: "Diğer",
                  contradiction: "Çelişki",
                  missing_interface: "Eksik arayüz",
                  missing_connection: "Eksik bağlantı",
                  ambiguous: "Belirsizlik",
                  traceability: "İzlenebilirlik",
                  classification: "Sınıflandırma",
                }).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <Field label="Gözlem">
            <textarea
              required
              rows={3}
              value={value.description}
              onChange={(e) => set("description", e.target.value)}
            />
          </Field>
          <Field label="Önerilen işlem">
            <textarea
              value={value.recommended_action || ""}
              onChange={(e) => set("recommended_action", e.target.value)}
            />
          </Field>
          <div className="form-grid checks">
            <div>
              <h3>İlgili bileşenler</h3>
              {[
                ...project.state.architecture.components,
                ...value.related_component_ids
                  .filter(
                    (id) =>
                      !project.state.architecture.components.some(
                        (c) => c.id === id,
                      ),
                  )
                  .map((id) => ({
                    id,
                    name: id + " (kaldırılmış; ilişkiyi güncelleyin)",
                  })),
              ].map((c) => (
                <label className="check" key={c.id}>
                  <input
                    type="checkbox"
                    checked={value.related_component_ids.includes(c.id)}
                    onChange={(e) =>
                      set(
                        "related_component_ids",
                        e.target.checked
                          ? [...value.related_component_ids, c.id]
                          : value.related_component_ids.filter(
                              (x) => x !== c.id,
                            ),
                      )
                    }
                  />
                  {c.name}
                </label>
              ))}
            </div>
            <div>
              <h3>İlgili bağlantılar</h3>
              {[
                ...project.state.architecture.connections,
                ...value.related_connection_ids
                  .filter(
                    (id) =>
                      !project.state.architecture.connections.some(
                        (c) => c.id === id,
                      ),
                  )
                  .map((id) => ({
                    id,
                    protocol: "Kaldırılmış; ilişkiyi güncelleyin",
                  })),
              ].map((c) => (
                <label className="check" key={c.id}>
                  <input
                    type="checkbox"
                    checked={value.related_connection_ids.includes(c.id)}
                    onChange={(e) =>
                      set(
                        "related_connection_ids",
                        e.target.checked
                          ? [...value.related_connection_ids, c.id]
                          : value.related_connection_ids.filter(
                              (x) => x !== c.id,
                            ),
                      )
                    }
                  />
                  {c.id} · {c.protocol || types[c.type]}
                </label>
              ))}
            </div>
          </div>
          <EvidenceEditor
            value={value.evidence}
            onChange={(v) => set("evidence", v)}
            sources={project.original.source_catalog}
          />
          <Field label="Kayıt gerekçesi">
            <textarea
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
        </div>
        <footer>
          <Button type="button" onClick={onClose}>
            Vazgeç
          </Button>
          <Button className="primary" icon={Save} disabled={busy}>
            Bulguyu kaydet
          </Button>
        </footer>
      </form>
    </Modal>
  );
}

function OpenDialog({ bootstrap, onOpen, onImport, onClose, busy }) {
  const [path, setPath] = useState("");
  return (
    <Modal
      title="İnceleme aç"
      subtitle="Kaydedilmiş çıktıyı açmak model çağrısı yapmaz."
      onClose={onClose}
      wide
    >
      <div className="modal-body">
        {bootstrap.projects.length > 0 && (
          <>
            <div className="section-label">Kaydedilmiş çalışma kopyaları</div>
            <div className="project-list">
              {bootstrap.projects.map((p) => (
                <button
                  key={p.id}
                  className="project-row"
                  disabled={busy}
                  onClick={() => onOpen(p.id)}
                >
                  <span className="file-square">
                    <Layers3 size={20} />
                  </span>
                  <span>
                    <strong>{p.name}</strong>
                    <small>
                      {date(p.updated)} · Sürüm {p.version}
                    </small>
                  </span>
                  <ChevronRight size={18} />
                </button>
              ))}
            </div>
          </>
        )}
        <div className="section-label">Analiz çıktıları</div>
        <div className="project-list">
          {bootstrap.runs.map((r) => (
            <button
              key={r.path}
              className="project-row"
              disabled={busy}
              onClick={() => onImport(r.path)}
            >
              <span className="file-square">
                <FolderOpen size={20} />
              </span>
              <span>
                <strong>{r.name}</strong>
                <small>
                  {r.run} · {r.model}
                </small>
              </span>
              <ChevronRight size={18} />
            </button>
          ))}
          {!bootstrap.runs.length && (
            <p className="muted">outputs klasöründe henüz analiz bulunmuyor.</p>
          )}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onImport(path);
          }}
        >
          <Field label="Başka bir çıktı klasörü veya analysis_result.json yolu">
            <input
              required
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="C:\Analizler\20260930_182611_214350"
            />
          </Field>
          <Button icon={FolderOpen} disabled={busy}>
            Dosya yolundan aç
          </Button>
        </form>
      </div>
    </Modal>
  );
}

function AnalysisDialog({ bootstrap, onStart, onClose, busy }) {
  const [value, setValue] = useState({
    input_path: bootstrap.demo_input,
    profile: "openrouter_nemotron",
    timeout: 600,
    max_tokens: 8192,
    two_pass: true,
    api_key: "",
    base_url: "",
    model: "",
  });
  const set = (k, v) => setValue((s) => ({ ...s, [k]: v }));
  const profile = bootstrap.profiles.find((p) => p.id === value.profile);
  return (
    <Modal
      title="Yeni doküman analizi"
      subtitle="TXT, DOCX veya PDF dosyasını bilgisayarındaki yoluyla aç."
      onClose={onClose}
      wide
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onStart({ ...value, demo: false });
        }}
      >
        <div className="modal-body">
          <Field label="Doküman yolu">
            <input
              required
              value={value.input_path}
              onChange={(e) => set("input_path", e.target.value)}
            />
          </Field>
          <Field label="Model bağlantısı">
            <select
              value={value.profile}
              onChange={(e) => {
                setValue((v) => ({
                  ...v,
                  profile: e.target.value,
                  base_url: "",
                  model: "",
                  api_key: "",
                }));
              }}
            >
              {bootstrap.profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id} · {p.model}
                </option>
              ))}
            </select>
          </Field>
          <div className="notice blue">
            <Network size={16} />
            <div>
              <strong>{value.base_url || profile?.base_url}</strong>
              <p>
                “Modelle analizi başlat” doküman içeriğini bu bağlantıya
                gönderir. Kayıtlı incelemeyi düzenlemek yeni model çağrısı
                yapmaz.
              </p>
            </div>
          </div>
          <details className="settings-details">
            <summary>Bağlantı ve çalışma ayarları</summary>
            <Field label="Sunucu adresi (isteğe bağlı)">
              <input
                value={value.base_url}
                onChange={(e) => set("base_url", e.target.value)}
                placeholder={profile?.base_url}
              />
            </Field>
            <Field label="Model kimliği (isteğe bağlı)">
              <input
                value={value.model}
                onChange={(e) => set("model", e.target.value)}
                placeholder={profile?.model}
              />
            </Field>
            <Field
              label="API anahtarı"
              hint={
                profile?.has_key
                  ? "Ortam ayarlarında anahtar var. Boş bırakırsanız kullanılır."
                  : "Yalnızca bu analiz için bellekte tutulur."
              }
            >
              <input
                type="password"
                autoComplete="off"
                value={value.api_key}
                onChange={(e) => set("api_key", e.target.value)}
              />
            </Field>
            <div className="form-grid">
              <Field label="Zaman aşımı (saniye)">
                <input
                  type="number"
                  min="10"
                  max="1800"
                  required
                  value={value.timeout}
                  onChange={(e) => set("timeout", Number(e.target.value))}
                />
              </Field>
              <Field label="Çıktı token sınırı">
                <input
                  type="number"
                  min="512"
                  max="65536"
                  required
                  value={value.max_tokens}
                  onChange={(e) => set("max_tokens", Number(e.target.value))}
                />
              </Field>
            </div>
            <label className="check">
              <input
                type="checkbox"
                checked={value.two_pass}
                onChange={(e) => set("two_pass", e.target.checked)}
              />
              İkinci tur model incelemesi
            </label>
          </details>
        </div>
        <footer>
          <Button
            type="button"
            icon={Play}
            disabled={busy}
            onClick={() => onStart({ ...value, demo: true })}
          >
            API olmadan örnek dene
          </Button>
          <Button className="primary" icon={Play} disabled={busy}>
            Modelle analizi başlat
          </Button>
        </footer>
      </form>
    </Modal>
  );
}

function Explorer({ project, selection, onSelect }) {
  const [group, setGroup] = useState("component"),
    [search, setSearch] = useState("");
  const a = project.state.architecture;
  const items =
    group === "source"
      ? project.original.source_catalog
      : group === "connection"
        ? a.connections
        : a.components;
  const match = (s) =>
    s.toLocaleLowerCase("tr").includes(search.toLocaleLowerCase("tr"));
  return (
    <aside className="explorer">
      <div className="explorer-header">
        <span className="section-label">GEZGİN</span>
        <span className="muted">{items.length}</span>
      </div>
      <div className="search-field">
        <Search size={15} />
        <input
          aria-label="Öğe ara"
          placeholder="Bu analizde ara…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div className="explorer-switch">
        {[
          ["component", "Bloklar"],
          ["connection", "Oklar"],
          ["source", "Kaynaklar"],
        ].map(([k, t]) => (
          <button
            key={k}
            className={group === k ? "active" : ""}
            onClick={() => setGroup(k)}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="explorer-list">
        {items
          .filter((o) =>
            match(o.name || o.text || [o.label, o.protocol, o.id].join(" ")),
          )
          .map((o) => {
            const id = o.requirement_id || o.id;
            return (
              <button
                key={id}
                className={
                  "explorer-item " +
                  (selection?.kind === group && selection.id === id
                    ? "active"
                    : "")
                }
                onClick={() => onSelect({ kind: group, id })}
              >
                <span className="explorer-item-icon">
                  {group === "source" ? (
                    <FileText size={16} />
                  ) : group === "connection" ? (
                    <Link2 size={16} />
                  ) : (
                    <Layers3 size={16} />
                  )}
                </span>
                <span>
                  <strong>
                    {group === "source"
                      ? loc(o)
                      : o.name || o.protocol || types[o.type]}
                  </strong>
                  <small>
                    {group === "source"
                      ? o.text.slice(0, 86)
                      : group === "component"
                        ? cats[o.category]
                        : a.components.find((c) => c.id === o.source)?.name +
                          " → " +
                          a.components.find((c) => c.id === o.target)?.name}
                  </small>
                </span>
              </button>
            );
          })}
      </div>
      <div className="explorer-footer">
        <ShieldCheck size={15} />
        <span>
          İlk çıktı korunur.
          <br />
          Kararların ayrı kaydedilir.
        </span>
      </div>
    </aside>
  );
}

function ReviewView({ project, onSelect, onIssue, setModal }) {
  const [filter, setFilter] = useState("findings");
  const groups = Object.groupBy(
    project.issues,
    (i) => i.source_id || i.object_id || i.related_id || "general",
  );
  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">İNCELEME MASASI</span>
          <h1>Sorunu anla, dayanağını gör, karar ver.</h1>
          <p>
            Modelin mühendislik bulguları ile yazılımın kayıt kontrolleri ayrı
            değerlendirilir.
          </p>
        </div>
        <Button icon={Plus} onClick={() => setModal({ type: "finding" })}>
          Bulgu ekle
        </Button>
      </div>
      <div className="segmented">
        <button
          className={filter === "findings" ? "active" : ""}
          onClick={() => setFilter("findings")}
        >
          Mühendislik konuları <b>{project.state.analysis.findings.length}</b>
        </button>
        <button
          className={filter === "checks" ? "active" : ""}
          onClick={() => setFilter("checks")}
        >
          Otomatik kontroller <b>{project.issues.length}</b>
        </button>
      </div>
      {filter === "findings" ? (
        <div className="finding-grid">
          {project.state.analysis.findings.map((f) => (
            <article className="finding-card" key={f.id}>
              <div className="inline spread">
                <Badge
                  tone={
                    ["critical", "high"].includes(f.severity) ? "amber" : ""
                  }
                >
                  {
                    {
                      high: "Yüksek öncelik",
                      medium: "Orta öncelik",
                      low: "Düşük öncelik",
                      critical: "Kritik",
                      info: "Bilgi",
                    }[f.severity]
                  }
                </Badge>
                <span className="micro">{f.id}</span>
              </div>
              <h2>{f.title}</h2>
              <p>{f.description}</p>
              <div className="suggestion">
                <Lightbulb size={16} />
                <span>{f.recommended_action || "Kaynağı inceleyin."}</span>
              </div>
              <div className="inline spread">
                <DecisionBadge
                  decision={project.state.decisions["finding:" + f.id]}
                />
                <Button
                  icon={ArrowUpRight}
                  onClick={() => onSelect({ kind: "finding", id: f.id })}
                >
                  İncele
                </Button>
              </div>
            </article>
          ))}
          {!project.state.analysis.findings.length && (
            <Empty title="Model bulgu bildirmemiş">
              Bu, sorun bulunmadığının kanıtı değildir. Kendi gözlemini
              ekleyebilirsin.
            </Empty>
          )}
        </div>
      ) : (
        <>
          <div className="notice blue">
            <CircleHelp size={17} />
            <p>
              Bu kontroller kayıt tutarlılığını sınar. “Kanıt bağı yok”
              bağlantının fiziksel olarak yanlış olduğu anlamına gelmez. Hata
              ancak ilgili kayıt düzeldiğinde listeden kalkar.
            </p>
          </div>
          {Object.entries(groups).map(([id, issues]) => {
            const s = project.original.source_catalog.find(
                (s) => s.requirement_id === id,
              ),
              o = [
                ...project.state.architecture.components,
                ...project.state.architecture.connections,
              ].find((o) => o.id === id);
            return (
              <article className="check-group" key={id}>
                <header>
                  <div>
                    <strong>{s ? loc(s) : o?.name || o?.label || id}</strong>
                    {s && <p>{s.text}</p>}
                  </div>
                  <Badge tone="amber">{issues.length} kontrol</Badge>
                </header>
                {issues.map((i) => (
                  <button
                    key={i.key}
                    className="check-row"
                    onClick={() => onIssue(i)}
                  >
                    <AlertTriangle size={17} />
                    <span>
                      <strong>{i.title}</strong>
                      <small>
                        {i.object_id && (
                          <>
                            {project.state.architecture.components.find(
                              (c) => c.id === i.object_id,
                            )?.name || i.object_id}{" "}
                            ·{" "}
                          </>
                        )}
                        {i.explanation}
                      </small>
                      <em>{i.suggestion}</em>
                    </span>
                    <ArrowUpRight size={17} />
                  </button>
                ))}
              </article>
            );
          })}
          {!project.issues.length && (
            <Empty icon={CheckCheck} title="Otomatik kayıt sorunu bulunmadı">
              Mühendislik doğruluğu ve onay kararları ayrı değerlendirilir.
            </Empty>
          )}
        </>
      )}
    </div>
  );
}

function SourcesView({ project, onSelect }) {
  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">KAYNAK KATALOĞU</span>
          <h1>Her cümleden şemadaki karşılığına.</h1>
          <p>
            Kaynak metin değişmez. Eşleştirmeleri ve mühendis kararlarını
            inceleme panelinde düzenleyebilirsin.
          </p>
        </div>
      </div>
      <div className="source-cards">
        {project.original.source_catalog.map((s) => {
          const cov = project.state.architecture.requirement_coverage.find(
              (c) => c.requirement_id === s.requirement_id,
            ),
            n = project.issues.filter(
              (i) => i.source_id === s.requirement_id,
            ).length;
          return (
            <button
              key={s.requirement_id}
              className="source-card"
              onClick={() => onSelect({ kind: "source", id: s.requirement_id })}
            >
              <div className="inline spread">
                <strong>{loc(s)}</strong>
                <Badge tone={n ? "amber" : ""}>
                  {n
                    ? n + " kontrol"
                    : coverageNames[cov?.status] || "Sınıflandırılmamış"}
                </Badge>
              </div>
              <p>{s.text}</p>
              <div className="inline spread">
                <small>{s.section || "Belge bilgisi"}</small>
                <ArrowUpRight size={17} />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function AssumptionsView({ project, commit, busy, setModal }) {
  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">VARSAYIMLAR VE AÇIK SORULAR</span>
          <h1>Belirsizlikleri görünür tut.</h1>
          <p>
            Bir model varsayımı, kaynakta yazan kesin bilgiyle aynı değildir.
          </p>
        </div>
      </div>
      <div className="assumption-grid">
        {project.state.architecture.assumptions.map((text, i) => (
          <article className="finding-card" key={i}>
            <div className="inline spread">
              <Badge>Varsayım {i + 1}</Badge>
              <Button
                icon={Pencil}
                onClick={() => setModal({ type: "assumption", index: i, text })}
              >
                Düzenle
              </Button>
            </div>
            <p>{text}</p>
            <DecisionForm
              entityKey={"assumption:" + i}
              {...{ project, commit, busy }}
            />
          </article>
        ))}
      </div>
      <div className="questions-grid">
        {[
          ["open_questions", "Modelin açık soruları"],
          ["missing_information", "Eksik bilgi notları"],
        ].map(([key, title]) => (
          <section className="question-section" key={key}>
            <h2>{title}</h2>
            <ul>
              {project.state.analysis[key].map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
function AssumptionEditor({ modal, commit, onClose, busy }) {
  const [text, setText] = useState(modal.text),
    [reason, setReason] = useState("");
  return (
    <Modal title="Varsayımı düzenle" onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (
            await commit(
              "set_assumption",
              String(modal.index),
              { text },
              reason,
            )
          )
            onClose();
        }}
      >
        <div className="modal-body">
          <Field label="Varsayım">
            <textarea
              required
              rows={5}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </Field>
          <Field label="Değişiklik gerekçesi">
            <textarea
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
        </div>
        <footer>
          <Button type="button" onClick={onClose}>
            Vazgeç
          </Button>
          <Button className="primary" icon={Save} disabled={busy}>
            Kaydet
          </Button>
        </footer>
      </form>
    </Modal>
  );
}

function HistoryView({ project }) {
  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">KARAR İZİ</span>
          <h1>Ne değişti, kim değiştirdi, neden?</h1>
          <p>
            İlk model çıktısı korunur. Geri alma işlemleri de geçmişte görünür.
          </p>
        </div>
        <Badge>Çalışma sürümü {project.version}</Badge>
      </div>
      <div className="history-grid">
        <section>
          <h2>
            <GitCompareArrows size={19} /> İlk model çıktısına göre farklar
          </h2>
          {!project.changes.length ? (
            <div className="plain-card">
              <p>Mimari nesneler ve eşleştirmeler ilk çıktıyla aynı.</p>
              <small>
                İnceleme kararları ve yerleşim değişiklikleri işlem geçmişinde
                listelenir.
              </small>
            </div>
          ) : (
            project.changes.map((c) => (
              <details className="diff-item" key={c.kind + c.id}>
                <summary>
                  <Badge tone={c.change === "removed" ? "red" : "teal"}>
                    {
                      {
                        added: "Eklendi",
                        removed: "Kaldırıldı",
                        modified: "Değiştirildi",
                      }[c.change]
                    }
                  </Badge>
                  {c.after?.name || c.before?.name || c.id}
                </summary>
                <div className="diff-grid">
                  <div>
                    <strong>Önce</strong>
                    <pre>{JSON.stringify(c.before, null, 2)}</pre>
                  </div>
                  <div>
                    <strong>Şimdi</strong>
                    <pre>{JSON.stringify(c.after, null, 2)}</pre>
                  </div>
                </div>
              </details>
            ))
          )}
        </section>
        <section>
          <h2>
            <History size={19} /> İşlem geçmişi
          </h2>
          <div className="timeline">
            {project.history.map((h, i) => (
              <article key={i}>
                <span className="timeline-dot" />
                <div className="inline spread">
                  <strong>{actions[h.action] || h.action}</strong>
                  <small>{date(h.at)}</small>
                </div>
                <p>{h.reason}</p>
                <small>
                  {h.actor} · Kayıt {h.revision}
                </small>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function HelpDialog({ onClose }) {
  return (
    <Modal title="İnceleme nasıl çalışır?" onClose={onClose} wide>
      <div className="modal-body help">
        <section>
          <span className="help-number">1</span>
          <div>
            <h3>Şemadan başla</h3>
            <p>
              Bir blok veya oka tıkla. Dayanak cümlesi, otomatik kontroller ve
              ilgili bulgular sağ panelde açılır. Kaynak satırına tıklayarak
              ters yönde de gezebilirsin.
            </p>
          </div>
        </section>
        <section>
          <span className="help-number">2</span>
          <div>
            <h3>Üç durumu ayır</h3>
            <p>
              <b>Karşılık seçilmiş:</b> model kaynakla nesneyi eşleştirmiş.{" "}
              <b>Alıntı metinde var:</b> yazılım metin eşleşmesini bulmuş.{" "}
              <b>Onaylandı:</b> mühendis gerekçeli karar vermiş. Bunlar aynı şey
              değildir.
            </p>
          </div>
        </section>
        <section>
          <span className="help-number">3</span>
          <div>
            <h3>Gerekçesiyle düzelt</h3>
            <p>
              Düzenle düğmesiyle yönü, arayüzü, sınıfı veya kanıtları değiştir.
              Yeni öğe ekleyebilir, tutamaçlardan bağlantı kurabilir ve öğe
              kaldırabilirsin. Kaydetmek mühendis onayı vermez.
            </p>
          </div>
        </section>
        <section>
          <span className="help-number">4</span>
          <div>
            <h3>Kararını kaydet</h3>
            <p>
              Bulgu kabul / red / çözüldü kararlarını ve birleştirmeleri
              gerekçesiyle kaydet. Mimari değişirse etkilenen eski kararlar
              yeniden incelemeye açılır.
            </p>
          </div>
        </section>
        <section>
          <span className="help-number">5</span>
          <div>
            <h3>Çalışmanı koru</h3>
            <p>
              Her kaydetme yerel veritabanında sürüm oluşturur. Sürüklenen
              konumlar otomatik kaydedilir. Geri al / yinele kullanılabilir.
              Çıktı paketi ilk modeli, güncel modeli, şemaları ve karar
              geçmişini içerir.
            </p>
          </div>
        </section>
      </div>
    </Modal>
  );
}

function App() {
  const [bootstrap, setBootstrap] = useState(null),
    [project, setProject] = useState(null),
    [view, setView] = useState("diagram"),
    [selection, setSelection] = useState(null),
    [modal, setModal] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [job, setJob] = useState(null),
    [railOpen, setRailOpen] = useState(true),
    [selectedIssue, setSelectedIssue] = useState(null);
  const [actor, setActor] = useState(
    () => localStorage.getItem("workbench.actor") || "Mühendis",
  );
  const busyRef = useRef(false);
  useEffect(() => setError(""), [modal?.type]);
  const refresh = async () => {
    const b = await api("/bootstrap");
    csrf = b.token;
    setBootstrap(b);
    return b;
  };
  useEffect(() => {
    refresh()
      .then(async (b) => {
        const saved = localStorage.getItem("workbench.project");
        const p = b.projects.find((p) => p.id === saved) || b.projects[0];
        if (p) setProject(await api("/projects/" + p.id));
        const running = b.jobs.find((j) =>
          ["queued", "running"].includes(j.status),
        );
        if (running) setJob(running);
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    localStorage.setItem("workbench.actor", actor);
  }, [actor]);
  useEffect(() => {
    if (project) localStorage.setItem("workbench.project", project.id);
  }, [project?.id]);
  useEffect(() => {
    if (!message) return;
    const t = setTimeout(() => setMessage(""), 4500);
    return () => clearTimeout(t);
  }, [message]);
  const select = useCallback((s) => {
    setSelection(s);
    setView("diagram");
    setSelectedIssue(null);
  }, []);
  const openEditor = useCallback(
    (kind, object = null, params = null) =>
      setModal({ type: "entity", kind, object, params }),
    [],
  );
  async function load(id) {
    setBusy(true);
    setError("");
    try {
      const p = await api("/projects/" + id);
      setProject(p);
      setSelection(null);
      setView("diagram");
      setModal(null);
      setSelectedIssue(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function importRun(path) {
    setBusy(true);
    setError("");
    try {
      const p = await api("/projects/import", { path });
      setProject(p);
      setSelection(null);
      setView("diagram");
      setModal(null);
      setSelectedIssue(null);
      await refresh();
      setMessage("İnceleme açıldı. İlk model çıktısı korunuyor.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function commit(action, id, value, reason) {
    if (busyRef.current) return false;
    if (!actor.trim()) {
      setError("Üst çubuktaki mühendis adını doldurun.");
      return false;
    }
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      const p = await api("/projects/" + project.id + "/changes", {
        action,
        id,
        value,
        reason,
        actor: actor.trim(),
        version: project.version,
      });
      setProject(p);
      setMessage(
        action === "layout"
          ? "Yerleşim kaydedildi."
          : "Değişiklik ve gerekçesi kaydedildi.",
      );
      return true;
    } catch (e) {
      setError(e.message);
      if (e.status === 409) {
        setProject(await api("/projects/" + project.id));
        setModal(null);
      }
      return false;
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  async function startAnalysis(body) {
    setBusy(true);
    setError("");
    try {
      const j = await api("/analysis", body);
      setJob(j);
      setModal(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    let cancelled = false;
    let polling = false;
    const timer = setInterval(async () => {
      if (polling) return;
      polling = true;
      try {
        const j = await api("/jobs/" + job.id);
        if (cancelled) return;
        if (["completed", "partial"].includes(j.status) && j.project_id) {
          const p = await api("/projects/" + j.project_id);
          if (cancelled) return;
          setProject(p);
          setSelection(null);
          setView("diagram");
          await refresh();
          setMessage(
            j.mode === "fixture"
              ? "Çevrimdışı örnek hazır. Bu bir model başarı testi değildir."
              : "Yeni analiz incelemeye hazır.",
          );
        }
        if (!cancelled) setJob(j);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        polling = false;
      }
    }, 1500);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [job?.id, job?.status]);
  const onIssue = (i) => {
    const comp = project.state.architecture.components.some(
      (c) => c.id === i.object_id,
    );
    setSelection(
      i.object_id
        ? { kind: comp ? "component" : "connection", id: i.object_id }
        : i.source_id
          ? { kind: "source", id: i.source_id }
          : i.finding_id
            ? { kind: "finding", id: i.finding_id }
            : null,
    );
    setSelectedIssue(i);
    setView("diagram");
    if (!i.object_id && !i.source_id && !i.finding_id)
      setError(i.explanation + " " + i.suggestion);
  };
  const activeJob = job && ["queued", "running"].includes(job.status);
  return (
    <ErrorContext.Provider value={error}>
      <div className="app-shell">
        <header className="app-header">
          <a
            className="brand"
            href="#"
            onClick={(e) => {
              e.preventDefault();
              setView("diagram");
            }}
          >
            <span className="brand-mark">
              <Layers3 size={23} />
            </span>
            <span>
              Mimari <b>Atölyesi</b>
              <small>Kaynak · Mimari · Mühendis kararı</small>
            </span>
          </a>
          <div className="header-center">
            {project ? (
              <>
                <span className="header-separator" />
                <span className="project-title">{project.name}</span>
                <Badge>Sürüm {project.version}</Badge>
              </>
            ) : (
              <span className="muted">Mühendislik inceleme alanı</span>
            )}
          </div>
          <div className="header-actions">
            <label className="reviewer">
              <span>Mühendis</span>
              <input
                aria-label="Mühendis adı"
                value={actor}
                maxLength={120}
                onChange={(e) => setActor(e.target.value)}
              />
            </label>
            <Button
              icon={FolderOpen}
              disabled={!bootstrap || busy}
              onClick={async () => {
                await refresh();
                setModal({ type: "open" });
              }}
            >
              Aç
            </Button>
            <Button
              icon={Plus}
              className="primary"
              disabled={!bootstrap || busy || activeJob}
              onClick={() => setModal({ type: "analysis" })}
            >
              Yeni analiz
            </Button>
            <button
              className="icon-button"
              aria-label="Kullanım rehberi"
              onClick={() => setModal({ type: "help" })}
            >
              <CircleHelp size={19} />
            </button>
          </div>
        </header>
        {error && (
          <div className="banner error" role="alert">
            <AlertTriangle size={17} />
            <span>{error}</span>
            <button
              className="icon-button"
              aria-label="Hata mesajını kapat"
              onClick={() => setError("")}
            >
              <X size={17} />
            </button>
          </div>
        )}
        {message && (
          <div className="toast" role="status">
            <CheckCheck size={16} />
            {message}
          </div>
        )}
        {job && (
          <div
            className={
              "job-banner " + (job.status === "failed" ? "failed" : "")
            }
            role="status"
          >
            {activeJob ? (
              <LoaderCircle size={17} className="spin" />
            ) : (
              <Check size={17} />
            )}
            <strong>
              {job.mode === "fixture" ? "Çevrimdışı örnek" : "Model analizi"}
            </strong>
            <span>
              {job.input_name} · {job.message}{" "}
              {job.error_code && "(" + job.error_code + ")"}
            </span>
            {!activeJob && (
              <button
                className="icon-button"
                aria-label="Analiz bildirimini kapat"
                onClick={() => setJob(null)}
              >
                <X size={16} />
              </button>
            )}
          </div>
        )}
        {project ? (
          <>
            <div className="workspace-bar">
              <nav aria-label="Çalışma bölümleri">
                {[
                  ["diagram", Network, "Şema"],
                  ["sources", FileText, "Kaynaklar"],
                  ["review", MessageSquare, "İnceleme"],
                  ["assumptions", Lightbulb, "Varsayımlar"],
                  ["history", History, "Geçmiş"],
                ].map(([k, Icon, label]) => (
                  <button
                    key={k}
                    className={view === k ? "active" : ""}
                    onClick={() => setView(k)}
                  >
                    <Icon size={16} />
                    {label}
                    {k === "review" && (
                      <span className="nav-count">
                        {project.issues.length +
                          project.state.analysis.findings.length}
                      </span>
                    )}
                  </button>
                ))}
              </nav>
              <div className="workspace-actions">
                <span className="save-state">
                  {busy ? (
                    <>
                      <LoaderCircle className="spin" size={14} />
                      Kaydediliyor…
                    </>
                  ) : (
                    <>
                      <CheckCheck size={15} />
                      Kaydedildi
                    </>
                  )}
                </span>
                <button
                  className="icon-button"
                  aria-label="Son işlemi geri al"
                  disabled={!project.can_undo || busy}
                  onClick={() =>
                    commit("undo", "", {}, "Son işlem geri alındı")
                  }
                >
                  <Undo2 size={18} />
                </button>
                <button
                  className="icon-button"
                  aria-label="Geri alınan işlemi yinele"
                  disabled={!project.can_redo || busy}
                  onClick={() =>
                    commit("redo", "", {}, "Geri alınan işlem yinelendi")
                  }
                >
                  <Redo2 size={18} />
                </button>
                <a
                  className="button"
                  href={"/api/projects/" + project.id + "/export"}
                >
                  <Download size={16} />
                  <span>Çıktı paketi</span>
                </a>
              </div>
            </div>
            <div className="context-strip">
              <span>
                <b>{project.state.architecture.components.length}</b> bileşen
              </span>
              <span>
                <b>{project.state.architecture.connections.length}</b> bağlantı
              </span>
              <span>
                <b>{project.original.source_catalog.length}</b> kaynak
              </span>
              <button
                onClick={() => setView("review")}
                className={project.issues.length ? "amber-text" : ""}
              >
                <AlertTriangle size={14} />
                {project.issues.length} otomatik kontrol kaydı
              </button>
              <span className="context-model">
                {project.original.run_metadata?.settings?.model ||
                  "Kayıtlı model"}{" "}
                ·{" "}
                {project.original.review_status === "completed"
                  ? "Model incelemesi tamamlandı"
                  : project.original.review_status === "failed"
                    ? "Model incelemesi başarısız"
                    : "İkinci tur yapılmadı"}
              </span>
            </div>
            {view === "diagram" ? (
              <div className={"workspace " + (!railOpen ? "rail-hidden" : "")}>
                {railOpen && (
                  <Explorer {...{ project, selection }} onSelect={select} />
                )}
                <ReactFlowProvider key={project.id}>
                  <Diagram
                    {...{
                      project,
                      selection,
                      commit,
                      openEditor,
                      busy,
                      railOpen,
                      setRailOpen,
                    }}
                    onSelect={select}
                  />
                </ReactFlowProvider>
                <Inspector
                  {...{
                    project,
                    selection,
                    commit,
                    openEditor,
                    setModal,
                    busy,
                    selectedIssue,
                  }}
                  onSelect={select}
                />
              </div>
            ) : view === "sources" ? (
              <SourcesView {...{ project }} onSelect={select} />
            ) : view === "review" ? (
              <ReviewView
                {...{ project, setModal, onIssue }}
                onSelect={select}
              />
            ) : view === "assumptions" ? (
              <AssumptionsView {...{ project, commit, busy, setModal }} />
            ) : (
              <HistoryView project={project} />
            )}
          </>
        ) : (
          <main className="welcome">
            <div className="welcome-copy">
              <span className="eyebrow">
                MÜHENDİSLİK KARARLARI İÇİN BİR ÇALIŞMA ALANI
              </span>
              <h1>
                Bir şemadan fazlası.
                <br />
                <em>Dayanağı görünen bir mimari.</em>
              </h1>
              <p>
                Modelin çıkardığı mimariyi kaynaklarıyla birlikte incele.
                Eksikleri düzelt, kararlarını gerekçesiyle kaydet ve her
                değişikliğin izini koru.
              </p>
              <div className="inline">
                <Button
                  className="primary"
                  icon={FolderOpen}
                  disabled={!bootstrap || busy}
                  onClick={() => setModal({ type: "open" })}
                >
                  Kaydedilmiş analizi aç
                </Button>
                <Button
                  icon={Plus}
                  disabled={!bootstrap || busy || activeJob}
                  onClick={() => setModal({ type: "analysis" })}
                >
                  Yeni analiz
                </Button>
              </div>
              <div className="welcome-features">
                <span>
                  <BookOpen size={19} />
                  Kanıta kadar ilerle
                </span>
                <span>
                  <Pencil size={19} />
                  Şemayı düzenle
                </span>
                <span>
                  <History size={19} />
                  Karar izini koru
                </span>
              </div>
            </div>
            <div className="recent-panel">
              <span className="section-label">BAŞLAMAK İÇİN</span>
              <h2>Mevcut çalışmaların</h2>
              {!bootstrap ? (
                <p>Çalışmalar yükleniyor…</p>
              ) : bootstrap.projects.length ? (
                bootstrap.projects.slice(0, 4).map((p) => (
                  <button
                    className="project-row"
                    key={p.id}
                    onClick={() => load(p.id)}
                  >
                    <span className="file-square">
                      <Layers3 size={20} />
                    </span>
                    <span>
                      <strong>{p.name}</strong>
                      <small>İncelemeye devam et · Sürüm {p.version}</small>
                    </span>
                    <ArrowUpRight size={17} />
                  </button>
                ))
              ) : bootstrap.runs.length ? (
                bootstrap.runs.slice(0, 4).map((r) => (
                  <button
                    className="project-row"
                    key={r.path}
                    onClick={() => importRun(r.path)}
                  >
                    <span className="file-square">
                      <FolderOpen size={20} />
                    </span>
                    <span>
                      <strong>{r.name}</strong>
                      <small>{r.run}</small>
                    </span>
                    <ArrowUpRight size={17} />
                  </button>
                ))
              ) : (
                <p>
                  İlk analizinle başlayabilir veya API olmadan örneği
                  deneyebilirsin.
                </p>
              )}
              <div className="notice blue">
                <ShieldCheck size={17} />
                <p>
                  İlk model çıktısı ayrı tutulur. Düzenlemeler ve kararlar bu
                  bilgisayarda saklanır.
                </p>
              </div>
            </div>
          </main>
        )}
        {modal?.type === "open" && bootstrap && (
          <OpenDialog
            {...{ bootstrap, busy }}
            onOpen={load}
            onImport={importRun}
            onClose={() => setModal(null)}
          />
        )}
        {modal?.type === "analysis" && bootstrap && (
          <AnalysisDialog
            {...{ bootstrap, busy }}
            onStart={startAnalysis}
            onClose={() => setModal(null)}
          />
        )}
        {modal?.type === "entity" && project && (
          <EntityEditor
            {...{ modal, project, commit, busy }}
            onClose={() => setModal(null)}
          />
        )}
        {modal?.type === "delete" && project && (
          <DeleteDialog
            {...{ modal, project, commit, busy }}
            onClose={() => setModal(null)}
          />
        )}
        {modal?.type === "coverage" && project && (
          <CoverageEditor
            source={modal.source}
            {...{ project, commit, busy }}
            onClose={() => setModal(null)}
          />
        )}
        {modal?.type === "finding" && project && (
          <FindingEditor
            object={modal.object}
            {...{ project, commit, busy }}
            onClose={() => setModal(null)}
          />
        )}
        {modal?.type === "assumption" && (
          <AssumptionEditor
            {...{ modal, commit, busy }}
            onClose={() => setModal(null)}
          />
        )}
        {modal?.type === "help" && (
          <HelpDialog onClose={() => setModal(null)} />
        )}
      </div>
    </ErrorContext.Provider>
  );
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  render() {
    if (this.state.error)
      return (
        <main className="fatal">
          <h1>Arayüz yüklenemedi</h1>
          <p>Kaydedilmiş veriler korunuyor. Sayfayı yenileyin.</p>
          <pre>{this.state.error.message}</pre>
          <Button onClick={() => location.reload()}>Yenile</Button>
        </main>
      );
    return this.props.children;
  }
}
createRoot(document.getElementById("root")).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
);
