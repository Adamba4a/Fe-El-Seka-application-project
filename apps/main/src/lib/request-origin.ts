import type { NextRequest } from "next/server";

// Bunny's proxy forwards the container's internal bind address (0.0.0.0:3000)
// as the raw Host header, with the real public host only in X-Forwarded-Host.
// request.url / request.nextUrl.origin resolve from the raw Host in Node.js
// Route Handlers (unlike middleware, which Next.js resolves specially), so
// building absolute redirect URLs from request.url alone sends users to
// http://0.0.0.0:3000 instead of the public site.
export function resolveOrigin(request: NextRequest): string {
  const forwardedHost = request.headers.get("x-forwarded-host");
  if (!forwardedHost) return request.nextUrl.origin;
  const forwardedProto = request.headers.get("x-forwarded-proto") ?? "https";
  return `${forwardedProto}://${forwardedHost}`;
}
