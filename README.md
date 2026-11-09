# Video Studio

A Next.js 16 / React 19 proof-of-concept for secure video uploads and non-destructive cut editing.

## Status

- **PR 1 / foundation:** GitHub OAuth, PostgreSQL/Prisma user and project models, project dashboard.
- **PR 2 / uploads:** S3-compatible multipart upload (8 MiB parts; 1 GiB file limit), object-store URLs, metadata collected from browser.
- **PR 3 / editor:** single video timeline, preview, trim by one second, split at playhead, reorder clips by drag/drop, remove, undo/redo, and autosave using optimistic revision checks.
- **Not included:** FFmpeg server-side probing, thumbnails/proxy generation, MP4 rendering/export, captions, audio tracks, resumable uploads across page refreshes, and production hardening. Browser-reported duration is **untrusted** convenience metadata; production must run FFprobe in an isolated worker and verify true container type and codec.

## Local setup

1. Install Node.js 22+, Docker and Docker Compose.
2. \`cp .env.example .env\` and set \`GITHUB_CLIENT_ID\` and \`GITHUB_CLIENT_SECRET\`.
3. In GitHub OAuth Apps register callback \`http://localhost:3000/api/auth/github/callback\`. Set \`APP_URL=http://localhost:3000\`.
4. \`docker compose up -d\` to start PostgreSQL and MinIO and create bucket \`video-studio\`.
5. \`npm install\` (this starter repository did not contain a lockfile), then \`npx prisma migrate dev --name init\`.
6. \`npm run dev\` and visit http://localhost:3000. Sign in through GitHub, create a project and upload MP4/MOV/WebM.
7. Run checks: \`npm test\`, \`npm run lint\`, \`npm run build\`, \`npx tsc --noEmit\`.

**Storage CORS requirement:** browser upload requires your S3/MinIO bucket to allow requests from \`http://localhost:3000\`, methods \`PUT, GET, HEAD\`, and expose response header \`ETag\`. Configure the bucket CORS policy to allow the application origin and expose \`ETag\`. Never allow origins \`*\` for authenticated production browser access. For MinIO, \`MINIO_API_CORS_ALLOW_ORIGIN\` controls origins; verify that \`ETag\` is exposed to browsers. Cloud environments should use TLS and signed URLs valid for a short period.

A complete CORS example for an AWS S3 bucket:

\`\`\`json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT", "HEAD"],
    "AllowedOrigins": ["http://localhost:3000"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
\`\`\`

## Security notes

Only authenticated users can access and modify their own projects and assets. Same-origin checks apply to mutating APIs; HttpOnly SameSite=Lax cookies hold opaque server-side sessions. Never put S3 credentials or OAuth secrets in the browser or commit a real \`.env\`. Multipart uploads validate file size and part numbering, then check uploaded object length. For production, add server-side magic-byte checks, antivirus scanning where relevant, FFprobe validation, resource quotas, and lifecycle cleanup of abandoned multipart uploads.

The only committed data is project metadata and the edit decision list. Editing never modifies the source file. A standalone transcoding worker will be required before MP4 export can be offered.

## Editing data

\`\`\`json
{
  "version": 1,
  "fps": 30,
  "clips": [
    {
      "id": "00112233-4455-4677-8899-aabbccddeeff",
      "assetId": "database-asset-id",
      "sourceStartMs": 3000,
      "durationMs": 8000
    }
  ]
}
\`\`\`

Editing commands live in \`src/features/editor/timeline.mjs\` and are covered by \`tests/timeline.test.mjs\`. Clip IDs use UUIDs and asset IDs map to project-owned media.
