/* Excel Brain 지식 뷰어 — 전부 클라이언트 사이드(sql.js).
   검색창: 텍스트 / eb 명령(neighbors·path…) / 원시 SQL 자동 감지. WebLLM(선택)이 켜지면
   자연어 → 질의로 변환해 실행, 안 되면 텍스트 검색으로 폴백.
   패널(문서/그래프): 상하·좌우 분할, 접기·드래그, 현재 노드 하이라이트, 상태 기억. */
"use strict";

const DATA_BASES = ["./data/", "../data/"];
const LS_KEY = "eb-view-state-v1";
const CMDS = ["search", "neighbors", "path", "degree", "suggest", "orphans", "components"];
const TYPE_COLORS = { pillar: "#7c3aed", concept: "#2563eb", fact: "#059669",
  decision: "#d97706", question: "#dc2626", playbook: "#0891b2", source: "#6b7280", note: "#94a3b8" };
const colorFor = (t) => TYPE_COLORS[t] || "#64748b";
const esc = (s) => (s == null ? "" : String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])));
const $ = (id) => document.getElementById(id);

let db = null, cy = null, current = null, allNodes = [], rawNodes = [], rawEdges = [];
let ratio = 0.55, llm = null, aiOn = false;

/* ---- 로드/DB ---- */
async function fetchCSV(name) {
  for (const base of DATA_BASES) {
    try { const r = await fetch(base + name); if (r.ok) return Papa.parse(await r.text(), { header: true, skipEmptyLines: true }).data; }
    catch (e) { /* 다음 경로 */ }
  }
  throw new Error(`${name} 로드 실패 — data/ (또는 ../data/)에 CSV가 있어야 합니다`);
}
function rows(sql, params = []) {
  const out = [], st = db.prepare(sql);
  st.bind(params); while (st.step()) out.push(st.getAsObject()); st.free();
  return out;
}
function buildDb(SQL, nodes, edges) {
  const d = new SQL.Database();
  d.run(`CREATE TABLE nodes(id TEXT PRIMARY KEY, title, type, namespace, visibility, summary, confidence REAL, tags, body);
         CREATE TABLE edges(source, type, target, weight REAL, note);`);
  const ni = d.prepare("INSERT OR REPLACE INTO nodes VALUES (?,?,?,?,?,?,?,?,?)");
  for (const n of nodes) if ((n.id || "").trim())
    ni.run([n.id.trim(), n.title, n.type, n.namespace, n.visibility, n.summary, n.confidence ? +n.confidence : null, n.tags, n.body]);
  ni.free();
  const ei = d.prepare("INSERT INTO edges VALUES (?,?,?,?,?)");
  for (const e of edges) if ((e.source || "").trim() && (e.target || "").trim())
    ei.run([e.source.trim(), e.type, e.target.trim(), e.weight ? +e.weight : null, e.note]);
  ei.free();
  return d;
}

/* ---- 상태 기억 ---- */
function saveState() {
  try { localStorage.setItem(LS_KEY, JSON.stringify({
    docCollapsed: $("docPanel").classList.contains("collapsed"),
    graphCollapsed: $("graphPanel").classList.contains("collapsed"),
    horizontal: $("center").classList.contains("horizontal"), ratio, current })); } catch (e) {}
}
function loadState() { try { return JSON.parse(localStorage.getItem(LS_KEY)) || {}; } catch (e) { return {}; } }

