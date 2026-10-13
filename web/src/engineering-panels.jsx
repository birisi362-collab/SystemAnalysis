import React, { useEffect, useState, useRef } from "react";
import { Button, Field, api, uid } from "./workspace-ui.jsx";
import { ObjectFields } from "./workspace-panels.jsx";
import { objectName, sourceName, readableText } from "./review-labels.js";
import {
  MessageCircle,
  Minus,
  Maximize2,
  Minimize2,
  X,
  Send,
} from "lucide-react";
import "./engineering.css";

export const assumptionStates = {
  pending: "İnceleme bekliyor",
  accepted: "Kabul edildi",
  rejected: "Reddedildi",
  waiting: "Bilgi bekliyor",
};
const kinds = {
  component: "Bileşen",
  connection: "Bağlantı",
  requirement: "TİD maddesi",
  assumption: "Varsayım",
  decision: "Mühendis kararı",
};
const fields = {
  text: "Metin",
  section: "Bölüm",
  name: "Ad",
  description: "Açıklama",
  protocol: "Arayüz",
  direction: "Yön",
  source: "Başlangıç",
  target: "Hedef",
  type: "Akış türü",
  label: "Etiket",
  evidence: "Dayanak",
  status: "Durum",
  note: "Karar gerekçesi",
  alternative: "Alternatif bilgi",
  rationale: "Varsayım gerekçesi",
  source_ids: "İlgili isterler",
  component_ids: "İlgili bileşenler",
  connection_ids: "İlgili bağlantılar",
  category: "Sınıf",
  stale: "Yeniden inceleme",
  stale_reason: "Yeniden inceleme gerekçesi",
  scope: "Karar kapsamı",
  original_id: "Doküman numarası",
  impact_review: "Yeniden inceleme seçimi",
};
const display = (value) =>
  value == null
    ? "—"
    : typeof value === "object" && !Array.isArray(value)
      ? value.action === "review"
        ? "Yeniden değerlendir"
        : value.action === "keep"
          ? "Yeniden değerlendirmeye gerek yok"
          : "—"
      : typeof value === "boolean"
        ? value
          ? "Evet"
          : "Hayır"
        : Array.isArray(value)
          ? value
              .map((x) =>
                typeof x === "object"
                  ? `${x.requirement_id}: ${x.quote || ""}`
                  : x,
              )
              .join("\n") || "—"
          : assumptionStates[value] ||
            { linked: "İlgili öğeler", project: "Proje genelinde" }[value] ||
            String(value);

