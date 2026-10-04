import React, { useState, useEffect, useRef } from "react";
import {
  Search,
  BookOpen,
  ChevronRight,
  ChevronLeft,
  Pencil,
  Trash2,
  Plus,
  ArrowRightLeft,
  Check,
  MessageSquare,
  X,
  Lightbulb,
} from "lucide-react";
import { Button, Field, cats, types } from "./workspace-ui.jsx";
import { sourceName, objectName, readableText } from "./review-labels.js";
import { topicPresentation, topicState } from "./topic-presentation.js";

export function DocumentPanel({
  project,
  sourceId,
  onSource,
  selectedObject,
  onSelect,
  onAttach,
  canAttach,
}) {
  const [query, setQuery] = useState(""),
    [selectedQuote, setSelectedQuote] = useState(null);
  const quote = selectedQuote?.sourceId === sourceId ? selectedQuote.text : "";
  const refs = useRef({});
  useEffect(() => {
    setQuery("");
    requestAnimationFrame(() =>
      refs.current[sourceId]?.scrollIntoView({
        block: "nearest",
        behavior: "smooth",
      }),
    );
  }, [sourceId]);
  const sources = project.original.source_catalog;
  return (
    <aside className="document-panel">
      <header className="panel-heading">
        <span className="eyebrow">
          <BookOpen size={14} /> KAYNAK BELGE
        </span>
        <h2>{project.original.run_metadata?.input_name || project.name}</h2>
        <label className="panel-search">
          <Search size={15} />
          <input
            aria-label="Belgede ara"
            placeholder="Belgede ara"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </header>
      <div className="document-scroll">
        {sources
          .filter((s) =>
            `${s.text} ${s.section || ""} ${sourceName(project, s.requirement_id)}`
              .toLocaleLowerCase("tr")
              .includes(query.toLocaleLowerCase("tr")),
          )
          .map((s, i) => {
            const active = sourceId === s.requirement_id;
            const attached = selectedObject?.evidence?.some(
              (e) => e.requirement_id === s.requirement_id,
            );
            const linked = [
              ...project.state.architecture.components.map((c) => ({
                ...c,
                kind: "component",
              })),
              ...project.state.architecture.connections.map((c) => ({
                ...c,
                kind: "connection",
              })),
            ].filter((o) =>
              o.evidence.some((e) => e.requirement_id === s.requirement_id),
            );
            return (
              <article
                key={s.requirement_id}
                ref={(el) => (refs.current[s.requirement_id] = el)}
                className={`document-fragment ${active ? "active" : ""} ${attached ? "attached" : ""}`}
              >
                <button
                  className="source-title"
                  onClick={() => onSource(s.requirement_id)}
                >
                  <span>{sourceName(project, s.requirement_id)}</span>
                  {attached && (
                    <span className="badge teal">Seçili öğenin kaynağı</span>
                  )}
                </button>
                {s.section && (
                  <small className="document-section">{s.section}</small>
                )}
                <p
                  onClick={() => onSource(s.requirement_id)}
                  onMouseUp={() => {
                    const selection = window.getSelection()?.toString().trim();
                    setSelectedQuote(
                      selection && s.text.includes(selection)
                        ? { sourceId: s.requirement_id, text: selection }
                        : null,
                    );
                  }}
                >
                  {s.text}
                </p>
                {active && (
                  <div className="source-actions">
                    {linked.map((o) => (
                      <button
                        className="text-button"
                        key={o.id}
                        onClick={() => onSelect({ kind: o.kind, id: o.id })}
                      >
                        {objectName(project, o.id)} <ChevronRight size={12} />
                      </button>
                    ))}
                    {canAttach && (
                      <Button
                        icon={Plus}
                        onClick={() =>
                          onAttach({
                            requirement_id: s.requirement_id,
                            quote:
                              quote && s.text.includes(quote) ? quote : s.text,
                          })
                        }
                      >
                        {quote && s.text.includes(quote)
                          ? "Seçili metni kaynak olarak kullan"
                          : "Bu metni kaynak olarak kullan"}
                      </Button>
                    )}
                  </div>
                )}
              </article>
            );
          })}
      </div>
      <div className="panel-footnote">
        Bir metne tıklayarak şemadaki karşılığını görebilirsiniz.
      </div>
    </aside>
  );
}