/* ---- 목록 + 원문 ---- */
function note(msg) { $("stats").textContent = msg; }
function liHtml(n) { return `<li data-id="${esc(n.id)}" class="${n.id === current ? "sel" : ""}">${esc(n.title || n.id)}<br><span class="t">${esc(n.type || "")}</span></li>`; }
function bindList() { $("list").querySelectorAll("li[data-id]").forEach((li) => li.addEventListener("click", () => select(li.dataset.id))); }
function renderList(filterIds) {
  const items = allNodes.filter((n) => !filterIds || filterIds.has(n.id));
  $("list").innerHTML = items.length ? items.map(liHtml).join("") : '<li class="empty">결과 없음</li>';
  bindList();
}
function renderOrdered(ids) {
  const byId = Object.fromEntries(allNodes.map((n) => [n.id, n]));
  $("list").innerHTML = ids.length ? ids.map((id) => liHtml(byId[id] || { id })).join("") : '<li class="empty">결과 없음</li>';
  bindList();
}
function renderDoc(id) {
  const n = rows("SELECT * FROM nodes WHERE id = ?", [id])[0], doc = $("doc");
  if (!n) { doc.innerHTML = '<p class="placeholder">노드를 선택하세요.</p>'; return; }
  const out = rows("SELECT type, target FROM edges WHERE source=? ORDER BY target", [id]);
  const inc = rows("SELECT type, source FROM edges WHERE target=? ORDER BY source", [id]);
  const link = (nid) => `<a data-id="${esc(nid)}">${esc(nid)}</a>`;
  const el = (arr, d) => arr.length ? arr.map((e) => `<li><span class="etype">${esc(e.type)}</span> ${d === "out" ? "→ " + link(e.target) : link(e.source) + " →"}</li>`).join("") : '<li class="placeholder">(없음)</li>';
  doc.innerHTML = `<h2>${esc(n.title || n.id)}</h2>
     <div class="meta"><span class="badge" style="background:${colorFor(n.type)}">${esc(n.type || "?")}</span>
       <code>${esc(n.id)}</code>${n.namespace ? " · " + esc(n.namespace) : ""} · 신뢰도 ${n.confidence ?? "-"}${n.tags ? " · " + esc(n.tags) : ""}</div>
     ${n.summary ? `<div class="summary">${esc(n.summary)}</div>` : ""}
     <div class="body">${esc(n.body) || '<span class="placeholder">(본문 없음)</span>'}</div>
     <h3>나가는 엣지 (${out.length})</h3><ul class="edges">${el(out, "out")}</ul>
     <h3>들어오는 엣지 / 백링크 (${inc.length})</h3><ul class="edges">${el(inc, "in")}</ul>`;
  doc.querySelectorAll("a[data-id]").forEach((a) => a.addEventListener("click", () => select(a.dataset.id)));
  doc.scrollTop = 0;
}
function markCurrent() {
  if (!cy) return;
  cy.nodes().removeClass("current");
  const el = cy.getElementById(current);
  if (el && el.length) { el.addClass("current"); if (!$("graphPanel").classList.contains("collapsed")) cy.animate({ center: { eles: el }, zoom: 1.3 }, { duration: 200 }); }
}
function select(id) {
  current = id; renderDoc(id);
  document.querySelectorAll("#list li").forEach((li) => li.classList.toggle("sel", li.dataset.id === id));
  markCurrent(); saveState();
}

/* ---- 그래프 강조(쿼리 결과) ---- */
function highlightInGraph(ids) {
  if (!cy) return;
  const set = new Set(ids);
  cy.batch(() => {
    cy.elements().removeClass("dim qhit");
    if (!ids.length) return;
    cy.nodes().forEach((n) => set.has(n.id()) ? n.addClass("qhit") : n.addClass("dim"));
    cy.edges().forEach((e) => { if (!(set.has(e.source().id()) && set.has(e.target().id()))) e.addClass("dim"); });
  });
}

