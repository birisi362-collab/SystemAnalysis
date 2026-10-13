import React from "react";
import { sourceName, objectName, readableText } from "./review-labels.js";

function FieldValue({ value, field, project, original = false }) {
  if (value === null || value === undefined || value === "")
    return <span className="muted">Belirtilmemiş</span>;
  if (field === "source" || field === "target")
    return objectName(project, value, original);
  if (field === "evidence")
    return value.length
      ? value.map((e, n) => (
          <p key={n}>
            <b>{sourceName(project, e.requirement_id)}</b>
            <br />
            {e.quote || "Alıntı yok"}
          </p>
        ))
      : "Dayanak eklenmemiş";
  if (field === "source_ids")
    return (
      value.map((id) => sourceName(project, id)).join(", ") || "Seçilmemiş"
    );
  if (field.endsWith("_ids"))
    return (
      value.map((id) => objectName(project, id, original)).join(", ") ||
      "Seçilmemiş"
    );
  if (field === "impact_review")
    return value.action === "review"
      ? "Mühendis yeniden değerlendirme istedi"
      : value.action === "keep"
        ? "Yeniden değerlendirmeye gerek yok"
        : "Belirtilmemiş";
  const names = {
    pending: "İnceleme bekliyor",
    accepted: "Kabul edildi",
    rejected: "Reddedildi",
    waiting: "Bilgi bekliyor",
    data: "Veri",
    power: "Güç",
    control: "Kontrol",
    communication: "Haberleşme",
    unknown: "Belirtilmemiş",
    system: "Sistem",
    subsystem: "Alt sistem",
    component: "Bileşen",
    external: "Dış sistem",
    covered: "Karşılık seçilmiş",
    partially_covered: "Kısmen temsil edilmiş",
    unmapped: "Henüz eşleştirilmemiş",
    not_architectural: "Bağlam / başlık",
    mechanical: "Mekanik",
    thermal: "Termal",
    contradiction: "Çelişki önerisi",
    ambiguous: "Belirsizlik",
    missing_interface: "Eksik arayüz",
    missing_connection: "Eksik bağlantı",
    traceability: "Kaynak izlenebilirliği",
    classification: "Sınıflandırma",
    other: "Diğer",
    low: "Düşük",
    medium: "Orta",
    high: "Yüksek",
    critical: "Kritik",
    info: "Bilgi",
    unidirectional: "Tek yönlü",
    bidirectional: "Çift yönlü",
  };
  if (typeof value === "string")
    return readableText(
      ["category", "type", "status", "severity", "direction"].includes(field)
        ? names[value] || value
        : value,
      project,
    );
  return Array.isArray(value) ? value.join(", ") : String(value);
}
const fields = {
  impact_review: "Yeniden inceleme seçimi",
  name: "Ad",
  label: "Bağlantı etiketi",
  description: "Açıklama",
  category: "Sınıf",
  source: "Başlangıç",
  target: "Hedef",
  direction: "Bağlantı yönü",
  type: "Akış türü",
  protocol: "Arayüz",
  evidence: "Doküman dayanağı",
  status: "Durum",
  related_component_ids: "Doğrudan bileşenler",
  related_connection_ids: "Doğrudan bağlantılar",
  contextual_component_ids: "Bağlamsal bileşenler",
  contextual_connection_ids: "Bağlamsal bağlantılar",
  notes: "Kapsama açıklaması",
  title: "Konu",
  recommended_action: "Öneri",
  text: "Metin",
  section: "Bölüm",
  note: "Karar gerekçesi",
  alternative: "Alternatif bilgi",
  rationale: "Varsayım gerekçesi",
  source_ids: "İlgili isterler",
  component_ids: "İlgili bileşenler",
  connection_ids: "İlgili bağlantılar",
  severity: "Önem",
};

export function HistoryChanges({ project, onSelect }) {
  const before = project.original.architecture;
  const after = project.state.architecture;
  const groups = [
    ["component", before.components, after.components],
    ["connection", before.connections, after.connections],
    ["source", before.requirement_coverage, after.requirement_coverage],
    [
      "requirement",
      project.original.source_catalog,
      project.state.source_catalog || project.original.source_catalog,
    ],
    [
      "finding",
      project.original.analysis.findings,
      project.state.analysis.findings,
    ],
    [
      "assumption",
      before.assumptions.map((text, id) => ({ id: String(id), text })),
      (
        project.state.assumption_records ||
        after.assumptions.map((text, id) => ({ id: String(id), text }))
      ).map((r, id) => ({ ...r, id: String(id) })),
    ],
  ];
  const changes = groups.flatMap(([kind, oldItems, newItems]) => {
    const key = (item) =>
      ["source", "requirement"].includes(kind) ? item.requirement_id : item.id;
    const ids = [...new Set([...oldItems, ...newItems].map(key))];
    return ids
      .map((id) => {
        const old = oldItems.find((item) => key(item) === id);
        const current = newItems.find((item) => key(item) === id);
        const changedFields = Object.keys(fields).filter((field) => {
          // Optional empty relation arrays added by newer schemas are not user edits.
          const empty = field.endsWith("_ids") ? [] : null;
          return (
            JSON.stringify(old?.[field] ?? empty) !==
            JSON.stringify(current?.[field] ?? empty)
          );
        });
        const name = ["source", "requirement"].includes(kind)
          ? sourceName(project, id)
          : kind === "finding"
            ? readableText(current?.title || old?.title, project)
            : kind === "assumption"
              ? current?.text || old?.text || "Varsayım"
              : objectName(project, id, !current);
        return { id, kind, old, current, changedFields, name };
      })
      .filter((row) => row.changedFields.length || !row.old || !row.current);
  });
  return (
    <details className="history-changes">
      <summary>
        Değişiklikleri gör <span>{changes.length} öğe</span>
      </summary>
      <p className="muted">
        İlk açılan model çıktısından bu yana yaptığınız düzenlemeler. Bir öğeyi
        açarak yalnız değişen alanlarını görebilirsiniz.
      </p>
      {!changes.length && (
        <p>
          Henüz içerik düzenlemesi yapılmamış. Kararlar ve şema yerleşimi
          aşağıdaki işlem geçmişinde görünür.
        </p>
      )}
      {changes.map((row) => (
        <details className="compare-object" key={row.kind + row.id}>
          <summary>
            <strong>{row.name}</strong>
            <span>
              {!row.old
                ? "Eklendi"
                : !row.current
                  ? "Kaldırıldı"
                  : `${row.changedFields.length} alan değişti`}
            </span>
          </summary>
          {row.current && row.kind !== "assumption" && (
            <button
              className="text-button"
              onClick={() => onSelect({ kind: row.kind, id: row.id })}
            >
              Güncel öğeyi aç
            </button>
          )}
          <div className="compare-scroll">
            <table className="compare-table">
              <thead>
                <tr>
                  <th>Değişen alan</th>
                  <th>İlk hali</th>
                  <th>Şimdi</th>
                </tr>
              </thead>
              <tbody>
                {row.changedFields.map((field) => (
                  <tr key={field}>
                    <th>
                      {row.kind === "finding"
                        ? {
                            type: "Konu türü",
                            related_component_ids: "İlgili bileşenler",
                            related_connection_ids: "İlgili bağlantılar",
                          }[field] || fields[field]
                        : fields[field]}
                    </th>
                    <td>
                      <FieldValue
                        project={project}
                        field={field}
                        value={row.old?.[field]}
                        original
                      />
                    </td>
                    <td>
                      <FieldValue
                        project={project}
                        field={field}
                        value={row.current?.[field]}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ))}
    </details>
  );
}
