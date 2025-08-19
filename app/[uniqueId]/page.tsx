import { redirect } from "next/navigation";
import prisma from "@/lib/prisma";

export const dynamic = "force-dynamic";

export default async function ValidateLink(props: {
  params: Promise<{ uniqueId: string }>;
}) {
  // Await params to resolve the promise
  const { uniqueId } = await props.params;
  console.log("Unique ID:", uniqueId);

  // Validate the link in the database
  const candidate = await prisma.candidate.findFirst({
    where: { Exam_URL: `http://localhost:3000/${uniqueId}` },
  });

  if (!candidate) {
    console.error("Invalid or expired link:", uniqueId);
    redirect("/404"); // Redirect to an error page if the link is invalid
    return;
  }

  // Redirect to the login page if the link is valid
  redirect(`/login/${uniqueId}`);
}

