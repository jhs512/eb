/* Excel Brain 그래프 뷰어 — 전부 클라이언트 사이드.
   브라우저가 CSV를 받아 sql.js(SQLite WASM)로 조회하고 cytoscape.js로 그린다. */
"use strict";

const DATA_BASE = "./data/";          // 배포 시 web/data/ 로 복사됨
const TYPE_COLORS = {
  pillar: "#7c3aed", concept: "#2563eb", fact: "#059669",
  decision: "#d97706", question: "#dc2626", playbook: "#0891b2",
  source: "#6b7280", note: "#94a3b8",
};
const colorFor = (t) => TYPE_COLORS[t] || "#64748b";

let db = null;     // sql.js Database
let cy = null;     // cytoscape instance

async function fetchCSV(name) {
  const res = await fetch(DATA_BASE + name);
  if (!res.ok) throw new Error(`${name} 로드 실패 (${res.status})`);
  return Papa.parse(await res.text(), { header: true, skipEmptyLines: true }).data;
}

function buildDb(SQL, nodes, edges) {
  const d = new SQL.Database();
  d.run(`CREATE TABLE nodes(id TEXT PRIMARY KEY, title, type, namespace,
           visibility, summary, confidence REAL, tags, body);
         CREATE TABLE edges(source, type, target, weight REAL, note);`);
  const ni = d.prepare("INSERT OR REPLACE INTO nodes VALUES (?,?,?,?,?,?,?,?,?)");
  for (const n of nodes) if ((n.id || "").trim())
    ni.run([n.id.trim(), n.title, n.type, n.namespace, n.visibility,
            n.summary, n.confidence ? +n.confidence : null, n.tags, n.body]);
  ni.free();
  const ei = d.prepare("INSERT INTO edges VALUES (?,?,?,?,?)");
  for (const e of edges) if ((e.source || "").trim() && (e.target || "").trim())
    ei.run([e.source.trim(), e.type, e.target.trim(), e.weight ? +e.weight : null, e.note]);
  ei.free();
  return d;
}

function rows(sql, params = []) {
  const out = [];
  const st = db.prepare(sql);
  st.bind(params);
  while (st.step()) out.push(st.getAsObject());
  st.free();
  return out;
}

function render(nodes, edges) {
  const ids = new Set(nodes.map((n) => (n.id || "").trim()).filter(Boolean));
  const els = [];
  for (const n of nodes) {
    const id = (n.id || "").trim();
    if (!id) continue;
    els.push({ data: { id, label: n.title || id, type: n.type || "" } });
  }
  for (const e of edges) {
    const s = (e.source || "").trim(), t = (e.target || "").trim();
    if (ids.has(s) && ids.has(t)) els.push({ data: { source: s, target: t, label: e.type || "" } });
  }
  cy = cytoscape({
    container: document.getElementById("cy"),
    elements: els,
    style: [
      { selector: "node", style: {
          "background-color": (n) => colorFor(n.data("type")),
          "label": "data(label)", "font-size": 10, "color": "#1c2230",
          "text-wrap": "wrap", "text-max-width": 90, "width": 20, "height": 20 } },
      { selector: "edge", style: {
          "width": 1.4, "line-color": "#c7cdd8", "target-arrow-color": "#c7cdd8",
          "target-arrow-shape": "triangle", "curve-style": "bezier",
          "label": "data(label)", "font-size": 8, "color": "#9aa3b2" } },
      { selector: ".dim", style: { "opacity": 0.12 } },
      { selector: ".hit", style: { "background-color": "#f59e0b", "width": 28, "height": 28 } },
    ],
    layout: { name: "cose", animate: false, padding: 30 },
  });
  cy.on("tap", "node", (ev) => showNode(ev.target.id()));
}

function showNode(id) {
  const n = rows("SELECT * FROM nodes WHERE id = ?", [id])[0];
  if (!n) return;
  const out = rows("SELECT type, target FROM edges WHERE source = ? ORDER BY target", [id]);
  const inc = rows("SELECT type, source FROM edges WHERE target = ? ORDER BY source", [id]);
  const li = (items, dir) => items.map((e) =>
    `<li><span class="etype">${e.type || ""}</span> ${dir === "out"
      ? `→ <a data-id="${e.target}">${e.target}</a>`
      : `<a data-id="${e.source}">${e.source}</a> →`}</li>`).join("") || "<li>(없음)</li>";
  const esc = (s) => (s == null ? "" : String(s).replace(/[&<>]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])));
  document.getElementById("panelBody").innerHTML =
    `<h2>${esc(n.title || n.id)}</h2>
     <div class="meta">${esc(n.type)} · ${esc(n.id)} · 신뢰도 ${n.confidence ?? "-"}${
       n.tags ? " · " + esc(n.tags) : ""}</div>
     ${n.summary ? `<div class="summary">${esc(n.summary)}</div>` : ""}
     <h3>나가는 엣지 (${out.length})</h3><ul>${li(out, "out")}</ul>
     <h3>들어오는 엣지 / 백링크 (${inc.length})</h3><ul>${li(inc, "in")}</ul>`;
  document.getElementById("panel").classList.remove("hidden");
  document.querySelectorAll("#panelBody a[data-id]").forEach((a) =>
    a.addEventListener("click", () => { focusNode(a.dataset.id); showNode(a.dataset.id); }));
  focusNode(id);
}

function focusNode(id) {
  const el = cy.getElementById(id);
  if (el) cy.animate({ center: { eles: el }, zoom: 1.4 }, { duration: 250 });
}

function runSearch(q) {
  cy.elements().removeClass("dim hit");
  if (!q.trim()) return;
  const like = "%" + q.trim().toLowerCase() + "%";
  // 클라이언트 사이드 SQLite 조회 (eb.py search 와 같은 부분일치)
  const hits = rows(
    `SELECT id FROM nodes WHERE lower(title) LIKE ? OR lower(summary) LIKE ?
       OR lower(tags) LIKE ? OR lower(body) LIKE ?`, [like, like, like, like]);
  const hitIds = new Set(hits.map((h) => h.id));
  cy.elements().addClass("dim");
  hits.forEach((h) => cy.getElementById(h.id).removeClass("dim").addClass("hit"));
  cy.edges().forEach((e) => {
    if (hitIds.has(e.source().id()) && hitIds.has(e.target().id())) e.removeClass("dim");
  });
}

async function main() {
  try {
    const SQL = await initSqlJs({
      locateFile: (f) => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${f}`,
    });
    const [nodes, edges] = await Promise.all([fetchCSV("nodes.csv"), fetchCSV("edges.csv")]);
    db = buildDb(SQL, nodes, edges);
    const n = rows("SELECT COUNT(*) c FROM nodes")[0].c;
    const e = rows("SELECT COUNT(*) c FROM edges")[0].c;
    document.getElementById("stats").textContent = `노드 ${n} · 엣지 ${e}`;
    render(nodes, edges);
    let timer;
    document.getElementById("q").addEventListener("input", (ev) => {
      clearTimeout(timer); timer = setTimeout(() => runSearch(ev.target.value), 150);
    });
    document.getElementById("closePanel").addEventListener("click", () =>
      document.getElementById("panel").classList.add("hidden"));
  } catch (err) {
    document.getElementById("stats").textContent = "오류: " + err.message;
    console.error(err);
  }
}
main();
