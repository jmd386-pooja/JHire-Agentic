import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const cookies = request.cookies;
  const candidateId = cookies.get("candidate_id")?.value || null;
  const candidateName = cookies.get("candidate_name")?.value || null;
  const token = cookies.get("token")?.value || null;
  const avatar = cookies.get("avatar")?.value || null;
  const voice = cookies.get("voice")?.value || null;
  const skills = cookies.get("skills")?.value || null;

  return NextResponse.json({ candidateId, candidateName, token, avatar, voice, skills });
}
