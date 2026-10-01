import React, { useState } from "react";
import { ChevronRight, Search, CheckCheck } from "lucide-react";
import { TopicDialog } from "./topic-dialog.jsx";
import { topicPresentation, topicState } from "./topic-presentation.js";
import "./review.css";

export function TopicWorkbench({
  project,
  onSelect,
  onIssue,
  setModal,
  commit,
  busy,
  Modal,
}) {
  const [filter, setFilter] = useState("open"),
    [query, setQuery] = useState(""),
    [selected, setSelected] = useState(null);
  if (!project.topics)
    return (
      <div className="content-page">
        <h2>Uygulamayı yeniden başlatın</h2>
        <p>
          Açık sunucu önceki sürümü çalıştırıyor. Sunucuyu kapatıp run_app.bat
          dosyasını tekrar açın.
        </p>
      </div>
    );
  const topics = project.topics;
  const isWaiting = (t) =>
    t.decision?.status === "waiting" &&
    t.status !== "reopened" &&
    t.status !== "completed";
  const matches = (t) =>
    filter === "completed"
      ? t.status === "completed"
      : filter === "waiting"
        ? isWaiting(t)
        : t.status !== "completed" && !isWaiting(t);
  const counts = {
    open: topics.filter((t) => t.status !== "completed" && !isWaiting(t))
      .length,
    waiting: topics.filter(isWaiting).length,
    completed: topics.filter((t) => t.status === "completed").length,
  };
  const entries = topics.map((topic) => ({
    topic,
    ...topicPresentation(
      topic,
      project.state.analysis.findings.find((f) => f.id === topic.finding_id),
      project.original.analysis.findings.find(
        (f) => f.id === topic.finding_id,
      ) || null,
    ),
  }));
  const visible = entries.filter(
    ({ topic, question, reason }) =>
      matches(topic) &&
      `${question} ${reason} ${topic.description} ${topic.context_label}`
        .toLocaleLowerCase("tr")
        .includes(query.toLocaleLowerCase("tr")),
  );
  const active = topics.find((t) => t.id === selected);
  return (
    <main className="content-page review-page simple-review">
      <div className="page-heading">
        <div>
          <span className="eyebrow">İNCELEME</span>
          <h1>Netleştirilecek konular</h1>
          <p>
            Bir konu seçin. Kaynağı görün, gerekirse düzenleyin, kararınızı
            kaydedin.
          </p>
        </div>
        <button
          className="button"
          onClick={() => setModal({ type: "finding" })}
        >
          Konu ekle
        </button>
      </div>
      <div className="review-list-toolbar">
        <div className="segmented" aria-label="Konu durumu">
          {[
            ["open", "Bekleyenler"],
            ["waiting", "Açıklama bekleyenler"],
            ["completed", "Tamamlananlar"],
          ].map(([key, label]) => (
            <button
              key={key}
              className={filter === key ? "active" : ""}
              onClick={() => setFilter(key)}
            >
              {label} <b>{counts[key]}</b>
            </button>
          ))}
        </div>
        <label className="topic-search">
          <Search size={16} />
          <input
            aria-label="Konularda ara"
            placeholder="Konu veya kaynak ara"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>
      <div className="review-rows">
        {visible.map(({ topic, question, reason }) => (
          <button
            type="button"
            className={`review-row ${topic.status}`}
            key={topic.id}
            onClick={() => setSelected(topic.id)}
            aria-label={`${question} — konuyu aç`}
          >
            <span className="review-row-copy">
              <strong>{question}</strong>
              <span>{reason}</span>
              <small>{topic.context_label}</small>
            </span>
            <span
              className={`badge ${topic.status === "reopened" ? "amber" : topic.status === "completed" ? "green" : ""}`}
            >
              {topicState(topic)}
            </span>
            <ChevronRight size={18} />
          </button>
        ))}
      </div>
      {!visible.length && (
        <div className="empty">
          <CheckCheck size={28} />
          <h3>{query ? "Aramanıza uygun konu yok" : "Bu listede konu yok"}</h3>
          <p>
            {query
              ? "Aramayı değiştirin veya temizleyin."
              : "Diğer listelere geçebilir veya yeni bir konu ekleyebilirsiniz."}
          </p>
        </div>
      )}
      <details className="technical audit-log">
        <summary>Ayrıntılı kontrol kaydı ({project.issues.length})</summary>
        <p>
          Gerekçeyle kapatılmış konuların teknik kontrolleri burada korunur.
        </p>
        {project.issues.map((i) => (
          <button key={i.key} className="check-row" onClick={() => onIssue(i)}>
            <span>
              <strong>{i.title}</strong>
              <small>{i.explanation}</small>
              <code>{i.code}</code>
            </span>
            <ChevronRight size={15} />
          </button>
        ))}
      </details>
      {active && (
        <TopicDialog
          key={active.id}
          {...{ project, setModal, commit, busy, Modal }}
          topic={active}
          onClose={() => setSelected(null)}
          onSelect={(s) => {
            setSelected(null);
            onSelect(s);
          }}
        />
      )}
    </main>
  );
}
