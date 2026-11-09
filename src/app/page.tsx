import ProjectDashboard from "@/components/ProjectDashboard";
import { prisma } from "@/lib/db";
import { getCurrentUser } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function Home() {
  const user = await getCurrentUser();
  const projects = user
    ? await prisma.project.findMany({
        where: { ownerId: user.id },
        orderBy: { updatedAt: "desc" },
        select: { id: true, name: true, revision: true, updatedAt: true },
      })
    : [];
  return (
    <ProjectDashboard
      login={user?.login ?? null}
      projects={projects.map((project) => ({
        ...project,
        updatedAt: project.updatedAt.toISOString(),
      }))}
    />
  );
}
