import { test } from "node:test";
import assert from "node:assert/strict";
import {
  reviewSectionStatus,
  reviewSectionCounts,
  reviewProgress,
} from "../src/review-status.js";

test("a full-design response with rejected quotes describes output acceptance", () => {
  const section = {
    label: "Bütün tasarım",
    status: "partial",
    accepted: 0,
    excluded: 3,
  };
  assert.equal(
    reviewSectionStatus(section),
    "Yanıtta kabul edilmeyen sonuçlar var",
  );
  assert.equal(
    reviewSectionCounts(section),
    "0 bulgu kabul edildi; 3 bulgu veya öneri kabul edilmedi.",
  );
  assert.equal(
    reviewProgress({ completed_sections: 1, total_sections: 1 }),
    "1/1 bölümün yanıtı işlendi",
  );
});

test("failed and split calls do not claim that findings were accepted", () => {
  for (const status of ["failed", "split"]) {
    assert.equal(reviewSectionCounts({ status }), null);
    assert.ok(reviewSectionStatus({ status }));
  }
  assert.equal(reviewProgress({}), "");
});

test("legacy accepted counts without an excluded count remain readable", () => {
  assert.equal(
    reviewSectionCounts({ accepted: 2 }),
    "2 bulgu kabul edildi; 0 bulgu veya öneri kabul edilmedi.",
  );
});