/* ---- 검색 디스패처: 텍스트 / 명령 / SQL ---- */
function classify(s) {
  if (/^\s*select\b/i.test(s)) return "sql";
  if (CMDS.includes(s.trim().split(/\s+/)[0])) return "cmd";
  return "text";
}
function flag(toks, name, def) { const i = toks.indexOf(name); return i >= 0 && toks[i + 1] ? toks[i + 1] : def; }
function adjSQL(dir) {
  const o = "SELECT source a, target b FROM edges", i = "SELECT target a, source b FROM edges";
  return dir === "out" ? o : dir === "in" ? i : `${o} UNION ${i}`;
}
function runText(q) {
  if (!q.trim()) { renderList(null); highlightInGraph([]); return; }
  const like = "%" + q.trim().toLowerCase() + "%";
  const ids = rows(`SELECT id FROM nodes WHERE lower(title) LIKE ? OR lower(summary) LIKE ? OR lower(tags) LIKE ? OR lower(body) LIKE ?`, [like, like, like, like]).map((r) => r.id);
  renderList(new Set(ids)); highlightInGraph(ids); note(`텍스트 '${q.trim()}': ${ids.length}건`);
}
function runSQL(s) {
  try {
    const r = rows(s);
    if (!r.length) { renderList(new Set()); highlightInGraph([]); note("SQL: 0행"); return; }
    if (!("id" in r[0])) { note(`SQL: ${r.length}행 (id 컬럼 없음 — id를 SELECT 하세요)`); return; }
    const ids = r.map((x) => x.id); renderOrdered(ids); highlightInGraph(ids); note(`SQL: ${ids.length}행`);
  } catch (e) { note("SQL 오류: " + e.message); }
}
function runCmd(s) {
  const toks = s.trim().split(/\s+/), cmd = toks[0], arg = toks[1];
  try {
    if (cmd === "search") return runText(toks.slice(1).join(" "));
    if (cmd === "neighbors") {
      const depth = +flag(toks, "--depth", 1), dir = flag(toks, "--direction", "both");
      const r = rows(`WITH RECURSIVE adj(a,b) AS (${adjSQL(dir)}), walk(id,dist) AS (
        SELECT ?,0 UNION SELECT adj.b, walk.dist+1 FROM adj JOIN walk ON adj.a=walk.id WHERE walk.dist<?)
        SELECT id, MIN(dist) dist FROM walk WHERE id<>? GROUP BY id ORDER BY dist, id`, [arg, depth, arg]);
      const ids = r.map((x) => x.id); renderOrdered(ids); highlightInGraph([arg, ...ids]); note(`${arg} 이웃 ${depth}홉(${dir}): ${ids.length}개`); return;
    }
    if (cmd === "path") {
      const dst = toks[2], dir = flag(toks, "--direction", "both");
      const row = rows(`WITH RECURSIVE adj(a,b) AS (${adjSQL(dir)}), walk(id,path,depth) AS (
        SELECT ?, '>'||?||'>', 0 UNION ALL SELECT adj.b, walk.path||adj.b||'>', walk.depth+1
          FROM adj JOIN walk ON adj.a=walk.id WHERE walk.depth<64 AND instr(walk.path,'>'||adj.b||'>')=0)
        SELECT path, depth FROM walk WHERE id=? ORDER BY depth LIMIT 1`, [arg, arg, dst])[0];
      if (!row) { renderOrdered([]); note(`경로 없음: ${arg} → ${dst}`); return; }
      const ids = row.path.split(">").filter(Boolean); renderOrdered(ids); highlightInGraph(ids);
      note(`경로(홉 ${row.depth}): ${ids.join(" → ")}`); return;
    }
    if (cmd === "degree") {
      const top = +flag(toks, "--top", 10);
      const ids = rows(`SELECT id, (SELECT COUNT(*) FROM edges WHERE source=n.id OR target=n.id) deg
        FROM nodes n ORDER BY deg DESC, id LIMIT ?`, [top]).map((x) => x.id);
      renderOrdered(ids); highlightInGraph(ids); note(`허브 상위 ${ids.length}`); return;
    }
    if (cmd === "orphans") {
      const ids = rows(`SELECT id FROM nodes WHERE id NOT IN (SELECT source FROM edges) AND id NOT IN (SELECT target FROM edges) ORDER BY id`).map((x) => x.id);
      renderOrdered(ids); highlightInGraph(ids); note(`고아 ${ids.length}개`); return;
    }
    if (cmd === "suggest") { runSuggest(arg); return; }
    if (cmd === "components") {
      const comps = components(); note(`연결 요소 ${comps.length}개 (최대 ${comps[0]?.length || 0})`); renderOrdered(comps[0] || []); highlightInGraph(comps[0] || []); return;
    }
  } catch (e) { note("명령 오류: " + e.message); }
}
function components() {
  const ids = allNodes.map((n) => n.id), parent = {}; ids.forEach((i) => parent[i] = i);
  const find = (x) => { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; };
  rawEdges.forEach((e) => { const s = (e.source || "").trim(), t = (e.target || "").trim(); if (parent[s] && parent[t]) { const a = find(s), b = find(t); if (a !== b) parent[b] = a; } });
  const g = {}; ids.forEach((i) => { const r = find(i); (g[r] = g[r] || []).push(i); });
  return Object.values(g).sort((a, b) => b.length - a.length);
}
function runSuggest(id) {
  const adj = {}, tags = {};
  allNodes.forEach((n) => { adj[n.id] = new Set(); });
  rawNodes.forEach((n) => { const i = (n.id || "").trim(); if (i) tags[i] = new Set(String(n.tags || "").split(";").map((x) => x.trim()).filter(Boolean)); });
  rawEdges.forEach((e) => { const s = (e.source || "").trim(), t = (e.target || "").trim(); if (adj[s] && adj[t]) { adj[s].add(t); adj[t].add(s); } });
  if (!adj[id]) { note("없는 노드: " + id); return; }
  const my = adj[id], myt = tags[id] || new Set(), out = [];
  for (const n of allNodes) {
    if (n.id === id || my.has(n.id)) continue;
    let common = 0; my.forEach((x) => { if (adj[n.id].has(x)) common++; });
    const ct = tags[n.id] || new Set(), uni = new Set([...myt, ...ct]); let inter = 0; myt.forEach((x) => { if (ct.has(x)) inter++; });
    const jac = uni.size ? inter / uni.size : 0, score = common + jac;
    if (score > 0) out.push({ id: n.id, score });
  }
  out.sort((a, b) => b.score - a.score);
  const ids = out.map((x) => x.id); renderOrdered(ids); highlightInGraph([id, ...ids]); note(`${id} 연결 후보 ${ids.length}`);
}

