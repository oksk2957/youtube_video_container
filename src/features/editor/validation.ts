import { z } from "zod";

export const videoClipSchema = z.object({
  id: z.string().uuid(),
  assetId: z.string().min(1).max(100),
  sourceStartMs: z.number().int().min(0).max(86_400_000),
  durationMs: z.number().int().min(100).max(14_400_000),
}).strict();

export const timelineSchema = z.object({
  version: z.literal(1),
  fps: z.number().int().min(1).max(60),
  clips: z.array(videoClipSchema).max(250),
}).strict().superRefine((value, ctx) => {
  const unique = new Set(value.clips.map((c) => c.id));
  if (unique.size !== value.clips.length) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Duplicate clip IDs" });
  }
  if (value.clips.reduce((s, c) => s + c.durationMs, 0) > 86_400_000) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Timeline longer than 24 hours" });
  }
});

export type VideoTimeline = z.infer<typeof timelineSchema>;
