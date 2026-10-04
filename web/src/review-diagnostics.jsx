import React, { useEffect, useState } from "react";
import { api } from "./workspace-ui.jsx";

const format = (value) =>
  Number.isFinite(value) ? value.toLocaleString("tr-TR") : "Kayıt yok";
const states = {
  completed: "Tamamlandı",
  partial: "Kısmen kullanılabildi",
  failed: "Tamamlanamadı",
  split: "Daha küçük parçalara ayrıldı",
};

export function ReviewDiagnostics({ job }) {
  const [detail, setDetail] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api(`/jobs/${job.id}/diagnostics`)
      .then((value) => {
        if (active) setDetail(value);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [job.id]);
  if (error)
    return (
      <div className="drawer-body" role="alert">
        {error}
      </div>
    );
  if (!detail) return <div className="drawer-body">Ayrıntılar açılıyor…</div>;
  const report = detail.review_report;
  return (
    <div className="drawer-body review-diagnostics">
      <p>{detail.message}</p>
      <p>
        Bu ekran yapay zekâ değerlendirmesinin durumunu açıklar. Kullanılamayan
        model çıktıları şemaya uygulanmaz; bunları sizin kanıtlamanız gerekmez.
      </p>
      <dl className="review-metrics">
        <div>
          <dt>Yeni eklenen bulgu</dt>
          <dd>{format(detail.added_findings)}</dd>
        </div>
        <div>
          <dt>Kullanılamayan bulgu / öneri</dt>
          <dd>{format(detail.excluded_findings)}</dd>
        </div>
        <div>
          <dt>Model çağrısı</dt>
          <dd>{format(detail.calls)}</dd>
        </div>
        <div>
          <dt>Her çağrı için çıktı sınırı</dt>
          <dd>{format(detail.max_tokens)}</dd>
        </div>
        <div>
          <dt>Toplam girdi tokenı</dt>
          <dd>{format(detail.token_usage?.prompt_tokens)}</dd>
        </div>
        <div>
          <dt>Toplam çıktı tokenı</dt>
          <dd>{format(detail.token_usage?.completion_tokens)}</dd>
        </div>
      </dl>
      {!report && (
        <p>
          Bu eski kayıtta ayrıntılı teşhis tutulmamış. Yeni değerlendirmelerde
          bölüm ve bulgu bazında nedenler saklanacak.
        </p>
      )}
      {detail.error_code && (
        <p>
          Hata kodu: <code>{detail.error_code}</code>
        </p>
      )}
      {report?.sections?.length > 0 && (
        <>
          <h3>İncelenen bölümler</h3>
          {report.sections.map((section, index) => (
            <details key={index}>
              <summary>
                {section.label} · {states[section.status] || section.status}
              </summary>
              {section.message && <p>{section.message}</p>}
              {section.error_code && (
                <p>
                  Hata kodu: <code>{section.error_code}</code>
                </p>
              )}
              {section.accepted !== undefined && (
                <p>
                  {section.accepted} bulgu kullanılabildi, {section.excluded}{" "}
                  bulgu veya öneri ayrı tutuldu.
                </p>
              )}
              {(section.transport || []).map((call, i) => (
                <div key={i} className="review-call">
                  <p>
                    Girdi: {format(call.usage?.prompt_tokens)} · Çıktı:{" "}
                    {format(call.usage?.completion_tokens)} · Sınır:{" "}
                    {format(call.settings?.max_tokens)}
                  </p>
                  <p>
                    Model:{" "}
                    {call.served_model || call.settings?.model || "Kayıt yok"} ·
                    Bitiş:{" "}
                    {call.finish_reason || call.error_code || "Kayıt yok"}
                  </p>
                  {call.usage?.completion_tokens_details?.reasoning_tokens !==
                    undefined && (
                    <p>
                      Düşünme tokenı:{" "}
                      {format(
                        call.usage.completion_tokens_details.reasoning_tokens,
                      )}
                    </p>
                  )}
                  {call.provider_message && (
                    <p>Sağlayıcının açıklaması: {call.provider_message}</p>
                  )}
                </div>
              ))}
            </details>
          ))}
        </>
      )}
      {report?.excluded?.length > 0 && (
        <>
          <h3>Kullanılamayan model çıktıları</h3>
          <p>
            Diğer geçerli bulgular korunur. Bu bölümdeki çıktı bir mühendislik
            hatası olarak işaretlenmez.
          </p>
          {report.excluded.map((item, index) => (
            <details key={index}>
              <summary>{item.title}</summary>
              <p>{item.message}</p>
              <p>
                {item.section} · <code>{item.code}</code>
              </p>
              <details>
                <summary>Teknik ayrıntı ve model çıktısı</summary>
                <pre>{JSON.stringify(item, null, 2)}</pre>
              </details>
            </details>
          ))}
        </>
      )}
      {detail.failure_detail && (
        <details>
          <summary>Uygulama hata ayrıntısı</summary>
          <pre>{JSON.stringify(detail.failure_detail, null, 2)}</pre>
        </details>
      )}
      <p className="micro">
        Çıktı tokenı, sağlayıcıya göre düşünme tokenlarını da içerebilir.
        Toplamlar bütün çağrılar içindir; sınır her çağrıya ayrı uygulanır.
      </p>
      <a href={`/api/jobs/${job.id}/diagnostics?download=true`}>
        Teşhis kaydını indir (JSON)
      </a>
    </div>
  );
}