export function ObjectFields({ kind, value, onChange, components }) {
  const set = (k, v) => onChange({ ...value, [k]: v });
  return (
    <>
      {kind === "component" ? (
        <>
          <Field label="Bileşen adı">
            <input
              required
              value={value.name || ""}
              onChange={(e) => set("name", e.target.value)}
            />
          </Field>
          <Field label="Sınıf">
            <select
              value={value.category || "component"}
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
      ) : (
        <>
          <Field label="Başlangıç bileşeni">
            <select
              required
              value={value.source || ""}
              onChange={(e) => set("source", e.target.value)}
            >
              <option value="">Bileşen seçin</option>
              {components.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name || "Yeni bileşen"}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Hedef bileşen">
            <select
              required
              value={value.target || ""}
              onChange={(e) => set("target", e.target.value)}
            >
              <option value="">Bileşen seçin</option>
              {components.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name || "Yeni bileşen"}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Bağlantı yönü">
            <select
              value={value.direction || "unidirectional"}
              onChange={(e) => set("direction", e.target.value)}
            >
              <option value="unidirectional">
                Tek yönlü · Başlangıç → Hedef
              </option>
              <option value="bidirectional">
                Çift yönlü · Başlangıç ↔ Hedef
              </option>
            </select>
          </Field>
          <button
            className="text-button"
            type="button"
            disabled={value.direction === "bidirectional"}
            onClick={() =>
              onChange({ ...value, source: value.target, target: value.source })
            }
          >
            <ArrowRightLeft size={14} /> Yönü ters çevir
          </button>
          <div className="compact-fields">
            <Field label="Akış türü">
              <select
                value={value.type || "unknown"}
                onChange={(e) => set("type", e.target.value)}
              >
                {Object.entries(types).map(([v, t]) => (
                  <option key={v} value={v}>
                    {t}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Arayüz">
              <input
                value={value.protocol || ""}
                onChange={(e) => set("protocol", e.target.value)}
                placeholder="Belirtilmemiş"
              />
            </Field>
          </div>
          <Field label="Bağlantı etiketi">
            <input
              value={value.label || ""}
              onChange={(e) => set("label", e.target.value)}
            />
          </Field>
        </>
      )}
      <Field label="Açıklama">
        <textarea
          rows={3}
          value={value.description || ""}
          onChange={(e) => set("description", e.target.value)}
        />
      </Field>
    </>
  );
}

export function EvidenceList({ project, evidence = [], onSource, onRemove }) {
  return (
    <div className="workspace-evidence">
      {evidence.map((e, i) => (
        <div key={e.requirement_id + ":" + i}>
          <div className="inline spread">
            <button
              type="button"
              className="text-button"
              onClick={() => onSource(e.requirement_id)}
            >
              {sourceName(project, e.requirement_id)} <ChevronRight size={13} />
            </button>
            {onRemove && (
              <button
                type="button"
                className="text-button"
                onClick={() => onRemove(i)}
              >
                Bu kaynak ilgili değil
              </button>
            )}
          </div>
          <blockquote>
            {e.quote ||
              project.original.source_catalog.find(
                (s) => s.requirement_id === e.requirement_id,
              )?.text ||
              "Kaynak metin bulunamadı."}
          </blockquote>
        </div>
      ))}
    </div>
  );
}

export function EntityPanel({
  project,
  selection,
  object,
  draft,
  setDraft,
  onEdit,
  onCancel,
  onDelete,
  commit,
  busy,
  onSource,
  onNewFinding,
}) {
  const [note, setNote] = useState("");
  const editing = draft?.mode === "entity",
    removing = draft?.mode === "remove";
  const kind = draft?.kind || selection?.kind;
  const value = editing ? draft.value : object;
  if (!value)
    return (
      <div className="panel-empty">
        <Lightbulb size={28} />
        <h3>Şema senin çalışma alanın</h3>
        <p>
          Bir blok veya bağlantı seç. Kaynağı solda gör, düzenlemeyi burada yap.
        </p>
      </div>
    );
  const connected =
    kind === "component"
      ? project.state.architecture.connections.filter(
          (e) => e.source === value.id || e.target === value.id,
        )
      : [];
  return (
    <section className="object-panel">
      <div className="inline spread">
        <span className="eyebrow">
          {kind === "component" ? "BİLEŞEN" : "BAĞLANTI"}{" "}
          {editing ? "DÜZENLE" : "AYRINTISI"}
        </span>
        {editing && <span className="badge amber">Önizleme</span>}
      </div>
      <h2>
        {kind === "component"
          ? value.name || "Yeni bileşen"
          : editing && !draft.original
            ? "Yeni bağlantı"
            : objectName(project, value.id)}
      </h2>
      {removing ? (
        <div className="remove-preview">
          <p>
            Bu öğe{" "}
            {connected.length ? `ve ${connected.length} bağlantısı ` : ""}
            şemadan kaldırılacak.
          </p>
          {connected.map((e) => (
            <p key={e.id}>{objectName(project, e.id)}</p>
          ))}
          <Button
            className="danger"
            disabled={busy}
            icon={Trash2}
            onClick={async () => {
              if (
                await commit(
                  "delete_" + kind,
                  value.id,
                  { cascade: true },
                  note,
                )
              )
                onCancel(true);
            }}
          >
            Kaldır
          </Button>
          <Button onClick={() => onCancel()}>Vazgeç</Button>
        </div>
      ) : editing ? (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (
              await commit(
                "upsert_" + kind,
                draft.original?.id || "",
                draft.value,
                note,
              )
            )
              onCancel(false, true);
          }}
        >
          <ObjectFields
            kind={kind}
            value={value}
            components={project.state.architecture.components}
            onChange={(v) => setDraft({ ...draft, value: v })}
          />
          <details className="source-edit" open>
            <summary>Kaynaklar · {value.evidence.length}</summary>
            <EvidenceList
              {...{ project, onSource }}
              evidence={value.evidence}
              onRemove={(i) =>
                setDraft({
                  ...draft,
                  value: {
                    ...value,
                    evidence: value.evidence.filter((_, n) => n !== i),
                  },
                })
              }
            />
            <p className="micro">
              Soldaki belgeden metin seçerek kaynak ekleyebilirsiniz. Kendi
              tasarım eklemenizde kaynak seçmek zorunlu değil.
            </p>
          </details>
          <Field label="Not (isteğe bağlı)">
            <textarea
              rows={2}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </Field>
          <div className="editor-actions">
            <Button
              type="submit"
              className="primary"
              disabled={busy}
              icon={Check}
            >
              Uygula
            </Button>
            <Button onClick={() => onCancel()}>Vazgeç</Button>
          </div>
        </form>
      ) : (
        <>
          <p className="object-description">
            {value.description || "Açıklama eklenmemiş."}
          </p>
          {kind === "connection" && (
            <div className="inline">
              <p className="badge teal">
                {value.protocol || types[value.type]}
              </p>
              <span className="badge">
                {value.direction === "bidirectional"
                  ? "↔ Çift yönlü"
                  : "→ Tek yönlü"}
              </span>
            </div>
          )}
          <div className="inline">
            <Button icon={Pencil} onClick={() => onEdit(kind, value)}>
              Düzenle
            </Button>
            <button
              className="icon-button"
              aria-label="Seçili öğeyi kaldır"
              onClick={() => onDelete(kind, value)}
            >
              <Trash2 size={17} />
            </button>
            <button
              className="icon-button"
              aria-label="Seçili öğeye not ekle"
              onClick={onNewFinding}
            >
              <MessageSquare size={17} />
            </button>
          </div>
          <h4>Bu öğe nereden çıkarıldı?</h4>
          <EvidenceList
            {...{ project, onSource }}
            evidence={value.evidence}
            onRemove={(i) =>
              onEdit(kind, value, {
                ...value,
                evidence: value.evidence.filter((_, n) => i !== n),
              })
            }
          />
          {!value.evidence.length && (
            <p className="muted">
              {project.state.provenance[kind + ":" + value.id]
                ? "Mühendis düzenlemesi."
                : "Belgede dayanak belirtilmemiş."}
            </p>
          )}
        </>
      )}
    </section>
  );
}

export function Suggestions({ project, activeId, onTopic, onNewFinding }) {
  const [filter, setFilter] = useState("open");
  const [collapsed, setCollapsed] = useState(false);
  const topics = project.topics;
  const state = (t) =>
    t.status === "completed"
      ? "completed"
      : t.decision?.status === "waiting" && t.status !== "reopened"
        ? "waiting"
        : "open";
  return (
    <section className="suggestions">
      <div className="inline spread">
        <button
          className="text-button eyebrow"
          aria-expanded={!collapsed}
          onClick={() => setCollapsed(!collapsed)}
        >
          <Lightbulb size={14} /> ÖNERİLER VE NOTLAR
        </button>
        <button
          className="icon-button"
          aria-label="İnceleme notu ekle"
          onClick={onNewFinding}
        >
          <Plus size={16} />
        </button>
      </div>
      {!collapsed && (
        <>
          <div className="suggestion-filters">
            {[
              ["open", "Bekleyen"],
              ["waiting", "Bilgi bekleyen"],
              ["completed", "Tamamlanan"],
            ].map(([key, label]) => (
              <button
                className={filter === key ? "active" : ""}
                key={key}
                onClick={() => setFilter(key)}
              >
                {label} <b>{topics.filter((t) => state(t) === key).length}</b>
              </button>
            ))}
          </div>
          <div className="suggestion-list">
            {topics
              .filter((t) => state(t) === filter)
              .map((t) => {
                const f = project.state.analysis.findings.find(
                  (f) => f.id === t.finding_id,
                );
                const p = topicPresentation(
                  t,
                  f,
                  project.original.analysis.findings.find(
                    (x) => x.id === f.id,
                  ) || null,
                );
                return (
                  <button
                    key={t.id}
                    className={
                      "suggestion-card " + (activeId === t.id ? "active" : "")
                    }
                    onClick={() => onTopic(t.id)}
                  >
                    <span>
                      <strong>{p.question}</strong>
                      <small>
                        {t.status === "reopened"
                          ? "Bilgi değişti · yeniden incele"
                          : t.context_label || "Mühendis notu"}
                      </small>
                    </span>
                    <ChevronRight size={16} />
                  </button>
                );
              })}
            {!topics.some((t) => state(t) === filter) && (
              <p className="muted small-empty">Bu listede konu yok.</p>
            )}
          </div>
        </>
      )}
    </section>
  );
}

export function TopicPanel({
  project,
  topic,
  onTopic,
  onSource,
  onSelect,
  draft,
  setDraft,
  commit,
  busy,
  onClose,
  onPickSource,
}) {
  const [mode, setMode] = useState(""),
    [note, setNote] = useState(""),
    [ack, setAck] = useState(false);
  const finding = project.state.analysis.findings.find(
      (f) => f.id === topic.finding_id,
    ),
    proposal = project.proposals?.[finding.id];
  const active = project.topics.filter((t) => t.status !== "completed"),
    index = active.findIndex((t) => t.id === topic.id);
  const presentation = topicPresentation(
    topic,
    finding,
    project.original.analysis.findings.find((f) => f.id === finding.id) || null,
  );
  const changes = draft?.mode === "proposal" ? draft.changes : null;
  const preview = () =>
    setDraft({
      mode: "proposal",
      findingId: finding.id,
      changes: structuredClone(finding.proposed_changes),
    });
  const allComponents = [
    ...project.state.architecture.components,
    ...(changes || [])
      .filter((c) => c.kind === "component" && c.action === "add")
      .map((c) => ({ ...c.value, id: c.id })),
  ];
  return (
    <section className="topic-work">
      <div className="inline spread">
        <span className="eyebrow">{topicState(topic)}</span>
        <div className="inline">
          <button
            className="icon-button"
            disabled={index <= 0 || !!draft}
            aria-label="Önceki öneri"
            onClick={() => onTopic(active[index - 1].id)}
          >
            <ChevronLeft size={16} />
          </button>
          <button
            className="icon-button"
            disabled={index < 0 || index >= active.length - 1 || !!draft}
            aria-label="Sonraki öneri"
            onClick={() => onTopic(active[index + 1].id)}
          >
            <ChevronRight size={16} />
          </button>
          <button
            className="icon-button"
            disabled={!!draft}
            aria-label="Konu ayrıntısını kapat"
            onClick={onClose}
          >
            <X size={16} />
          </button>
        </div>
      </div>
      <h2>{presentation.question}</h2>
      <p>{presentation.reason}</p>
      <details className="model-note">
        <summary>Neden önerildi?</summary>
        <p>{readableText(finding.description, project)}</p>
        <p>{readableText(finding.recommended_action, project)}</p>
      </details>
      <div className="source-chips">
        {topic.source_ids.map((id) => (
          <button key={id} onClick={() => onSource(id)}>
            <BookOpen size={12} />
            {sourceName(project, id)}
          </button>
        ))}
      </div>
      <div className="related-links">
        {topic.primary_object_ids.map((id) => {
          const c = project.state.architecture.components.find(
              (c) => c.id === id,
            ),
            e = project.state.architecture.connections.find((e) => e.id === id);
          return (
            (c || e) && (
              <button
                className="text-button"
                key={id}
                onClick={() =>
                  onSelect({ kind: c ? "component" : "connection", id })
                }
              >
                {objectName(project, id)} <Pencil size={12} />
              </button>
            )
          );
        })}
      </div>
      {!!finding.proposed_changes?.length && !changes && (
        <Button
          className="primary"
          icon={Lightbulb}
          disabled={
            !!draft || proposal?.stale || topic.decision?.status === "applied"
          }
          onClick={preview}
        >
          Değişikliği önizle
        </Button>
      )}
      {proposal?.stale && topic.decision?.status !== "applied" && (
        <div className="notice amber">
          Önerinin dayandığı öğeler değişti. Güncel tasarımı yeniden
          değerlendirebilir veya öğeyi elle düzenleyebilirsiniz.
          <ul>
            {proposal.changed_objects?.map((c) => (
              <li key={c.id}>
                {c.after?.name || c.before?.name || objectName(project, c.id)}:{" "}
                {c.after
                  ? c.before
                    ? "Bilgileri değişti"
                    : "Eklendi"
                  : "Kaldırıldı"}
              </li>
            ))}
          </ul>
        </div>
      )}
      {changes && (
        <form
          className="proposal-edit"
          onSubmit={async (e) => {
            e.preventDefault();
            if (
              await commit(
                "apply_proposal",
                finding.id,
                { fingerprint: proposal.fingerprint, changes },
                note || "Öneri uygulandı: " + presentation.question,
              )
            ) {
              setDraft(null);
              setNote("");
            }
          }}
        >
          {changes.map((c, i) => {
            const field = c.kind === "component" ? "components" : "connections";
            const old = project.state.architecture[field].find(
              (o) => o.id === c.id,
            );
            const value = {
              evidence: [],
              ...(old || {}),
              ...c.value,
              id: c.id,
            };
            return (
              <details open key={i}>
                <summary>
                  {c.action === "add"
                    ? "Ekle"
                    : c.action === "remove"
                      ? "Kaldır"
                      : "Düzenle"}{" "}
                  ·{" "}
                  {c.kind === "component"
                    ? value.name || "Bileşen"
                    : "Bağlantı"}
                </summary>
                {c.action === "remove" ? (
                  <p>{objectName(project, c.id)}</p>
                ) : (
                  <>
                    <ObjectFields
                      kind={c.kind}
                      value={value}
                      components={allComponents}
                      onChange={(v) =>
                        setDraft({
                          ...draft,
                          changes: changes.map((x, n) =>
                            n === i ? { ...x, value: v } : x,
                          ),
                        })
                      }
                    />
                    <EvidenceList
                      {...{ project, onSource }}
                      evidence={value.evidence}
                      onRemove={(removeIndex) =>
                        setDraft({
                          ...draft,
                          changes: changes.map((x, n) =>
                            n === i
                              ? {
                                  ...x,
                                  value: {
                                    ...value,
                                    evidence: value.evidence.filter(
                                      (_, j) => j !== removeIndex,
                                    ),
                                  },
                                }
                              : x,
                          ),
                        })
                      }
                    />
                    <Button
                      onClick={() => {
                        setDraft({ ...draft, sourceTarget: i });
                        onPickSource();
                      }}
                    >
                      {draft.sourceTarget === i
                        ? "Soldaki belgeden metin seçin"
                        : "Belgeden kaynak ekle"}
                    </Button>
                  </>
                )}
              </details>
            );
          })}
          {!!finding.open_details?.length && (
            <>
              <p>{finding.open_details.join(" ")}</p>
              <label className="check">
                <input
                  type="checkbox"
                  checked={ack}
                  onChange={(e) => setAck(e.target.checked)}
                />
                Eksik bilgileri değerlendirdim ve alanları düzenledim.
              </label>
            </>
          )}
          <Field label="Uygulama notu (isteğe bağlı)">
            <textarea
              rows={2}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </Field>
          <div className="editor-actions">
            <Button
              type="submit"
              className="primary"
              disabled={busy || (!!finding.open_details?.length && !ack)}
            >
              Öneriyi uygula
            </Button>
            <Button onClick={() => setDraft(null)}>Vazgeç</Button>
          </div>
        </form>
      )}
      {!changes && (
        <>
          <div className="topic-actions">
            <Button disabled={!!draft} onClick={() => setMode("resolved")}>
              İnceledim
            </Button>
            <Button disabled={!!draft} onClick={() => setMode("waiting")}>
              Bilgi bekliyorum
            </Button>
            <Button disabled={!!draft} onClick={() => setMode("rejected")}>
              Reddet
            </Button>
          </div>
          {mode && (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (
                  await commit(
                    "set_topic_decision",
                    topic.id,
                    { status: mode },
                    note,
                  )
                ) {
                  setMode("");
                  setNote("");
                }
              }}
            >
              <Field label="Kısa karar notu">
                <textarea
                  required
                  rows={2}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder={
                    mode === "waiting"
                      ? "Hangi bilgi netleşmeli?"
                      : "Kararınızı kısaca açıklayın."
                  }
                />
              </Field>
              <Button
                type="submit"
                className="primary"
                disabled={busy || !note.trim()}
              >
                Kararı kaydet
              </Button>
            </form>
          )}
        </>
      )}
      {topic.decision && (
        <details className="previous-decision">
          <summary>Önceki karar</summary>
          <p>{topic.decision.note}</p>
          <small>
            {topic.decision.actor} ·{" "}
            {new Date(topic.decision.at).toLocaleString("tr-TR")}
          </small>
        </details>
      )}
    </section>
  );
}

export function NoteEditor({ project, selection, onClose, commit, busy }) {
  const [title, setTitle] = useState(""),
    [description, setDescription] = useState("");
  return (
    <form
      className="object-panel"
      onSubmit={async (e) => {
        e.preventDefault();
        const f = {
          id: "F_" + crypto.randomUUID().slice(0, 8),
          title,
          description,
          type: "other",
          severity: "info",
          evidence: [],
          related_component_ids:
            selection?.kind === "component" ? [selection.id] : [],
          related_connection_ids:
            selection?.kind === "connection" ? [selection.id] : [],
        };
        if (await commit("add_finding", "", f)) onClose();
      }}
    >
      <h2>İnceleme notu ekle</h2>
      <Field label="Not başlığı">
        <input
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </Field>
      <Field label="Gözlem ve öneri">
        <textarea
          required
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={4}
        />
      </Field>
      <div className="editor-actions">
        <Button type="submit" className="primary" disabled={busy}>
          Notu ekle
        </Button>
        <Button onClick={onClose}>Vazgeç</Button>
      </div>
    </form>
  );
}
