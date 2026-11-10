import { redirect } from "next/navigation";

// Old bookmarks are intentionally redirected to the one-shot home screen.
export default function LegacyProjectEditor() {
  redirect("/");
}
