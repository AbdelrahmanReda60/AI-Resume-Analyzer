import fs from "node:fs";

// Requires a headless Chrome with remote debugging:
//   google-chrome --headless=new --remote-debugging-port=9222 \
//     --user-data-dir=/tmp/chromeprofile --no-sandbox about:blank
// and the API server on 127.0.0.1:8080.
// Verifies the dashboard resumes table no longer overflows horizontally,
// and that forced :hover still changes nothing.
const PORT = 9222;
const BASE = "http://127.0.0.1:8080";
const WIDTHS = [360, 375, 414, 600, 700, 768, 1280];
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

const SCAN = `(() => {
  const doc = document.documentElement;
  const c = document.getElementById("resumes-table-container");
  const t = c ? c.querySelector("table") : null;
  const rows = document.querySelectorAll("#resumes-tbody tr");
  const r0 = rows[0] || null;
  const over = [];
  document.querySelectorAll("body *").forEach((el) => {
    const cs = getComputedStyle(el);
    if (cs.overflowY === "visible" && cs.overflowX === "visible") return;
    const spillY = el.scrollHeight - el.clientHeight;
    const spillX = el.scrollWidth - el.clientWidth;
    if (spillX > 1 || spillY > 1) {
      over.push((el.id ? "#" + el.id : el.tagName.toLowerCase()) + " spillX=" + spillX + " spillY=" + spillY);
    }
  });
  return JSON.parse(JSON.stringify({
    docScrollW: doc.scrollWidth, docClientW: doc.clientWidth,
    tableOverflowX: c ? getComputedStyle(c).overflowX : null,
    tableContainerSpillX: c ? c.scrollWidth - c.clientWidth : null,
    tableW: t ? Math.round(t.getBoundingClientRect().width) : null,
    rowCount: rows.length,
    firstRowDisplay: r0 ? getComputedStyle(r0).display : null,
    firstCellDisplay: r0 ? getComputedStyle(r0.querySelector("td")).display : null,
    firstCellLabel: r0 ? getComputedStyle(r0.querySelector("td"), "::before").content : null,
    overflowing: over,
  }));
})()`;

