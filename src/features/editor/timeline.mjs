/**
 * Pure, non-destructive, single-track timeline engine. All durations use
 * integer milliseconds. No media bytes are mutated by these commands.
 */
export const MAX_CLIPS = 250;
export const MIN_CLIP_MS = 100;

export function emptyTimeline() {
  return { version: 1, fps: 30, clips: [] };
}

function assertInt(value, min, name) {
  if (!Number.isSafeInteger(value) || value < min) {
    throw new RangeError(name + " must be an integer >= " + min);
  }
}

function findClipIndex(timeline, id) {
  const index = timeline.clips.findIndex((clip) => clip.id === id);
  if (index === -1) throw new Error("Clip not found");
  return index;
}

export function appendClip(timeline, { id, assetId, durationMs }) {
  if (timeline.clips.length >= MAX_CLIPS) throw new RangeError("Clip limit reached");
  assertInt(durationMs, MIN_CLIP_MS, "durationMs");
  if (!id || !assetId || timeline.clips.some((clip) => clip.id === id)) {
    throw new Error("Invalid or duplicate clip ID");
  }
  return {
    ...timeline,
    clips: [...timeline.clips, { id, assetId, sourceStartMs: 0, durationMs }],
  };
}

export function splitClip(timeline, id, offsetMs, newId) {
  const index = findClipIndex(timeline, id);
  const clip = timeline.clips[index];
  assertInt(offsetMs, MIN_CLIP_MS, "offsetMs");
  if (offsetMs > clip.durationMs - MIN_CLIP_MS) throw new RangeError("Split outside clip");
  if (!newId || timeline.clips.some((part) => part.id === newId)) {
    throw new Error("New clip must have a unique ID");
  }
  if (timeline.clips.length >= MAX_CLIPS) throw new RangeError("Clip limit reached");
  const clips = [...timeline.clips];
  clips.splice(
    index,
    1,
    { ...clip, durationMs: offsetMs },
    {
      ...clip,
      id: newId,
      sourceStartMs: clip.sourceStartMs + offsetMs,
      durationMs: clip.durationMs - offsetMs,
    },
  );
  return { ...timeline, clips };
}

export function trimClip(timeline, id, startMs, endMs) {
  const index = findClipIndex(timeline, id);
  const clip = timeline.clips[index];
  assertInt(startMs, 0, "startMs");
  assertInt(endMs, 0, "endMs");
  if (clip.durationMs - startMs - endMs < MIN_CLIP_MS) {
    throw new RangeError("Trim would remove entire clip");
  }
  const clips = [...timeline.clips];
  clips[index] = {
    ...clip,
    sourceStartMs: clip.sourceStartMs + startMs,
    durationMs: clip.durationMs - startMs - endMs,
  };
  return { ...timeline, clips };
}

export function removeClip(timeline, id) {
  const index = findClipIndex(timeline, id);
  return { ...timeline, clips: timeline.clips.filter((_, i) => i !== index) };
}

export function moveClip(timeline, id, targetIndex) {
  const index = findClipIndex(timeline, id);
  assertInt(targetIndex, 0, "targetIndex");
  if (targetIndex >= timeline.clips.length) throw new RangeError("Invalid target index");
  const clips = [...timeline.clips];
  const [clip] = clips.splice(index, 1);
  clips.splice(targetIndex, 0, clip);
  return { ...timeline, clips };
}

export function durationMs(timeline) {
  return timeline.clips.reduce((sum, clip) => sum + clip.durationMs, 0);
}

/** Locates the clip at positionMs. End is exclusive except at final boundary. */
export function clipAt(timeline, positionMs) {
  let startMs = 0;
  for (let index = 0; index < timeline.clips.length; index += 1) {
    const clip = timeline.clips[index];
    const endMs = startMs + clip.durationMs;
    if (positionMs < endMs) return { clip, index, startMs, endMs };
    startMs = endMs;
  }
  return null;
}
