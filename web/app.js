/* Excel Brain 지식 뷰어 — 전부 클라이언트 사이드(sql.js).
   검색창: 그냥 단어=텍스트검색, neighbors/path/node/degree/suggest/health/orphans 명령,
   원시 SELECT SQL 자동 감지. 채팅 탭: 자연어→그래프 탐색(WebLLM, 선택).
   패널(문서/그래프/채팅): 상하·좌우 분할, 접기(헤더 클릭·Alt+1/2/3), 드래그 크기조절, 상태 기억. */
"use strict";

const DATA_BASES = ["./data/", "../data/"];
const LS_KEY = "eb-view-state-v2";
const PANELS = ["docPanel", "graphPanel", "chatPanel"];
const CMDS = ["search", "neighbors", "path", "node", "degree", "suggest", "health", "orphans", "components", "layout", "show", "hide", "toggle"];
const TYPE_COLORS = { pillar: "#7c3aed", concept: "#2563eb", fact: "#059669",
  decision: "#d97706", question: "#dc2626", playbook: "#0891b2", source: "#6b7280", note: "#94a3b8" };
const colorFor = (t) => TYPE_COLORS[t] || "#64748b";
const esc = (s) => (s == null ? "" : String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])));
const $ = (id) => document.getElementById(id);

let db = null, cy = null, current = null, allNodes = [], rawNodes = [], rawEdges = [];
let grows = { docPanel: 1, graphPanel: 1.5, chatPanel: 1 }, lastIds = [];
let llm = null, llmTried = false, llmModel = null, chatHistory = [];   // 대화 메모리(후속 질문용)
const LS_MODEL = "eb-chat-model";

const HELP = [
  ["'분산락' 관련 노트 다 찾아", "분산락", "제목·요약·태그·본문 부분일치(랭크)"],
  ["바로 연결된 것", "neighbors redis --depth 1", "직접 이웃(1홉)"],
  ["주변 지형 넓게", "neighbors redis --depth 2 --direction both", "2홉 이내(거리별) — 맥락"],
  ["A와 B가 어떻게 엮이지?", "path redis 동시성-제어", "둘을 잇는 최단 경로"],
  ["무엇이 이걸 참조/지지하나", "node redis", "상세 + 백링크(들어오는 엣지)"],
  ["핵심 허브", "degree --top 5", "연결 많은 중심 노드"],
  ["이어질 만한데 안 이어진 것", "suggest redis", "공통 이웃·태그 추천 후보"],
  ["근거 약한(신뢰도 낮은) 노드", "health --confidence 0.6", "저신뢰·미상 노드"],
  ["재검토할 결정들(타입+속성)", "SELECT id,title FROM nodes WHERE type='decision' AND confidence<0.7", "신뢰도 낮은 decision"],
  ["서로 모순되는 지식 쌍", "SELECT source,target FROM edges WHERE type='contradicts'", "contradicts 노드 쌍"],
  ["화면을 상하/좌우로", "layout 상하", "패널 분할 방향(상하·좌우)"],
  ["문서 탭 숨기기/열기", "hide 문서  ·  show 그래프", "패널 접기/펼치기(문서·그래프·채팅)"],
];

/* ---- 로드/DB ---- */
async function fetchCSV(name) {
  for (const base of DATA_BASES) {
    try { const r = await fetch(base + name); if (r.ok) return Papa.parse(await r.text(), { header: true, skipEmptyLines: true }).data; }
    catch (e) {}
  }
  throw new Error(`${name} 로드 실패 — data/ (또는 ../data/)에 CSV가 있어야 합니다`);
}
function rows(sql, params = []) { const out = [], st = db.prepare(sql); st.bind(params); while (st.step()) out.push(st.getAsObject()); st.free(); return out; }
function buildDb(SQL, nodes, edges) {
  const d = new SQL.Database();
  d.run(`CREATE TABLE nodes(id TEXT PRIMARY KEY, title, type, namespace, visibility, summary, confidence REAL, tags, body);
         CREATE TABLE edges(source, type, target, weight REAL, note);`);
  const ni = d.prepare("INSERT OR REPLACE INTO nodes VALUES (?,?,?,?,?,?,?,?,?)");
  for (const n of nodes) if ((n.id || "").trim()) ni.run([n.id.trim(), n.title, n.type, n.namespace, n.visibility, n.summary, n.confidence ? +n.confidence : null, n.tags, n.body]);
  ni.free();
  const ei = d.prepare("INSERT INTO edges VALUES (?,?,?,?,?)");
  for (const e of edges) if ((e.source || "").trim() && (e.target || "").trim()) ei.run([e.source.trim(), e.type, e.target.trim(), e.weight ? +e.weight : null, e.note]);
  ei.free();
  return d;
}

/* ---- 상태 기억 ---- */
function saveState() {
  try { localStorage.setItem(LS_KEY, JSON.stringify({
    collapsed: Object.fromEntries(PANELS.map((p) => [p, $(p).classList.contains("collapsed")])),
    horizontal: $("center").classList.contains("horizontal"), grows, current })); } catch (e) {}
}
function loadState() { try { return JSON.parse(localStorage.getItem(LS_KEY)) || {}; } catch (e) { return {}; } }

