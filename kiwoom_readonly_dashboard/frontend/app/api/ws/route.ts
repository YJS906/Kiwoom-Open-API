import { NextResponse } from "next/server";

export async function GET() {
  const baseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
  const wsUrl = baseUrl.replace(/^http/i, "ws") + "/ws/stream";
  return NextResponse.json({ url: wsUrl });
}
