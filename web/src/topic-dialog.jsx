import React, { useState } from "react";
import { ArrowRight, ArrowUpRight, Pencil } from "lucide-react";
import { sourceName, objectName, readableText } from "./review-labels.js";
import {
  relevantObjects,
  topicPresentation,
  topicState,
} from "./topic-presentation.js";

const decisionLabels = {
  resolved: "İnceleme tamamlandı",
  accepted: "Gerekçeyle kabul edildi",
  waiting: "Açıklama bekleniyor",
  needs_review: "İncelemeye geri alındı",
  merged: "Başka konuyla birleştirildi",
  rejected: "Reddedildi",
  approved: "Onaylandı",
};

function TopicDiagram({ project, topic, onSelect, onEdit, busy }) {
  const { edges, standalone } = relevantObjects(project, topic);
  if (!edges.length && !standalone.length)
    return (
      <p className="muted">
        Henüz ilgili bir şema öğesi seçilmemiş. Kaynağın ilişkisini
        düzenleyebilirsiniz.
      </p>
    );
  const a = project.state.architecture;
  const componentButton = (id) => (
    <button
      type="button"
      className="mini-component"
      onClick={() => onSelect({ kind: "component", id })}
    >
      {a.components.find((c) => c.id === id)?.name || "Bileşen bulunamadı"}
    </button>
  );
  return (
    <div className="topic-diagram" aria-label="Konuyla ilgili şema parçası">
      {edges.map((edge) => (
        <div className="mini-flow" key={edge.id}>
          {componentButton(edge.source)}
          <button
            type="button"
            className="mini-connection"
            aria-label={`${objectName(project, edge.id)} bağlantısını düzenle`}
            disabled={busy}
            onClick={() => onEdit("entity", edge, "connection")}
          >
            <span>{edge.protocol || "Arayüz belirtilmemiş"}</span>
            <ArrowRight size={26} />
            <small>
              <Pencil size={12} /> Bağlantıyı düzenle
            </small>
          </button>
          {componentButton(edge.target)}
        </div>
      ))}
      {standalone.map((c) => (
        <div className="mini-standalone" key={c.id}>
          {componentButton(c.id)}
          <button
            type="button"
            className="text-button"
            disabled={busy}
            onClick={() => onEdit("entity", c, "component")}
          >
            Bileşeni düzenle <Pencil size={14} />
          </button>
        </div>
      ))}
      <p className="micro">
        Şemada şu an kayıtlı olan ilişkiler. Bir öğeye tıklayarak dayanağını
        açabilirsiniz.
      </p>
    </div>
  );
}

function SourceCards({
  project,
  topic,
  finding,
  onSelect,
  onEditSource,
  busy,
}) {
  const ids = topic.primary_source_ids?.length
    ? topic.primary_source_ids
    : topic.source_ids;
  if (!ids.length)
    return (
      <p className="muted">
        Kaynak eklenmemiş. İlgili öğeyi düzenleyerek belge dayanağını ekleyin.
      </p>
    );
  return (
    <div className="topic-sources">
      {ids.map((id) => {
        const source = project.original.source_catalog.find(
          (s) => s.requirement_id === id,
        );
        if (!source)
          return (
            <p key={id} className="notice amber">
              İlişkilendirilen kaynak bulunamadı. İlgili öğenin dayanağını
              düzeltin.
            </p>
          );
        const quote = finding?.evidence.find(
          (e) => e.requirement_id === id,
        )?.quote;
        const index = quote ? source.text.indexOf(quote) : -1;
        return (
          <article className="source-excerpt" key={id}>
            <div className="inline spread">
              <button
                type="button"
                className="text-button"
                onClick={() => onSelect({ kind: "source", id })}
              >
                {sourceName(project, id)} <ArrowUpRight size={14} />
              </button>
              <button
                type="button"
                className="text-button"
                disabled={busy}
                onClick={() => onEditSource(source)}
              >
                Kaynak ilişkisini düzenle
              </button>
            </div>
            <blockquote>
              {index >= 0 ? (
                <>
                  {source.text.slice(0, index)}
                  <mark>{quote}</mark>
                  {source.text.slice(index + quote.length)}
                </>
              ) : (
                source.text
              )}
            </blockquote>
          </article>
        );
      })}
    </div>
  );
}