/* ---- 목록 + 원문 ---- */
function note(m) { $("stats").textContent = m; }
function liHtml(n) { return `<li data-id="${esc(n.id)}" class="${n.id === current ? "sel" : ""}">${esc(n.title || n.id)}<br><span class="t">${esc(n.type || "")}</span></li>`; }
function bindList() { $("list").querySelectorAll("li[data-id]").forEach((li) => li.addEventListener("click", () => select(li.dataset.id, true))); }
function renderList(filterIds) {
  const items = allNodes.filter((n) => !filterIds || filterIds.has(n.id));
  lastIds = items.map((n) => n.id);
  $("list").innerHTML = items.length ? items.map(liHtml).join("") : '<li class="empty">결과 없음</li>'; bindList();
}
function renderOrdered(ids) {
  lastIds = ids.slice();
  const byId = Object.fromEntries(allNodes.map((n) => [n.id, n]));
  $("list").innerHTML = ids.length ? ids.map((id) => liHtml(byId[id] || { id })).join("") : '<li class="empty">결과 없음</li>'; bindList();
}
function renderDoc(id) {
  const n = rows("SELECT * FROM nodes WHERE id=?", [id])[0], doc = $("doc");
  if (!n) { doc.innerHTML = '<p class="placeholder">노드를 선택하세요.</p>'; return; }
  const out = rows("SELECT type,target FROM edges WHERE source=? ORDER BY target", [id]);
  const inc = rows("SELECT type,source FROM edges WHERE target=? ORDER BY source", [id]);
  const link = (x) => `<a data-id="${esc(x)}">${esc(x)}</a>`;
  const el = (a, d) => a.length ? a.map((e) => `<li><span class="etype">${esc(e.type)}</span> ${d === "out" ? "→ " + link(e.target) : link(e.source) + " →"}</li>`).join("") : '<li class="placeholder">(없음)</li>';
  doc.innerHTML = `<div class="docwrap">
     <div class="doc-main">
       <h2>${esc(n.title || n.id)}</h2>
       <div class="meta"><span class="badge" style="background:${colorFor(n.type)}">${esc(n.type || "?")}</span>
         <code>${esc(n.id)}</code>${n.namespace ? " · " + esc(n.namespace) : ""} · 신뢰도 ${n.confidence ?? "-"}${n.tags ? " · " + esc(n.tags) : ""}</div>
       ${n.summary ? `<div class="summary">${esc(n.summary)}</div>` : ""}
       <div class="body">${esc(n.body) || '<span class="placeholder">(본문 없음)</span>'}</div>
     </div>
     <aside class="doc-edges">
       <h3>나가는 엣지 (${out.length})</h3><ul class="edges">${el(out, "out")}</ul>
       <h3>들어오는 엣지 / 백링크 (${inc.length})</h3><ul class="edges">${el(inc, "in")}</ul>
     </aside>
   </div>`;
  doc.querySelectorAll("a[data-id]").forEach((a) => a.addEventListener("click", () => select(a.dataset.id, true)));
  doc.scrollTop = 0;
}
function markCurrent() {                            // 하이라이트(클래스)만 — 카메라 이동 없음
  if (!cy) return;
  cy.nodes().removeClass("current");
  const el = cy.getElementById(current);
  if (el && el.length) el.addClass("current");
}
function select(id, focus) {                        // focus=true(사용자 클릭)일 때만 그래프 카메라 이동
  current = id; renderDoc(id);
  document.querySelectorAll("#list li").forEach((li) => li.classList.toggle("sel", li.dataset.id === id));
  markCurrent();
  if (focus && cy && isOpen("graphPanel")) { const el = cy.getElementById(id); if (el && el.length) cy.animate({ center: { eles: el }, zoom: 1.3 }, { duration: 200 }); }
  saveState();
}
function highlightInGraph(ids) {
  if (!cy) return; const set = new Set(ids);
  cy.batch(() => { cy.elements().removeClass("dim qhit"); if (!ids.length) return;
    cy.nodes().forEach((n) => set.has(n.id()) ? n.addClass("qhit") : n.addClass("dim"));
    cy.edges().forEach((e) => { if (!(set.has(e.source().id()) && set.has(e.target().id()))) e.addClass("dim"); }); });
}