export function ChangePreview({
  preview,
  project,
  busy,
  error,
  onApply,
  onCancel,
  onRepreview,
}) {
  const [commands, setCommands] = useState(preview.commands);
  const [editing, setEditing] = useState(false);
  const [reviews, setReviews] = useState(preview.assumption_reviews || {});
  const [showAll, setShowAll] = useState(false);
  const candidates = preview.assumption_review_candidates || [];
  const reviewDirty =
    JSON.stringify(reviews) !==
    JSON.stringify(preview.assumption_reviews || {});
  const dirty =
    reviewDirty ||
    JSON.stringify(commands) !== JSON.stringify(preview.commands);
  const stale = project.version !== preview.version;
  const setValue = (i, value) =>
    setCommands(commands.map((c, n) => (n === i ? { ...c, value } : c)));
  return (
    <div className="drawer-body engineering-preview">
      <p>{readableText(preview.reason, project)}</p>
      <p className="micro">
        Proje sürümü {preview.version} · {preview.changes.length} değişen kayıt
        · Tek işlemle geri alınabilir.
      </p>
      {(error || stale) && (
        <p className="banner error" role="alert">
          {error ||
            "Proje bu önizlemeden sonra değişti. Kapatıp güncel kayıt üzerinden yeniden hazırlayın."}
        </p>
      )}
      <div className="impact-box">
        <strong>Değişikliğin etkisi</strong>
        <p>
          Etkilenen TİD maddeleri:{" "}
          {preview.affected_source_ids
            .map((id) => sourceName(project, id))
            .join(", ") || "Doğrudan bağlı madde yok."}
        </p>
        {preview.document_review_required && (
          <p>
            Şema değişiyor. TİD ile tutarlılığı “Şemaya göre güncelleme öner”
            ile inceleyebilirsiniz.
          </p>
        )}
        {!!preview.stale_assumptions.length && (
          <p>
            {preview.stale_assumptions.length} varsayım yeniden incelemeye
            açılacak.
          </p>
        )}
        {!!Object.keys(preview.stale_links).length && (
          <p>
            {Object.keys(preview.stale_links).length} kaydın kaynak dayanağı
            yeniden incelenmeli.
          </p>
        )}
      </div>
      {!!candidates.length && (
        <section className="review-choices">
          <h3>Hangi varsayımlar yeniden değerlendirilsin?</h3>
          <p className="micro">
            Önerilen seçimi değiştirebilirsiniz. Önceki kabul/ret kararı ve
            gerekçesi korunur. Bu seçim yalnızca önizlenen değişiklik için
            geçerlidir.
          </p>
          {candidates
            .filter((r) => showAll || r.affected || reviews[r.id])
            .map((r) => (
              <fieldset key={r.id}>
                <legend>{r.text}</legend>
                <p>
                  <span className={"status-tag " + r.status}>
                    {assumptionStates[r.status]}
                  </span>{" "}
                  <small>
                    {r.reason ||
                      "İlgili teknik dayanakta otomatik olarak değişiklik saptanmadı."}
                  </small>
                </p>
                <div className="review-options">
                  {[
                    ["review", "Yeniden değerlendir"],
                    ["keep", "Yeniden değerlendirmeye gerek yok"],
                  ].map(([value, label]) => (
                    <label key={value}>
                      <input
                        type="radio"
                        name={"review-" + r.id}
                        value={value}
                        checked={(reviews[r.id] || r.suggested) === value}
                        disabled={busy || stale}
                        onChange={() =>
                          setReviews({ ...reviews, [r.id]: value })
                        }
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </fieldset>
            ))}
          {!candidates.some((r) => r.affected) && !showAll && (
            <p>Otomatik olarak yeniden inceleme gerektiren varsayım yok.</p>
          )}
          <Button onClick={() => setShowAll(!showAll)}>
            {showAll
              ? "Yalnızca etkilenenleri göster"
              : "Diğer varsayımları da göster"}
          </Button>
        </section>
      )}
      {preview.changes.map((c) => (
        <article className="change-card" key={c.kind + c.id}>
          <strong>
            {kinds[c.kind]} ·{" "}
            {c.kind === "assumption"
              ? c.after?.text || c.before?.text
              : c.kind === "requirement"
                ? c.after?.original_id ||
                  c.before?.original_id ||
                  sourceName(project, c.id)
                : c.after?.name || c.before?.name || objectName(project, c.id)}
          </strong>
          <span className="badge">
            {!c.before
              ? "Eklenecek"
              : !c.after
                ? "Kaldırılacak"
                : "Düzenlenecek"}
          </span>
          {c.kind === "assumption" && c.after && (
            <p
              className={
                "notice " + (c.after.status === "pending" ? "amber" : "")
              }
            >
              <b>
                {commands.some(
                  (x) =>
                    x.action === "upsert_assumption" && x.value?.id === c.id,
                )
                  ? "Kaydedilecek karar"
                  : "Mevcut karar korunuyor"}
                : {assumptionStates[c.after.status]}
              </b>
              {c.after.status === "pending" && (
                <>
                  {" "}
                  · Bu işlem kabul/ret kararı içermez. Varsayım inceleme
                  beklemeye devam eder.
                </>
              )}
            </p>
          )}
          {Object.entries(fields)
            .filter(
              ([key]) =>
                JSON.stringify(c.before?.[key]) !==
                JSON.stringify(c.after?.[key]),
            )
            .map(([key, label]) => (
              <div className="field-diff" key={key}>
                <b>{label}</b>
                <div>
                  <small>Önce</small>
                  <p>{readableText(display(c.before?.[key]), project)}</p>
                </div>
                <div>
                  <small>Sonra</small>
                  <p>{readableText(display(c.after?.[key]), project)}</p>
                </div>
              </div>
            ))}
        </article>
      ))}
      {!preview.changes.length && <p>Görünen içerikte değişiklik yok.</p>}
      <Button disabled={busy || stale} onClick={() => setEditing(!editing)}>
        {editing ? "Öneri düzenlemeyi kapat" : "Öneriyi düzenle"}
      </Button>
      {editing &&
        commands.map((c, i) => (
          <div className="change-card" key={i}>
            <strong>
              {c.action === "upsert_assumption"
                ? c.value.text
                : c.value?.name ||
                  sourceName(project, c.value?.requirement_id) ||
                  "Yeni kayıt"}
            </strong>
            {c.action === "upsert_source" && (
              <>
                <Field label="Önerilen TİD metni">
                  <textarea
                    rows={5}
                    value={c.value.text}
                    onChange={(e) =>
                      setValue(i, { ...c.value, text: e.target.value })
                    }
                  />
                </Field>
                <Field label="Bölüm">
                  <input
                    value={c.value.section || ""}
                    onChange={(e) =>
                      setValue(i, { ...c.value, section: e.target.value })
                    }
                  />
                </Field>
              </>
            )}
            {["upsert_component", "upsert_connection"].includes(c.action) && (
              <ObjectFields
                kind={
                  c.action === "upsert_component" ? "component" : "connection"
                }
                value={c.value}
                components={[
                  ...project.state.architecture.components,
                  ...commands
                    .filter((x) => x.action === "upsert_component" && !x.id)
                    .map((x) => x.value),
                ]}
                onChange={(value) => setValue(i, value)}
              />
            )}
            {c.action === "upsert_assumption" && (
              <>
                <Field label="Mühendis kararı">
                  <select
                    value={c.value.status}
                    onChange={(e) =>
                      setValue(i, { ...c.value, status: e.target.value })
                    }
                  >
                    {Object.entries(assumptionStates).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Varsayım">
                  <textarea
                    value={c.value.text}
                    onChange={(e) =>
                      setValue(i, { ...c.value, text: e.target.value })
                    }
                  />
                </Field>
                <Field label="Karar gerekçesi">
                  <textarea
                    value={c.value.note || ""}
                    onChange={(e) =>
                      setValue(i, { ...c.value, note: e.target.value })
                    }
                  />
                </Field>
              </>
            )}
            {![
              "upsert_source",
              "upsert_component",
              "upsert_connection",
              "upsert_assumption",
            ].includes(c.action) && (
              <p>
                Bu işlemi değiştirmek için önizlemeyi kapatıp kaydı düzenleyin.
              </p>
            )}
          </div>
        ))}
      <div className="engineering-actions">
        {dirty ? (
          <Button
            className="primary"
            disabled={busy || stale}
            onClick={() => onRepreview(commands, reviews)}
          >
            Düzenlemeleri yeniden önizle
          </Button>
        ) : (
          <Button
            className="primary"
            disabled={busy || stale}
            onClick={onApply}
          >
            Değişiklikleri uygula
          </Button>
        )}
        <Button disabled={busy} onClick={onCancel}>
          Vazgeç
        </Button>
      </div>
    </div>
  );
}

export function TidPanel({
  project,
  onCommands,
  onAssistant,
  onContextChange,
  busy,
}) {
  const [original, setOriginal] = useState(false),
    [query, setQuery] = useState(""),
    [selected, setSelected] = useState(null),
    [edit, setEdit] = useState(null);
  const sources = original
    ? project.original.source_catalog
    : project.state.source_catalog;
  const visible = sources.filter((s) =>
    `${s.text} ${s.section || ""} ${s.original_id || ""}`
      .toLocaleLowerCase("tr")
      .includes(query.toLocaleLowerCase("tr")),
  );
  const sections = [...new Set(visible.map((s) => s.section || "Belge"))];
  const start = (s) =>
    setEdit({
      base: project.version,
      id: s?.requirement_id || "",
      value: s
        ? {
            requirement_id: s.requirement_id,
            text: s.text,
            section: s.section,
            original_id: s.original_id,
          }
        : {
            requirement_id: uid("TID"),
            text: "",
            section: "",
            original_id: null,
          },
    });
  const set = (key, value) =>
    setEdit((e) => ({ ...e, value: { ...e.value, [key]: value } }));
  const save = async (remove = false) => {
    if (
      await onCommands(
        [
          {
            action: remove ? "delete_source" : "upsert_source",
            id: edit.id,
            value: remove ? {} : edit.value,
          },
        ],
        remove ? "TİD maddesi kaldırılacak" : "TİD çalışma sürümü düzenlemesi",
        edit.base,
      )
    )
      setEdit(null);
  };
  const select = (s, e) => {
    setSelected(s.requirement_id);
    const selection = window.getSelection();
    const quote =
      selection &&
      e.currentTarget.contains(selection.anchorNode) &&
      e.currentTarget.contains(selection.focusNode)
        ? selection.toString().trim()
        : "";
    if (quote)
      onContextChange({
        source_id: s.requirement_id,
        document: original ? "original" : "current",
        quote,
      });
  };
  return (
    <section className="document-workspace" aria-label="TİD çalışma alanı">
      <header className="page-toolbar">
        <div>
          <h1>Teknik İsterler Dokümanı</h1>
          <small>
            Çalışma sürümü · {project.state.document_revision}. düzenleme
          </small>
        </div>
        <div className="toolbar-actions">
          <select
            aria-label="Belge sürümü"
            value={original ? "original" : "current"}
            onChange={(e) => {
              setOriginal(e.target.value === "original");
              setSelected(null);
            }}
            disabled={!!edit}
          >
            <option value="current">Çalışma sürümü</option>
            <option value="original">Orijinal belge</option>
          </select>
          <Button
            disabled={busy || original || !!edit || !selected}
            onClick={() =>
              start(sources.find((s) => s.requirement_id === selected))
            }
          >
            Düzenle
          </Button>
          <Button
            disabled={busy || original || !!edit}
            onClick={() => start(null)}
          >
            Madde ekle
          </Button>
          <Button
            disabled={busy || !!edit}
            onClick={() =>
              onAssistant({
                message:
                  "Güncel şemaya ve mühendis kararlarına göre çalışma TİD’inde gereken güncellemeleri öner. Orijinal belge ile farkları açıkla.",
              })
            }
          >
            Şemaya göre güncelleme öner
          </Button>
          <a
            className="button"
            href={`/api/projects/${project.id}/tid?format=docx&original=${original}`}
          >
            Word indir
          </a>
          <a
            className="button"
            href={`/api/projects/${project.id}/tid?format=txt&original=${original}`}
          >
            TXT indir
          </a>
        </div>
      </header>
      <div className="document-layout">
        <aside className="document-outline">
          <Field label="Belgede ara">
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Metin veya bölüm…"
            />
          </Field>
          <h3>Bölümler</h3>
          {sections.map((section, i) => (
            <button
              key={section}
              onClick={() =>
                document
                  .getElementById(`tid-section-${i}`)
                  ?.scrollIntoView({ block: "start", behavior: "smooth" })
              }
            >
              {section}
              <span>
                {
                  visible.filter((s) => (s.section || "Belge") === section)
                    .length
                }
              </span>
            </button>
          ))}
          <p className="micro">
            Düzenlemek için bir madde seçin. Metinden bir bölüm seçtiğinizde
            asistan konuşmasına bağlam olarak eklenir.
          </p>
        </aside>
        <div className="document-scroll">
          {edit ? (
            <form
              className="document-paper"
              onSubmit={(e) => {
                e.preventDefault();
                save();
              }}
            >
              <h2>{edit.id ? "TİD maddesini düzenle" : "Yeni TİD maddesi"}</h2>
              <Field label="Bölüm">
                <input
                  value={edit.value.section || ""}
                  onChange={(e) => set("section", e.target.value)}
                />
              </Field>
              <Field label="Doküman numarası (isteğe bağlı)">
                <input
                  value={edit.value.original_id || ""}
                  onChange={(e) => set("original_id", e.target.value || null)}
                />
              </Field>
              <Field label="Madde metni">
                <textarea
                  required
                  rows={12}
                  value={edit.value.text}
                  onChange={(e) => set("text", e.target.value)}
                />
              </Field>
              {edit.base !== project.version && (
                <p role="alert" className="notice amber">
                  Çalışma güncellendi. Vazgeçip güncel maddeyi tekrar açın.
                </p>
              )}
              <div className="engineering-actions">
                <Button
                  type="submit"
                  className="primary"
                  disabled={busy || edit.base !== project.version}
                >
                  Değişikliği önizle
                </Button>
                <Button onClick={() => setEdit(null)}>Vazgeç</Button>
                {edit.id && (
                  <Button
                    className="danger"
                    disabled={busy || edit.base !== project.version}
                    onClick={() => save(true)}
                  >
                    Kaldırmayı önizle
                  </Button>
                )}
              </div>
            </form>
          ) : (
            <article className="document-paper">
              <div className="document-caption">
                {original ? "ORİJİNAL BELGE" : "ÇALIŞMA SÜRÜMÜ"}
              </div>
              <h2>{project.name}</h2>
              {sections.map((section, i) => (
                <section
                  key={section}
                  id={`tid-section-${i}`}
                  className="document-section"
                >
                  <h3>{section}</h3>
                  {visible
                    .filter((s) => (s.section || "Belge") === section)
                    .map((s) => (
                      <div
                        key={s.requirement_id}
                        tabIndex={0}
                        className={
                          "document-paragraph " +
                          (selected === s.requirement_id ? "selected" : "")
                        }
                        onMouseUp={(e) => select(s, e)}
                        onClick={() => setSelected(s.requirement_id)}
                        onFocus={() => setSelected(s.requirement_id)}
                      >
                        {s.original_id && <small>{s.original_id}</small>}
                        <p>{s.text}</p>
                      </div>
                    ))}
                </section>
              ))}
              {!visible.length && <p>Aramanızla eşleşen metin bulunamadı.</p>}
            </article>
          )}
        </div>
      </div>
    </section>
  );
}

function LinkPicker({ label, values, selected, onChange }) {
  return (
    <fieldset className="link-picker">
      <legend>{label}</legend>
      <div>
        {values.map((x) => (
          <label key={x.id}>
            <input
              type="checkbox"
              checked={selected.includes(x.id)}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? [...selected, x.id]
                    : selected.filter((id) => id !== x.id),
                )
              }
            />
            <span>{x.label}</span>
          </label>
        ))}
        {!values.length && <small>İlgili kayıt yok.</small>}
      </div>
    </fieldset>
  );
}

export function AssumptionsPanel({ project, onCommands, onAssistant, busy }) {
  const [edit, setEdit] = useState(null),
    [filter, setFilter] = useState("review"),
    [query, setQuery] = useState("");
  const records = project.state.assumption_records;
  const matches = (r, f) =>
    f === "all" ||
    (f === "review"
      ? r.status === "pending" || r.status === "waiting" || r.stale
      : r.status === f);
  const filters = [
    ["review", "İnceleme bekleyen"],
    ["accepted", "Kabul edilen"],
    ["rejected", "Reddedilen"],
    ["all", "Tümü"],
  ];
  const start = (r, status) =>
    setEdit({
      base: project.version,
      id: r?.id || "",
      value: {
        ...(r
          ? structuredClone(r)
          : {
              id: uid("ASM"),
              text: "",
              rationale: "",
              source_ids: [],
              component_ids: [],
              connection_ids: [],
              scope: "linked",
              status: "pending",
              note: "",
              alternative: "",
            }),
        ...(status ? { status } : {}),
      },
    });
  const set = (key, value) =>
    setEdit((e) => ({ ...e, value: { ...e.value, [key]: value } }));
  const command = () => ({
    action: "upsert_assumption",
    id: edit.id,
    value: edit.value,
  });
  const save = async () => {
    if (
      await onCommands(
        [command()],
        edit.value.status === "pending"
          ? "Varsayım düzenlemesi; karar verilmedi"
          : "Varsayım kararı: " + assumptionStates[edit.value.status],
        edit.base,
      )
    ) {
      setFilter(
        ["accepted", "rejected"].includes(edit.value.status)
          ? edit.value.status
          : "review",
      );
      setEdit(null);
    }
  };
  const links = (r) => [
    ...r.component_ids.map((id) => objectName(project, id)),
    ...r.connection_ids.map((id) => objectName(project, id)),
    ...r.source_ids.map((id) => sourceName(project, id)),
  ];
  return (
    <section
      className="assumptions-workspace"
      aria-label="Varsayımlar çalışma alanı"
    >
      <header className="page-toolbar">
        <div>
          <h1>Varsayımlar</h1>
          <p>
            Kararını kaydet, gerekçesini görünür tut. Şema ve TİD
            değişikliklerini ayrıca önizle.
          </p>
        </div>
        <Button
          className="primary"
          disabled={busy || !!edit}
          onClick={() => start(null)}
        >
          Varsayım ekle
        </Button>
      </header>
      <div className="assumptions-content">
        <div className="assumption-filters" aria-label="Varsayım filtreleri">
          {filters.map(([id, label]) => (
            <button
              key={id}
              aria-pressed={filter === id}
              onClick={() => setFilter(id)}
            >
              {label}
              <span>{records.filter((r) => matches(r, id)).length}</span>
            </button>
          ))}
          <input
            aria-label="Varsayımlarda ara"
            type="search"
            placeholder="Varsayımlarda ara…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        {edit && (
          <form
            className="assumption-editor change-card"
            onSubmit={(e) => {
              e.preventDefault();
              save();
            }}
          >
            <h2>{edit.id ? "Varsayımı değerlendir" : "Yeni varsayım"}</h2>
            <Field label="Varsayım">
              <textarea
                required
                rows={3}
                value={edit.value.text}
                onChange={(e) => set("text", e.target.value)}
              />
            </Field>
            <div className="decision-options">
              {[
                ["accepted", "Kabul et"],
                ["rejected", "Reddet"],
                ["waiting", "Bilgi bekle"],
              ].map(([id, label]) => (
                <label
                  key={id}
                  className={edit.value.status === id ? "selected " + id : ""}
                >
                  <input
                    type="radio"
                    name="assumption-status"
                    checked={edit.value.status === id}
                    onChange={() => set("status", id)}
                  />
                  {label}
                </label>
              ))}
            </div>
            {edit.value.status === "pending" && (
              <p className="notice amber">
                Henüz karar seçilmedi. Yalnızca metni düzenlemek kabul/ret
                kararı oluşturmaz.
              </p>
            )}
            <Field label="Karar gerekçesi">
              <textarea
                required={edit.value.status !== "pending"}
                value={edit.value.note}
                onChange={(e) => set("note", e.target.value)}
              />
            </Field>
            <Field label="Doğru bilgi veya alternatif (varsa)">
              <textarea
                value={edit.value.alternative}
                onChange={(e) => set("alternative", e.target.value)}
              />
            </Field>
            <details>
              <summary>Varsayım gerekçesi ve ilgili öğeler</summary>
              <Field label="Varsayımın gerekçesi">
                <textarea
                  value={edit.value.rationale}
                  onChange={(e) => set("rationale", e.target.value)}
                />
              </Field>
              <LinkPicker
                label="İlgili bileşenler"
                values={project.state.architecture.components.map((s) => ({
                  id: s.id,
                  label: s.name,
                }))}
                selected={edit.value.component_ids}
                onChange={(v) => set("component_ids", v)}
              />
              <LinkPicker
                label="İlgili bağlantılar"
                values={project.state.architecture.connections.map((s) => ({
                  id: s.id,
                  label: objectName(project, s.id),
                }))}
                selected={edit.value.connection_ids}
                onChange={(v) => set("connection_ids", v)}
              />
              <LinkPicker
                label="İlgili TİD maddeleri"
                values={project.state.source_catalog.map((s) => ({
                  id: s.requirement_id,
                  label: sourceName(project, s.requirement_id) + " · " + s.text,
                }))}
                selected={edit.value.source_ids}
                onChange={(v) => set("source_ids", v)}
              />
              <label className="check">
                <input
                  type="checkbox"
                  checked={edit.value.scope === "project"}
                  onChange={(e) =>
                    set("scope", e.target.checked ? "project" : "linked")
                  }
                />
                Bu karar bütün projenin teknik içeriğine bağlı
              </label>
              <p className="micro">
                İlgili öğe seçilmezse başka proje değişiklikleri bu kararı
                otomatik olarak yeniden incelemeye açmaz.
              </p>
            </details>
            {edit.base !== project.version && (
              <p className="notice amber">
                Çalışma güncellendi. Vazgeçip güncel varsayımı tekrar açın.
              </p>
            )}
            <div className="engineering-actions">
              <Button
                type="submit"
                className="primary"
                disabled={busy || edit.base !== project.version}
              >
                {edit.value.status === "pending"
                  ? "Düzenlemeyi önizle (karar vermeden)"
                  : edit.value.status === "accepted"
                    ? "Kabul kararını önizle"
                    : edit.value.status === "rejected"
                      ? "Ret kararını önizle"
                      : "Kararı önizle"}
              </Button>
              <Button onClick={() => setEdit(null)}>Vazgeç</Button>
            </div>
            <p className="micro">
              Bu işlem kararınızı kaydeder. Gereken şema/TİD değişikliklerini
              karar kaydından sonra “Şema ve TİD etkilerini öner” ile
              hazırlayabilirsiniz.
            </p>
          </form>
        )}
        <div className="assumption-list">
          {records
            .filter(
              (r) =>
                matches(r, filter) &&
                r.text
                  .toLocaleLowerCase("tr")
                  .includes(query.toLocaleLowerCase("tr")),
            )
            .map((r) => (
              <article className="assumption-card" key={r.id}>
                <div className="assumption-card-heading">
                  <h2>{r.text}</h2>
                  <span className={"status-tag " + r.status}>
                    {assumptionStates[r.status]}
                  </span>
                </div>
                {r.stale && (
                  <p className="notice amber">
                    <b>Yeniden inceleme gerekli</b>
                    <br />
                    {r.stale_reason}
                    <br />
                    <small>Önceki karar: {assumptionStates[r.status]}</small>
                  </p>
                )}
                {r.rationale && (
                  <p className="assumption-rationale">{r.rationale}</p>
                )}
                <div className="linked-items">
                  {links(r).map((name, i) => (
                    <span key={i}>{name}</span>
                  ))}
                  {r.scope === "project" && <span>Proje genelinde</span>}
                  {!links(r).length && r.scope !== "project" && (
                    <small>İlgili öğe belirtilmemiş</small>
                  )}
                </div>
                {r.note && (
                  <p>
                    <b>Karar gerekçesi:</b> {r.note}
                  </p>
                )}
                {r.alternative && (
                  <p>
                    <b>Doğru bilgi / alternatif:</b> {r.alternative}
                  </p>
                )}
                {r.actor && (
                  <small>
                    {r.actor}
                    {r.at ? " · " + new Date(r.at).toLocaleString("tr-TR") : ""}
                  </small>
                )}
                {r.impact_review?.action && (
                  <p className="micro">
                    {r.impact_review.action === "keep"
                      ? "Son değişiklik için yeniden değerlendirmeye gerek olmadığı belirtildi."
                      : "Mühendis yeniden değerlendirme istedi."}{" "}
                    {r.impact_review.actor}
                  </p>
                )}
                <div className="engineering-actions">
                  <Button
                    disabled={busy || !!edit}
                    onClick={() => start(r, "accepted")}
                  >
                    Kabul et
                  </Button>
                  <Button
                    className="danger"
                    disabled={busy || !!edit}
                    onClick={() => start(r, "rejected")}
                  >
                    Reddet
                  </Button>
                  <Button disabled={busy || !!edit} onClick={() => start(r)}>
                    Düzenle
                  </Button>
                  {r.status !== "pending" && (
                    <Button
                      disabled={busy || !!edit}
                      onClick={() =>
                        onAssistant({
                          selection: { assumption_id: r.id },
                          message: `Kaydedilen bu varsayım kararının şema ve TİD üzerindeki etkilerini incele ve gereken değişiklikleri öner: ${r.text}. Karar: ${assumptionStates[r.status]}. Gerekçe: ${r.note}. Doğru bilgi: ${r.alternative || "Belirtilmedi; bilinmeyen ayrıntıyı uydurma."}`,
                        })
                      }
                    >
                      Şema ve TİD etkilerini öner
                    </Button>
                  )}
                </div>
              </article>
            ))}
        </div>
        {!records.some(
          (r) =>
            matches(r, filter) &&
            r.text
              .toLocaleLowerCase("tr")
              .includes(query.toLocaleLowerCase("tr")),
        ) && (
          <div className="empty-state">
            Bu görünümde varsayım yok. Diğer filtrelerden kararları
            inceleyebilirsiniz.
          </div>
        )}
      </div>
    </section>
  );
}

