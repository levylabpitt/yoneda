// Yoneda site Worker: serves the static page, and exposes /api/profile, which
// reverse-engineers a group profile from DOIs (Crossref, live, no auth). This is
// the front half of print-on-demand: a lab pastes its DOIs and immediately sees
// the book will be aimed at ITS people and materials. The compile-to-PDF stage
// is added on top of this once the book template lands.

const UA = "yoneda-site/1.0 (mailto:jeremy.levy@levylab.org)";

// See the redirect below. On since 2026-07-25, when the Access wall came off
// the apex and yoneda.app began serving publicly.
const CANONICAL_REDIRECT = true;

// chemical-formula-ish tokens (LaAlO3, SrTiO3, KTaO3, MoS2), from extract.py
const FORMULA = /\b(?:[A-Z][a-z]?\d*){2,}\b/g;
const NOT_FORMULA = new Set(["DNA","RNA","PCR","NMR","STM","AFM","SEM","TEM","XRD","USA","PhD","II","III","IV","MHz","GHz","THz"]);

async function crossref(doi) {
  try {
    const r = await fetch("https://api.crossref.org/works/" + encodeURIComponent(doi),
                          { headers: { "User-Agent": UA } });
    if (!r.ok) return null;
    const m = (await r.json()).message;
    const authors = [], affs = [];
    for (const a of (m.author || [])) {
      const n = `${a.given || ""} ${a.family || ""}`.trim();
      if (n) authors.push(n);
      for (const x of (a.affiliation || [])) if (x.name) affs.push(x.name);
    }
    const dp = (m.issued && m.issued["date-parts"] && m.issued["date-parts"][0]) || [];
    return {
      doi,
      title: (m.title && m.title[0] || "").replace(/<[^>]+>/g, "").trim(),
      journal: (m["container-title"] && m["container-title"][0]) || "",
      year: dp[0] || 0,
      authors, affiliations: affs,
      abstract: (m.abstract || "").replace(/<[^>]+>/g, " ").trim(),
    };
  } catch { return null; }
}

function tally(arr) {
  const m = new Map();
  for (const x of arr) m.set(x, (m.get(x) || 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1]);
}

async function buildProfile(dois) {
  const papers = (await Promise.all(dois.map(crossref))).filter(Boolean);
  if (!papers.length) return { error: "No DOI resolved. Check the identifiers." };
  const people = tally(papers.flatMap(p => p.authors)).slice(0, 30)
                   .map(([name, n]) => ({ name, n }));
  const venues = tally(papers.map(p => p.journal).filter(Boolean)).slice(0, 8)
                   .map(([journal, n]) => ({ journal, n }));
  const matHits = [];
  for (const p of papers)
    for (const t of ((p.title + " " + p.abstract).match(FORMULA) || []))
      if (!NOT_FORMULA.has(t) && t.length >= 3 && /\d/.test(t)) matHits.push(t);
  const materials = tally(matHits).slice(0, 10).map(([term, n]) => ({ term, n }));
  const years = papers.map(p => p.year).filter(Boolean);
  const nAbs = papers.filter(p => p.abstract).length;
  const gaps = [];
  if (nAbs < papers.length)
    gaps.push(`Only ${nAbs} of ${papers.length} abstracts were in Crossref (ACS and APS do not deposit them), so the materials list is thinner than it looks.`);
  gaps.push("File formats and instruments cannot come from publication metadata; they live in methods sections. Upload one paper PDF to fill those.");
  return {
    n_papers: papers.length,
    year_span: years.length ? [Math.min(...years), Math.max(...years)] : [0, 0],
    people, venues, materials,
    gaps,
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    // Force HTTPS. Cloudflare's "Always Use HTTPS" is off, so a bare
    // http://yoneda.science stays HTTP and browsers (esp. incognito HTTPS-First)
    // warn "not secure". CF-Visitor carries the visitor's original scheme.
    const visitor = request.headers.get("cf-visitor") || "";
    if (url.protocol === "http:" || visitor.includes('"scheme":"http"')) {
      url.protocol = "https:";
      return Response.redirect(url.toString(), 301);
    }
    // Canonical host: yoneda.app. The .science name predates it (Pitt's Defender
    // blocked .science as uncategorized). Flip CANONICAL_REDIRECT on only once
    // the apex serves the public site: while a Cloudflare Access wall fronts
    // yoneda.app, redirecting sends every visitor (and every /api/profile call
    // from /make) into a login screen. Turning it on also requires
    // run_worker_first in wrangler.toml, since static assets otherwise bypass
    // this Worker entirely and would never see the redirect.
    if (CANONICAL_REDIRECT && url.hostname === "yoneda.science") {
      url.hostname = "yoneda.app";
      return Response.redirect(url.toString(), 301);
    }
    // yoneda.store is the plasmid store. Deliberately its own host rather than a
    // path on yoneda.app: a store is a peer instance, so another lab running one
    // is the same shape rather than a special case. Its apex serves store.html;
    // every other path falls through to the shared asset store, so /yo_paint.mp4
    // and the stem-cell files resolve on either hostname.
    // Ask the asset store for "/store", not "/store.html". Its default html
    // handling strips the extension, so requesting the .html internally answers
    // with a 307 to /store, which would land back here and loop forever.
    if (url.hostname === "yoneda.store" && url.pathname === "/") {
      return env.ASSETS.fetch(new Request(new URL("/store", url), request));
    }
    // The guessable path on the main site goes to the real home rather than
    // serving a second copy that would drift out of sync with it.
    if (url.hostname === "yoneda.app" && (url.pathname === "/store" || url.pathname === "/store/")) {
      return Response.redirect("https://yoneda.store/", 301);
    }
    if (url.pathname === "/api/profile" && request.method === "POST") {
      let body;
      try { body = await request.json(); } catch { return json({ error: "bad JSON" }, 400); }
      const dois = (body.dois || []).map(s => String(s).trim()).filter(Boolean).slice(0, 20);
      if (!dois.length) return json({ error: "Give at least one DOI." }, 400);
      return json(await buildProfile(dois));
    }
    return env.ASSETS.fetch(request);
  },
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj, null, 2),
    { status, headers: { "content-type": "application/json; charset=utf-8" } });
}