function runQuery(input, fromEnter) {
  const s = (input || "").trim();
  if (!s) { renderList(null); highlightInGraph([]); note(`노드 ${allNodes.length}`); return; }
  const kind = classify(s);
  if (aiOn && fromEnter && kind === "text") return runAI(s);
  if (kind === "sql") return runSQL(s);
  if (kind === "cmd") return runCmd(s);
  return runText(s);
}

/* ---- WebLLM (선택, CDN, 자연어 → 질의) ---- */
async function enableAI() {
  $("ai").textContent = "🤖 로딩…";
  try {
    const webllm = await import("https://esm.run/@mlc-ai/web-llm");
    llm = await webllm.CreateMLCEngine("Qwen2.5-0.5B-Instruct-q4f16_1-MLC",
      { initProgressCallback: (p) => { $("ai").textContent = "🤖 " + Math.round((p.progress || 0) * 100) + "%"; } });
    aiOn = true; $("ai").textContent = "🤖 AI 켜짐";
  } catch (e) { aiOn = false; llm = null; $("ai").textContent = "🤖 AI(미지원)"; alert("WebLLM 사용 불가: " + e.message + "\n텍스트·SQL 검색을 쓰세요."); }
}
async function runAI(q) {
  if (!llm) return runText(q);
  note("🤖 생각 중…");
  const list = allNodes.slice(0, 300).map((n) => `${n.id} | ${n.title} | ${n.type}`).join("\n");
  const sys = `너는 지식그래프 질의 변환기다. 사용자의 한국어 질문을 아래 중 정확히 한 줄로만 출력한다(설명·코드블록 금지).
- 텍스트: search <키워드>
- 이웃:   neighbors <노드id> --depth <N> --direction both
- 경로:   path <노드id> <노드id>
- SQL:    SELECT id,title FROM nodes WHERE ...
스키마: nodes(id,title,type,namespace,visibility,summary,confidence REAL,tags,body), edges(source,type,target,weight,note). id는 kebab-case.
노드 목록(id | title | type):\n${list}`;
  try {
    const r = await llm.chat.completions.create({ messages: [{ role: "system", content: sys }, { role: "user", content: q }], temperature: 0 });
    const line = (r.choices[0].message.content || "").trim().split("\n")[0].replace(/^`+|`+$/g, "").trim();
    $("q").value = line; runQuery(line, false); note("🤖 → " + line);
  } catch (e) { note("AI 오류 — 텍스트로"); runText(q); }
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
  ], layout: { name: "cose", animate: false, padding: 30 } });
  cy.on("tap", "node", (ev) => select(ev.target.id()));
  markCurrent();
}

