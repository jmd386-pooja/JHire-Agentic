import { NextRequest, NextResponse } from "next/server";

const AGENT_BASE_URL = process.env.AGENT_BASE_URL || "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  try {
    const { message } = await req.json();
    if (!message || typeof message !== "string") {
      return NextResponse.json(
        { status: "error", error: "message is required" },
        { status: 400 }
      );
    }

    const r = await fetch(`${AGENT_BASE_URL}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message }),
    });

    const data = await r.json();
    return NextResponse.json(data, { status: r.status || 200 });
  } catch (e: any) {
    return NextResponse.json(
      { status: "error", error: String(e?.message || e) },
      { status: 500 }
    );
  }
}
