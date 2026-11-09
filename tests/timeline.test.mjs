import assert from "node:assert/strict";
import test from "node:test";
import {
  appendClip, clipAt, durationMs, emptyTimeline, moveClip,
  removeClip, splitClip, trimClip,
} from "../src/features/editor/timeline.mjs";

const one = () => appendClip(emptyTimeline(), { id: "clip-a", assetId: "asset-1", durationMs: 30_000 });

test("new timeline is empty and uses 30fps", () => {
  const timeline = emptyTimeline();
  assert.equal(timeline.fps, 30);
  assert.equal(durationMs(timeline), 0);
});
test("appending clip records source offset and duration", () => {
  const timeline = one();
  assert.deepEqual(timeline.clips[0], {
    id: "clip-a", assetId: "asset-1", sourceStartMs: 0, durationMs: 30_000,
  });
});
test("split preserves source continuity, total duration and input object", () => {
  const original = one();
  const split = splitClip(original, "clip-a", 12_000, "clip-b");
  assert.equal(split.clips[0].durationMs, 12_000);
  assert.equal(split.clips[1].sourceStartMs, 12_000);
  assert.equal(split.clips[1].durationMs, 18_000);
  assert.equal(durationMs(split), 30_000);
  assert.equal(original.clips.length, 1);
});
test("split rejects invalid boundaries and duplicate IDs", () => {
  assert.throws(() => splitClip(one(), "clip-a", 50, "clip-b"), RangeError);
  assert.throws(() => splitClip(one(), "clip-a", 30_000, "clip-b"), RangeError);
  assert.throws(() => splitClip(one(), "clip-a", 5_000, "clip-a"));
});
test("trim adjusts source and duration without mutating input", () => {
  const before = one();
  const after = trimClip(before, "clip-a", 2_000, 3_000);
  assert.equal(after.clips[0].sourceStartMs, 2_000);
  assert.equal(after.clips[0].durationMs, 25_000);
  assert.equal(before.clips[0].durationMs, 30_000);
});
test("trim cannot erase entire clip", () => {
  assert.throws(() => trimClip(one(), "clip-a", 20_000, 10_000), RangeError);
});
test("moving changes ordering, not contents", () => {
  const original = appendClip(one(), { id: "clip-b", assetId: "asset-2", durationMs: 10_000 });
  const moved = moveClip(original, "clip-a", 1);
  assert.deepEqual(moved.clips.map((clip) => clip.id), ["clip-b", "clip-a"]);
  assert.deepEqual(original.clips.map((clip) => clip.id), ["clip-a", "clip-b"]);
});
test("remove deletes only the chosen clip", () => {
  const original = appendClip(one(), { id: "clip-b", assetId: "asset-2", durationMs: 10_000 });
  assert.deepEqual(removeClip(original, "clip-a").clips.map((clip) => clip.id), ["clip-b"]);
});
test("clipAt respects end-exclusive boundaries", () => {
  const original = appendClip(one(), { id: "clip-b", assetId: "asset-2", durationMs: 10_000 });
  assert.equal(clipAt(original, 0)?.clip.id, "clip-a");
  assert.equal(clipAt(original, 29_999)?.clip.id, "clip-a");
  assert.equal(clipAt(original, 30_000)?.clip.id, "clip-b");
  assert.equal(clipAt(original, 40_000), null);
});
test("append prevents duplicates, zero-length and overlong stacks", () => {
  assert.throws(() => appendClip(one(), { id: "clip-a", assetId: "asset-3", durationMs: 200 }));
  assert.throws(() => appendClip(one(), { id: "clip-z", assetId: "asset-3", durationMs: 0 }), RangeError);
});