function TopicDecision({ project, topic, finding, commit, busy, onClose }) {
  const [mode, setMode] = useState(null),
    [status, setStatus] = useState("resolved"),
    [note, setNote] = useState(""),
    [target, setTarget] = useState("");
  const choose = (value) => {
    setMode(value);
    setStatus(value);
  };
  const decision = topic.decision;
  return (
    <section className="topic-decision-section">
      <div className="decision-actions" aria-label="Konu için sonraki işlem">
        <button
          type="button"
          className={`button ${mode === "resolved" ? "primary" : ""}`}
          aria-pressed={mode === "resolved"}
          onClick={() => choose("resolved")}
        >
          Gerekçeyle kapat
        </button>
        <button
          type="button"
          className={`button ${mode === "waiting" ? "primary" : ""}`}
          aria-pressed={mode === "waiting"}
          onClick={() => choose("waiting")}
        >
          Açıklama bekleniyor
        </button>
        {decision && (
          <button
            type="button"
            className={`button ${mode === "needs_review" ? "primary" : ""}`}
            aria-pressed={mode === "needs_review"}
            onClick={() => choose("needs_review")}
          >
            İncelemeye geri al
          </button>
        )}
      </div>
      {mode && (
        <form
          className="decision-entry"
          onSubmit={async (e) => {
            e.preventDefault();
            if (
              await commit(
                "set_topic_decision",
                topic.id,
                { status, merged_into: status === "merged" ? target : null },
                note,
              )
            )
              onClose();
          }}
        >
          {mode === "resolved" && (
            <label className="field">
              <span>Sonuç</span>
              <select
                aria-label="Kapatma sonucu"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                <option value="resolved">
                  Konuyu inceledim / düzeltmeyi tamamladım
                </option>
                <option value="accepted">
                  Bu durumu gerekçesiyle kabul ediyorum
                </option>
              </select>
            </label>
          )}
          {mode === "waiting" && (
            <p>
              Hangi bilginin eksik olduğunu yazın. Konu “Açıklama bekleyenler”de
              kalacak.
            </p>
          )}
          {mode === "needs_review" && (
            <p>Konu yeniden bekleyen incelemelere alınacak.</p>
          )}
          {status === "merged" && (
            <label className="field">
              <span>Takip edilecek diğer konu</span>
              <select
                required
                aria-label="Birleştirilecek konu"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
              >
                <option value="">Konu seçin</option>
                {project.topics
                  .filter((t) => t.finding_id && t.id !== topic.id)
                  .map((t) => (
                    <option value={t.id} key={t.id}>
                      {t.title}
                    </option>
                  ))}
              </select>
            </label>
          )}
          <label className="field">
            <span>
              {mode === "waiting" ? "Beklenen bilgi" : "Kararın gerekçesi"}
            </span>
            <textarea
              aria-label="Karar açıklaması"
              required
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              placeholder={
                mode === "waiting"
                  ? "Hangi bilgi netleşmeli? Kimden veya hangi belgeden bekleniyor?"
                  : "Neyi kontrol ettiniz? Neyi düzelttiniz veya neden kabul ettiniz?"
              }
            />
          </label>
          <div className="inline">
            <button className="button primary" disabled={busy || !note.trim()}>
              Kararı kaydet
            </button>
            <button
              type="button"
              className="button"
              onClick={() => setMode(null)}
            >
              Vazgeç
            </button>
          </div>
          <p className="micro">
            Karar ve gerekçe saklanır. İlgili bilgi değişirse konu yeniden
            incelemeye açılır.
          </p>
        </form>
      )}
      {decision && (
        <details
          className="previous-decision"
          open={topic.status === "reopened"}
        >
          <summary>
            Önceki karar ·{" "}
            {decision.auto_completed
              ? "Kayıt kontrolü giderildi"
              : decisionLabels[decision.status] || "İncelendi"}
          </summary>
          <p>{decision.note}</p>
          <small>
            {decision.actor} · {new Date(decision.at).toLocaleString("tr-TR")}
          </small>
          {topic.status === "reopened" && (
            <p className="amber-text">{decision.stale_reason}</p>
          )}
          {topic.completion_note && <p>{topic.completion_note}</p>}
        </details>
      )}
      {finding && (
        <details className="technical">
          <summary>Aynı konu başka bir kayıtta da var mı?</summary>
          <p>
            İki bulguyu birlikte takip etmek için diğer konuyu seçin.
            Birleştirme gerekçesi saklanır.
          </p>
          <button
            type="button"
            className="text-button"
            onClick={() => choose("merged")}
          >
            Başka konuyla birleştir
          </button>
        </details>
      )}
    </section>
  );
}