/* ---- 검색 디스패처 ---- */
function classify(s) { if (/^\s*select\b/i.test(s)) return "sql"; return CMDS.includes(s.trim().split(/\s+/)[0]) ? "cmd" : "text"; }
function flag(t, n, d) { const i = t.indexOf(n); return i >= 0 && t[i + 1] ? t[i + 1] : d; }
function adjSQL(dir) { const o = "SELECT source a,target b FROM edges", i = "SELECT target a,source b FROM edges"; return dir === "out" ? o : dir === "in" ? i : `${o} UNION ${i}`; }
function textIds(q) {                               // 텍스트 검색 id (렌더 없음)
  if (!q || !q.trim()) return [];
  const like = "%" + q.trim().toLowerCase() + "%";
  return rows(`SELECT id FROM nodes WHERE lower(id) LIKE ? OR lower(title) LIKE ? OR lower(summary) LIKE ? OR lower(tags) LIKE ? OR lower(body) LIKE ?`, [like, like, like, like, like]).map((r) => r.id);
}
function keywordIds(q) {                            // 질문 단어 OR 검색 id (렌더 없음)
  const toks = [];
  for (const r of (q || "").split(/[^0-9A-Za-z가-힣]+/)) for (const p of (r.match(/[A-Za-z0-9]+|[가-힣]+/g) || [])) if (p.length >= 2 && !toks.includes(p)) toks.push(p);
  if (!toks.length) return [];
  toks.splice(8);
  const conds = [], params = [];
  for (const w of toks) { const lk = "%" + w.toLowerCase() + "%"; ["id", "title", "summary", "tags", "body"].forEach((c) => { conds.push(`lower(${c}) LIKE ?`); params.push(lk); }); }
  return rows(`SELECT id FROM nodes WHERE ${conds.join(" OR ")}`, params).map((r) => r.id);
}
function retrieve(input) {                          // 채팅용 조용한 조회(UI 안 건드림)
  const s = (input || "").trim(); if (!s) return [];
  if (/^\s*select\b/i.test(s)) { try { const r = rows(s), set = new Set(allNodes.map((n) => n.id)), out = []; for (const row of r) for (const v of Object.values(row)) if (typeof v === "string" && set.has(v) && !out.includes(v)) out.push(v); return out; } catch (e) { return []; } }
  const t = s.split(/\s+/), cmd = t[0], arg = t[1];
  try {
    if (cmd === "search") return textIds(t.slice(1).join(" "));
    if (cmd === "node") return allNodes.some((n) => n.id === arg) ? [arg] : [];
    if (cmd === "neighbors") { const depth = +flag(t, "--depth", 1), dir = flag(t, "--direction", "both"); return rows(`WITH RECURSIVE adj(a,b) AS (${adjSQL(dir)}), walk(id,dist) AS (SELECT ?,0 UNION SELECT adj.b,walk.dist+1 FROM adj JOIN walk ON adj.a=walk.id WHERE walk.dist<?) SELECT id FROM walk WHERE id<>? GROUP BY id`, [arg, depth, arg]).map((x) => x.id); }
    if (cmd === "path") { const dst = t[2], dir = flag(t, "--direction", "both"); const row = rows(`WITH RECURSIVE adj(a,b) AS (${adjSQL(dir)}), walk(id,path,depth) AS (SELECT ?, '>'||?||'>',0 UNION ALL SELECT adj.b, walk.path||adj.b||'>', walk.depth+1 FROM adj JOIN walk ON adj.a=walk.id WHERE walk.depth<64 AND instr(walk.path,'>'||adj.b||'>')=0) SELECT path FROM walk WHERE id=? ORDER BY depth LIMIT 1`, [arg, arg, dst])[0]; return row ? row.path.split(">").filter(Boolean) : []; }
    if (cmd === "degree") return rows(`SELECT id,(SELECT COUNT(*) FROM edges WHERE source=n.id OR target=n.id) deg FROM nodes n ORDER BY deg DESC,id LIMIT ?`, [+flag(t, "--top", 10)]).map((x) => x.id);
    if (cmd === "orphans") return rows(`SELECT id FROM nodes WHERE id NOT IN (SELECT source FROM edges) AND id NOT IN (SELECT target FROM edges)`).map((x) => x.id);
  } catch (e) { return []; }
  return textIds(s);                               // 일반어 → 텍스트 검색
}
function runText(q) {
  if (!q.trim()) { renderList(null); highlightInGraph([]); note(`노드 ${allNodes.length}`); return; }
  const ids = textIds(q);
  renderList(new Set(ids)); highlightInGraph(ids); note(`텍스트 '${q.trim()}': ${ids.length}건`);
}
function runSQL(s) {
  try {
    const r = rows(s);
    if (!r.length) { renderList(new Set()); highlightInGraph([]); note("SQL: 0행"); return; }
    const idset = new Set(allNodes.map((n) => n.id)), seen = [], out = new Set();
    for (const row of r) for (const v of Object.values(row)) if (typeof v === "string" && idset.has(v) && !out.has(v)) { out.add(v); seen.push(v); }
    if (!seen.length) { note(`SQL: ${r.length}행 (노드 id 없음)`); return; }
    renderOrdered(seen); highlightInGraph(seen); note(`SQL: ${r.length}행 · 노드 ${seen.length}`);
  } catch (e) { note("SQL 오류: " + e.message); }
}
function runCmd(s) {
  const t = s.trim().split(/\s+/), cmd = t[0], arg = t[1];
  try {
    if (cmd === "search") return runText(t.slice(1).join(" "));
    if (cmd === "node") { if (allNodes.some((n) => n.id === arg)) { select(arg); renderOrdered([arg]); highlightInGraph([arg]); note("노드: " + arg); } else note("없는 노드: " + arg); return; }
    if (cmd === "neighbors") {
      const depth = +flag(t, "--depth", 1), dir = flag(t, "--direction", "both");
      const ids = rows(`WITH RECURSIVE adj(a,b) AS (${adjSQL(dir)}), walk(id,dist) AS (
        SELECT ?,0 UNION SELECT adj.b,walk.dist+1 FROM adj JOIN walk ON adj.a=walk.id WHERE walk.dist<?)
        SELECT id,MIN(dist) dist FROM walk WHERE id<>? GROUP BY id ORDER BY dist,id`, [arg, depth, arg]).map((x) => x.id);
      renderOrdered(ids); highlightInGraph([arg, ...ids]); note(`${arg} 이웃 ${depth}홉(${dir}): ${ids.length}개`); return;
    }
    if (cmd === "path") {
      const dst = t[2], dir = flag(t, "--direction", "both");
      const row = rows(`WITH RECURSIVE adj(a,b) AS (${adjSQL(dir)}), walk(id,path,depth) AS (
        SELECT ?, '>'||?||'>',0 UNION ALL SELECT adj.b, walk.path||adj.b||'>', walk.depth+1
          FROM adj JOIN walk ON adj.a=walk.id WHERE walk.depth<64 AND instr(walk.path,'>'||adj.b||'>')=0)
        SELECT path,depth FROM walk WHERE id=? ORDER BY depth LIMIT 1`, [arg, arg, dst])[0];
      if (!row) { renderOrdered([]); note(`경로 없음: ${arg} → ${dst}`); return; }
      const ids = row.path.split(">").filter(Boolean); renderOrdered(ids); highlightInGraph(ids); note(`경로(홉 ${row.depth}): ${ids.join(" → ")}`); return;
    }
    if (cmd === "degree") {
      const top = +flag(t, "--top", 10);
      const ids = rows(`SELECT id,(SELECT COUNT(*) FROM edges WHERE source=n.id OR target=n.id) deg FROM nodes n ORDER BY deg DESC,id LIMIT ?`, [top]).map((x) => x.id);
      renderOrdered(ids); highlightInGraph(ids); note(`허브 상위 ${ids.length}`); return;
    }
    if (cmd === "health") {
      const thr = +flag(t, "--confidence", 0.6);
      const ids = rows(`SELECT id FROM nodes WHERE confidence IS NULL OR confidence<? ORDER BY (confidence IS NOT NULL), confidence`, [thr]).map((x) => x.id);
      renderOrdered(ids); highlightInGraph(ids); note(`저신뢰/미상 (<${thr}): ${ids.length}`); return;
    }
    if (cmd === "orphans") {
      const ids = rows(`SELECT id FROM nodes WHERE id NOT IN (SELECT source FROM edges) AND id NOT IN (SELECT target FROM edges) ORDER BY id`).map((x) => x.id);
      renderOrdered(ids); highlightInGraph(ids); note(`고아 ${ids.length}개`); return;
    }
    if (cmd === "suggest") return runSuggest(arg);
    if (cmd === "components") { const c = comps(); renderOrdered(c[0] || []); highlightInGraph(c[0] || []); note(`연결 요소 ${c.length}개 (최대 ${c[0]?.length || 0})`); return; }
    if (cmd === "layout") { const h = /좌우|가로|h|horizontal/i.test(arg || ""); setLayout(h); note("레이아웃: " + (h ? "좌우" : "상하")); return; }
    if (cmd === "show" || cmd === "hide" || cmd === "toggle") {
      const id = resolvePanel(arg); if (!id) { note("패널 이름? 문서/그래프/채팅"); return; }
      if (cmd === "toggle") togglePanel(id); else setPanelOpen(id, cmd === "show");
      note(`${arg} ${cmd === "hide" ? "숨김" : cmd === "show" ? "표시" : "토글"}`); return;
    }
  } catch (e) { note("명령 오류: " + e.message); }
}
function comps() {
  const ids = allNodes.map((n) => n.id), p = {}; ids.forEach((i) => p[i] = i);
  const f = (x) => { while (p[x] !== x) { p[x] = p[p[x]]; x = p[x]; } return x; };
  rawEdges.forEach((e) => { const s = (e.source || "").trim(), t = (e.target || "").trim(); if (p[s] && p[t]) { const a = f(s), b = f(t); if (a !== b) p[b] = a; } });
  const g = {}; ids.forEach((i) => { (g[f(i)] = g[f(i)] || []).push(i); });
  return Object.values(g).sort((a, b) => b.length - a.length);
}
function runSuggest(id) {
  const adj = {}, tg = {}; allNodes.forEach((n) => adj[n.id] = new Set());
  rawNodes.forEach((n) => { const i = (n.id || "").trim(); if (i) tg[i] = new Set(String(n.tags || "").split(";").map((x) => x.trim()).filter(Boolean)); });
  rawEdges.forEach((e) => { const s = (e.source || "").trim(), t = (e.target || "").trim(); if (adj[s] && adj[t]) { adj[s].add(t); adj[t].add(s); } });
  if (!adj[id]) { note("없는 노드: " + id); return; }
  const my = adj[id], myt = tg[id] || new Set(), out = [];
  for (const n of allNodes) { if (n.id === id || my.has(n.id)) continue;
    let common = 0; my.forEach((x) => { if (adj[n.id].has(x)) common++; });
    const ct = tg[n.id] || new Set(), uni = new Set([...myt, ...ct]); let it = 0; myt.forEach((x) => { if (ct.has(x)) it++; });
    const sc = common + (uni.size ? it / uni.size : 0); if (sc > 0) out.push({ id: n.id, sc }); }
  out.sort((a, b) => b.sc - a.sc); const ids = out.map((x) => x.id);
  renderOrdered(ids); highlightInGraph([id, ...ids]); note(`${id} 연결 후보 ${ids.length}`);
}
function searchKeywords(q) {                        // 검색창용 키워드 검색(렌더)
  const ids = keywordIds(q);
  renderList(new Set(ids)); highlightInGraph(ids); note(`키워드 검색: ${ids.length}건`);
}
function runQuery(input) {
  const s = (input || "").trim();
  if (!s) { runText(""); return; }
  const k = classify(s); if (k === "sql") return runSQL(s); if (k === "cmd") return runCmd(s); return runText(s);
}

