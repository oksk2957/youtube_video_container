export type VideoClip = {
  id: string;
  assetId: string;
  sourceStartMs: number;
  durationMs: number;
};
export type Timeline = { version: 1; fps: number; clips: VideoClip[] };
export const MAX_CLIPS: number;
export const MIN_CLIP_MS: number;
export function emptyTimeline(): Timeline;
export function appendClip(timeline: Timeline, input: { id: string; assetId: string; durationMs: number }): Timeline;
export function splitClip(timeline: Timeline, id: string, offsetMs: number, newId: string): Timeline;
export function trimClip(timeline: Timeline, id: string, startMs: number, endMs: number): Timeline;
export function removeClip(timeline: Timeline, id: string): Timeline;
export function moveClip(timeline: Timeline, id: string, targetIndex: number): Timeline;
export function durationMs(timeline: Timeline): number;
export function clipAt(timeline: Timeline, positionMs: number): { clip: VideoClip; index: number; startMs: number; endMs: number } | null;
