/* Excel Brain 지식 뷰어 — 전부 클라이언트 사이드.
   문서·그래프 두 패널: 상하/좌우 분할, 각 패널 접기·드래그 크기조절,
   그래프에서 현재 노드 하이라이트, 패널 상태 localStorage 기억.
   브라우저가 CSV를 받아 sql.js(SQLite WASM)로 조회한다. */
"use strict";

const DATA_BASES = ["./data/", "../data/"];
const LS_KEY = "eb-view-state-v1";
const TYPE_COLORS = {
  pillar: "#7c3aed", concept: "#2563eb", fact: "#059669",
  decision: "#d97706", question: "#dc2626", playbook: "#0891b2",
  source: "#6b7280", note: "#94a3b8",
};
const colorFor = (t) => TYPE_COLORS[t] || "#64748b";
const esc = (s) => (s == null ? "" : String(s).replace(/[&<>]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])));
const $ = (id) => document.getElementById(id);

let db = null, cy = null, current = null, allNodes = [], rawNodes = [], rawEdges = [];
let ratio = 0.55;   // 문서 패널 비중(둘 다 펼쳤을 때)

/* ---- 로드/DB ---- */
async function fetchCSV(name) {
  for (const base of DATA_BASES) {
    try { const r = await fetch(base + name); if (r.ok)
      return Papa.parse(await r.text(), { header: true, skipEmptyLines: true }).data;
    } catch (e) { /* 다음 경로 */ }
  }
  throw new Error(`${name} 로드 실패 — data/ (또는 ../data/)에 CSV가 있어야 합니다`);
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

/* ---- 상태 기억 ---- */
function saveState() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({
      docCollapsed: $("docPanel").classList.contains("collapsed"),
      graphCollapsed: $("graphPanel").classList.contains("collapsed"),
      horizontal: $("center").classList.contains("horizontal"),
      ratio, current,
    }));
  } catch (e) { /* 사파리 프라이빗 등 무시 */ }
}
function loadState() { try { return JSON.parse(localStorage.getItem(LS_KEY)) || {}; } catch (e) { return {}; } }

/* ---- 목록 + 원문 ---- */
function renderList(filterIds) {
  const ul = $("list");
  const items = allNodes.filter((n) => !filterIds || filterIds.has(n.id));
  if (!items.length) { ul.innerHTML = '<li class="empty">결과 없음</li>'; return; }
  ul.innerHTML = items.map((n) =>
    `<li data-id="${esc(n.id)}" class="${n.id === current ? "sel" : ""}">
       ${esc(n.title || n.id)}<br><span class="t">${esc(n.type || "")}</span></li>`).join("");
  ul.querySelectorAll("li[data-id]").forEach((li) =>
    li.addEventListener("click", () => select(li.dataset.id)));
}
function renderDoc(id) {
  const n = rows("SELECT * FROM nodes WHERE id = ?", [id])[0];
  const doc = $("doc");
  if (!n) { doc.innerHTML = '<p class="placeholder">노드를 선택하세요.</p>'; return; }
  const out = rows("SELECT type, target FROM edges WHERE source = ? ORDER BY target", [id]);
  const inc = rows("SELECT type, source FROM edges WHERE target = ? ORDER BY source", [id]);
  const link = (nid) => `<a data-id="${esc(nid)}">${esc(nid)}</a>`;
  const elist = (arr, dir) => arr.length ? arr.map((e) =>
    `<li><span class="etype">${esc(e.type)}</span> ${
      dir === "out" ? "→ " + link(e.target) : link(e.source) + " →"}</li>`).join("")
    : '<li class="placeholder">(없음)</li>';
  doc.innerHTML =
    `<h2>${esc(n.title || n.id)}</h2>
     <div class="meta"><span class="badge" style="background:${colorFor(n.type)}">${esc(n.type || "?")}</span>
       <code>${esc(n.id)}</code>${n.namespace ? " · " + esc(n.namespace) : ""}
       · 신뢰도 ${n.confidence ?? "-"}${n.tags ? " · " + esc(n.tags) : ""}</div>
     ${n.summary ? `<div class="summary">${esc(n.summary)}</div>` : ""}
     <div class="body">${esc(n.body) || '<span class="placeholder">(본문 없음)</span>'}</div>
     <h3>나가는 엣지 (${out.length})</h3><ul class="edges">${elist(out, "out")}</ul>
     <h3>들어오는 엣지 / 백링크 (${inc.length})</h3><ul class="edges">${elist(inc, "in")}</ul>`;
  doc.querySelectorAll("a[data-id]").forEach((a) =>
    a.addEventListener("click", () => select(a.dataset.id)));
  doc.scrollTop = 0;
}
function markCurrent() {
  if (!cy) return;
  cy.nodes().removeClass("current");
  const el = cy.getElementById(current);
  if (el) {
    el.addClass("current");
    if (!$("graphPanel").classList.contains("collapsed"))
      cy.animate({ center: { eles: el }, zoom: 1.3 }, { duration: 200 });
  }
}
function select(id) {
  current = id;
  renderDoc(id);
  document.querySelectorAll("#list li").forEach((li) =>
    li.classList.toggle("sel", li.dataset.id === id));
  markCurrent();
  saveState();
}

