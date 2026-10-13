import React, { useEffect, useState } from "react";
import { Button, Field } from "./workspace-ui.jsx";

const storageKey = "workbench.model-settings.v1";
export function useModelSettings(profiles = []) {
  const [config, setConfig] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
      // Credentials are session-only, including when reading an older value.
      return {
        profile: saved.profile || "",
        overrides: Object.fromEntries(
          Object.entries(saved.overrides || {}).map(([id, p]) => [
            id,
            {
              model: p.model || "",
              base_url: p.base_url || "",
              timeout: p.timeout || 600,
              max_tokens: p.max_tokens || 8192,
            },
          ]),
        ),
      };
    } catch {
      return { profile: "", overrides: {} };
    }
  });
  useEffect(() => {
    const overrides = Object.fromEntries(
      Object.entries(config.overrides).map(([id, { api_key, ...rest }]) => [
        id,
        rest,
      ]),
    );
    localStorage.setItem(storageKey, JSON.stringify({ ...config, overrides }));
  }, [config]);
  const profile = profiles.some((p) => p.id === config.profile)
    ? config.profile
    : profiles.find((p) => p.has_key)?.id ||
      profiles.find((p) => p.id === "openrouter_nemotron")?.id ||
      profiles[0]?.id ||
      "";
  const select = (id) => setConfig((c) => ({ ...c, profile: id }));
  const getSettings = (id = profile) => {
    const p = profiles.find((p) => p.id === id) || {};
    return {
      profile: id,
      api_key: "",
      model: p.model || "",
      base_url: p.base_url || "",
      timeout: p.timeout || 600,
      max_tokens: p.max_tokens || 8192,
      ...config.overrides[id],
    };
  };
  const save = (id, values) =>
    setConfig((c) => ({
      profile: id,
      overrides: { ...c.overrides, [id]: values },
    }));
  return { profile, select, getSettings, save };
}

export function ModelSettings({ profiles, modelSettings, onClose }) {
  const [profile, setProfile] = useState(modelSettings.profile);
  const [draft, setDraft] = useState(modelSettings.getSettings());
  const set = (key, value) => setDraft((d) => ({ ...d, [key]: value }));
  const changeProfile = (id) => {
    setProfile(id);
    setDraft(modelSettings.getSettings(id));
  };
  return (
    <form
      className="drawer-body"
      onSubmit={(e) => {
        e.preventDefault();
        const { profile: unused, ...values } = draft;
        modelSettings.save(profile, values);
        onClose();
      }}
    >
      <p>
        Analiz, yeniden değerlendirme ve asistan aynı model profilinin
        ayarlarını kullanır.
      </p>
      <Field label="Model profili">
        <select value={profile} onChange={(e) => changeProfile(e.target.value)}>
          {profiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.model || p.id}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Model adı">
        <input
          required
          value={draft.model}
          onChange={(e) => set("model", e.target.value)}
        />
      </Field>
      <Field label="Sunucu adresi">
        <input
          required
          type="url"
          value={draft.base_url}
          onChange={(e) => set("base_url", e.target.value)}
        />
      </Field>
      <Field label="API anahtarı">
        <input
          type="password"
          autoComplete="off"
          value={draft.api_key}
          placeholder={
            profiles.find((p) => p.id === profile)?.has_key
              ? "Yerel anahtar ayarlı"
              : "Yerel ayar varsa boş bırakın"
          }
          onChange={(e) => set("api_key", e.target.value)}
        />
      </Field>
      <p className="micro">
        Buraya girilen anahtar bu oturumda kullanılır. Kalıcı bağlantı için
        uygulamanın yerel profil ayarını kullanabilirsiniz.
      </p>
      <details>
        <summary>Gelişmiş model ayarları</summary>
        <Field label="Süre sınırı (saniye)">
          <input
            required
            type="number"
            min="10"
            max="1800"
            value={draft.timeout}
            onChange={(e) =>
              set(
                "timeout",
                e.target.value === "" ? "" : Number(e.target.value),
              )
            }
          />
        </Field>
        <Field label="Çıktı token sınırı">
          <input
            required
            type="number"
            min="512"
            max="65536"
            value={draft.max_tokens}
            onChange={(e) =>
              set(
                "max_tokens",
                e.target.value === "" ? "" : Number(e.target.value),
              )
            }
          />
        </Field>
      </details>
      <div className="engineering-actions">
        <Button type="submit" className="primary">
          Ayarları kaydet
        </Button>
        <Button onClick={onClose}>Vazgeç</Button>
      </div>
    </form>
  );
}
