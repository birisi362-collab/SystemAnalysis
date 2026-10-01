import { test } from "node:test";
import assert from "node:assert/strict";
import {
  relevantObjects,
  topicState,
  topicPresentation,
} from "../src/topic-presentation.js";

test("a proposed missing connection is never drawn as an existing edge", () => {
  const project = {
    state: {
      architecture: {
        components: [
          { id: "A", evidence: [] },
          { id: "B", evidence: [] },
        ],
        connections: [
          { id: "unrelated", source: "A", target: "B", evidence: [] },
        ],
      },
      analysis: {
        findings: [
          {
            id: "F",
            related_component_ids: ["A", "B"],
            related_connection_ids: [],
          },
        ],
      },
    },
  };
  const shown = relevantObjects(project, {
    finding_id: "F",
    object_ids: ["A", "B", "unrelated"],
  });
  assert.deepEqual(shown.edges, []);
  assert.deepEqual(
    shown.standalone.map((c) => c.id),
    ["A", "B"],
  );
});

test("changed or completed topics take priority over an earlier waiting decision", () => {
  assert.equal(
    topicState({ status: "open", decision: { status: "waiting" } }),
    "Açıklama bekleniyor",
  );
  assert.equal(
    topicState({ status: "reopened", decision: { status: "waiting" } }),
    "Yeniden inceleme",
  );
  assert.equal(
    topicState({ status: "completed", decision: { status: "waiting" } }),
    "Tamamlandı",
  );
});

test("the ADC question needs both source terms and does not rewrite the finding", () => {
  const topic = { title: "Özgün konu" };
  const finding = {
    type: "contradiction",
    evidence: [{ quote: "ADC kullanılır" }],
  };
  assert.equal(topicPresentation(topic, finding).question, topic.title);
  finding.evidence.push({ quote: "LVDS üzerinden aktarılır" });
  const before = JSON.stringify(finding);
  assert.equal(
    topicPresentation(topic, finding).question,
    "ADC hangi modülde bulunuyor?",
  );
  assert.equal(JSON.stringify(finding), before);
  const edited = { ...finding, title: "Mühendisin kendi sorusu" };
  assert.equal(
    topicPresentation({ title: edited.title }, edited, finding).question,
    edited.title,
  );
});
