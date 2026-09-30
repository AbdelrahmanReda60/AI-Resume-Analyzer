// Requires a headless Chrome with remote debugging:
//   google-chrome --headless=new --remote-debugging-port=9222 \
//     --user-data-dir=/tmp/chromeprofile --no-sandbox about:blank
// and the API server on 127.0.0.1:8080.
// Multi-width hover + clipping probe.
const PORT = 9222;
const BASE = "http://127.0.0.1:8080";
const WIDTHS = [375, 768, 1280];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Always opens a dedicated tab so parallel runs never fight over one target.
async function getWsUrl() {
  for (let i = 0; i < 40; i++) {
    try {
      const t = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" })).json();
      if (t && t.webSocketDebuggerUrl) return t.webSocketDebuggerUrl;
    } catch (_) {}
    await sleep(250);
  }
  throw new Error("devtools not up");
}

function cdp(ws) {
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
    }
  });
  return {
    send(method, params = {}) {
      const mid = ++id;
      ws.send(JSON.stringify({ id: mid, method, params }));
      return new Promise((resolve, reject) => {
        pending.set(mid, { resolve, reject });
        setTimeout(() => { if (pending.has(mid)) { pending.delete(mid); reject(new Error("timeout " + method)); } }, 8000);
      });
    },
  };
}

// Finds elements whose painted content is cut off by an ancestor, and
// any element whose computed box differs when :hover is forced.
const SCAN = `(() => {
  const report = { clipped: [], overflowers: [], notes: [] };
  const doc = document.documentElement;
  report.notes.push("doc scrollW/clientW=" + doc.scrollWidth + "/" + doc.clientWidth
    + " scrollH/clientH=" + doc.scrollHeight + "/" + doc.clientHeight);
  const all = document.querySelectorAll("body *");
  all.forEach((el) => {
    const cs = getComputedStyle(el);
    const tag = el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + (el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\\s+/).join(".") : "");
    // 1. element itself clips its content
    const clips = ["hidden", "clip", "auto", "scroll"].includes(cs.overflowY) || ["hidden","clip","auto","scroll"].includes(cs.overflowX);
    if (clips) {
      const spillY = el.scrollHeight - el.clientHeight;
      const spillX = el.scrollWidth - el.clientWidth;
      if (spillY > 1 || spillX > 1) report.clipped.push(tag + " overflow=" + cs.overflow + " spillY=" + spillY + " spillX=" + spillX);
    }
    // 2. child painted outside a clipping ancestor
    if (cs.overflow === "visible") return;
    const pr = el.getBoundingClientRect();
    for (const child of el.children) {
      const cr = child.getBoundingClientRect();
      const outside = cr.bottom > pr.bottom + 1 || cr.top < pr.top - 1 || cr.right > pr.right + 1 || cr.left < pr.left - 1;
      if (outside) report.overflowers.push(tag + " > " + child.tagName.toLowerCase() +
        " childBottom=" + Math.round(cr.bottom) + " parentBottom=" + Math.round(pr.bottom) +
        " childH=" + Math.round(cr.height) + " parentH=" + Math.round(pr.height));
    }
    // 3. fixed height / max-height / opacity 0 / display none / visibility hidden
    if (cs.maxHeight !== "none") report.notes.push("max-height on " + tag + " = " + cs.maxHeight);
    if (cs.opacity !== "1" && cs.visibility !== "hidden") report.notes.push("opacity on " + tag + " = " + cs.opacity);
  });
  // header + cards summary
  ["main > div", ".card", ".card-title", ".card-header", ".grid"].forEach((s) => {
    document.querySelectorAll(s).forEach((el, i) => {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      report.notes.push(s + "[" + i + "] h=" + Math.round(r.height) + " overflow=" + cs.overflow + " height=" + cs.height + " maxH=" + cs.maxHeight + " display=" + cs.display + " opacity=" + cs.opacity + " transform=" + cs.transform);
    });
  });
  return JSON.parse(JSON.stringify(report));
})()`;

const SNAPSHOT = `(() => {
  const out = {};
  document.querySelectorAll("body *").forEach((el, i) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    out[i] = [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height),
              cs.display, cs.visibility, cs.opacity, cs.height, cs.overflow, cs.transform, cs.boxShadow, cs.borderColor];
  });
  out.__n = document.querySelectorAll("body *").length;
  out.__scroll = [window.scrollY, document.documentElement.scrollHeight];
  return JSON.parse(JSON.stringify(out));
})()`;

