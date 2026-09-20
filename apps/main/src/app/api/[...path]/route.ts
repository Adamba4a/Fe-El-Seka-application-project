import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function targetFor(request: NextRequest, path: string[]) {
  const apiOrigin = process.env.BACKEND_INTERNAL_URL;
  if (!apiOrigin) {
    throw new Error("BACKEND_INTERNAL_URL is required for API proxy requests.");
  }

  const target = new URL(`/api/${path.map(encodeURIComponent).join("/")}`, apiOrigin);
  target.search = request.nextUrl.search;
  return target;
}

async function proxy(request: NextRequest, context: { params: { path: string[] } }) {
  try {
    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.delete("content-length");

    const upstream = await fetch(targetFor(request, context.params.path), {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
      // Required by Node's fetch implementation when streaming a request body.
      // @ts-expect-error Next's bundled fetch supports this undici option.
      duplex: "half",
      cache: "no-store",
    });

    const responseHeaders = new Headers(upstream.headers);
    for (const header of HOP_BY_HOP_HEADERS) responseHeaders.delete(header);
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch (error) {
    console.error("API proxy request failed", error);
    return Response.json(
      { error: "api_unavailable", message: "Service temporarily unavailable. Please try again." },
      { status: 503 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
