/**
 * Tomb of Light — Cloudflare Worker: API Gateway
 *
 * Proxies /api-gateway/* requests from tomboflight.com to
 * tomboflight-api.onrender.com, making all API calls same-origin
 * from the browser's perspective and eliminating CORS entirely.
 *
 * Deploy in Cloudflare Dashboard:
 *   Workers & Pages → Create → Create Worker → paste this code → Deploy
 *   Then: Websites → tomboflight.com → Workers Routes →
 *         Route: tomboflight.com/api-gateway/*  →  select this worker
 *
 * After deploying the route, config.js lists https://tomboflight.com/api-gateway
 * as the primary API base URL. The browser never directly contacts onrender.com.
 */

const BACKEND_ORIGIN = "https://tomboflight-api.onrender.com";
const GATEWAY_PREFIX = "/api-gateway";

export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (!url.pathname.startsWith(GATEWAY_PREFIX)) {
      return new Response(JSON.stringify({ detail: "Not found." }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    // Strip /api-gateway prefix and preserve path + query string
    const backendPath = url.pathname.slice(GATEWAY_PREFIX.length) || "/";
    const backendUrl = `${BACKEND_ORIGIN}${backendPath}${url.search}`;

    // Forward the request with all original headers intact
    const backendRequest = new Request(backendUrl, {
      method: request.method,
      headers: request.headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "follow",
    });

    let response;
    try {
      response = await fetch(backendRequest);
    } catch (_error) {
      return new Response(
        JSON.stringify({ detail: "API gateway: backend unreachable." }),
        {
          status: 502,
          headers: {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
          },
        }
      );
    }

    // Return the backend response as-is; backend CORS headers are not needed
    // because the browser sees this as a same-origin response from tomboflight.com.
    const responseHeaders = new Headers(response.headers);
    responseHeaders.set("Cache-Control", "no-store");
    // Remove backend CORS headers — not needed for same-origin responses.
    responseHeaders.delete("Access-Control-Allow-Origin");
    responseHeaders.delete("Access-Control-Allow-Credentials");
    responseHeaders.delete("Access-Control-Allow-Methods");
    responseHeaders.delete("Access-Control-Allow-Headers");
    responseHeaders.delete("Access-Control-Max-Age");

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  },
};
