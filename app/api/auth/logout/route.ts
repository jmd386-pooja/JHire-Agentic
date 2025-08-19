import { NextResponse } from "next/server";

export async function POST() {
  const response = NextResponse.json(
    { message: "Logged out successfully" },
    { status: 200 }
  );

  // if(response.cookies.get("user_token"))
    response.cookies.delete("user_token");
  // if(response.cookies.get("candidate_token"))
    response.cookies.delete("candidate_token");

  return response;
}


