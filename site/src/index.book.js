// Yoneda site Worker.
//
// FRONT HALF (live): /api/profile reverse-engineers a group profile from DOIs
// (Crossref, no auth). A lab pastes its DOIs and sees who/what the book aims at.
//
// BACK HALF (this file adds it): POST /api/book turns that profile into a filled,
// compiled Yoneda book PDF and streams it back. Pipeline:
//   (a) buildProfile(dois)                      -> group profile
//   (b) expandSlots(profile, methods) via AI    -> complete 202-slot lab_slots map
//   (c) POST {lab, lab_slots} to the container  -> latexmk build
//   (d) stream the PDF bytes back to the browser
//
// The container class (BookCompiler) is exported from this entry module so the
// Durable-Object runtime that backs Cloudflare Containers can find it. It listens
// on defaultPort, where the container's server.py HTTP server runs make_edition +
// fill_codeblocks + latexmk and returns the PDF.

import { Container, getContainer } from "@cloudflare/containers";
import SLOT_MANIFEST from "../slots-manifest.json";

const UA = "yoneda-site/1.0 (mailto:jeremy.levy@levylab.org)";

// The Workers AI model used for slot-fill. On the JSON-mode compatibility list,
// largest/fastest instruct model there, accepts response_format json_schema.
const AI_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";
// Fill this many slots per AI call. A 202-field schema in one shot risks blowing
// the model's context/output window (docs do not state the limit), so we batch.
const SLOT_BATCH = 40;

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
    // kept internal for the slot-fill prompt, not shown by /api/profile:
    _titles: papers.map(p => p.title).filter(Boolean).slice(0, 20),
    _affiliations: tally(papers.flatMap(p => p.affiliations)).slice(0, 6).map(([a]) => a),
  };
}

// A filesystem-safe lab key derived from the dominant author surname (falls back
// to "lab"). Used to name profile-<lab>.tex / build-<lab> in the container.
function labKey(profile) {
  const top = (profile.people && profile.people[0] && profile.people[0].name) || "";
  const surname = top.split(/\s+/).filter(Boolean).pop() || "lab";
  const slug = surname.toLowerCase().replace(/[^a-z0-9]/g, "");
  return slug || "lab";
}

// A compact, model-friendly description of the lab, from the profile.
function profileBrief(profile, methodsText) {
  const people = (profile.people || []).slice(0, 12).map(p => p.name).join(", ");
  const mats = (profile.materials || []).map(m => m.term).join(", ") || "(none extracted)";
  const venues = (profile.venues || []).map(v => v.journal).join(", ") || "(unknown)";
  const affs = (profile._affiliations || []).join("; ") || "(unknown)";
  const titles = (profile._titles || []).slice(0, 10).map(t => "- " + t).join("\n");
  let brief =
`People (most frequent authors, the first is likely the PI): ${people}
Materials / systems studied: ${mats}
Publishes in: ${venues}
Affiliations: ${affs}
Representative paper titles:
${titles}`;
  if (methodsText && methodsText.trim()) {
    brief += `\n\nMethods text the lab supplied (mine it for instruments, cryostats, file formats, sample naming, software):\n${methodsText.trim().slice(0, 6000)}`;
  }
  return brief;
}

// Ask Workers AI to map the lab's profile onto one batch of book slots. Returns a
// { name: value } object; on any failure returns {} so callers fall back to defaults.
async function fillBatch(env, brief, batch) {
  const properties = {}, required = [];
  const lines = [];
  for (const name of batch) {
    properties[name] = { type: "string" };
    required.push(name);
    lines.push(`${name}  (generic default: "${SLOT_MANIFEST[name].default}")`);
  }
  const system =
`You are localizing a printed book to a specific research group. The book is about a data/knowledge system and threads a running worked example through it: a lab, its instruments, cryostats, materials, samples, file formats, colleagues, and corpus. Each item below is a "slot": a token that appears in the book's prose and code examples, with a GENERIC default. Replace each with a concrete, believable value drawn from THIS lab's real people, materials, instruments, and methods. Rules: keep the same kind and grammatical shape as the default (if the default is a lowercase noun phrase, return a lowercase noun phrase; if it looks like an ID such as SAMPLE-0001 or a file extension such as dat, return something of that exact shape); keep values short (usually 1-6 words); do not add quotes, LaTeX, or explanation; if you have no lab-specific basis, return a sensible plausible value rather than repeating the word "your". Return every requested key.`;
  const user = `The lab:\n\n${brief}\n\nFill these ${batch.length} slots:\n${lines.join("\n")}`;
  try {
    const r = await env.AI.run(AI_MODEL, {
      messages: [
        { role: "system", content: system },
        { role: "user", content: user },
      ],
      response_format: {
        type: "json_schema",
        json_schema: { type: "object", properties, required },
      },
    });
    let o = r && r.response !== undefined ? r.response : r;
    if (typeof o === "string") { try { o = JSON.parse(o); } catch { o = {}; } }
    return (o && typeof o === "object") ? o : {};
  } catch {
    return {};
  }
}

