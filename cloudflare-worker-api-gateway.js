/**
 * Tomb of Light — Cloudflare Worker: API Gateway
 *
 * Proxies /api-gateway/* requests from tomboflight.com to the Render API.
 * Deploy with Wrangler or the Cloudflare dashboard, then attach both
 * production hostname routes defined in wrangler.toml.
 */

const BACKEND_ORIGIN = "https://tomboflight-api.onrender.com";
const GATEWAY_PREFIX = "/api-gateway";
const ALLOWED_ORIGINS = new Set([
  "https://tomboflight.com",
  "https://www.tomboflight.com",
]);
const ALLOWED_HEADERS =
  "Authorization, Content-Type, Accept, Origin, X-CSRF-Token, Idempotency-Key";
const ALLOWED_METHODS = "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS";

function corsHeaders(request) {
  const origin = request.headers.get("Origin") || "";
  const headers = new Headers({
    "Access-Control-Allow-Methods": ALLOWED_METHODS,
    "Access-Control-Allow-Headers": ALLOWED_HEADERS,
    "Access-Control-Max-Age": "600",
    Vary: "Origin",
  });
  if (ALLOWED_ORIGINS.has(origin)) {
    headers.set("Access-Control-Allow-Origin", origin);
    headers.set("Access-Control-Allow-Credentials", "true");
  }
  return headers;
}

function jsonResponse(body, status, request) {
  const headers = corsHeaders(request);
  headers.set("Content-Type", "application/json");
  headers.set("Cache-Control", "no-store");
  return new Response(JSON.stringify(body), { status, headers });
}

export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (!url.pathname.startsWith(GATEWAY_PREFIX)) {
      return jsonResponse({ detail: "Not found." }, 404, request);
    }

    // Handle preflight at the gateway. It must never depend on Render's
    // availability and must never be proxied as a business operation.
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(request),
      });
    }

    const backendPath = url.pathname.slice(GATEWAY_PREFIX.length) || "/";
    const backendUrl = `${BACKEND_ORIGIN}${backendPath}${url.search}`;
    const forwardedHeaders = new Headers(request.headers);
    // These are connection/request-specific and must be regenerated for the
    // Render origin rather than copied from tomboflight.com.
    forwardedHeaders.delete("Host");
    forwardedHeaders.delete("Content-Length");
    forwardedHeaders.set("X-Forwarded-Host", url.host);
    forwardedHeaders.set("X-Forwarded-Proto", url.protocol.replace(":", ""));

    const backendRequest = new Request(backendUrl, {
      method: request.method,
      headers: forwardedHeaders,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "follow",
    });

    let response;
    try {
      response = await fetch(backendRequest);
    } catch (_error) {
      return jsonResponse(
        { detail: "API gateway: backend temporarily unavailable." },
        502,
        request,
      );
    }

    const responseHeaders = new Headers(response.headers);
    responseHeaders.set("Cache-Control", "no-store");
    responseHeaders.delete("Access-Control-Allow-Origin");
    responseHeaders.delete("Access-Control-Allow-Credentials");
    responseHeaders.delete("Access-Control-Allow-Methods");
    responseHeaders.delete("Access-Control-Allow-Headers");
    responseHeaders.delete("Access-Control-Max-Age");
    const gatewayCors = corsHeaders(request);
    for (const [key, value] of gatewayCors) {
      responseHeaders.set(key, value);
    }

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  },
};