/* ---- 패널 ---- */
function bothExpanded() { return !$("docPanel").classList.contains("collapsed") && !$("graphPanel").classList.contains("collapsed"); }
function setSplit(r) { ratio = Math.max(0.15, Math.min(0.85, r)); if (bothExpanded()) { $("docPanel").style.flex = `${ratio} 1 0`; $("graphPanel").style.flex = `${1 - ratio} 1 0`; } }
function applyFlex() { if (bothExpanded()) setSplit(ratio); else { $("docPanel").style.flex = ""; $("graphPanel").style.flex = ""; } }
function fitGraph() { if (cy && !$("graphPanel").classList.contains("collapsed")) requestAnimationFrame(() => { cy.resize(); cy.fit(undefined, 40); }); }
function syncResizer() { $("resizer").classList.toggle("hidden", !bothExpanded()); }
function setArrows() { for (const p of ["docPanel", "graphPanel"]) $(p).querySelector(".toggle").textContent = $(p).classList.contains("collapsed") ? "▸" : "▾"; }
function togglePanel(which) {
  const el = which === "doc" ? $("docPanel") : $("graphPanel");
  el.classList.toggle("collapsed");
  if (which === "graph" && !el.classList.contains("collapsed") && !cy) buildGraph();
  applyFlex(); setArrows(); syncResizer(); fitGraph(); saveState();
}
function toggleLayout() { const h = $("center").classList.toggle("horizontal"); $("layout").textContent = h ? "⬌ 좌우" : "⬍ 상하"; applyFlex(); fitGraph(); saveState(); }
function initResize() {
  const center = $("center");
  const move = (e) => { const rect = center.getBoundingClientRect();
    setSplit(center.classList.contains("horizontal") ? (e.clientX - rect.left) / rect.width : (e.clientY - rect.top) / rect.height);
    if (cy && !$("graphPanel").classList.contains("collapsed")) cy.resize(); };
  const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); fitGraph(); saveState(); };
  $("resizer").addEventListener("mousedown", (e) => { if ($("resizer").classList.contains("hidden")) return; e.preventDefault(); document.addEventListener("mousemove", move); document.addEventListener("mouseup", up); });
}

async function main() {
  try {
    const SQL = await initSqlJs({ locateFile: (f) => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${f}` });
    [rawNodes, rawEdges] = await Promise.all([fetchCSV("nodes.csv"), fetchCSV("edges.csv")]);
    db = buildDb(SQL, rawNodes, rawEdges);
    allNodes = rows("SELECT id, title, type FROM nodes ORDER BY type, title");
    const nc = rows("SELECT COUNT(*) c FROM nodes")[0].c, ec = rows("SELECT COUNT(*) c FROM edges")[0].c;
    note(`노드 ${nc} · 엣지 ${ec}`);

    const st = loadState();
    if (st.horizontal) $("center").classList.add("horizontal");
    $("layout").textContent = $("center").classList.contains("horizontal") ? "⬌ 좌우" : "⬍ 상하";
    if (typeof st.ratio === "number") ratio = st.ratio;
    if (st.docCollapsed) $("docPanel").classList.add("collapsed");
    if (st.graphCollapsed === false) { $("graphPanel").classList.remove("collapsed"); buildGraph(); }

    renderList(null);
    const fp = (rows("SELECT id FROM nodes WHERE type='pillar' ORDER BY id LIMIT 1")[0] || {}).id;
    const want = (st.current && allNodes.some((n) => n.id === st.current)) ? st.current : (fp || (allNodes[0] || {}).id);
    if (want) select(want); else $("doc").innerHTML = '<p class="placeholder">노드가 없습니다.</p>';
    setArrows(); syncResizer(); applyFlex(); fitGraph();

    $("docPanel").querySelector(".phead").addEventListener("click", () => togglePanel("doc"));
    $("graphPanel").querySelector(".phead").addEventListener("click", () => togglePanel("graph"));
    $("layout").addEventListener("click", toggleLayout);
    $("ai").addEventListener("click", () => { if (!aiOn && !llm) enableAI(); else { aiOn = !aiOn; $("ai").textContent = aiOn ? "🤖 AI 켜짐" : "🤖 AI 꺼짐"; } });
    initResize();
    let timer;
    $("q").addEventListener("input", (ev) => { const s = ev.target.value; if (aiOn || classify(s) !== "text") return; clearTimeout(timer); timer = setTimeout(() => runQuery(s, false), 200); });
    $("q").addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); runQuery(ev.target.value, true); } });
    window.addEventListener("resize", fitGraph);
  } catch (err) { note("오류: " + err.message); console.error(err); }
}
main();
