/* Excel Brain 지식 뷰어 — 전부 클라이언트 사이드.
   기본은 문서 본문 모드(중앙에 원문), 그래프는 토글로 보는 선택 뷰.
   브라우저가 CSV를 받아 sql.js(SQLite WASM)로 조회한다. */
"use strict";

const DATA_BASE = "./data/";
const TYPE_COLORS = {
  pillar: "#7c3aed", concept: "#2563eb", fact: "#059669",
  decision: "#d97706", question: "#dc2626", playbook: "#0891b2",
  source: "#6b7280", note: "#94a3b8",
};
const colorFor = (t) => TYPE_COLORS[t] || "#64748b";
const esc = (s) => (s == null ? "" : String(s).replace(/[&<>]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])));

let db = null, cy = null, current = null, allNodes = [];

async function fetchCSV(name) {
  const res = await fetch(DATA_BASE + name);
  if (!res.ok) throw new Error(`${name} 로드 실패 (${res.status})`);
  return Papa.parse(await res.text(), { header: true, skipEmptyLines: true }).data;
}
function rows(sql, params = []) {
  const out = [], st = db.prepare(sql);
  st.bind(params);
  while (st.step()) out.push(st.getAsObject());
  st.free();
  return out;
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

/* ---- 좌측 목록 ---- */
function renderList(filterIds) {
  const ul = document.getElementById("list");
  const items = allNodes.filter((n) => !filterIds || filterIds.has(n.id));
  if (!items.length) { ul.innerHTML = '<li class="empty">결과 없음</li>'; return; }
  ul.innerHTML = items.map((n) =>
    `<li data-id="${esc(n.id)}" class="${n.id === current ? "sel" : ""}">
       ${esc(n.title || n.id)}<br><span class="t">${esc(n.type || "")}</span></li>`).join("");
  ul.querySelectorAll("li[data-id]").forEach((li) =>
    li.addEventListener("click", () => select(li.dataset.id)));
}

/* ---- 중앙 문서(원문) ---- */
function renderDoc(id) {
  const n = rows("SELECT * FROM nodes WHERE id = ?", [id])[0];
  const doc = document.getElementById("doc");
  if (!n) { doc.innerHTML = '<p class="placeholder">노드를 선택하세요.</p>'; return; }
  const out = rows("SELECT type, target FROM edges WHERE source = ? ORDER BY target", [id]);
  const inc = rows("SELECT type, source FROM edges WHERE target = ? ORDER BY source", [id]);
  const link = (nid) => `<a data-id="${esc(nid)}">${esc(nid)}</a>`;
  const elist = (arr, dir) => arr.length ? arr.map((e) =>
    `<li><span class="etype">${esc(e.type)}</span> ${
      dir === "out" ? "→ " + link(e.target) : link(e.source) + " →"}</li>`).join("")
    : "<li class=\"placeholder\">(없음)</li>";
  doc.innerHTML =
    `<h2>${esc(n.title || n.id)}</h2>
     <div class="meta">
       <span class="badge" style="background:${colorFor(n.type)}">${esc(n.type || "?")}</span>
       <code>${esc(n.id)}</code>${n.namespace ? " · " + esc(n.namespace) : ""}
       · 신뢰도 ${n.confidence ?? "-"}${n.tags ? " · " + esc(n.tags) : ""}
     </div>
     ${n.summary ? `<div class="summary">${esc(n.summary)}</div>` : ""}
     <div class="body">${esc(n.body) || '<span class="placeholder">(본문 없음)</span>'}</div>
     <h3>나가는 엣지 (${out.length})</h3><ul class="edges">${elist(out, "out")}</ul>
     <h3>들어오는 엣지 / 백링크 (${inc.length})</h3><ul class="edges">${elist(inc, "in")}</ul>`;
  doc.querySelectorAll("a[data-id]").forEach((a) =>
    a.addEventListener("click", () => select(a.dataset.id)));
  doc.scrollTop = 0;
}

function select(id) {
  current = id;
  renderDoc(id);
  document.querySelectorAll("#list li").forEach((li) =>
    li.classList.toggle("sel", li.dataset.id === id));
  if (cy) { const el = cy.getElementById(id); if (el) cy.animate({ center: { eles: el }, zoom: 1.3 }, { duration: 200 }); }
}

/* ---- 그래프 모드(선택) ---- */
function buildGraph(nodes, edges) {
  const ids = new Set(nodes.map((n) => (n.id || "").trim()).filter(Boolean));
  const els = [];
  for (const n of nodes) { const id = (n.id || "").trim(); if (id) els.push({ data: { id, label: n.title || id, type: n.type || "" } }); }
  for (const e of edges) { const s = (e.source || "").trim(), t = (e.target || "").trim();
    if (ids.has(s) && ids.has(t)) els.push({ data: { source: s, target: t, label: e.type || "" } }); }
  cy = cytoscape({
    container: document.getElementById("cy"), elements: els,
    style: [
      { selector: "node", style: { "background-color": (n) => colorFor(n.data("type")),
          "label": "data(label)", "font-size": 10, "text-wrap": "wrap", "text-max-width": 90,
          "width": 20, "height": 20, "color": "#1c2230" } },
      { selector: "edge", style: { "width": 1.4, "line-color": "#c7cdd8",
          "target-arrow-color": "#c7cdd8", "target-arrow-shape": "triangle",
          "curve-style": "bezier", "label": "data(label)", "font-size": 8, "color": "#9aa3b2" } },
    ],
    layout: { name: "cose", animate: false, padding: 30 },
  });
  // 그래프에서 노드 클릭 → 그 원문을 문서 모드로 본다
  cy.on("tap", "node", (ev) => { setMode("doc"); select(ev.target.id()); });
}

function setMode(mode) {
  const graph = mode === "graph";
  document.getElementById("doc").classList.toggle("hidden", graph);
  document.getElementById("cy").classList.toggle("hidden", !graph);
  document.getElementById("modeDoc").classList.toggle("active", !graph);
  document.getElementById("modeGraph").classList.toggle("active", graph);
  if (graph && cy) { cy.resize(); cy.fit(undefined, 40); }
}

function runSearch(q) {
  if (!q.trim()) { renderList(null); return; }
  const like = "%" + q.trim().toLowerCase() + "%";
  const hits = rows(`SELECT id FROM nodes WHERE lower(title) LIKE ? OR lower(summary) LIKE ?
                       OR lower(tags) LIKE ? OR lower(body) LIKE ?`, [like, like, like, like]);
  renderList(new Set(hits.map((h) => h.id)));
}

async function main() {
  try {
    const SQL = await initSqlJs({ locateFile: (f) => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${f}` });
    const [nodes, edges] = await Promise.all([fetchCSV("nodes.csv"), fetchCSV("edges.csv")]);
    db = buildDb(SQL, nodes, edges);
    allNodes = rows("SELECT id, title, type FROM nodes ORDER BY type, title");
    const nc = rows("SELECT COUNT(*) c FROM nodes")[0].c, ec = rows("SELECT COUNT(*) c FROM edges")[0].c;
    document.getElementById("stats").textContent = `노드 ${nc} · 엣지 ${ec}`;

    renderList(null);
    const first = (rows("SELECT id FROM nodes WHERE type='pillar' ORDER BY id LIMIT 1")[0]
                   || allNodes[0] || {}).id;
    if (first) select(first); else document.getElementById("doc").innerHTML =
      '<p class="placeholder">노드가 없습니다.</p>';

    document.getElementById("modeDoc").addEventListener("click", () => setMode("doc"));
    document.getElementById("modeGraph").addEventListener("click", () => {
      if (!cy) buildGraph(nodes, edges);
      setMode("graph");
    });
    let timer;
    document.getElementById("q").addEventListener("input", (ev) => {
      clearTimeout(timer); timer = setTimeout(() => runSearch(ev.target.value), 150);
    });
  } catch (err) {
    document.getElementById("stats").textContent = "오류: " + err.message;
    console.error(err);
  }
}
main();