export function TopicDialog({
  project,
  topic,
  onClose,
  onSelect,
  setModal,
  commit,
  busy,
  Modal,
}) {
  const finding = project.state.analysis.findings.find(
    (f) => f.id === topic.finding_id,
  );
  const presentation = topicPresentation(
    topic,
    finding,
    project.original.analysis.findings.find((f) => f.id === topic.finding_id) ||
      null,
  );
  // The native editor opens above this dialog; saving returns to the same topic.
  const edit = (type, object, kind) => setModal({ type, object, kind });
  return (
    <Modal
      title={presentation.question}
      subtitle={topicState(topic)}
      onClose={onClose}
      wide
    >
      <div className="modal-body topic-detail simple-topic">
        <section className="topic-step">
          <h3>
            <span>1</span> Neyi netleştirmeliyim?
          </h3>
          <p className="topic-purpose">{presentation.reason}</p>
          {finding && (
            <details className="model-note">
              <summary>Bu konu neden önerildi?</summary>
              <p>{readableText(finding.description, project)}</p>
              {finding.recommended_action && (
                <p>
                  <b>Önerilen değerlendirme:</b>{" "}
                  {readableText(finding.recommended_action, project)}
                </p>
              )}
              <p className="micro">
                Bu bir inceleme önerisidir; kesin hata kararı değildir.
              </p>
              <button
                type="button"
                className="text-button"
                disabled={busy}
                onClick={() => edit("finding", finding)}
              >
                Konu açıklamasını düzenle <Pencil size={14} />
              </button>
            </details>
          )}
        </section>
        <section className="topic-step">
          <h3>
            <span>2</span> Belge ne söylüyor?
          </h3>
          <SourceCards
            {...{ project, topic, finding, onSelect, busy }}
            onEditSource={(source) => setModal({ type: "coverage", source })}
          />
          <h4>İlgili şema parçası</h4>
          <TopicDiagram {...{ project, topic, onSelect, busy }} onEdit={edit} />
          <details className="technical">
            <summary>Diğer ilgili öğeleri düzenle</summary>
            <div className="topic-objects">
              {topic.object_ids.map((id) => {
                const c = project.state.architecture.components.find(
                  (c) => c.id === id,
                );
                const obj =
                  c ||
                  project.state.architecture.connections.find(
                    (e) => e.id === id,
                  );
                return (
                  obj && (
                    <div className="inline spread" key={id}>
                      <span>{objectName(project, id)}</span>
                      <button
                        type="button"
                        className="text-button"
                        disabled={busy}
                        onClick={() =>
                          edit("entity", obj, c ? "component" : "connection")
                        }
                      >
                        Düzenle
                      </button>
                    </div>
                  )
                );
              })}
            </div>
            <button
              type="button"
              className="text-button"
              disabled={busy}
              onClick={() => edit("entity", null, "connection")}
            >
              Yeni bağlantı ekle
            </button>
          </details>
        </section>
        <section className="topic-step">
          <h3>
            <span>3</span> Nasıl ilerleyebilirim?
          </h3>
          <p className="muted">
            Öğeyi yukarıdan düzenleyin veya inceleme kararınızı kaydedin.
          </p>
          <TopicDecision
            {...{ project, topic, finding, commit, busy, onClose }}
          />
        </section>
        {!!topic.checks.length && (
          <details className="technical">
            <summary>Kontrol ayrıntıları ({topic.checks.length})</summary>
            {topic.checks.map((i) => (
              <div className="plain-card" key={i.key}>
                <strong>{i.title}</strong>
                <p>{i.explanation}</p>
                <p>{i.suggestion}</p>
                <code>{i.code}</code>
              </div>
            ))}
          </details>
        )}
      </div>
      <footer>
        <button className="button" onClick={onClose}>
          Listeye dön
        </button>
      </footer>
    </Modal>
  );
}
