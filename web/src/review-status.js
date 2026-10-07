const states = {
  completed: "İnceleme yanıtı alındı",
  partial: "Yanıtta kabul edilmeyen sonuçlar var",
  failed: "İnceleme yanıtı alınamadı veya işlenemedi",
  split: "İnceleme daha küçük bölümlere ayrıldı",
};

export function reviewSectionStatus(section) {
  return states[section.status] || section.status;
}

export function reviewSectionCounts(section) {
  if (!Number.isFinite(section.accepted)) return null;
  const excluded = Number.isFinite(section.excluded) ? section.excluded : 0;
  return `${section.accepted} bulgu kabul edildi; ${excluded} bulgu veya öneri kabul edilmedi.`;
}

export function reviewProgress(job) {
  return job.total_sections
    ? `${job.completed_sections || 0}/${job.total_sections} bölümün yanıtı işlendi`
    : "";
}
