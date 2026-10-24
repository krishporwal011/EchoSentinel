import assert from "node:assert/strict";
import test from "node:test";
import { detectionReducer, initialDetectionState } from "../src/lib/detectionState.ts";
import { parseDetectionResponse } from "../src/lib/detection.ts";

const result = (label) => ({
  success: true,
  prediction: {
    label,
    ai_probability: 0.4,
    human_probability: 0.6,
    risk_level: "medium",
    confidence: null,
    confidence_note: "Uncalibrated model output.",
    probability_type: "uncalibrated_softmax",
  },
  processing_status: "completed",
  processing_time_ms: 1,
});

test("a failed upload after a successful upload clears the old result", () => {
  const first = result("likely_human_recorded");
  let state = detectionReducer(initialDetectionState, {
    type: "request_started", requestId: 1, clearResult: true,
  });
  assert.equal(state.isAnalyzing, true);
  state = detectionReducer(state, { type: "request_succeeded", requestId: 1, result: first });
  assert.equal(state.result, first);
  assert.equal(state.isAnalyzing, false);

  state = detectionReducer(state, { type: "request_started", requestId: 2, clearResult: true });
  assert.equal(state.result, null);
  assert.equal(state.errorMessage, null);
  assert.equal(state.isAnalyzing, true);
  state = detectionReducer(state, {
    type: "request_failed", requestId: 2, clearResult: true, message: "Could not decode audio.",
  });
  assert.equal(state.result, null);
  assert.equal(state.errorMessage, "Could not decode audio.");
  assert.equal(state.isAnalyzing, false);
});

test("out-of-order upload responses cannot replace or fail the newest result", () => {
  let state = detectionReducer(initialDetectionState, {
    type: "request_started", requestId: 1, clearResult: true,
  });
  state = detectionReducer(state, { type: "request_started", requestId: 2, clearResult: true });
  const newest = result("likely_ai_generated");
  state = detectionReducer(state, { type: "request_succeeded", requestId: 2, result: newest });

  const afterOldSuccess = detectionReducer(state, {
    type: "request_succeeded", requestId: 1, result: result("likely_human_recorded"),
  });
  const afterOldFailure = detectionReducer(afterOldSuccess, {
    type: "request_failed", requestId: 1, clearResult: true, message: "Stale failure",
  });
  assert.equal(afterOldFailure.result, newest);
  assert.equal(afterOldFailure.errorMessage, null);
  assert.equal(afterOldFailure.isAnalyzing, false);
});

test("reset invalidates pending work and a subsequent upload can complete", () => {
  let state = detectionReducer(initialDetectionState, {
    type: "request_started", requestId: 1, clearResult: true,
  });
  state = detectionReducer(state, { type: "reset", requestId: 2 });
  assert.equal(state.result, null);
  assert.equal(state.errorMessage, null);
  assert.equal(state.isAnalyzing, false);

  state = detectionReducer(state, { type: "request_started", requestId: 3, clearResult: true });
  const nextResult = result("inconclusive");
  state = detectionReducer(state, { type: "request_succeeded", requestId: 3, result: nextResult });
  state = detectionReducer(state, {
    type: "request_succeeded", requestId: 1, result: result("likely_ai_generated"),
  });
  assert.equal(state.result, nextResult);
  assert.equal(state.isAnalyzing, false);
});

test("starting a new live session clears the previous result and stale errors", () => {
  const previous = result("likely_human_recorded");
  const state = {
    ...initialDetectionState,
    result: previous,
    errorMessage: "An old request failed.",
    latestRequestId: 4,
  };
  const next = detectionReducer(state, {
    type: "request_invalidated", requestId: 5, clearResult: true,
  });
  assert.equal(next.result, null);
  assert.equal(next.errorMessage, null);
  assert.equal(next.isAnalyzing, false);
});

test("malformed successful API payloads are rejected before reaching UI", () => {
  assert.throws(() => parseDetectionResponse({ success: true }), /invalid response/);
  assert.throws(() => parseDetectionResponse({
    success: true,
    prediction: {
      label: "likely_ai_generated", ai_probability: 0.9, human_probability: 0.9,
      risk_level: "high", confidence: null, confidence_note: "n/a", probability_type: "softmax",
    },
  }), /invalid response/);
});