export function AssistantPanel({
  project,
  bootstrap,
  actor,
  job,
  onJob,
  onCommands,
  request,
  onRequestHandled,
  busy,
  modelSettings,
  open,
  onOpenChange,
  context,
  onClearContext,
  connectionError,
}) {
  const [message, setMessage] = useState(""),
    [turns, setTurns] = useState([]),
    [error, setError] = useState(""),
    [working, setWorking] = useState(false),
    [expanded, setExpanded] = useState(false);
  const history = useRef(null),
    composer = useRef(null);
  const running = working || ["queued", "running"].includes(job?.status);
  useEffect(() => {
    let active = true;
    api(`/projects/${project.id}/conversation`)
      .then((v) => {
        if (active) setTurns(v);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [project.id, job?.status]);
  useEffect(() => {
    if (request?.message) {
      setMessage((m) =>
        m.trim() ? m + "\n\n" + request.message : request.message,
      );
      onRequestHandled();
    }
  }, [request]);
  useEffect(() => {
    if (open) composer.current?.focus();
  }, [open]);
  useEffect(() => {
    if (history.current)
      history.current.scrollTop = history.current.scrollHeight;
  }, [turns, open]);
  const send = async (e) => {
    e.preventDefault();
    setWorking(true);
    setError("");
    try {
      const result = await api(`/projects/${project.id}/assistant`, {
        ...modelSettings.getSettings(),
        version: project.version,
        message,
        mode: "chat",
        actor: actor.trim() || "Mühendis",
        selection: context || {},
      });
      onJob(result);
      setMessage("");
    } catch (e) {
      setError(e.message);
    } finally {
      setWorking(false);
    }
  };
  const contextLabel =
    context?.quote ||
    (context?.assumption_id
      ? project.state.assumption_records.find(
          (r) => r.id === context.assumption_id,
        )?.text
      : context?.source_id
        ? sourceName(project, context.source_id)
        : context?.id
          ? objectName(project, context.id)
          : "");
  return (
    <>
      {!open && (
        <button
          className="assistant-launcher"
          onClick={() => onOpenChange(true)}
          aria-label="Asistanı aç"
        >
          <MessageCircle size={20} />
          <span>
            Asistan
            {running && job?.mode === "assistant"
              ? " · Yanıt hazırlanıyor"
              : ""}
          </span>
        </button>
      )}
      <section
        hidden={!open}
        className={"assistant-window " + (expanded ? "expanded" : "")}
        aria-label="Proje asistanı"
      >
        <header>
          <div>
            <MessageCircle size={19} />
            <strong>Proje asistanı</strong>
          </div>
          <div>
            <button
              className="icon-button"
              aria-label={expanded ? "Sohbeti küçült" : "Sohbeti büyüt"}
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
            </button>
            <button
              className="icon-button"
              aria-label="Asistanı daralt"
              onClick={() => onOpenChange(false)}
            >
              <Minus size={19} />
            </button>
          </div>
        </header>
        <div className="chat-model">
          <select
            aria-label="Sohbet modeli"
            value={modelSettings.profile}
            onChange={(e) => modelSettings.select(e.target.value)}
          >
            {bootstrap.profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {modelSettings.getSettings(p.id).model || p.id}
              </option>
            ))}
          </select>
        </div>
        <div className="chat-history" ref={history} aria-live="polite">
          {!turns.length && (
            <div className="chat-welcome">
              <MessageCircle size={28} />
              <h3>Tasarım üzerine konuşalım.</h3>
              <p>
                TİD, şema ve varsayımlar hakkında soru sorun veya düzenleme
                isteyin. Değişiklikleri uygulamadan önce önizleyeceksiniz.
              </p>
            </div>
          )}
          {turns.map((t) => (
            <article className="chat-turn" key={t.id}>
              <div className="chat-question">
                <small>{t.actor}</small>
                <p className="preserve-text">
                  {readableText(t.message, project)}
                </p>
              </div>
              {t.result ? (
                <div className="chat-answer">
                  <small>Proje asistanı</small>
                  <p className="preserve-text">
                    {readableText(t.result.answer, project)}
                  </p>
                  {t.result.citations?.map((c, i) => (
                    <blockquote key={i}>
                      <b>
                        {c.document === "original"
                          ? "Orijinal TİD"
                          : "Çalışma TİD’i"}{" "}
                        · {sourceName(project, c.source_id)}
                      </b>
                      <p>{c.quote}</p>
                    </blockquote>
                  ))}
                  {t.result.proposal_error && (
                    <p className="notice amber">
                      {readableText(t.result.proposal_error, project)}
                    </p>
                  )}
                  {!!t.result.commands?.length && (
                    <>
                      <Button
                        disabled={
                          busy ||
                          t.imported ||
                          t.version !== project.version ||
                          !!t.result.proposal_error
                        }
                        onClick={() =>
                          onCommands(t.result.commands, t.message, t.version)
                        }
                      >
                        Değişiklikleri önizle · {t.result.commands.length}
                      </Button>
                      {(t.imported || t.version !== project.version) && (
                        <p className="micro">
                          Proje değişti. Güncel durum için yeni öneri isteyin.
                        </p>
                      )}
                    </>
                  )}
                </div>
              ) : (
                <p>
                  {readableText(
                    t.error ||
                      (["queued", "running"].includes(t.status) && !running
                        ? "Bu yanıt tamamlanmadı. Soruyu yeniden gönderebilirsiniz."
                        : "Yanıt hazırlanıyor…"),
                    project,
                  )}
                </p>
              )}
            </article>
          ))}
        </div>
        {(error || (job?.mode === "assistant" && connectionError)) && (
          <p className="banner error" role="alert">
            {error || connectionError}
          </p>
        )}
        <form className="chat-composer" onSubmit={send}>
          {contextLabel && (
            <div className="context-chip" title={contextLabel}>
              <span>
                {context?.quote ? "Seçilen metin: " : "Bağlam: "}
                {contextLabel}
              </span>
              <button
                type="button"
                aria-label="Konuşma bağlamını kaldır"
                onClick={onClearContext}
              >
                <X size={14} />
              </button>
            </div>
          )}
          <textarea
            ref={composer}
            aria-label="Mesajınız"
            required
            rows={3}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Bir soru sorun veya değişiklik isteyin…"
          />
          <div className="chat-send">
            <small>
              {running
                ? "Model işlemi sürüyor…"
                : "Değişiklikler onayınızla uygulanır."}
            </small>
            {running && job?.mode === "assistant" ? (
              <Button
                onClick={() =>
                  api(`/jobs/${job.id}/cancel`, {}).catch((e) =>
                    setError(e.message),
                  )
                }
              >
                Durdur
              </Button>
            ) : (
              <Button
                icon={Send}
                type="submit"
                className="primary"
                disabled={running || busy || !message.trim()}
              >
                Gönder
              </Button>
            )}
          </div>
        </form>
      </section>
    </>
  );
}
