import { NextRequest } from "next/server";
import { forwardHeaders, RESPONSE_HEADERS, upstreamUrl } from "../../../../lib/proxy";

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  let target: URL;
  try { target = upstreamUrl(request.url, path); } catch { return new Response("API proxy is not configured", { status: 503 }); }
  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();
  try {
    const upstream = await fetch(target, { method: request.method, headers: forwardHeaders(request.headers), body, redirect: "manual", cache: "no-store" });
    const headers = new Headers();
    for (const name of RESPONSE_HEADERS) { const value = upstream.headers.get(name); if (value) headers.set(name, value); }
    headers.set("cache-control", "private, no-store");
    const getSetCookie = (upstream.headers as Headers & { getSetCookie?: () => string[] }).getSetCookie;
    const cookies = getSetCookie?.call(upstream.headers) ?? (upstream.headers.get("set-cookie") ? [upstream.headers.get("set-cookie") as string] : []);
    for (const cookie of cookies) headers.append("set-cookie", cookie);
    // Fetch responses with a status that forbids a body (for example the
    // admin logout 204) must be reconstructed without passing the upstream
    // stream. Passing it to the Response constructor throws and turns a
    // successful logout into a client-visible 503.
    if ([204, 205, 304].includes(upstream.status)) {
      return new Response(null, { status: upstream.status, headers });
    }
    return new Response(upstream.body, { status: upstream.status, headers });
  } catch { return new Response("API is unavailable", { status: 503, headers: { "cache-control": "private, no-store" } }); }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
