import test from "node:test";
import assert from "node:assert/strict";
import { readableText } from "../src/review-labels.js";

test("assistant and history use assumption text while keeping internal identities untouched", () => {
  const project = {
    source_labels: { "G-01": "Satır 1" },
    state: {
      architecture: { components: [], connections: [] },
      assumption_records: [
        { id: "ASM-5c0c02dac9e3", text: "Güç kaynağı yedeklidir." },
      ],
    },
  };
  assert.equal(
    readableText("ASM-5c0c02dac9e3 için G-01 incelendi.", project),
    "Güç kaynağı yedeklidir. için Satır 1 incelendi.",
  );
  assert.equal(
    readableText("Yeni öneri ASM_ab123cd4", project),
    "Yeni öneri Varsayım",
  );
  assert.equal(project.state.assumption_records[0].id, "ASM-5c0c02dac9e3");
});