/* ---- 그래프(lazy) ---- */
function buildGraph() {
  const ids = new Set(rawNodes.map((n) => (n.id || "").trim()).filter(Boolean)), els = [];
  for (const n of rawNodes) { const id = (n.id || "").trim(); if (id) els.push({ data: { id, label: n.title || id, type: n.type || "" } }); }
  for (const e of rawEdges) { const s = (e.source || "").trim(), t = (e.target || "").trim(); if (ids.has(s) && ids.has(t)) els.push({ data: { source: s, target: t, label: e.type || "" } }); }
  cy = cytoscape({ container: $("cy"), elements: els, style: [
    { selector: "node", style: { "background-color": (n) => colorFor(n.data("type")), "label": "data(label)", "font-size": 10, "text-wrap": "wrap", "text-max-width": 90, "width": 20, "height": 20, "color": "#1c2230" } },
    { selector: "node.current", style: { "width": 30, "height": 30, "border-width": 4, "border-color": "#f59e0b", "z-index": 99 } },
    { selector: "node.qhit", style: { "border-width": 3, "border-color": "#2563eb" } },
    { selector: ".dim", style: { "opacity": 0.12 } },
    { selector: "edge", style: { "width": 1.4, "line-color": "#c7cdd8", "target-arrow-color": "#c7cdd8", "target-arrow-shape": "triangle", "curve-style": "bezier", "label": "data(label)", "font-size": 8, "color": "#9aa3b2" } },
  ], layout: { name: "grid", rows: 1 } });
  cy.on("tap", "node", (ev) => select(ev.target.id(), true));
  const l = cy.layout({ name: "cose", animate: false, padding: 24, idealEdgeLength: 110, nodeRepulsion: 12000, nodeOverlap: 24, gravity: 0.25, componentSpacing: 120 });
  l.one("layoutstop", () => requestAnimationFrame(() => { stretchToAspect(); fitGraph(); markCurrent(); }));   // 초기 1회: 패널 크기 적용 후 가로 채우기
  l.run();
}
function stretchToAspect() {                       // 초기화면만: 그래프를 패널 가로비율에 맞게 늘림(왜곡 상한)
  if (!cy) return;
  const bb = cy.elements().boundingBox(), c = cy.container().getBoundingClientRect();
  if (!bb.w || !bb.h || !c.width || !c.height) return;
  const gA = bb.w / bb.h, pA = c.width / c.height;
  if (pA <= gA * 1.1) return;                      // 패널이 충분히 더 넓을 때만
  const factor = Math.min((pA / gA) * 0.85, 4.5), cx = (bb.x1 + bb.x2) / 2;   // 가로로 더 펼침(상한 4.5x)
  cy.nodes().forEach((n) => { const p = n.position(); n.position({ x: cx + (p.x - cx) * factor, y: p.y }); });
}

