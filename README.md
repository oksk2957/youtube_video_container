# Video Studio: AI Auto-Edit + Timeline Editor

This repository evolves the Next.js 16 starter into a browser editor with a separate Python/FFmpeg AI rendering worker.

## What is implemented

- GitHub OAuth authentication and project access checks.
- PostgreSQL/Prisma projects, JSON edit timeline, browser clip preview, trim, split, reorder, delete, undo, redo, autosave.
- Multipart uploads to an S3-compatible object store.
- Per-user OpenAI-compatible **Base URL**, chat model, transcription model and API key settings.
- API keys are stored encrypted with AES-256-GCM; never returned by GET and never injected into browser code.
- Python worker reads queued edit jobs from Postgres, downloads the source video, extracts MP3, transcribes using OpenAI-compatible `/audio/transcriptions`, asks the AI to choose **whole timed transcript segments** using `/chat/completions`, validates all cut boundaries and output length, and renders an MP4 with subtitles using FFmpeg.
- 9:16 Shorts (720x1280; original full image preserved on blurred background) or 16:9 landscape (1280x720), 30/45/60/120 second targets.
- Output saved to S3. Download available only after authenticated, authorized job lookup.

## Local development

1. Install Node 22+, Docker Compose.
2. `cp .env.example .env` (or copy it manually on Windows).
3. Set `AI_CONFIG_ENCRYPTION_KEY` to **your own** 32-byte random hex secret generated with `python -c "import secrets; print(secrets.token_hex(32))"`. Keep the same key across web and worker deployments. Do not commit `.env`.
4. Create GitHub OAuth app and configure `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` and callback URL `http://localhost:3000/api/auth/github/callback`.
5. `docker compose up -d` starts PostgreSQL/MinIO and creates the `video-studio` bucket.
6. `npm install`, then `npx prisma migrate deploy` to apply the versioned initial database migration.
7. `npm run dev`, sign in through GitHub and create a project.
8. In a second terminal run `docker compose --profile ai up -d --build ai-worker`.
9. Upload a supported video containing speech. Open the AI panel. Enter your provider's Base URL (API root, for example `https://api.openai.com/v1`), analysis/chat model, transcription model, and API key. Save settings, choose 9:16 or 16:9, and start auto-edit.
10. Monitor job status; download the resulting MP4 when DONE.

**Other AI providers:** Set `AI_ALLOWED_HOSTS=api.openai.com,api.example.com` in `.env` and restart both web and worker when allowing another host. Server validates the exact host, HTTPS scheme, and no embedded credentials. Provider must support OpenAI-compatible chat completions and **audio transcriptions returning `verbose_json` with segment start/end times**. Many text-only LLM APIs do not offer ASR: set the transcription model in the UI to `local:tiny`, `local:base` or `local:small` to use bundled CPU faster-whisper instead. The model is downloaded on first use into a persistent Docker volume; CPU transcription may be slow. This keeps the audio local, but the transcript is still sent to the configured chat model for cut selection. For an on-device localhost LLM, additional operator-controlled networking configuration is required.

**Object store CORS:** The bucket must allow the UI origin to PUT/GET/HEAD objects using signed URLs, and expose ETag to the browser. AWS S3 CORS example:

```json
[{"AllowedHeaders":["*"],"AllowedMethods":["PUT","GET","HEAD"],"AllowedOrigins":["http://localhost:3000"],"ExposeHeaders":["ETag"]}]
```

MinIO local mode also needs these CORS semantics; verify your selected MinIO image version. The repo does not include credentials or local production secrets.

## Tests

```bash
npm test
npm run lint
npm run build
npx tsc --noEmit
python -m pip install -r worker/requirements.txt
python -m unittest discover -s worker/tests -v
```

CI runs these on GitHub Actions. The AI provider requires a real API key to run end-to-end; the unit tests use no paid external provider.

## Accuracy and privacy

The AI selects passages from **actual ASR timestamp segments**, not made-up source timestamps. The code rejects overlaps, out-of-range cuts, overlong outputs and malformed responses. Subtitles come from transcription text, not fabricated narration. Still, this is a **first-stage prototype**: it does **not** fact-check disputed claims, reconstruct slides, extract OCR/text overlays, or guarantee the clip's rhetorical context. Never publish political/financial/medical excerpts without reviewing against the original. API requests send audio transcripts to your chosen AI provider.

There is no FFprobe worker processing on media **at upload time**; ingestion metadata is browser-supplied until the AI job probes the actual uploaded container. Unsupported/silent videos, codecs, no ASR timestamps or unsupported endpoint responses can fail with an explicit job error. Add resource limits, retention, upload content validation, lifecycle expiration, job recovery, and a managed database migration before production.

Existing manual timeline edits and auto-edit outputs currently run as separate workflows; the AI export is not yet editable in the manual timeline UI.
