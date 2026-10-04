import React, { useState } from "react";
import { Upload, FolderOpen, Play, LoaderCircle } from "lucide-react";
import { Button, Field, api } from "./workspace-ui.jsx";
import { HistoryChanges } from "./history-changes.jsx";

export function StartPanel({
  bootstrap,
  project,
  onProject,
  onJob,
  onClose,
  reevaluate = false,
  retryJob = null,
}) {
  const [value, setValue] = useState({
      profile:
        retryJob?.profile ||
        bootstrap.profiles.find((p) => p.id === "openrouter_nemotron")?.id ||
        bootstrap.profiles[0]?.id ||
        "",
      input_path: "",
      api_key: "",
      two_pass: true,
      demo: false,
      max_tokens: retryJob?.max_tokens || 32768,
      ...(retryJob ? { retry_job_id: retryJob.id } : {}),
      timeout: retryJob?.timeout || 600,
      ...(retryJob?.model ? { model: retryJob.model } : {}),
    }),
    [filename, setFilename] = useState(""),
    [working, setWorking] = useState(false),
    [error, setError] = useState("");
  const set = (k, v) => setValue((s) => ({ ...s, [k]: v }));
  const receive = async (file) => {
    if (!file) return;
    setWorking(true);
    setError("");
    try {
      const result = await api(
        "/documents?name=" + encodeURIComponent(file.name),
        file,
        true,
      );
      if (result.project) {
        onProject(result.project);
        onClose();
      } else {
        set("input_path", result.path);
        setFilename(file.name);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setWorking(false);
    }
  };
  const open = async (path) => {
    setWorking(true);
    setError("");
    try {
      onProject(await api("/projects/import", { path }));
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setWorking(false);
    }
  };
  return (
    <div className="drawer-body">
      <p>
        {reevaluate
          ? retryJob
            ? "Geçerli sonuçlar korunacak; yalnızca eksik bölümler veya kullanılamayan sonuçların geldiği bölümler yeniden incelenecek. Tasarım değiştiyse yeni değerlendirme başlatın."
            : "Güncel tasarım parça parça incelenir ve bölümler arası ilişkiler ayrıca değerlendirilir. Düzenlemeleriniz çalışma alanında kalır."
          : "Belgenizi seçin veya kaydedilmiş bir çalışmayı açın."}
      </p>
      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}
      {!reevaluate && (
        <>
          <label
            className="document-upload"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              receive(e.dataTransfer.files[0]);
            }}
          >
            <Upload size={30} />
            <strong>
              {working
                ? "Dosya açılıyor…"
                : filename || "Belgeyi buraya bırakın"}
            </strong>
            <span>veya dosya seçin · TXT, DOCX, PDF, çalışma ZIP paketi</span>
            <input
              type="file"
              aria-label="Belge veya çalışma paketi seç"
              accept=".txt,.docx,.pdf,.zip"
              disabled={working}
              onChange={(e) => receive(e.target.files[0])}
            />
          </label>
        </>
      )}
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setWorking(true);
          setError("");
          try {
            const job = await api(
              reevaluate ? `/projects/${project.id}/review` : "/analysis",
              value,
            );
            onJob(job);
            onClose();
          } catch (e) {
            setError(e.message);
          } finally {
            setWorking(false);
          }
        }}
      >
        <Field label="Model profili">
          <select
            value={value.profile}
            onChange={(e) => set("profile", e.target.value)}
          >
            {bootstrap.profiles.map((p) => (
              <option value={p.id} key={p.id}>
                {p.id} · {p.model}
              </option>
            ))}
          </select>
        </Field>
        <details>
          <summary>Bağlantı ve gelişmiş seçenekler</summary>
          <Field label="API anahtarı (yerel ayar varsa boş bırakın)">
            <input
              type="password"
              autoComplete="off"
              value={value.api_key}
              onChange={(e) => set("api_key", e.target.value)}
            />
          </Field>
          {!reevaluate && (
            <Field label="Yerel belge yolu">
              <input
                value={value.input_path}
                onChange={(e) => set("input_path", e.target.value)}
              />
            </Field>
          )}
          <Field label="Sunucu adresi (isteğe bağlı)">
            <input
              value={value.base_url || ""}
              onChange={(e) => set("base_url", e.target.value)}
            />
          </Field>
          <Field label="Model adı (isteğe bağlı)">
            <input
              value={value.model || ""}
              onChange={(e) => set("model", e.target.value)}
            />
          </Field>
          <Field label="Çıktı token sınırı">
            <input
              type="number"
              min={512}
              max={65536}
              step={512}
              required
              value={value.max_tokens}
              onChange={(e) =>
                set(
                  "max_tokens",
                  e.target.value === "" ? "" : Number(e.target.value),
                )
              }
            />
          </Field>
          <p className="micro">
            Sınır her model çağrısı içindir. Büyük değerlendirmeler otomatik
            bölünür. Küçük bir bölüm de kesilirse sağlayıcının desteklediği
            ölçüde sınırı artırabilirsiniz.
          </p>
          <Field label="Toplam süre sınırı (saniye)">
            <input
              type="number"
              min={10}
              max={1800}
              step={10}
              required
              value={value.timeout}
              onChange={(e) =>
                set(
                  "timeout",
                  e.target.value === "" ? "" : Number(e.target.value),
                )
              }
            />
          </Field>
          <p className="micro">
            Süre bütün değerlendirme içindir. Sınırda tamamlanan sonuçlar
            korunur; kalan bölümler ayrıca sürdürülebilir.
          </p>
          {!reevaluate && (
            <label className="check">
              <input
                type="checkbox"
                checked={value.demo}
                onChange={(e) => set("demo", e.target.checked)}
              />
              Örnek verilerle çevrimdışı dene
            </label>
          )}
        </details>
        <Button
          type="submit"
          className="primary"
          icon={working ? LoaderCircle : Play}
          disabled={
            working || (!reevaluate && !value.input_path && !value.demo)
          }
        >
          {reevaluate ? "Yeni değerlendirme iste" : "Analizi başlat"}
        </Button>
      </form>
      {!reevaluate && (
        <>
          <h3>Kaydedilmiş çalışmalar</h3>
          {bootstrap.projects.map((p) => (
            <button
              className="open-run"
              key={p.id}
              disabled={working}
              onClick={async () => {
                setWorking(true);
                try {
                  onProject(await api("/projects/" + p.id));
                  onClose();
                } catch (e) {
                  setError(e.message);
                } finally {
                  setWorking(false);
                }
              }}
            >
              <FolderOpen size={16} />
              <span>
                <strong>{p.name}</strong>
                <small>{new Date(p.updated).toLocaleString("tr-TR")}</small>
              </span>
            </button>
          ))}
          <details>
            <summary>Önceki analiz çıktıları</summary>
            {bootstrap.runs.map((r) => (
              <button
                className="open-run"
                key={r.path}
                disabled={working}
                onClick={() => open(r.path)}
              >
                <FolderOpen size={16} />
                <span>
                  <strong>{r.name}</strong>
                  <small>
                    {r.run} · {r.model}
                  </small>
                </span>
              </button>
            ))}
          </details>
        </>
      )}
    </div>
  );
}
const actions = {
  import: "Çalışma açıldı",
  upsert_component: "Bileşen düzenlendi",
  upsert_connection: "Bağlantı düzenlendi",
  delete_component: "Bileşen kaldırıldı",
  delete_connection: "Bağlantı kaldırıldı",
  apply_proposal: "Öneri uygulandı",
  append_review: "Yeni değerlendirme",
  set_topic_decision: "İnceleme kararı",
  add_finding: "Mühendis notu",
  edit_finding: "Not düzenlendi",
  set_assumption: "Varsayım düzenlendi",
  layout: "Şema yerleşimi",
  undo: "Geri alındı",
  redo: "Yinelendi",
};
export function HistoryPanel({ project, onSelect }) {
  return (
    <div className="drawer-body">
      <HistoryChanges {...{ project, onSelect }} />
      <h3>İşlem geçmişi</h3>
      {project.history.map((e, i) => (
        <article className="history-entry" key={i}>
          <strong>
            {actions[e.action] || "Önceki sürümde kaydedilen işlem"}
          </strong>
          <p>{e.reason}</p>
          <small>
            {e.actor} · {new Date(e.at).toLocaleString("tr-TR")}
          </small>
        </article>
      ))}
    </div>
  );
}