/* ---- 패널: 접기/분할/크기조절 ---- */
function isOpen(id) { return !$(id).classList.contains("collapsed"); }
function applyFlex() { for (const id of PANELS) $(id).style.flex = isOpen(id) ? `${grows[id]} 1 0` : "0 0 auto"; }
function fitGraph() { if (cy && isOpen("graphPanel")) requestAnimationFrame(() => { cy.resize(); cy.fit(undefined, 24); }); }
function setArrows() { for (const id of PANELS) $(id).querySelector(".toggle").textContent = isOpen(id) ? "▾" : "▸"; }
function syncResizers() { document.querySelectorAll(".resizer").forEach((rz) => { const [a, b] = rz.dataset.between.split(","); rz.classList.toggle("hidden", !(isOpen(a) && isOpen(b))); }); }
function refreshPanels() { applyFlex(); setArrows(); syncResizers(); fitGraph(); saveState(); }
function togglePanel(id) {
  $(id).classList.toggle("collapsed");
  if (id === "graphPanel" && isOpen(id) && !cy) buildGraph();
  if (id === "chatPanel" && isOpen(id)) setTimeout(() => $("chatin").focus(), 0);
  refreshPanels();
}
function toggleLayout() { const h = $("center").classList.toggle("horizontal"); $("layout").textContent = h ? "⬌ 좌우" : "⬍ 상하"; applyFlex(); fitGraph(); saveState(); }
function setLayout(horiz) { if (horiz !== $("center").classList.contains("horizontal")) toggleLayout(); }
function setPanelOpen(id, open) { if (open !== isOpen(id)) togglePanel(id); }
function resolvePanel(w) { const s = (w || "").toLowerCase(); const m = { "문서": "docPanel", doc: "docPanel", "그래프": "graphPanel", graph: "graphPanel", "채팅": "chatPanel", chat: "chatPanel" }; return m[w] || m[s]; }
function initResizers() {
  document.querySelectorAll(".resizer").forEach((rz) => {
    const [aId, bId] = rz.dataset.between.split(",");
    rz.addEventListener("mousedown", (e) => {
      if (rz.classList.contains("hidden")) return; e.preventDefault();
      const a = $(aId), b = $(bId), horiz = $("center").classList.contains("horizontal");
      const move = (ev) => {
        const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
        const start = horiz ? ra.left : ra.top, end = horiz ? rb.right : rb.bottom;
        let frac = ((horiz ? ev.clientX : ev.clientY) - start) / (end - start);
        frac = Math.max(0.12, Math.min(0.88, frac));
        const sum = grows[aId] + grows[bId]; grows[aId] = sum * frac; grows[bId] = sum * (1 - frac);
        applyFlex(); if (cy) cy.resize();
      };
      const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); fitGraph(); saveState(); };
      document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
    });
  });
}

