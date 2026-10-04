export const sourceName = (project, id) =>
  project.source_labels?.[id] || "Kaynak bulunamadı";
const escapeRegex = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
export function objectName(project, id, original = false) {
  const a = original
    ? project.original.architecture
    : project.state.architecture;
  const c = a.components.find((x) => x.id === id);
  if (c) return c.name;
  const e = a.connections.find((x) => x.id === id);
  return e
    ? `${a.components.find((c) => c.id === e.source)?.name || "Kaldırılmış başlangıç"} ${e.direction === "bidirectional" ? "↔" : "→"} ${a.components.find((c) => c.id === e.target)?.name || "Kaldırılmış hedef"}`
    : "Kaldırılmış öğe";
}
export function readableText(text, project) {
  const labels = {
    ...project.source_labels,
    ...Object.fromEntries(
      [
        ...project.state.architecture.components,
        ...project.state.architecture.connections,
      ].map((o) => [o.id, objectName(project, o.id)]),
    ),
  };
  const keys = Object.keys(labels).sort((a, b) => b.length - a.length);
  return keys.length
    ? (text || "").replace(
        new RegExp(
          `(?<![\\w-])(${keys.map(escapeRegex).join("|")})(?![\\w-])`,
          "g",
        ),
        (id) => labels[id],
      )
    : text || "";
}
