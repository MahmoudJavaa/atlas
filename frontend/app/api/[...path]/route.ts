import { NextRequest, NextResponse } from "next/server";

const API_BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function handler(req: NextRequest) {
  const path = req.nextUrl.pathname;   // e.g. /api/sites  or /api/sites/
  const search = req.nextUrl.search;   // e.g. ?intent=commercial
  const target = `${API_BACKEND}${path}${path.endsWith("/") ? "" : "/"}${search}`;

  const headers = new Headers(req.headers);
  headers.delete("host");

  const resp = await fetch(target, {
    method: req.method,
    headers,
    body: req.method !== "GET" && req.method !== "HEAD" ? await req.text() : undefined,
  });

  const data = await resp.arrayBuffer();
  return new NextResponse(data, {
    status: resp.status,
    statusText: resp.statusText,
    headers: Object.fromEntries(resp.headers.entries()),
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