/* ---- 사용법 모달 ---- */
function buildHelp() {
  $("helpTable").innerHTML = "<tr><th>#</th><th>알고 싶은 것</th><th>표현식</th><th>나오는 것</th></tr>" +
    HELP.map(([want, expr, res], i) => `<tr><td>${i + 1}</td><td>${esc(want)}</td><td><code data-expr="${esc(expr)}">${esc(expr)}</code></td><td>${esc(res)}</td></tr>`).join("");
  $("helpTable").querySelectorAll("code[data-expr]").forEach((c) => c.addEventListener("click", () => {
    $("q").value = c.dataset.expr; $("helpModal").classList.add("hidden"); $("q").focus();
  }));
}
function toggleHelp(show) { $("helpModal").classList.toggle("hidden", show === false ? true : show === true ? false : undefined); }

/* ---- 채팅(WebLLM, 선택) ---- */
function bubble(role, html) { const d = document.createElement("div"); d.className = "bubble " + role; d.innerHTML = html; $("chatlog").appendChild(d); $("chatlog").scrollTop = $("chatlog").scrollHeight; return d; }
async function ensureLLM() {
  const model = $("chatmodel").value, label = $("chatmodel").selectedOptions[0].textContent;
  if (llmModel === model && (llm || llmTried)) return llm;   // 같은 모델 재사용/재시도금지
  llmTried = true; llmModel = model; llm = null;
  const b = bubble("sys", `🤖 ${label} 로딩 중… (처음 한 번만)`);
  try {
    const webllm = await import("https://esm.run/@mlc-ai/web-llm");
    llm = await webllm.CreateMLCEngine(model,
      { initProgressCallback: (p) => { b.textContent = `🤖 ${label} 로딩 ${Math.round((p.progress || 0) * 100)}%`; } });
    b.textContent = `🤖 ${label} 준비 완료`;
  } catch (e) { b.textContent = "🤖 로드 실패(WebGPU/메모리 부족 가능). 더 작은 모델을 고르거나 검색창의 표현식을 쓰세요."; }
  return llm;
}
function uiIntent(q) {                            // 자연어 UI 제어 (LLM 없이 규칙으로)
  const s = q.replace(/\s/g, "");
  if (/(상하|세로|수직)(로|으로)?(해|바꿔|만들|배치)?/.test(s)) return () => { setLayout(false); return "화면을 상하 분할로 바꿨어요."; };
  if (/(좌우|가로|수평)(로|으로)?(해|바꿔|만들|배치)?/.test(s)) return () => { setLayout(true); return "화면을 좌우 분할로 바꿨어요."; };
  const p = /문서/.test(s) ? "docPanel" : /그래프/.test(s) ? "graphPanel" : /채팅/.test(s) ? "chatPanel" : null;
  const nm = { docPanel: "문서", graphPanel: "그래프", chatPanel: "채팅" }[p];
  if (p && /(숨겨|숨김|닫|접|최소화|감춰|hide|꺼|끄)/.test(s)) return () => { setPanelOpen(p, false); return nm + " 탭을 숨겼어요."; };
  if (p && /(보여|열|펼|표시|show|켜)/.test(s)) return () => { setPanelOpen(p, true); return nm + " 탭을 열었어요."; };
  return null;
}
function buildChatTeach() {                         // in-context 학습: 실제 그래프 어휘 + few-shot
  const types = [...new Set(allNodes.map((n) => n.type).filter(Boolean))];
  const etypes = [...new Set(rawEdges.map((e) => (e.type || "").trim()).filter(Boolean))];
  const tagOf = {}; rawNodes.forEach((n) => { const i = (n.id || "").trim(); if (i) tagOf[i] = (n.tags || "").trim(); });
  const nl = allNodes.slice(0, 300).map((n) => `${n.id} | ${n.title || ""} | ${n.type || ""}${tagOf[n.id] ? " | " + tagOf[n.id] : ""}`).join("\n");
  const fs = [], add = (u, a) => fs.push({ role: "user", content: u }, { role: "assistant", content: a });
  const pillar = allNodes.find((n) => n.type === "pillar") || allNodes[0];
  if (pillar) add(`${pillar.title || pillar.id} 와 연결된 노드`, `neighbors ${pillar.id} --depth 1 --direction both`);
  const e = rawEdges.find((x) => (x.source || "").trim() && (x.target || "").trim() && x.source !== x.target);
  if (e) add(`${e.source.trim()} 랑 ${e.target.trim()} 어떻게 이어져?`, `path ${e.source.trim()} ${e.target.trim()}`);
  const kwNode = allNodes.find((n) => /[A-Za-z]{2,}/.test(n.title || ""));
  if (kwNode) add(`${(kwNode.title.match(/[A-Za-z]{2,}/) || [""])[0]} 관련 노트 찾아줘`, `search ${(kwNode.title.match(/[A-Za-z]{2,}/) || [""])[0]}`);
  if (types.includes("decision")) add("신뢰도 낮은 결정들", "SELECT id,title FROM nodes WHERE type='decision' AND confidence<0.7");
  add("가장 중요한(연결 많은) 노드", "degree --top 5");
  add("고립된 노드 있어?", "orphans");
  const sys = `너는 지식그래프 질의 변환기다. 사용자 질문을 아래 한 줄 형식 중 하나로만 출력한다. 설명·문장·따옴표·코드블록 금지, 정확히 한 줄.
형식:
- search <키워드>            : 단어로 찾기(키워드는 사람이 쓰는 한국어/영어 단어, id 아님)
- neighbors <id> --depth <N> --direction both : "X와 관련/연결/주변" 인 것
- path <id> <id>            : A와 B가 어떻게 이어지는지(경로)
- node <id>                 : 한 노드 자세히/백링크
- degree --top <N>          : 허브(연결 많은 노드)
- suggest <id>              : 이어질 만한 연결 후보
- orphans                   : 고립 노드
- SELECT ... FROM nodes WHERE ... : 타입/신뢰도 등 조건 질의
규칙: (1) <id>는 반드시 아래 '노드 목록'의 실제 id를 그대로(추측 금지). (2) "관련/연결/주변"=neighbors, "A와 B 관계/경로"=path. (3) 위 예시들의 형식을 그대로 따라라.
노드 타입: ${types.join(", ")}
엣지 타입: ${etypes.join(", ")}
노드 목록(id | title | type | tags):\n${nl}`;
  return { sys, fewshot: fs };
}
async function chatAsk(q) {
  bubble("user", esc(q));
  if (q.startsWith("~~")) {                       // 채팅에서 검색창 직접 제어 (LLM 미사용)
    const expr = q.slice(2).trim();
    if (!expr) { bubble("sys", "~~ 뒤에 검색식을 적어주세요. 예) ~~ neighbors redis --depth 2"); return; }
    $("q").value = expr; runQuery(expr);
    bubble("sys", `🔎 검색창 실행: ${esc(expr)} · ${lastIds.length}건 (좌측 목록·그래프 갱신)`);
    return;
  }
  const ui = uiIntent(q);                          // "문서 탭 숨겨줘", "상하로 해줘" 등
  if (ui) { bubble("sys", "🪟 " + ui()); return; }
  const engine = await ensureLLM();
  if (!engine) { bubble("sys", "브라우저 AI가 없어 자연어 답변을 못 만들어요. 검색은 검색창이나 `~~ <검색식>`을 써주세요."); return; }
  const thinking = bubble("bot", "…");
  const hist = chatHistory.slice(-6);   // 최근 대화 맥락(후속 질문 해석용)
  try {
    const { sys: sys1, fewshot } = buildChatTeach();   // 실제 그래프 어휘 + 예시 주입
    const r1 = await engine.chat.completions.create({ messages: [{ role: "system", content: sys1 }, ...fewshot, ...hist, { role: "user", content: q }], temperature: 0 });
    const query = (r1.choices[0].message.content || "").trim().split("\n")[0].replace(/^`+|`+$/g, "").trim();
    let ids = retrieve(query);                       // 내부 조회만 (검색창·목록·그래프 안 건드림)
    if (!ids.length) ids = keywordIds(q);            // 0건이면 질문 키워드로 재시도
    const found = ids.slice(0, 8);
    if (!found.length) {                              // 진짜 결과 없으면 환각 대신 솔직히
      const msg = "그래프에서 관련 노드를 찾지 못했어요. 다르게 물어봐 주세요.";
      chatHistory.push({ role: "user", content: q }, { role: "assistant", content: msg });
      thinking.innerHTML = esc(msg) + `<br><span style="opacity:.6;font-size:12px">↳ ${esc(query)} · 0건</span>`; return;
    }
    const ctx = found.map((id) => { const n = rows("SELECT title,type,summary,body FROM nodes WHERE id=?", [id])[0] || {}; return `## ${n.title || id} (${n.type || ""})\n요약: ${n.summary || "-"}\n내용: ${(n.body || "-").slice(0, 400)}`; }).join("\n\n");
    const sys2 = `너는 이 지식그래프 전용 비서다. 아래 '노드 내용'에 적힌 사실만으로 한국어 2~4문장으로 답하라.
금지: 일반 상식·사전적 정의·외부 지식(예: 약자 풀이)·노드에 없는 내용 추가. 노드에 답이 없으면 정확히 "그래프에 그 정보가 없어요"라고만 답하라.
노드 내용:\n${ctx}`;
    const r2 = await engine.chat.completions.create({ messages: [{ role: "system", content: sys2 }, { role: "user", content: q }], temperature: 0 });
    const ans = (r2.choices[0].message.content || "").trim();
    chatHistory.push({ role: "user", content: q }, { role: "assistant", content: ans });   // 메모리 누적
    thinking.innerHTML = esc(ans) + `<br><span style="opacity:.6;font-size:12px">↳ ${esc(query)} · ${found.length}건 (내부검색)</span>`;
  } catch (e) { thinking.textContent = "오류: " + e.message; }
}