async function main() {
  const ws = new WebSocket(await getWsUrl());
  await new Promise((r) => (ws.onopen = r));
  const c = cdp(ws);
  await c.send("Page.enable"); await c.send("DOM.enable"); await c.send("CSS.enable");

  const email = "probe2_" + Date.now() + "@example.com";
  const reg = await (await fetch(BASE + "/api/auth/register", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password: "Password123!", full_name: "Probe User" }),
  })).json();
  const seed = `localStorage.setItem("token", ${JSON.stringify(reg.access_token)});
    localStorage.setItem("user", ${JSON.stringify(JSON.stringify(reg.user))});`;
  await c.send("Page.addScriptToEvaluateOnNewDocument", { source: seed });

  // Real data so the analysis / recommendations pages actually render cards
  let resumeId = null;
  try {
    let bytes;
    const buf = await fetch(BASE + "/samples/jane_doe_resume.pdf").then(r => r.ok ? r : null).catch(() => null);
    if (buf) {
      bytes = new Uint8Array(await buf.arrayBuffer());
    } else {
      // fall back to a minimal PDF built in-page
      const enc = new TextEncoder();
      const stream = "BT\n/F1 11 Tf\n14 TL\n50 760 Td\n(Jane Doe Senior Software Engineer Python FastAPI Docker PostgreSQL AWS Git) Tj T*\nET";
      const objs = ["<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        "<< /Length " + stream.length + " >>\nstream\n" + stream + "\nendstream"];
      let out = "%PDF-1.4\n", offs = [];
      objs.forEach((o, i) => { offs.push(out.length); out += (i + 1) + " 0 obj\n" + o + "\nendobj\n"; });
      const xref = out.length;
      out += "xref\n0 " + (objs.length + 1) + "\n0000000000 65535 f \n";
      offs.forEach((o) => { out += String(o).padStart(10, "0") + " 00000 n \n"; });
      out += "trailer\n<< /Size " + (objs.length + 1) + " /Root 1 0 R >>\nstartxref\n" + xref + "\n%%EOF";
      const arr = new Uint8Array(out.length);
      for (let i = 0; i < out.length; i++) arr[i] = out.charCodeAt(i) & 0xff;
      bytes = arr;
    }
    const fd = new FormData();
    fd.append("file", new Blob([bytes], { type: "application/pdf" }), "jane.pdf");
    const up = await (await fetch(BASE + "/api/resumes/upload", {
      method: "POST", headers: { Authorization: "Bearer " + reg.access_token }, body: fd,
    })).json();
    resumeId = up.id;
    await fetch(BASE + "/api/resumes/" + resumeId + "/analyze", {
      method: "POST", headers: { Authorization: "Bearer " + reg.access_token },
    });
    console.log("seeded resume id", resumeId);
  } catch (e) { console.log("resume seeding failed:", e.message); }

  const pages = ["dashboard.html", "jobs.html",
    "job-recommendations.html" + (resumeId ? "?id=" + resumeId : ""),
    "resume-analysis.html" + (resumeId ? "?id=" + resumeId : "")];

  for (const page of pages) {
    for (const w of WIDTHS) {
      await c.send("Emulation.setDeviceMetricsOverride", {
        width: w, height: 900, deviceScaleFactor: 1, mobile: w < 500,
      });
      await c.send("Page.navigate", { url: `${BASE}/${page}` });
      await sleep(2600);
      const loc = (await c.send("Runtime.evaluate", { expression: "location.pathname + location.search", returnByValue: true })).result.value;
      if (!loc.includes(page.split("?")[0]) || loc.includes("login.html")) { console.log(`-- ${page}@${w}: ended at ${loc}`); continue; }

      const before = (await c.send("Runtime.evaluate", { expression: SNAPSHOT, returnByValue: true })).result.value;
      const scan = (await c.send("Runtime.evaluate", { expression: SCAN, returnByValue: true })).result.value;

      // Force :hover on every element that has a hover rule ancestor candidate
      const doc = await c.send("DOM.getDocument", { depth: -1 });
      const targets = [".card", ".card-title", ".card-header", "main > div", ".btn"];
      const ids = [];
      for (const sel of targets) {
        const qq = await c.send("DOM.querySelector", { nodeId: doc.root.nodeId, selector: sel }).catch(() => null);
        if (qq && qq.nodeId) { ids.push(qq.nodeId); await c.send("CSS.forcePseudoState", { nodeId: qq.nodeId, forcedPseudoClasses: ["hover"] }); }
      }
      await sleep(500);
      const after = (await c.send("Runtime.evaluate", { expression: SNAPSHOT, returnByValue: true })).result.value;

      const diffs = [];
      for (const k of Object.keys(before)) {
        if (k === "__n" || k === "__scroll") continue;
        if (JSON.stringify(before[k]) !== JSON.stringify(after[k])) diffs.push(k + ": " + JSON.stringify(before[k]) + " -> " + JSON.stringify(after[k]));
      }
      const scrollChanged = JSON.stringify(before.__scroll) !== JSON.stringify(after.__scroll);

      console.log(`\n### ${page.split("?")[0]} @ ${w}px  (elements=${before.__n})`);
      console.log("  hover diffs:", diffs.length ? diffs.join("\n    ") : "NONE");
      if (scrollChanged) console.log("  SCROLL CHANGED:", JSON.stringify(before.__scroll), "->", JSON.stringify(after.__scroll));
      if (scan.clipped.length) console.log("  CLIPPED:", scan.clipped.slice(0, 8).join(" | "));
      if (scan.overflowers.length) console.log("  CHILD OUTSIDE CLIPPING PARENT:", scan.overflowers.slice(0, 8).join(" | "));
      const interesting = scan.notes.filter((n) => /max-height|opacity=0/.test(n) || /overflow=(hidden|clip|auto|scroll)/.test(n));
      if (interesting.length) console.log("  NOTES:", interesting.slice(0, 10).join(" | "));

      for (const id of ids) await c.send("CSS.forcePseudoState", { nodeId: id, forcedPseudoClasses: [] }).catch(() => {});
    }
  }
  try { await c.send('Page.close'); } catch (_) {}
  ws.close();
}

main().catch((e) => { console.error("ERR", e); process.exit(1); });
