import { notFound, redirect } from "next/navigation";
import EditorShell from "@/components/editor/EditorShell";
import { getCurrentUser } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { timelineSchema } from "@/features/editor/validation";
import { emptyTimeline } from "@/features/editor/timeline.mjs";

export const dynamic = "force-dynamic";

export default async function EditPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/");
  const { projectId } = await params;
  const project = await prisma.project.findFirst({ where: { id: projectId, ownerId: user.id } });
  if (!project) notFound();

  const assets = await prisma.mediaAsset.findMany({
    where: { projectId: project.id, status: "READY" },
    orderBy: { createdAt: "asc" },
    select: {
      id: true, fileName: true, contentType: true,
      durationMs: true, width: true, height: true,
    },
  });
  const parsed = timelineSchema.safeParse(project.timeline);
  return (
    <EditorShell
      projectId={project.id}
      projectName={project.name}
      initialTimeline={parsed.success ? parsed.data : emptyTimeline()}
      initialRevision={project.revision}
      initialAssets={assets}
    />
  );
}