function runQueryFromBox() { runQuery($("q").value); }
async function main() {
  try {
    const SQL = await initSqlJs({ locateFile: (f) => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${f}` });
    [rawNodes, rawEdges] = await Promise.all([fetchCSV("nodes.csv"), fetchCSV("edges.csv")]);
    db = buildDb(SQL, rawNodes, rawEdges);
    allNodes = rows("SELECT id,title,type FROM nodes ORDER BY type,title");
    note(`노드 ${rows("SELECT COUNT(*) c FROM nodes")[0].c} · 엣지 ${rows("SELECT COUNT(*) c FROM edges")[0].c}`);
    buildHelp();

    const st = loadState();
    if (st.horizontal) $("center").classList.add("horizontal");
    $("layout").textContent = $("center").classList.contains("horizontal") ? "⬌ 좌우" : "⬍ 상하";
    if (st.grows) grows = Object.assign(grows, st.grows);
    if (st.collapsed) for (const id of PANELS) if (id in st.collapsed) $(id).classList.toggle("collapsed", !!st.collapsed[id]);
    if (isOpen("graphPanel")) buildGraph();

    renderList(null);
    const fp = (rows("SELECT id FROM nodes WHERE type='pillar' ORDER BY id LIMIT 1")[0] || {}).id;
    const want = (st.current && allNodes.some((n) => n.id === st.current)) ? st.current : (fp || (allNodes[0] || {}).id);
    if (want) select(want);
    setArrows(); syncResizers(); applyFlex(); fitGraph();

    PANELS.forEach((id) => $(id).querySelector(".phead").addEventListener("click", () => togglePanel(id)));
    $("layout").addEventListener("click", toggleLayout);
    $("help").addEventListener("click", () => $("helpModal").classList.remove("hidden"));
    $("helpClose").addEventListener("click", () => $("helpModal").classList.add("hidden"));
    $("helpModal").addEventListener("click", (e) => { if (e.target === $("helpModal")) $("helpModal").classList.add("hidden"); });
    initResizers();

    let timer;
    $("q").addEventListener("input", (ev) => { if (classify(ev.target.value) !== "text") return; clearTimeout(timer); timer = setTimeout(runQueryFromBox, 200); });
    $("q").addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); runQueryFromBox(); } });
    $("chatform").addEventListener("submit", (ev) => { ev.preventDefault(); const v = $("chatin").value.trim(); if (v) { $("chatin").value = ""; chatAsk(v); } });
    $("chatclear").addEventListener("click", () => { $("chatlog").innerHTML = ""; chatHistory = []; $("chatin").focus(); });
    try { const m = localStorage.getItem(LS_MODEL); if (m && [...$("chatmodel").options].some((o) => o.value === m)) $("chatmodel").value = m; } catch (e) {}
    $("chatmodel").addEventListener("change", () => {
      try { localStorage.setItem(LS_MODEL, $("chatmodel").value); } catch (e) {}
      if (llmModel && llmModel !== $("chatmodel").value) { llm = null; llmTried = false; bubble("sys", "모델을 바꿨어요. 다음 질문 때 새로 받습니다."); }
    });

    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") { $("helpModal").classList.add("hidden"); return; }
      const typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement && document.activeElement.tagName);
      if (ev.altKey && ev.key === "1") { ev.preventDefault(); togglePanel("docPanel"); }
      else if (ev.altKey && ev.key === "2") { ev.preventDefault(); togglePanel("graphPanel"); }
      else if (ev.altKey && ev.key === "3") { ev.preventDefault(); togglePanel("chatPanel"); }
      else if (ev.key === "?" && !typing) { ev.preventDefault(); $("helpModal").classList.remove("hidden"); }
    });
    window.addEventListener("resize", fitGraph);
  } catch (err) { note("오류: " + err.message); console.error(err); }
}
main();
