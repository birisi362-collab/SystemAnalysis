import React, { useEffect, useState } from "react";
import { Button, Field, api, uid } from "./workspace-ui.jsx";
import { ObjectFields } from "./workspace-panels.jsx";
import { objectName } from "./review-labels.js";
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
};
const display = (value) =>
  value == null
    ? "—"
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
  const dirty = JSON.stringify(commands) !== JSON.stringify(preview.commands);
  const stale = project.version !== preview.version;
  const setValue = (i, value) =>
    setCommands(commands.map((c, n) => (n === i ? { ...c, value } : c)));
  return (
    <div className="drawer-body engineering-preview">
      <p>{preview.reason}</p>
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
          {preview.affected_source_ids.join(", ") ||
            "Doğrudan bağlı madde yok."}
        </p>
        {preview.document_review_required && (
          <p>
            Şema değişiyor. TİD ile tutarlılığı “TİD güncellemesi öner” ile
            inceleyebilirsiniz.
          </p>
        )}
        {!!preview.stale_assumptions.length && (
          <div>
            <p>Bu değişiklik nedeniyle yeniden incelenecek varsayımlar:</p>
            {(preview.stale_assumption_details || []).map((r) => (
              <p key={r.id}>
                <b>{r.text}</b>
                <br />
                {r.reason}
              </p>
            ))}
          </div>
        )}
        {!!Object.keys(preview.stale_links).length && (
          <p>
            {Object.keys(preview.stale_links).length} kaydın kaynak dayanağı
            yeniden incelenmeli.
          </p>
        )}
      </div>
      {preview.changes.map((c) => (
        <article className="change-card" key={c.kind + c.id}>
          <strong>
            {kinds[c.kind]} · {c.after?.name || c.before?.name || c.id}
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
              <b>Kaydedilecek karar: {assumptionStates[c.after.status]}</b>
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
                  <p>{display(c.before?.[key])}</p>
                </div>
                <div>
                  <small>Sonra</small>
                  <p>{display(c.after?.[key])}</p>
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
              {c.value?.name || c.value?.requirement_id || c.id || "Yeni kayıt"}
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
            onClick={() => onRepreview(commands)}
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

export function TidPanel({ project, onCommands, onAssistant, busy }) {
  const [original, setOriginal] = useState(false),
    [query, setQuery] = useState(""),
    [edit, setEdit] = useState(null);
  const sources = original
    ? project.original.source_catalog
    : project.state.source_catalog;
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
  const save = async (remove) => {
    const ok = await onCommands(
      [
        {
          action: remove ? "delete_source" : "upsert_source",
          id: edit.id,
          value: remove ? {} : edit.value,
        },
      ],
      remove ? "TİD maddesini kaldır" : "TİD maddesini düzenle",
      edit.base,
    );
    if (ok) setEdit(null);
  };
  return (
    <div className="drawer-body">
      <div className="inline spread">
        <p>TİD çalışma sürümü {project.state.document_revision}</p>
        <a className="button" href={`/api/projects/${project.id}/tid`}>
          Word indir
        </a>
        <a
          className="button"
          href={`/api/projects/${project.id}/tid?format=txt`}
        >
          TXT indir
        </a>
      </div>
      <p>
        Kaynak maddeleri burada düzenleyebilir, yeni madde ekleyebilir ve güncel
        TİD'i yeni doküman olarak indirebilirsiniz.
      </p>
      <div className="inline">
        <Button disabled={busy || !!edit} onClick={() => start(null)}>
          Madde ekle
        </Button>
        <Button
          disabled={busy || !!edit}
          onClick={() =>
            onAssistant({
              mode: "tid",
              message:
                "Mimari değişikliklerini güncel TİD ile karşılaştır. Gerekli hedefli TİD değişikliklerini gerekçeleriyle öner; ilgisiz isterleri koru.",
            })
          }
        >
          TİD güncellemesi öner
        </Button>
      </div>
      <label className="check">
        <input
          type="checkbox"
          checked={original}
          onChange={(e) => setOriginal(e.target.checked)}
        />
        Özgün TİD'i göster
      </label>
      {edit ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save(false);
          }}
          className="change-card"
        >
          <strong>
            {edit.id ? "TİD maddesini düzenle" : "Yeni TİD maddesi"}
          </strong>
          <Field label="Kalıcı ister kimliği">
            <input
              required
              disabled={!!edit.id}
              value={edit.value.requirement_id}
              onChange={(e) =>
                setEdit({
                  ...edit,
                  value: { ...edit.value, requirement_id: e.target.value },
                })
              }
            />
          </Field>
          <Field label="Bölüm">
            <input
              value={edit.value.section || ""}
              onChange={(e) =>
                setEdit({
                  ...edit,
                  value: { ...edit.value, section: e.target.value },
                })
              }
            />
          </Field>
          <Field label="İster metni">
            <textarea
              required
              rows={7}
              value={edit.value.text}
              onChange={(e) =>
                setEdit({
                  ...edit,
                  value: { ...edit.value, text: e.target.value },
                })
              }
            />
          </Field>
          {edit.base !== project.version && (
            <p className="notice amber">
              Çalışma güncellendi. Vazgeçip maddeyi tekrar açın.
            </p>
          )}
          <div className="inline">
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
        <>
          <Field label="TİD içinde ara">
            <input value={query} onChange={(e) => setQuery(e.target.value)} />
          </Field>
          {sources
            .filter((s) =>
              (s.text + " " + s.requirement_id)
                .toLocaleLowerCase("tr")
                .includes(query.toLocaleLowerCase("tr")),
            )
            .map((s) => (
              <article className="change-card" key={s.requirement_id}>
                <div className="inline spread">
                  <strong>{s.original_id || s.requirement_id}</strong>
                  {!original && (
                    <Button disabled={busy} onClick={() => start(s)}>
                      Düzenle
                    </Button>
                  )}
                </div>
                {s.section && <small>{s.section}</small>}
                <p className="preserve-text">{s.text}</p>
                <Button
                  onClick={() =>
                    onAssistant({
                      selection: { source_id: s.requirement_id },
                      message:
                        "Bu TİD maddesinin güncel mimaride nasıl karşılandığını açıkla.",
                    })
                  }
                >
                  Asistana sor
                </Button>
              </article>
            ))}
        </>
      )}
      {!!project.state.retired_sources.length && (
        <details>
          <summary>
            Kaldırılmış maddeler · {project.state.retired_sources.length}
          </summary>
          {project.state.retired_sources.map((s, i) => (
            <p key={i}>
              {s.requirement_id}: {s.text}
            </p>
          ))}
        </details>
      )}
    </div>
  );
}

function LinkPicker({ label, values, selected, onChange }) {
  return (
    <Field label={label}>
      <select
        multiple
        value={selected}
        onChange={(e) =>
          onChange([...e.target.selectedOptions].map((o) => o.value))
        }
      >
        {values.map((x) => (
          <option key={x.id} value={x.id}>
            {x.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

export function AssumptionsPanel({ project, onCommands, onAssistant, busy }) {
  const [edit, setEdit] = useState(null);
  const start = (r) =>
    setEdit({
      base: project.version,
      id: r?.id || "",
      value: r
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
          },
    });
  const set = (key, value) =>
    setEdit((current) => ({
      ...current,
      value: { ...current.value, [key]: value },
    }));
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
    )
      setEdit(null);
  };
  return (
    <div className="drawer-body">
      <p>
        Kararı ve gerekçesini kaydedin. İlgili ister ve şema öğelerini seçerek
        hangi değişikliklerin bu kararı yeniden incelemeye açacağını belirleyin.
      </p>
      <Button disabled={busy || !!edit} onClick={() => start(null)}>
        Varsayım ekle
      </Button>
      {edit ? (
        <form
          className="change-card"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <Field label="Varsayım">
            <textarea
              required
              rows={3}
              value={edit.value.text}
              onChange={(e) => set("text", e.target.value)}
            />
          </Field>
          <Field label="Varsayımın gerekçesi">
            <textarea
              value={edit.value.rationale}
              onChange={(e) => set("rationale", e.target.value)}
            />
          </Field>
          <Field label="Mühendis kararı">
            <select
              required
              value={edit.value.status === "pending" ? "" : edit.value.status}
              onChange={(e) => set("status", e.target.value)}
            >
              <option value="" disabled>
                Karar seçin
              </option>
              {Object.entries(assumptionStates)
                .filter(([v]) => v !== "pending")
                .map(([v, t]) => (
                  <option key={v} value={v}>
                    {t}
                  </option>
                ))}
            </select>
          </Field>
          {edit.value.status === "pending" && (
            <p className="notice amber">
              Henüz karar seçilmedi. İlgili öğeleri seçmek varsayımı kabul veya
              ret etmez. Karar vermek için yukarıdan kabul, ret veya bilgi
              bekliyor seçin.
            </p>
          )}
          <Field label="Karar gerekçesi">
            <textarea
              required={edit.value.status !== "pending"}
              value={edit.value.note}
              onChange={(e) => set("note", e.target.value)}
            />
          </Field>
          <Field label="Doğru bilgi veya alternatif">
            <textarea
              value={edit.value.alternative}
              onChange={(e) => set("alternative", e.target.value)}
            />
          </Field>
          <LinkPicker
            label="İlgili TİD maddeleri (çoklu seçim)"
            values={project.state.source_catalog.map((s) => ({
              id: s.requirement_id,
              label:
                (s.original_id || s.requirement_id) +
                " · " +
                s.text.slice(0, 70),
            }))}
            selected={edit.value.source_ids}
            onChange={(v) => set("source_ids", v)}
          />
          <LinkPicker
            label="İlgili bileşenler (çoklu seçim)"
            values={project.state.architecture.components.map((s) => ({
              id: s.id,
              label: s.name,
            }))}
            selected={edit.value.component_ids}
            onChange={(v) => set("component_ids", v)}
          />
          <LinkPicker
            label="İlgili bağlantılar (çoklu seçim)"
            values={project.state.architecture.connections.map((s) => ({
              id: s.id,
              label: objectName(project, s.id),
            }))}
            selected={edit.value.connection_ids}
            onChange={(v) => set("connection_ids", v)}
          />
          <p className="micro">
            Çoklu seçim için Ctrl tuşunu kullanın. Karar yalnızca seçilen teknik
            dayanaklarla takip edilir. Öğe seçilmezse projenin diğer
            değişiklikleri bu kararı yeniden incelemeye açmaz.
          </p>
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
          <div className="engineering-actions">
            <Button
              type="submit"
              className="primary"
              disabled={
                busy ||
                edit.base !== project.version ||
                edit.value.status === "pending"
              }
            >
              {edit.value.status === "accepted"
                ? "Kabul kararını önizle"
                : edit.value.status === "rejected"
                  ? "Ret kararını önizle"
                  : "Kararı önizle"}
            </Button>
            {edit.value.status === "pending" && (
              <Button
                disabled={
                  busy ||
                  edit.base !== project.version ||
                  !edit.value.text.trim()
                }
                onClick={save}
              >
                Düzenlemeyi önizle (karar vermeden)
              </Button>
            )}
            <Button
              disabled={
                busy ||
                edit.base !== project.version ||
                edit.value.status === "pending" ||
                !edit.value.text.trim() ||
                (edit.value.status !== "pending" && !edit.value.note.trim())
              }
              onClick={() =>
                onAssistant({
                  mode: "assumption",
                  message: `Bu mühendis kararının şema ve TİD üzerindeki etkilerini incele ve gereken değişiklikleri öner. Varsayım: ${edit.value.text}. Karar: ${assumptionStates[edit.value.status]}. Gerekçe: ${edit.value.note}. Alternatif bilgi: ${edit.value.alternative || "Henüz belirtilmedi; bilinmeyen ayrıntıyı uydurma."}`,
                  pending_commands: [command()],
                })
              }
            >
              Karar ve etkilerini öner
            </Button>
            <Button onClick={() => setEdit(null)}>Vazgeç</Button>
          </div>
        </form>
      ) : (
        project.state.assumption_records.map((r) => (
          <article className="change-card" key={r.id}>
            <div className="inline spread">
              <strong>{r.id}</strong>
              <span className="badge">{assumptionStates[r.status]}</span>
            </div>
            <p>{r.text}</p>
            {r.stale && (
              <p className="notice amber">
                <b>Yeniden incelenmeli:</b> {r.stale_reason}
              </p>
            )}
            {r.scope !== "project" &&
              !["source_ids", "component_ids", "connection_ids"].some(
                (key) => r[key]?.length,
              ) && (
                <p className="micro">
                  İlgili öğeler belirtilmemiş; proje değişiklikleri bu kararı
                  otomatik olarak yeniden incelemeye açmaz.
                </p>
              )}
            {r.note && (
              <p>
                <b>Mühendis gerekçesi:</b> {r.note}
              </p>
            )}
            {r.alternative && (
              <p>
                <b>Alternatif:</b> {r.alternative}
              </p>
            )}
            <Button disabled={busy} onClick={() => start(r)}>
              İncele ve karar ver
            </Button>
          </article>
        ))
      )}
      {!project.state.assumption_records.length && !edit && (
        <p>Henüz varsayım kaydı yok.</p>
      )}
    </div>
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
  settings,
  setSettings,
}) {
  const [message, setMessage] = useState(request?.message || ""),
    [mode, setMode] = useState(request?.mode || "chat"),
    [turns, setTurns] = useState([]),
    [error, setError] = useState(""),
    [working, setWorking] = useState(false);
  const running = working || ["queued", "running"].includes(job?.status);
  const set = (key, value) => setSettings({ ...settings, [key]: value });
  useEffect(() => {
    api(`/projects/${project.id}/conversation`)
      .then(setTurns)
      .catch((e) => setError(e.message));
  }, [project.id, job?.status]);
  const send = async (e) => {
    e.preventDefault();
    setWorking(true);
    setError("");
    try {
      const result = await api(`/projects/${project.id}/assistant`, {
        ...settings,
        version: project.version,
        message,
        mode,
        actor,
        selection: request?.selection || {},
        pending_commands: request?.pending_commands || [],
      });
      onJob(result);
      setMessage("");
      onRequestHandled();
    } catch (e) {
      setError(e.message);
    } finally {
      setWorking(false);
    }
  };
  return (
    <div className="drawer-body assistant-panel">
      <p>
        Güncel TİD, mimari, varsayımlar ve mühendis kararları hakkında konuşun.
        Önerilen düzenlemeleri önizleyerek uygulayın.
      </p>
      {request?.selection && (
        <p className="badge">
          Seçili bağlam: {request.selection.id || request.selection.source_id}
        </p>
      )}
      {!!request?.pending_commands?.length && (
        <p className="notice amber">
          Varsayım kararı henüz kaydedilmedi. Asistanın hazırladığı paketle
          birlikte önizlenecek.
        </p>
      )}
      <div className="chat-history" aria-live="polite">
        {turns.map((t) => (
          <article className="chat-turn" key={t.id}>
            <div className="chat-question">
              <small>
                {t.actor} · Proje sürümü {t.version}
              </small>
              <p>{t.message}</p>
            </div>
            {t.result ? (
              <div className="chat-answer">
                <small>Proje asistanı · Model yanıtı</small>
                <p className="preserve-text">{t.result.answer}</p>
                {t.result.citations?.map((c, i) => (
                  <blockquote key={i}>
                    <b>
                      {c.document === "original"
                        ? "Özgün TİD"
                        : "Çalışma TİD’i"}{" "}
                      · {c.source_id}
                    </b>
                    <p>{c.quote}</p>
                  </blockquote>
                ))}
                {t.result.proposal_error && (
                  <p className="notice amber">{t.result.proposal_error}</p>
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
                        Yanıttan sonra proje değişti. Güncel durum için yeni
                        öneri isteyin.
                      </p>
                    )}
                  </>
                )}
              </div>
            ) : (
              <p>
                {t.error ||
                  (["queued", "running"].includes(t.status) && !running
                    ? "Bu yanıt tamamlanmadı. Soruyu yeniden gönderebilirsiniz."
                    : "Yanıt hazırlanıyor…")}
              </p>
            )}
          </article>
        ))}
      </div>
      {error && (
        <p className="banner error" role="alert">
          {error}
        </p>
      )}
      <form onSubmit={send}>
        <Field label="Çalışma modu">
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="chat">Soru sor / düzenleme iste</option>
            <option value="tid">TİD güncellemesi öner</option>
            <option value="assumption">Varsayım etkilerini incele</option>
          </select>
        </Field>
        <Field label="Mesajınız">
          <textarea
            required
            rows={4}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Bu bağlantı hangi istere dayanıyor?"
          />
        </Field>
        <details open>
          <summary>Model bağlantısı</summary>
          <Field label="Model profili">
            <select
              value={settings.profile}
              onChange={(e) => set("profile", e.target.value)}
            >
              {bootstrap.profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id} · {p.model}
                </option>
              ))}
            </select>
          </Field>
          <Field label="API anahtarı (yerel ayar varsa boş)">
            <input
              type="password"
              autoComplete="off"
              value={settings.api_key}
              onChange={(e) => set("api_key", e.target.value)}
            />
          </Field>
          <Field label="Sunucu adresi (isteğe bağlı)">
            <input
              value={settings.base_url}
              onChange={(e) => set("base_url", e.target.value)}
            />
          </Field>
          <Field label="Model adı (isteğe bağlı)">
            <input
              value={settings.model}
              onChange={(e) => set("model", e.target.value)}
            />
          </Field>
          <Field label="Süre sınırı (saniye)">
            <input
              type="number"
              min={10}
              max={1800}
              value={settings.timeout}
              onChange={(e) => set("timeout", Number(e.target.value))}
            />
          </Field>
          <Field label="Çıktı token sınırı">
            <input
              type="number"
              min={512}
              max={65536}
              value={settings.max_tokens}
              onChange={(e) => set("max_tokens", Number(e.target.value))}
            />
          </Field>
        </details>
        <Button
          type="submit"
          className="primary"
          disabled={running || busy || !message.trim()}
        >
          {running ? "Model işlemi sürüyor…" : "Gönder"}
        </Button>
        {running && job?.mode === "assistant" && (
          <Button
            onClick={() =>
              api(`/jobs/${job.id}/cancel`, {}).catch((e) =>
                setError(e.message),
              )
            }
          >
            Yanıtı durdur
          </Button>
        )}
      </form>
    </div>
  );
}
