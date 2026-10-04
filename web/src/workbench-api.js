let token = "";
export const setToken = (value) => {
  token = value;
};
export class ApiError extends Error {
  constructor(message, code) {
    super(message);
    this.code = code;
  }
}

export async function api(path, body, raw = false, renewed = false) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  let response, result;
  try {
    response = await fetch("/api" + path, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        "X-Workbench-Token": token,
        ...(!raw ? { "Content-Type": "application/json" } : {}),
      },
      body: body === undefined ? undefined : raw ? body : JSON.stringify(body),
      signal: controller.signal,
    });
    result = await response.json();
  } catch (error) {
    if (response && error.name !== "AbortError")
      throw new ApiError(
        "Uygulama beklenen yanıtı döndürmedi.",
        "RESPONSE_FORMAT",
      );
    throw new ApiError(
      body === undefined
        ? "Yerel uygulamayla bağlantı kesildi. run_app.bat ile uygulamayı açın; bağlantı geldiğinde durum yeniden okunacak."
        : "Yerel uygulamaya ulaşılamadı. İşlemin kaydedilip kaydedilmediği doğrulanamadı; yeniden göndermeden önce güncel durumu kontrol edin.",
      "NETWORK",
    );
  } finally {
    clearTimeout(timer);
  }
  // A rejected session token means the mutation did not run. Refresh only that specific rejection.
  if (
    response.status === 403 &&
    !renewed &&
    body !== undefined &&
    typeof result.detail === "string" &&
    result.detail.includes("oturumu yenilenmiş")
  ) {
    const bootstrap = await api("/bootstrap");
    setToken(bootstrap.token);
    return api(path, body, raw, true);
  }
  if (!response.ok)
    throw new ApiError(
      typeof result.detail === "string"
        ? result.detail
        : "Alanları kontrol edin.",
      "HTTP_" + response.status,
    );
  return result;
}

export function pollJob({
  read,
  onResult,
  onError,
  schedule = setTimeout,
  cancel = clearTimeout,
}) {
  let stopped = false,
    timer,
    failures = 0;
  async function poll() {
    if (stopped) return;
    try {
      const result = await read();
      if (stopped) return;
      failures = 0;
      await onResult(result);
      if (!["queued", "running"].includes(result.status)) return;
    } catch (error) {
      if (stopped) return;
      failures += 1;
      onError(error);
    }
    if (!stopped)
      timer = schedule(
        poll,
        failures ? Math.min(10000, 1500 * 2 ** failures) : 1500,
      );
  }
  poll();
  return () => {
    stopped = true;
    cancel(timer);
  };
}
