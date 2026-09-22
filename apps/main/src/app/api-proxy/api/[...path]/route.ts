import { NextRequest, NextResponse } from "next/server";

import { env } from "@/lib/env";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Forward only headers the API needs from browser requests. Keeping this
// explicit avoids accidentally relaying host, cookie, or proxy headers.
const REQUEST_HEADERS = ["authorization", "content-type", "x-device-id"];

async function proxy(
  request: NextRequest,
  { params }: { params: { path: string[] } },
) {
  const headers = new Headers();
  for (const header of REQUEST_HEADERS) {
    const value = request.headers.get(header);
    if (value) headers.set(header, value);
  }

  const target = new URL(`/api/${params.path.join("/")}`, env.serverApiUrl);
  target.search = request.nextUrl.search;

  const hasBody = !["GET", "HEAD"].includes(request.method);
  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? request.body : undefined,
    // Required when forwarding a readable request stream in Node.js.
    // @ts-expect-error Next's RequestInit accepts duplex at runtime.
    duplex: hasBody ? "half" : undefined,
    cache: "no-store",
  });

  const responseHeaders = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) responseHeaders.set("content-type", contentType);

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