const SNAP = `(() => {
  const out = {};
  document.querySelectorAll("body *").forEach((el, i) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    out[i] = [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height),
              cs.display, cs.visibility, cs.opacity, cs.height, cs.overflow, cs.transform];
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
  await c.send("Network.enable"); await c.send("Network.setCacheDisabled", { cacheDisabled: true });

  const email = "table_" + Date.now() + "@example.com";
  const reg = await (await fetch(BASE + "/api/auth/register", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password: "Password123!", full_name: "Table Probe" }),
  })).json();
  await c.send("Page.addScriptToEvaluateOnNewDocument", {
    source: `localStorage.setItem("token", ${JSON.stringify(reg.access_token)});
      localStorage.setItem("user", ${JSON.stringify(JSON.stringify(reg.user))});`,
  });

  // Seed 3 resumes so multiple rows render (server accepts PDF/DOCX only)
  const stream = "BT\n/F1 11 Tf\n14 TL\n50 760 Td\n(Jane Doe Senior Software Engineer Python FastAPI Docker PostgreSQL AWS) Tj T*\nET";
  const objs = ["<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    "<< /Length " + stream.length + " >>\nstream\n" + stream + "\nendstream"];
  let pdf = "%PDF-1.4\n", offs = [];
  objs.forEach((o, i) => { offs.push(pdf.length); pdf += (i + 1) + " 0 obj\n" + o + "\nendobj\n"; });
  const xref = pdf.length;
  pdf += "xref\n0 " + (objs.length + 1) + "\n0000000000 65535 f \n";
  offs.forEach((o) => { pdf += String(o).padStart(10, "0") + " 00000 n \n"; });
  pdf += "trailer\n<< /Size " + (objs.length + 1) + " /Root 1 0 R >>\nstartxref\n" + xref + "\n%%EOF";
  const bytes = new Uint8Array(pdf.length);
  for (let i = 0; i < pdf.length; i++) bytes[i] = pdf.charCodeAt(i) & 0xff;

  for (let i = 1; i <= 3; i++) {
    const f = new FormData();
    f.append("file", new Blob([bytes], { type: "application/pdf" }), "resume" + i + ".pdf");
    const res = await fetch(BASE + "/api/resumes/upload", {
      method: "POST", headers: { Authorization: "Bearer " + reg.access_token }, body: f,
    });
    if (!res.ok) console.log("seed", i, res.status, (await res.text()).slice(0, 200));
  }
  const seeded = await (await fetch(BASE + "/api/resumes", { headers: { Authorization: "Bearer " + reg.access_token } })).json();
  console.log("seeded resumes:", seeded.length);

  let fail = 0;
  for (const w of WIDTHS) {
    await c.send("Emulation.setDeviceMetricsOverride", { width: w, height: 900, deviceScaleFactor: 1, mobile: w < 500 });
    await c.send("Page.navigate", { url: BASE + "/dashboard.html" });
    await sleep(2500);
    const loc = (await c.send("Runtime.evaluate", { expression: "location.pathname", returnByValue: true })).result.value;
    if (loc !== "/dashboard.html") { console.log(`@${w}: redirected to ${loc}`); continue; }
    const s = (await c.send("Runtime.evaluate", { expression: SCAN, returnByValue: true })).result.value;
    const bad = s.overflowing.filter((x) => !/select|option/.test(x));
    const docHScroll = s.docScrollW > s.docClientW + 1;
    const stacked = w <= 700;
    const layoutOk = stacked
      ? s.firstRowDisplay === "block" && s.firstCellDisplay === "flex" && /Title/.test(s.firstCellLabel || "")
      : s.firstRowDisplay === "table-row";
    const ok = !docHScroll && s.tableContainerSpillX <= 1 && bad.length === 0 && s.rowCount > 0 && layoutOk;
    if (!ok) fail++;
    console.log(`@${w}px ${ok ? "OK " : "FAIL"} doc=${s.docScrollW}/${s.docClientW} tableSpillX=${s.tableContainerSpillX} ` +
      `tableW=${s.tableW} rows=${s.rowCount} rowDisplay=${s.firstRowDisplay} cell=${s.firstCellDisplay} ` +
      `label=${s.firstCellLabel} overflow=${JSON.stringify(bad)}`);

    if (w === 375 || w === 768 || w === 1280) {
      const shot = await c.send("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(`/tmp/opencode/table_${w}.png`, Buffer.from(shot.data, "base64"));
      const b = (await c.send("Runtime.evaluate", { expression: SNAP, returnByValue: true })).result.value;
      const doc = await c.send("DOM.getDocument", { depth: -1 });
      const ids = [];
      for (const sel of [".card", ".card-title", ".resume-row", "main > div", ".btn"]) {
        const qq = await c.send("DOM.querySelector", { nodeId: doc.root.nodeId, selector: sel }).catch(() => null);
        if (qq && qq.nodeId) { ids.push(qq.nodeId); await c.send("CSS.forcePseudoState", { nodeId: qq.nodeId, forcedPseudoClasses: ["hover"] }); }
      }
      await sleep(400);
      const a = (await c.send("Runtime.evaluate", { expression: SNAP, returnByValue: true })).result.value;
      const diffs = Object.keys(b).filter((k) => k !== "__n" && k !== "__scroll" && JSON.stringify(b[k]) !== JSON.stringify(a[k]));
      console.log(`       hover diffs: ${diffs.length ? diffs.join(" | ") : "NONE"}`);
      if (diffs.length) fail++;
      for (const id of ids) await c.send("CSS.forcePseudoState", { nodeId: id, forcedPseudoClasses: [] }).catch(() => {});
      const shot2 = await c.send("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(`/tmp/opencode/table_${w}_hover.png`, Buffer.from(shot2.data, "base64"));
    }
  }
  console.log(fail ? `\n${fail} FAILING CHECKS` : "\nALL CHECKS PASSED");
  try { await c.send('Page.close'); } catch (_) {}
  ws.close();
  process.exit(fail ? 1 : 0);
}
main().catch((e) => { console.error("ERR", e); process.exit(1); });
