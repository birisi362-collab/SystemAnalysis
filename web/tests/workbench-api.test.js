import test from "node:test";
import assert from "node:assert/strict";
import { api, pollJob, setToken } from "../src/workbench-api.js";

test("a failed mutation is explained and never blindly repeated", async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    throw new TypeError("Failed to fetch");
  };
  try {
    await assert.rejects(
      api("/projects/p/review", {}),
      (e) => e.code === "NETWORK" && e.message.includes("doğrulanamadı"),
    );
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = original;
  }
});

test("only a rejected expired session token is refreshed before a mutation retry", async () => {
  const original = globalThis.fetch;
  const requests = [];
  setToken("old");
  globalThis.fetch = async (path, options) => {
    requests.push([path, options.method, options.headers["X-Workbench-Token"]]);
    const data =
      requests.length === 1
        ? { detail: "Uygulama oturumu yenilenmiş. Sayfayı yenileyin." }
        : requests.length === 2
          ? { token: "new" }
          : { id: "job" };
    return {
      status: requests.length === 1 ? 403 : 200,
      ok: requests.length !== 1,
      json: async () => data,
    };
  };
  try {
    assert.equal((await api("/projects/p/review", {})).id, "job");
    assert.deepEqual(
      requests.map((r) => r[1]),
      ["POST", "GET", "POST"],
    );
    assert.equal(requests[2][2], "new");
  } finally {
    globalThis.fetch = original;
  }
});

test("job polling waits for each read, backs off on outage and recovers the existing job", async () => {
  let resolveRead,
    reads = 0;
  const scheduled = [],
    results = [],
    errors = [];
  const stop = pollJob({
    read: () => {
      reads++;
      return new Promise((resolve) => {
        resolveRead = resolve;
      });
    },
    onResult: (r) => results.push(r),
    onError: (e) => errors.push(e),
    schedule: (fn, ms) => {
      scheduled.push([fn, ms]);
      return scheduled.length;
    },
    cancel: () => {},
  });
  assert.equal(reads, 1);
  assert.equal(scheduled.length, 0);
  resolveRead({ id: "same-job", status: "running" });
  await new Promise(setImmediate);
  assert.equal(scheduled[0][1], 1500);
  assert.equal(reads, 1);
  stop();
  scheduled[0][0](); // cancellation prevents future reads
});

test("outage recovery never submits another review and stops at a terminal job", async () => {
  let reads = 0;
  const scheduled = [],
    results = [],
    errors = [];
  const stop = pollJob({
    read: async () => {
      if (++reads === 1) throw new TypeError("Failed to fetch");
      return { id: "original", status: "interrupted" };
    },
    onResult: (r) => results.push(r),
    onError: (e) => errors.push(e),
    schedule: (f, ms) => {
      scheduled.push([f, ms]);
    },
    cancel: () => {},
  });
  await new Promise(setImmediate);
  assert.equal(errors.length, 1);
  assert.equal(scheduled[0][1], 3000);
  await scheduled[0][0]();
  assert.equal(results[0].id, "original");
  assert.equal(scheduled.length, 1);
  stop();
});