/* ---- 그래프(lazy) ---- */
function buildGraph() {
  const ids = new Set(rawNodes.map((n) => (n.id || "").trim()).filter(Boolean));
  const els = [];
  for (const n of rawNodes) { const id = (n.id || "").trim(); if (id) els.push({ data: { id, label: n.title || id, type: n.type || "" } }); }
  for (const e of rawEdges) { const s = (e.source || "").trim(), t = (e.target || "").trim();
    if (ids.has(s) && ids.has(t)) els.push({ data: { source: s, target: t, label: e.type || "" } }); }
  cy = cytoscape({
    container: $("cy"), elements: els,
    style: [
      { selector: "node", style: { "background-color": (n) => colorFor(n.data("type")),
          "label": "data(label)", "font-size": 10, "text-wrap": "wrap", "text-max-width": 90,
          "width": 20, "height": 20, "color": "#1c2230" } },
      { selector: "node.current", style: { "width": 30, "height": 30,
          "border-width": 4, "border-color": "#f59e0b", "font-weight": "bold", "z-index": 99 } },
      { selector: "edge", style: { "width": 1.4, "line-color": "#c7cdd8",
          "target-arrow-color": "#c7cdd8", "target-arrow-shape": "triangle",
          "curve-style": "bezier", "label": "data(label)", "font-size": 8, "color": "#9aa3b2" } },
    ],
    layout: { name: "cose", animate: false, padding: 30 },
  });
  cy.on("tap", "node", (ev) => select(ev.target.id()));
  markCurrent();
}

/* ---- 패널 접기/분할/크기조절 ---- */
function bothExpanded() { return !$("docPanel").classList.contains("collapsed") && !$("graphPanel").classList.contains("collapsed"); }
function setSplit(r) {
  ratio = Math.max(0.15, Math.min(0.85, r));
  if (bothExpanded()) { $("docPanel").style.flex = `${ratio} 1 0`; $("graphPanel").style.flex = `${1 - ratio} 1 0`; }
}
function applyFlex() {
  if (bothExpanded()) setSplit(ratio);
  else { $("docPanel").style.flex = ""; $("graphPanel").style.flex = ""; }
}
function fitGraph() { if (cy && !$("graphPanel").classList.contains("collapsed")) requestAnimationFrame(() => { cy.resize(); cy.fit(undefined, 40); }); }
function syncResizer() { $("resizer").classList.toggle("hidden", !bothExpanded()); }
function setArrows() {
  for (const p of ["docPanel", "graphPanel"])
    $(p).querySelector(".toggle").textContent = $(p).classList.contains("collapsed") ? "▸" : "▾";
}
function togglePanel(which) {
  const el = which === "doc" ? $("docPanel") : $("graphPanel");
  el.classList.toggle("collapsed");
  if (which === "graph" && !el.classList.contains("collapsed") && !cy) buildGraph();
  applyFlex(); setArrows(); syncResizer(); fitGraph(); saveState();
}
function toggleLayout() {
  const horiz = $("center").classList.toggle("horizontal");
  $("layout").textContent = horiz ? "⬌ 좌우" : "⬍ 상하";
  applyFlex(); fitGraph(); saveState();
}
function initResize() {
  const center = $("center");
  const move = (e) => {
    const rect = center.getBoundingClientRect();
    const r = center.classList.contains("horizontal")
      ? (e.clientX - rect.left) / rect.width
      : (e.clientY - rect.top) / rect.height;
    setSplit(r);
    if (cy && !$("graphPanel").classList.contains("collapsed")) cy.resize();
  };
  const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); fitGraph(); saveState(); };
  $("resizer").addEventListener("mousedown", (e) => {
    if ($("resizer").classList.contains("hidden")) return;
    e.preventDefault(); document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
  });
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
    [rawNodes, rawEdges] = await Promise.all([fetchCSV("nodes.csv"), fetchCSV("edges.csv")]);
    db = buildDb(SQL, rawNodes, rawEdges);
    allNodes = rows("SELECT id, title, type FROM nodes ORDER BY type, title");
    const nc = rows("SELECT COUNT(*) c FROM nodes")[0].c, ec = rows("SELECT COUNT(*) c FROM edges")[0].c;
    $("stats").textContent = `노드 ${nc} · 엣지 ${ec}`;

    // 저장된 패널 상태 복원
    const st = loadState();
    if (st.horizontal) $("center").classList.add("horizontal");
    $("layout").textContent = $("center").classList.contains("horizontal") ? "⬌ 좌우" : "⬍ 상하";
    if (typeof st.ratio === "number") ratio = st.ratio;
    if (st.docCollapsed) $("docPanel").classList.add("collapsed");
    if (st.graphCollapsed === false) { $("graphPanel").classList.remove("collapsed"); buildGraph(); }

    renderList(null);
    const firstPillar = (rows("SELECT id FROM nodes WHERE type='pillar' ORDER BY id LIMIT 1")[0] || {}).id;
    const want = (st.current && allNodes.some((n) => n.id === st.current))
      ? st.current : (firstPillar || (allNodes[0] || {}).id);
    if (want) select(want); else $("doc").innerHTML = '<p class="placeholder">노드가 없습니다.</p>';

    setArrows(); syncResizer(); applyFlex(); fitGraph();

    $("docPanel").querySelector(".phead").addEventListener("click", () => togglePanel("doc"));
    $("graphPanel").querySelector(".phead").addEventListener("click", () => togglePanel("graph"));
    $("layout").addEventListener("click", toggleLayout);
    initResize();
    let timer;
    $("q").addEventListener("input", (ev) => { clearTimeout(timer); timer = setTimeout(() => runSearch(ev.target.value), 150); });
    window.addEventListener("resize", fitGraph);
  } catch (err) {
    $("stats").textContent = "오류: " + err.message;
    console.error(err);
  }
}
main();