// Build a COMPLETE lab_slots map for every arity-0 slot (200 of them). AI values
// are validated; anything missing/blank/non-string falls back to the generic
// default so the book always compiles. The 2 arity-1 table macros are omitted on
// purpose: they carry multi-line LaTeX defaults the model should not author, and
// make_edition falls back to those defaults for any slot we do not name.
async function expandSlots(env, profile, methodsText) {
  const names = Object.keys(SLOT_MANIFEST).filter(n => SLOT_MANIFEST[n].arity === 0);
  const brief = profileBrief(profile, methodsText);

  const batches = [];
  for (let i = 0; i < names.length; i += SLOT_BATCH) batches.push(names.slice(i, i + SLOT_BATCH));

  const filled = {};
  // Fire the batches concurrently; each is independent.
  const results = await Promise.all(batches.map(b => fillBatch(env, brief, b)));
  for (const res of results) Object.assign(filled, res);

  const lab_slots = {};
  let aiCount = 0;
  for (const name of names) {
    const v = filled[name];
    if (typeof v === "string" && v.trim()) { lab_slots[name] = v.trim(); aiCount++; }
    else lab_slots[name] = SLOT_MANIFEST[name].default;
  }
  return { lab_slots, aiCount, total: names.length };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/profile" && request.method === "POST") {
      let body;
      try { body = await request.json(); } catch { return json({ error: "bad JSON" }, 400); }
      const dois = (body.dois || []).map(s => String(s).trim()).filter(Boolean).slice(0, 20);
      if (!dois.length) return json({ error: "Give at least one DOI." }, 400);
      const prof = await buildProfile(dois);
      // strip the internal fields before returning the public profile
      if (!prof.error) { delete prof._titles; delete prof._affiliations; }
      return json(prof);
    }

    if (url.pathname === "/api/book" && request.method === "POST") {
      let body;
      try { body = await request.json(); } catch { return json({ error: "bad JSON" }, 400); }
      const dois = (body.dois || []).map(s => String(s).trim()).filter(Boolean).slice(0, 20);
      if (!dois.length) return json({ error: "Give at least one DOI." }, 400);
      const methodsText = typeof body.methods_text === "string" ? body.methods_text : "";

      const profile = await buildProfile(dois);
      if (profile.error) return json(profile, 400);

      const lab = labKey(profile);
      const { lab_slots } = await expandSlots(env, profile, methodsText);

      // Hand the completed slot map to the container, which compiles and returns
      // the PDF bytes. getContainer(...).fetch(req) auto-starts the instance and
      // proxies to defaultPort; we hold the connection until latexmk finishes.
      const container = getContainer(env.BOOK_COMPILER);
      const compileReq = new Request("http://book-compiler/compile", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ lab, lab_slots }),
      });
      let resp;
      try {
        resp = await container.fetch(compileReq);
      } catch (e) {
        return json({ error: "Compile service unreachable: " + e }, 502);
      }
      if (!resp.ok) {
        const detail = await resp.text().catch(() => "");
        return json({ error: "Compile failed (" + resp.status + "). " + detail.slice(0, 2000) }, 502);
      }
      // Stream the PDF back with a download filename.
      return new Response(resp.body, {
        status: 200,
        headers: {
          "content-type": "application/pdf",
          "content-disposition": `attachment; filename="yoneda-${lab}.pdf"`,
          "cache-control": "no-store",
        },
      });
    }

    return env.ASSETS.fetch(request);
  },
};

// Container class backing the Cloudflare Container. Must be exported from the
// entry module and registered in wrangler ([[containers]] + a DO binding + a
// migration listing it in new_sqlite_classes). defaultPort matches the port the
// container's server.py listens on.
export class BookCompiler extends Container {
  defaultPort = 8080;
  // A full-book latexmk run takes many seconds; keep the instance warm well past
  // a single request so back-to-back builds reuse the started TeX Live process.
  sleepAfter = "15m";
  onError(error) { console.log("BookCompiler error:", error); }
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj, null, 2),
    { status, headers: { "content-type": "application/json; charset=utf-8" } });
}
