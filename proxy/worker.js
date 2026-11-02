const MAX_REDIRECTS = 3;
const MAX_MANIFEST_BYTES = 2097152;

function hostList(env) {
  return new Set((env.ALLOWED_HOSTS || "").split(",").map(x => x.trim().toLowerCase()).filter(Boolean));
}
function isAllowed(url, hosts) {
  return url.protocol === "https:" && hosts.has(url.hostname.toLowerCase());
}
function decodeUrl(path) {
  const raw = path.slice(3).replace(/-/g, "+").replace(/_/g, "/");
  if (!raw || raw.includes("/")) throw new Error("bad target");
  const binary = atob(raw + "=".repeat((4 - raw.length % 4) % 4));
  const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
  return new URL(new TextDecoder().decode(bytes));
}
function encodeUrl(value) {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}
function wrapUrl(base, target) {
  const u = new URL(base);
  u.pathname = "/p/" + encodeUrl(target);
  u.search = "";
  return u.toString();
}
async function fetchOrigin(target, request, hosts, env) {
  let current = target;
  for (let hop = 0; hop <= MAX_REDIRECTS; hop++) {
    if (!isAllowed(current, hosts)) return {response:new Response("Host not allowlisted", {status:403}), url:current};
    const headers = new Headers();
    for (const key of ["range","if-range","if-none-match","if-modified-since"]) {
      const value = request.headers.get(key);
      if (value) headers.set(key, value);
    }
    headers.set("User-Agent", env.UPSTREAM_USER_AGENT || "SmoothTiviMateProxy/1.0");
    const response = await fetch(current.toString(), {method:request.method, headers, redirect:"manual"});
    if (![301,302,303,307,308].includes(response.status)) return {response, url:current};
    const location = response.headers.get("location");
    if (!location || hop === MAX_REDIRECTS) return {response:new Response("Redirect limit reached", {status:502}), url:current};
    current = new URL(location, current);
  }
}
function rewriteManifest(text, origin, requestUrl) {
  const rewrite = value => wrapUrl(requestUrl, new URL(value, origin).toString());
  return text.split(/\r?\n/).map(line => {
    const trimmed = line.trim();
    if (!trimmed) return line;
    if (trimmed.startsWith("#")) return line.replace(/URI="([^"]+)"/g, (_m, uri) => 'URI="' + rewrite(uri) + '"');
    return rewrite(trimmed);
  }).join("\n");
}
export default {
  async fetch(request, env) {
    if (!["GET","HEAD"].includes(request.method)) return new Response("Method not allowed", {status:405});
    const expected = env.PROXY_TOKEN || "";
    const provided = (request.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
    if (!expected || provided !== expected) return new Response("Unauthorized", {status:401});
    const hosts = hostList(env);
    if (!hosts.size) return new Response("Proxy is not configured", {status:503});
    let target;
    try { target = decodeUrl(new URL(request.url).pathname); }
    catch { return new Response("Invalid target URL", {status:400}); }
    if (!isAllowed(target, hosts)) return new Response("Target host not allowlisted", {status:403});

    const result = await fetchOrigin(target, request, hosts, env);
    const upstream = result.response;
    const headers = new Headers(upstream.headers);
    headers.delete("set-cookie");
    headers.delete("server");
    headers.set("Access-Control-Allow-Origin", "*");
    headers.set("Cache-Control", "no-store");
    if (request.method === "HEAD" || !upstream.ok) return new Response(null, {status:upstream.status, headers});

    const type = (headers.get("content-type") || "").toLowerCase();
    const manifest = result.url.pathname.toLowerCase().endsWith(".m3u8") || type.includes("mpegurl");
    if (!manifest) return new Response(upstream.body, {status:upstream.status, headers});
    const size = Number(headers.get("content-length") || "0");
    if (size > MAX_MANIFEST_BYTES) return new Response("Manifest too large", {status:413});
    const bytes = await upstream.arrayBuffer();
    if (bytes.byteLength > MAX_MANIFEST_BYTES) return new Response("Manifest too large", {status:413});
    const rewritten = rewriteManifest(new TextDecoder().decode(bytes), result.url, request.url);
    headers.delete("content-length");
    headers.set("Content-Type", "application/vnd.apple.mpegurl; charset=utf-8");
    return new Response(rewritten, {status:upstream.status, headers});
  }
};
