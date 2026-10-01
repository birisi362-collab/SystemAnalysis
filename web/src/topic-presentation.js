// Presentation only: these questions do not assert that a model finding is true.
export function topicPresentation(topic, finding, originalFinding = finding) {
  const code = topic.checks?.[0]?.code || "";
  if (!finding) {
    if (topic.dependency_kind === "coverage")
      return {
        question: "Bu kaynağın şemadaki karşılığı ne?",
        reason: "Kaynak ile seçilen öğelerin ilişkisini netleştirin.",
      };
    if (topic.dependency_kind === "evidence")
      return {
        question: "Bu öğenin belge dayanağı nerede?",
        reason: "Dayanak eksik veya kaynak metinle uyuşmuyor.",
      };
    if (topic.dependency_kind === "protocol")
      return {
        question: "Bu bağlantıda hangi arayüz kullanılmalı?",
        reason: "Bağlantıdaki arayüzü kaynak cümlesiyle birlikte kontrol edin.",
      };
    if (code === "ORPHAN_COMPONENT")
      return {
        question: "Bu bileşenin bağlantısı olmalı mı?",
        reason: "Şemada bu bileşene bağlı bir akış bulunmuyor.",
      };
    return { question: topic.title, reason: topic.description };
  }
  const quote = finding.evidence.map((e) => e.quote || "").join(" ");
  if (
    originalFinding?.title === finding.title &&
    ["contradiction", "ambiguous"].includes(finding.type) &&
    /\bADC\b/i.test(quote) &&
    /\bLVDS\b/i.test(quote)
  ) {
    return {
      question: "ADC hangi modülde bulunuyor?",
      reason:
        "LVDS aktarımı ile analog verinin dönüştürüldüğü yeri birlikte netleştirin.",
    };
  }
  const reasons = {
    contradiction:
      "Kaynak ifadelerinin gerçekten çelişip çelişmediğini değerlendirin.",
    ambiguous:
      "Belgede açık olmayan bilgiyi veya tasarım kararını netleştirin.",
    missing_interface: "Önerilen arayüz ihtiyacını kaynakla doğrulayın.",
    missing_connection:
      "Önerilen bağlantının gerekli olup olmadığını kaynakla doğrulayın.",
    traceability: "Konu ile belge dayanağının ilişkisini kontrol edin.",
    classification: "Öğenin sınıfını ve sistem içindeki yerini değerlendirin.",
  };
  return {
    question: topic.title,
    reason:
      reasons[finding.type] ||
      "Bu gözlemi kaynak ve ilgili öğelerle birlikte değerlendirin.",
  };
}

export function topicState(topic) {
  if (topic.status === "reopened") return "Yeniden inceleme";
  if (topic.status === "completed") return "Tamamlandı";
  if (topic.decision?.status === "waiting") return "Açıklama bekleniyor";
  return "İncelenecek";
}

export function relevantObjects(project, topic) {
  const a = project.state.architecture;
  const finding = project.state.analysis.findings.find(
    (f) => f.id === topic.finding_id,
  );
  const primary = new Set(
    finding
      ? [...finding.related_component_ids, ...finding.related_connection_ids]
      : topic.primary_object_ids || [],
  );
  if (!primary.size) {
    const sources = new Set(topic.primary_source_ids || []);
    for (const o of [...a.components, ...a.connections])
      if (o.evidence.some((e) => sources.has(e.requirement_id)))
        primary.add(o.id);
  }
  if (!primary.size) for (const id of topic.object_ids) primary.add(id);
  // Show only declared relevant edges; never invent an implied missing connection.
  const edges = a.connections.filter((e) => primary.has(e.id));
  const endpointIds = new Set(edges.flatMap((e) => [e.source, e.target]));
  const standalone = a.components.filter(
    (c) => primary.has(c.id) && !endpointIds.has(c.id),
  );
  return { edges, standalone };
}
