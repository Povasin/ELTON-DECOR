import { NextRequest } from "next/server";
import { forwardHeaders, PRIVATE_PREFIXES, RESPONSE_HEADERS, upstreamUrl } from "../../../../lib/proxy";

function copyResponseHeaders(source: Headers, path: string): Headers {
  const headers = new Headers();
  for (const name of RESPONSE_HEADERS) {
    const value = source.get(name);
    if (value) headers.set(name, value);
  }
  const isPrivate = PRIVATE_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
  if (isPrivate) headers.set("cache-control", "private, no-store");
  const getSetCookie = (source as Headers & { getSetCookie?: () => string[] }).getSetCookie;
  const cookies = getSetCookie?.call(source) ?? (source.get("set-cookie") ? [source.get("set-cookie") as string] : []);
  for (const cookie of cookies) headers.append("set-cookie", cookie);
  return headers;
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  let target: URL;
  try { target = upstreamUrl(request.url, path); } catch { return new Response("API proxy is not configured", { status: 503 }); }
  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();
  let upstream: Response;
  try {
    upstream = await fetch(target, { method: request.method, headers: forwardHeaders(request.headers), body, redirect: "manual", cache: "no-store" });
  } catch {
    return new Response("API is unavailable", { status: 503, headers: { "cache-control": "private, no-store" } });
  }
  // A 204/205/304 response cannot contain a body. Keep the upstream stream
  // for normal responses, but omit it for bodyless statuses so the proxy
  // does not throw while forwarding successful mutations.
  const headers = copyResponseHeaders(upstream.headers, `/${path.join("/")}`);
  if ([204, 205, 304].includes(upstream.status)) {
    return new Response(null, { status: upstream.status, headers });
  }
  return new Response(upstream.body, { status: upstream.status, headers });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
