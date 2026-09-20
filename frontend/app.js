/* 全球鹰 GEO 全球AI推荐系统 - 控制台前端 */
'use strict';

const state = {
  tab: 'console',
  health: null,
  run: null,
  cache: {},
};

const TABS = [
  { id: 'console', name: '控制台', sub: '输入买家真实采购问题，运行 GEO 全链路' },
  { id: 'queries', name: '查询矩阵', sub: 'A03 十类查询意图扩展（Query Coverage）' },
  { id: 'entity', name: '实体图谱', sub: 'A05 Brand→Product→Model→Cert→Market→Buyer' },
  { id: 'evidence', name: '证据图谱', sub: 'A06 Claim → Evidence → Source → Citation' },
  { id: 'score', name: 'GEO 评分', sub: 'A07 八个维度 100 分制 AI 可见性优化度' },
  { id: 'content', name: '内容工厂', sub: 'A09 AI Answer Ready Content + A10 JSON-LD' },
  { id: 'competitor', name: '竞争与差距', sub: 'A08 竞争实体矩阵与五类 Gap' },
  { id: 'visibility', name: '可见性监测', sub: 'A12 GEO Visibility Dashboard' },
  { id: 'crm', name: '询盘 / CRM', sub: 'A13 GEO → 询盘 → RFQ → 成交' },
  { id: 'approval', name: '人工审核', sub: 'Human-in-the-loop Approval Queue' },
  { id: 'audit', name: '审计日志', sub: '全链路可追溯审计' },
  { id: 'plugins', name: '插件', sub: '外部连接器 · RedditGrow（MCP）' },
  { id: 'settings', name: '系统设置', sub: '自定义大模型提供商 · 本地 CLI 接入（OpenClaw / AnyGen / WorkBuddy）' },
  { id: 'arch', name: '系统架构', sub: 'OpenClaw Orchestrator + Agent Cluster' },
];

/* ---------------- utils ---------------- */
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const pct = (v) => `${Number(v || 0).toFixed(1)}%`;

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.hidden = false;
  setTimeout(() => { el.hidden = true; }, 2600);
}

function statusChip(status) {
  const map = {
    verified: ['ok', 'verified'],
    unverified: ['bad', 'unverified'],
    conflicting: ['warn', 'conflicting'],
    pending: ['warn', 'pending'],
    approved: ['ok', 'approved'],
    rejected: ['bad', 'rejected'],
    revision_required: ['warn', 'revision'],
  };
  const [cls, label] = map[status] || ['info', status || 'unknown'];
  return `<span class="chip ${cls}">${esc(label)}</span>`;
}

function markdown(text) {
  return esc(text)
    .replace(/^## (.+)$/gm, '<h4>$1</h4>')
    .replace(/^- (.+)$/gm, '<div>· $1</div>')
    .replace(/^  A: (.+)$/gm, '<div style="padding-left:14px;color:#93a4c2">A: $1</div>');
}

/* ---------------- boot ---------------- */
async function boot() {
  buildNav();
  try {
    state.health = await api('/api/health');
    renderHealth();
    if (!state.health.counts.entities) {
      await api('/api/seed?force=false', { method: 'POST' });
      state.health = await api('/api/health');
      renderHealth();
    }
    const markets = await api('/api/markets');
    $('#qMarket').innerHTML = ['<option value="">自动识别</option>']
      .concat(markets.markets.map((m) => `<option>${esc(m)}</option>`)).join('');
    $('#qMarket').value = 'Hong Kong';
    $('#demoNotice').hidden = false;
    $('#demoNotice').textContent = `演示数据提示：${state.health.demo_notice || ''}`;
  } catch (e) {
    toast('后端连接失败：' + e.message);
  }
  switchTab('console');
}

function renderHealth() {
  const h = state.health;
  if (!h) return;
  $('#healthBox').innerHTML = `状态 <b>OK</b> · 实体 ${h.counts.entities} · Claim ${h.counts.claims} · 信源 ${h.counts.sources}`;
  const c = h.connectors;
  $('#engineBadge').textContent =
    `Connectors: 检索 ${c.web_search ? 'ON' : 'OFF'} · AI探针 ${c.ai_engine_probe ? 'ON' : 'OFF'} · LLM ${c.llm_polish ? 'ON' : 'OFF'} · RedditGrow ${c.redditgrow ? 'ON' : 'OFF'} · 本地CLI ${c.local_cli_ready ?? 0}/${c.local_cli_total ?? 3}`;
}

function buildNav() {
  $('#nav').innerHTML = TABS.map((t) =>
    `<button data-tab="${t.id}"><span>${t.name}</span></button>`).join('');
  $('#nav').querySelectorAll('button').forEach((b) =>
    b.addEventListener('click', () => switchTab(b.dataset.tab)));
}

async function switchTab(id) {
  state.tab = id;
  $('#nav').querySelectorAll('button').forEach((b) =>
    b.classList.toggle('active', b.dataset.tab === id));
  document.querySelectorAll('.view').forEach((v) => { v.hidden = v.id !== `view-${id}`; });
  const tab = TABS.find((t) => t.id === id);
  $('#pageTitle').textContent = tab.name;
  $('#pageSub').textContent = tab.sub;
  await renderTab(id);
}

async function renderTab(id) {
  try {
    if (id === 'queries') await renderQueries();
    if (id === 'entity') await renderEntity();
    if (id === 'evidence') await renderEvidence();
    if (id === 'score') await renderScore();
    if (id === 'content') await renderContent();
    if (id === 'competitor') await renderCompetitor();
    if (id === 'visibility') await renderVisibility();
    if (id === 'crm') await renderCrm();
    if (id === 'approval') await renderApproval();
    if (id === 'audit') await renderAudit();
    if (id === 'plugins') await renderPlugins();
    if (id === 'settings') await renderSettings();
    if (id === 'arch') renderArch();
  } catch (e) {
    $(`#view-${id}`).innerHTML = `<div class="card"><div class="empty">加载失败：${esc(e.message)}</div></div>`;
  }
}

/* ---------------- console ---------------- */
$('#btnRun').addEventListener('click', runPipeline);
$('#btnSeed').addEventListener('click', async () => {
  await api('/api/seed?force=true', { method: 'POST' });
  state.run = null;
  state.cache = {};
  $('#runResult').innerHTML = '';
  toast('演示数据已重置');
  await boot();
});

async function runPipeline() {
  const btn = $('#btnRun');
  btn.disabled = true;
  btn.textContent = '运行中…';
  try {
    const payload = {
      query: $('#qQuery').value,
      market: $('#qMarket').value || null,
      language: $('#qLanguage').value,
      engines: Array.from($('#qEngines').selectedOptions).map((o) => o.value),
      enable_web_verify: $('#qWebVerify').checked,
    };
    state.run = await api('/api/pipeline/run', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    state.cache = {};
    renderRun();
    toast('流水线执行完成');
  } catch (e) {
    toast('运行失败：' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '运行流水线';
  }
}

function renderRun() {
  const run = state.run;
  if (!run) return;
  const o = run.output;
  const g = o.geo_score || {};
  const bd = g.score_breakdown || {};
  const dims = [
    ['evidence_authority', '证据权威度', 25], ['query_relevance', '查询相关性', 20],
    ['entity_clarity', '实体清晰度', 15], ['extractability', '可抽取性', 10],
    ['market_relevance', '市场相关性', 10], ['differentiation', '差异化', 10],
    ['citation_coverage', '引用覆盖', 5], ['freshness', '时效性', 5],
  ];
  $('#runResult').innerHTML = `
    <div class="card">
      <div class="card-head"><h3>流水线执行轨迹</h3>
        <span class="hint">run ${esc(run.id)} · ${run.duration_ms} ms · market ${esc(run.market)}</span></div>
      <div class="timeline">${(o.pipeline_trace || []).map((t) => `
        <div class="row"><span><span class="dot"></span> ${esc(t.step)}</span>
        <span class="muted">${esc(t.agent)}</span><span class="muted">${t.duration_ms}ms</span></div>`).join('')}
      </div>
    </div>

    <div class="grid c4">
      <div class="kpi accent"><div class="label">GEO Score</div><div class="value">${g.overall ?? 0}</div>
        <div class="sub">置信度 ${pct(g.confidence)}</div></div>
      <div class="kpi blue"><div class="label">Evidence Coverage</div><div class="value">${pct(g.evidence_coverage)}</div>
        <div class="sub">不确定度 ${pct(g.uncertainty)}</div></div>
      <div class="kpi"><div class="label">候选 / 查询</div><div class="value">${o.candidate_entities.length} / ${o.query_expansion.total_queries || 0}</div>
        <div class="sub">Top20 混合召回</div></div>
      <div class="kpi gold"><div class="label">待人工审核</div><div class="value">${o.human_approval_required.length}</div>
        <div class="sub">Human Approval Queue</div></div>
    </div>

    <div class="card">
      <div class="card-head"><h3>GEO Score 构成</h3><span class="hint">仅表示 AI 可见性优化程度，不代表必然被推荐</span></div>
      <div class="score-hero">
        <div class="gauge" style="--p:${g.overall || 0}">
          <div class="inner"><b>${g.overall ?? 0}</b><span>/ 100</span></div>
        </div>
        <div class="dim-list">
          ${dims.map(([k, label, max]) => `
            <div class="dim"><span class="name">${label}</span>
              <span class="bar"><i style="width:${((bd[k] || 0) / max) * 100}%"></i></span>
              <span>${(bd[k] || 0).toFixed(1)}/${max}</span></div>`).join('')}
        </div>
      </div>
      <p class="muted" style="margin-top:12px">${esc(o.system?.disclaimer || '')}</p>
    </div>

    <div class="card">
      <div class="card-head"><h3>候选实体排序</h3><span class="hint">Evidence First · 相关性优先于关键词</span></div>
      <table><thead><tr><th>#</th><th>Brand / Company</th><th>Product</th><th>Score</th>
        <th>Citation</th><th>Market</th><th>Risk</th></tr></thead><tbody>
      ${o.ranked_entities.map((r) => `<tr>
        <td>${r.rank}</td>
        <td><b>${esc(r.brand)}</b><div class="muted">${esc(r.company)} · ${esc(r.country)}</div></td>
        <td>${esc(r.product)}</td>
        <td><b>${r.geo_score}</b><div class="muted">置信 ${pct(r.confidence)}</div></td>
        <td>${statusChip(r.citation_readiness.toLowerCase().replace('high', 'verified').replace('medium', 'pending').replace('low', 'unverified'))}</td>
        <td class="muted">${esc(r.market_relevance)}</td>
        <td>${(r.risk || []).map((x) => `<div class="risk">· ${esc(x)}</div>`).join('') || '<span class="muted">—</span>'}</td>
      </tr>`).join('')}
      </tbody></table>
    </div>

    <div class="card">
      <div class="card-head"><h3>优先优化动作</h3><span class="hint">来自 Evidence / Entity / Content / Query / Market / Citation Gap</span></div>
      <div class="list">${(o.optimization_actions || []).slice(0, 10).map((a) => `
        <div class="list-item"><div class="t">
          <span class="chip ${a.priority === 'P0' ? 'bad' : a.priority === 'P1' ? 'warn' : 'info'}">${a.priority}</span>
          ${esc(a.action)}</div>
          <div class="m">${esc(a.category)}</div></div>`).join('') || '<div class="empty">暂无</div>'}
      </div>
    </div>

    <div class="card">
      <div class="card-head"><h3>统一输出 JSON</h3><span class="hint">Claim → Evidence → Citation 全链路可追溯</span></div>
      <details><summary class="muted">展开完整统一输出（Section 28 契约）</summary>
        <pre>${esc(JSON.stringify(o, null, 2))}</pre></details>
    </div>`;
}

/* ---------------- queries ---------------- */
async function renderQueries() {
  if (!state.run) { $('#view-queries').innerHTML = emptyRun(); return; }
  const qe = state.run.output.query_expansion;
  const cats = {
    product_query: '产品查询', supplier_query: '供应商查询', comparison_query: '对比查询',
    technical_query: '技术查询', price_query: '价格查询', certification_query: '认证查询',
    application_query: '应用查询', local_market_query: '本地市场查询',
    long_tail_query: '长尾查询', conversational_query: '对话式查询',
  };
  $('#view-queries').innerHTML = `
    <div class="grid c4">
      <div class="kpi accent"><div class="label">Query 总数</div><div class="value">${qe.total_queries}</div></div>
      <div class="kpi blue"><div class="label">覆盖意图类别</div><div class="value">${Object.keys(qe.matrix || {}).length}/10</div></div>
      <div class="kpi"><div class="label">Buyer Stage</div><div class="value" style="font-size:18px">${esc(state.run.output.query.buyer_stage)}</div></div>
      <div class="kpi gold"><div class="label">意图类型</div><div class="value" style="font-size:15px">${(state.run.output.query.intent.intent_type || []).join(' / ')}</div></div>
    </div>
    ${Object.entries(qe.matrix || {}).map(([k, list]) => `
      <div class="card"><div class="card-head"><h3>${cats[k] || k}</h3><span class="hint">${list.length} 条</span></div>
      <div>${list.map((q) => `<span class="chip">${esc(q)}</span>`).join('')}</div></div>`).join('')}`;
}

function emptyRun() {
  return `<div class="card"><div class="empty">请先在「控制台」运行一次 GEO 流水线。</div></div>`;
}

/* ---------------- entity graph ---------------- */
async function renderEntity() {
  const data = state.cache.graph || (state.cache.graph = await api('/api/graph'));
  const g = data.entity_graph;
  const colors = {
    Brand: '#21e6c1', Company: '#4aa8ff', Product: '#ffc46b', ProductModel: '#ff8fb1',
    Specification: '#8ea2c6', Certification: '#37d67a', Industry: '#c08bff',
    Application: '#7ad7ff', Market: '#ffb020', Buyer: '#ff6b81', Competitor: '#ff9f68',
    ThirdPartySource: '#9fb4d8', CaseStudy: '#b6f2d8',
  };
  const svg = forceGraph(g.nodes.slice(0, 160), g.edges, colors);
  const focus = (state.run?.output.ranked_entities || [])[0];
  const chain = focus ? (state.run.output.industrial_intelligence_graph || {})[focus.entity_id] : null;
  $('#view-entity').innerHTML = `
    <div class="grid c4">
      <div class="kpi accent"><div class="label">实体节点</div><div class="value">${g.stats.nodes}</div></div>
      <div class="kpi blue"><div class="label">关系边</div><div class="value">${g.stats.edges}</div></div>
      <div class="kpi"><div class="label">实体类型</div><div class="value">${Object.keys(g.stats.by_type).length}</div></div>
      <div class="kpi gold"><div class="label">证据节点</div><div class="value">${data.evidence_graph.nodes.length}</div></div>
    </div>
    <div class="card">
      <div class="card-head"><h3>Entity Knowledge Graph</h3><span class="hint">Brand→Company→Product→Model→Spec→Cert→Industry→Application→Market→Buyer</span></div>
      <div class="graph-box">${svg}</div>
      <div class="legend">${Object.entries(colors).map(([k, c]) =>
        `<span><i style="background:${c}"></i>${k}</span>`).join('')}</div>
    </div>
    ${chain ? `<div class="card"><div class="card-head"><h3>全球鹰五维产业 Graph · ${esc(focus.brand)}</h3>
      <span class="hint">产业链 + 采购决策链 + 买家链 + 流量链 + 信任链 + 履约链</span></div>
      <div class="grid c2">
        ${Object.entries(chain).map(([k, v]) => `<div class="list-item"><div class="t">${esc(k)}</div>
          <div class="m">${esc(JSON.stringify(v).slice(0, 260))}</div></div>`).join('')}
      </div></div>` : ''}`;
}

function forceGraph(nodes, edges, colors) {
  const W = 900, H = 520;
  const ids = new Set(nodes.map((n) => n.id));
  const links = edges.filter((e) => ids.has(e.source) && ids.has(e.target)).slice(0, 320);
  const pos = new Map();
  nodes.forEach((n, i) => {
    const a = (i / nodes.length) * Math.PI * 2;
    pos.set(n.id, { x: W / 2 + Math.cos(a) * 200 + (Math.random() - 0.5) * 40,
                    y: H / 2 + Math.sin(a) * 170 + (Math.random() - 0.5) * 40 });
  });
  for (let it = 0; it < 260; it++) {
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = pos.get(nodes[i].id), b = pos.get(nodes[j].id);
        let dx = a.x - b.x, dy = a.y - b.y;
        let d = Math.sqrt(dx * dx + dy * dy) || 0.01;
        if (d < 46) {
          const f = ((46 - d) / d) * 0.28;
          a.x += dx * f; a.y += dy * f; b.x -= dx * f; b.y -= dy * f;
        }
      }
    }
    links.forEach((l) => {
      const a = pos.get(l.source), b = pos.get(l.target);
      const dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const f = ((d - 92) / d) * 0.05;
      a.x += dx * f; a.y += dy * f; b.x -= dx * f; b.y -= dy * f;
    });
    pos.forEach((p) => {
      p.x = Math.max(26, Math.min(W - 26, p.x + (W / 2 - p.x) * 0.004));
      p.y = Math.max(22, Math.min(H - 22, p.y + (H / 2 - p.y) * 0.004));
    });
  }
  return `<svg viewBox="0 0 ${W} ${H}">
    ${links.map((l) => {
      const a = pos.get(l.source), b = pos.get(l.target);
      return `<line class="link" x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}"/>`;
    }).join('')}
    ${nodes.map((n) => {
      const p = pos.get(n.id);
      const c = colors[n.type] || '#8ea2c6';
      return `<g class="node" transform="translate(${p.x.toFixed(1)},${p.y.toFixed(1)})">
        <circle r="6" fill="${c}" fill-opacity="0.85"/>
        <text x="9" y="3">${esc(String(n.label).slice(0, 16))}</text></g>`;
    }).join('')}
  </svg>`;
}

/* ---------------- evidence ---------------- */
async function renderEvidence() {
  const [claims, sources, entities] = await Promise.all([
    api('/api/claims'), api('/api/sources'), api('/api/entities'),
  ]);
  const srcMap = Object.fromEntries(sources.sources.map((s) => [s.id, s]));
  const entMap = Object.fromEntries(entities.entities.map((e) => [e.id, e]));
  const byEntity = {};
  claims.claims.forEach((c) => { (byEntity[c.entity_id] = byEntity[c.entity_id] || []).push(c); });

  $('#view-evidence').innerHTML = `
    <div class="card"><div class="card-head"><h3>证据核验</h3>
      <span class="hint">未核验信息 status=unverified，不得作为核心推荐依据</span></div>
      <div class="actions">
        <button class="btn primary" id="btnVerifyWeb">联网核验信源（真实 HTTP 请求）</button>
        <button class="btn" id="btnVerifyLocal">仅重算本地核验状态</button>
      </div>
      <p class="muted" style="margin-top:8px">核验通过条件：信源必须真实可达（HTTP 2xx/3xx）+ 信源层级 Tier1/Tier2 达标；或经人工审核批准。</p>
    </div>
    ${Object.entries(byEntity).map(([eid, list]) => {
      const e = entMap[eid] || {};
      const ok = list.filter((c) => c.verification_status === 'verified').length;
      return `<div class="card"><div class="card-head"><h3>${esc(e.brand || eid)}</h3>
        <span class="hint">${ok}/${list.length} verified · ${e.is_demo ? '演示实体' : ''}</span></div>
        <div class="list">${list.map((c) => `
          <div class="list-item">
            <div class="t">${statusChip(c.verification_status)} ${esc(c.claim)}</div>
            <div class="m">category: ${esc(c.category)} · confidence ${pct((c.confidence || 0) * 100)}${c.verification_note ? ' · ' + esc(c.verification_note) : ''}</div>
            <div>${(c.evidence_source_ids || []).map((sid) => {
              const s = srcMap[sid];
              if (!s) return '';
              return `<span class="chip ${s.tier <= 2 ? 't1' : ''}">Tier${s.tier} ${esc(s.source_type)}${s.is_demo ? ' ·demo' : ''} · ${esc(s.domain)}</span>
                <span class="chip ${s.reachable === true ? 'ok' : s.reachable === false ? 'bad' : ''}">${s.reachable === true ? 'reachable' : s.reachable === false ? 'unreachable' : 'unchecked'}</span>`;
            }).join(' ')}</div>
            <div class="m">${(c.evidence_source_ids || []).map((sid) => esc(srcMap[sid]?.url || '')).join('<br/>')}</div>
          </div>`).join('')}
        </div></div>`;
    }).join('')}`;

  $('#btnVerifyWeb').addEventListener('click', () => doVerify(true));
  $('#btnVerifyLocal').addEventListener('click', () => doVerify(false));
}

async function doVerify(web) {
  toast(web ? '正在发起真实 HTTP 核验…' : '重算本地核验状态…');
  const res = await api(`/api/claims/verify?enable_web=${web}`, { method: 'POST' });
  toast(`核验完成：verified ${res.verified} / unverified ${res.unverified}`);
  await renderEvidence();
}

/* ---------------- score ---------------- */
async function renderScore() {
  if (!state.run) { $('#view-score').innerHTML = emptyRun(); return; }
  const o = state.run.output;
  const dims = [['evidence_authority', '证据权威度', 25], ['query_relevance', '查询相关性', 20],
    ['entity_clarity', '实体清晰度', 15], ['extractability', '可抽取性', 10],
    ['market_relevance', '市场相关性', 10], ['differentiation', '差异化', 10],
    ['citation_coverage', '引用覆盖', 5], ['freshness', '时效性', 5]];
  $('#view-score').innerHTML = o.ranked_entities.map((r) => `
    <div class="card">
      <div class="card-head"><h3>#${r.rank} ${esc(r.brand)} · ${esc(r.product || '')}</h3>
        <span class="hint">${esc(r.company)}</span></div>
      <div class="score-hero">
        <div class="gauge" style="--p:${r.geo_score}"><div class="inner"><b>${r.geo_score}</b><span>/100</span></div></div>
        <div class="dim-list">${dims.map(([k, l, m]) => `
          <div class="dim"><span class="name">${l}</span>
            <span class="bar"><i style="width:${((r.score_breakdown[k] || 0) / m) * 100}%"></i></span>
            <span>${(r.score_breakdown[k] || 0).toFixed(1)}/${m}</span></div>`).join('')}
        </div>
      </div>
      <div class="grid c4" style="margin-top:14px">
        <div class="kpi"><div class="label">Evidence Coverage</div><div class="value">${pct(r.evidence_coverage)}</div></div>
        <div class="kpi"><div class="label">Confidence</div><div class="value">${pct(r.confidence)}</div></div>
        <div class="kpi"><div class="label">Uncertainty</div><div class="value">${pct(r.uncertainty)}</div></div>
        <div class="kpi"><div class="label">Citation Readiness</div><div class="value" style="font-size:18px">${esc(r.citation_readiness)}</div></div>
      </div>
      <div style="margin-top:12px"><b>风险与限制</b>
        <div class="list" style="margin-top:6px">${(r.risk || []).map((x) =>
          `<div class="list-item"><div class="risk">${esc(x)}</div></div>`).join('') || '<div class="muted">无</div>'}</div>
      </div>
    </div>`).join('') + `<div class="card"><div class="card-head"><h3>评分口径</h3></div>
      <p class="muted">${esc(o.geo_score_detail?.disclaimer || '')}</p>
      <p class="muted">动态权重（A15 反馈学习）：${esc(JSON.stringify(o.geo_score_detail?.weights_applied || {}))}</p></div>`;
}

/* ---------------- content ---------------- */
async function renderContent() {
  if (!state.run) { $('#view-content').innerHTML = emptyRun(); return; }
  const o = state.run.output;
  const contents = o.ai_answer_ready_content || [];
  $('#view-content').innerHTML = `
    <div class="card"><div class="card-head"><h3>AI Answer Ready Content</h3>
      <span class="hint">Direct Answer → Entity Definition → Specs → Use Cases → Market → Differentiation → Evidence → FAQ → CTA</span></div>
      ${contents.map((c, i) => `
        <div class="list-item" style="margin-bottom:12px">
          <div class="t"><span class="chip info">${esc(c.language)}</span>
            <span class="chip">${esc(c.market)}</span>
            <span class="chip ${c.citation_readiness === 'High' ? 'ok' : c.citation_readiness === 'Medium' ? 'warn' : 'bad'}">${esc(c.citation_readiness)}</span>
            <b>${esc(c.brand)} · ${esc(c.product)}</b></div>
          <div class="answer" style="margin-top:8px">${markdown(c.answer)}</div>
          <div class="grid c2" style="margin-top:10px">
            <div><b>Key Facts（仅已核验）</b>
              <div class="list">${(c.key_facts || []).map((f) => `<div class="list-item"><div class="t">${esc(f)}</div></div>`).join('') || '<div class="muted">无已核验证据</div>'}</div></div>
            <div><b>未核验声明（禁止对外发布为事实）</b>
              <div class="list">${(c.unverified_statements || []).map((f) =>
                `<div class="list-item"><div class="risk">${esc(f.claim)}</div><div class="m">${esc(f.status)} · ${esc(f.note)}</div></div>`).join('') || '<div class="muted">无</div>'}</div></div>
          </div>
        </div>`).join('') || '<div class="empty">暂无内容</div>'}
    </div>
    <div class="card">
      <div class="card-head"><h3>本地化（A11）</h3><span class="hint">按市场与买家角色重构语言，非机翻直译</span></div>
      <div class="grid c3">${(o.localization?.packages || []).map((p) => `
        <div class="list-item"><div class="t">${esc(p.language_name)} · ${esc(p.market)}</div>
          <div class="m">${esc(p.compliance_note)}</div>
          <div class="m">${(p.local_terms || []).map((t) => `<span class="chip">${esc(t)}</span>`).join('')}</div>
          <div class="m">状态：${p.human_review_required ? '需母语审校' : 'ready'}</div></div>`).join('')}</div>
    </div>
    <div class="card">
      <div class="card-head"><h3>JSON-LD Schema（A10）</h3><span class="hint">仅已核验 Claim 进入 Schema</span></div>
      <pre>${esc(JSON.stringify(o.schema?.schema || {}, null, 2))}</pre>
      <p class="muted" style="margin-top:8px">被排除的 Claim：${(o.schema?.excluded_claims || []).map((x) => esc(x.claim)).join('；') || '无'}</p>
    </div>`;
}

/* ---------------- competitor ---------------- */
async function renderCompetitor() {
  if (!state.run) { $('#view-competitor').innerHTML = emptyRun(); return; }
  const o = state.run.output;
  const gapCards = [['entity_gap', '实体缺口'], ['evidence_gap', '证据缺口'],
    ['content_gap', '内容缺口'], ['query_gap', '查询缺口'], ['market_gap', '市场缺口'],
    ['citation_gap', '引用缺口']];
  $('#view-competitor').innerHTML = `
    <div class="card"><div class="card-head"><h3>竞争实体矩阵</h3>
      <span class="hint">禁止贬低竞争对手 / 禁止无证据的第一、最佳、最低价、最大供应商表述</span></div>
      <table><thead><tr><th>Brand</th><th>Product</th><th>Spec</th><th>Certification</th>
        <th>Market</th><th>第三方提及</th><th>AI Visibility</th></tr></thead><tbody>
      ${(o.competitor_matrix || []).map((m) => `<tr>
        <td><b>${esc(m.brand)}</b></td><td>${esc(m.product)}</td>
        <td class="muted">${esc(m.specification)}</td>
        <td>${(m.certification || []).map((c) => `<span class="chip">${esc(c)}</span>`).join('')}</td>
        <td class="muted">${(m.market || []).join(', ')}</td>
        <td>${m.third_party_mentions}</td><td>${m.ai_visibility}</td></tr>`).join('')}
      </tbody></table></div>
    <div class="grid c3">${gapCards.map(([k, label]) => `
      <div class="card"><div class="card-head"><h3>${label}</h3><span class="hint">${(o[k] || []).length} 项</span></div>
      <div class="list">${(o[k] || []).map((g) => `<div class="list-item">
        <div class="t"><span class="chip ${g.severity === 'high' ? 'bad' : g.severity === 'medium' ? 'warn' : 'info'}">${esc(g.severity || '')}</span>${esc(g.item)}</div>
        <div class="m">${esc(g.action || '')}</div></div>`).join('') || '<div class="muted">无缺口</div>'}</div></div>`).join('')}</div>
    <div class="card"><div class="card-head"><h3>优化动作清单</h3><span class="hint">按 P0/P1/P2 排序</span></div>
      <table><thead><tr><th>优先级</th><th>类别</th><th>动作</th></tr></thead><tbody>
      ${(o.optimization_actions || []).map((a) => `<tr><td><span class="chip ${a.priority === 'P0' ? 'bad' : a.priority === 'P1' ? 'warn' : 'info'}">${a.priority}</span></td>
        <td class="muted">${esc(a.category)}</td><td>${esc(a.action)}</td></tr>`).join('')}
      </tbody></table></div>`;
}

/* ---------------- visibility ---------------- */
async function renderVisibility() {
  const d = await api('/api/monitoring/dashboard');
  const plan = state.run?.output.visibility_monitoring_plan;
  $('#view-visibility').innerHTML = `
    <div class="grid c4">
      <div class="kpi accent"><div class="label">AI Mention Rate</div><div class="value">${pct(d.ai_mention_rate)}</div><div class="sub">live ${d.live_probes} 探针</div></div>
      <div class="kpi blue"><div class="label">Citation Rate</div><div class="value">${pct(d.citation_rate)}</div></div>
      <div class="kpi"><div class="label">Entity Recognition</div><div class="value">${pct(d.entity_recognition_rate)}</div></div>
      <div class="kpi gold"><div class="label">Competitor Share of Voice</div><div class="value">${pct(d.competitor_share_of_voice)}</div><div class="sub">simulated ${d.simulated_probes}</div></div>
    </div>
    <div class="card"><div class="card-head"><h3>引擎维度</h3><span class="hint">未配置 API Key 时为模拟基线，不计入真实指标</span></div>
      <table><thead><tr><th>Engine</th><th>Probes</th><th>Live</th><th>Mentions</th><th>Citations</th></tr></thead><tbody>
      ${Object.entries(d.by_engine || {}).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.probes}</td><td>${v.live}</td><td>${v.mentions}</td><td>${v.citations}</td></tr>`).join('') || '<tr><td colspan="5" class="muted">暂无探针</td></tr>'}
      </tbody></table></div>
    <div class="card"><div class="card-head"><h3>发起监测探针</h3></div>
      <div class="form-grid">
        <label class="field span2"><span>Query 列表（每行一条）</span><textarea id="pQueries" rows="3">AI server GPU supplier Hong Kong
GPU server supplier for Malaysia data center</textarea></label>
        <label class="field"><span>Market</span><input id="pMarket" value="Hong Kong" /></label>
        <label class="field"><span>Language</span><input id="pLang" value="en" /></label>
      </div>
      <div class="actions"><button class="btn primary" id="btnProbe">运行探针</button></div>
    </div>
    ${plan ? `<div class="card"><div class="card-head"><h3>监测计划</h3><span class="hint">${esc(plan.cadence || '')}</span></div>
      <div class="muted">探针组合：${plan.probe_counts?.total_probes || 0} 个（${plan.probe_counts?.queries || 0} query × ${plan.probe_counts?.engines || 0} engine）</div>
      <div class="muted">${esc(plan.note || '')}</div></div>` : ''}
    <div class="card"><div class="card-head"><h3>最近探针快照</h3></div>
      <div class="list">${(d.latest || []).map((s) => `<div class="list-item">
        <div class="t">${esc(s.query)} · ${esc(s.ai_engine)} · ${esc(s.mode)}
          ${s.brand_mention ? '<span class="chip ok">brand mentioned</span>' : ''}
          ${s.estimated ? '<span class="chip warn">estimated</span>' : ''}</div>
        <div class="m">${esc(s.market || '')} · ${esc(s.language || '')} · ${esc(s.timestamp)}
          ${s.citation_count ? `· citations ${s.citation_count}` : ''}</div></div>`).join('') || '<div class="muted">暂无快照</div>'}</div></div>`;
  $('#btnProbe').addEventListener('click', async () => {
    const queries = $('#pQueries').value.split('\n').map((s) => s.trim()).filter(Boolean);
    await api('/api/monitoring/probe', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ queries, market: $('#pMarket').value, language: $('#pLang').value }),
    });
    toast('探针完成');
    await renderVisibility();
  });
}

/* ---------------- crm ---------------- */
async function renderCrm() {
  const [leads, analytics] = await Promise.all([api('/api/leads'), api('/api/analytics')]);
  const l3 = analytics.level3_engagement, l4 = analytics.level4_revenue;
  $('#view-crm').innerHTML = `
    <div class="grid c4">
      <div class="kpi"><div class="label">Leads</div><div class="value">${leads.leads.length}</div></div>
      <div class="kpi blue"><div class="label">Inquiry → RFQ</div><div class="value">${pct(l3.inquiry_to_rfq_rate)}</div></div>
      <div class="kpi accent"><div class="label">Qualified Rate</div><div class="value">${pct(l3.qualified_rate)}</div></div>
      <div class="kpi gold"><div class="label">Orders</div><div class="value">${l4.order}</div><div class="sub">GMV ${l4.gmv}</div></div>
    </div>
    <div class="card"><div class="card-head"><h3>录入询盘（Lead Source = GEO）</h3></div>
      <div class="form-grid">
        <label class="field"><span>公司名</span><input id="lCompany" value="Demo Buyer Ltd" /></label>
        <label class="field"><span>邮箱</span><input id="lEmail" value="buyer@demo.com" /></label>
        <label class="field"><span>市场</span><input id="lMarket" value="Hong Kong" /></label>
        <label class="field"><span>产品</span><input id="lProduct" value="VX-840G" /></label>
        <label class="field"><span>数量</span><input id="lQty" value="20 units" /></label>
        <label class="field"><span>时间</span><input id="lTime" value="Q4" /></label>
        <label class="field"><span>Buyer Stage</span><select id="lStage">
          <option>Awareness</option><option>Consideration</option><option>Evaluation</option>
          <option selected>Decision</option><option>Procurement</option><option>Repeat Purchase</option></select></label>
        <label class="field"><span>AI 平台</span><input id="lAi" value="ChatGPT" /></label>
      </div>
      <div class="actions"><button class="btn primary" id="btnLead">创建询盘并判定资质</button></div>
    </div>
    <div class="card"><div class="card-head"><h3>询盘管道</h3><span class="hint">AI Answer → Website → AI Agent → Qualification → CRM → RFQ → Order</span></div>
      <table><thead><tr><th>Lead</th><th>Company</th><th>Market</th><th>Product</th><th>Stage</th><th>Score</th><th>Status</th><th>RFQ</th></tr></thead><tbody>
      ${leads.leads.map((l) => `<tr><td>${esc(l.id)}</td><td>${esc(l.contact?.company_name)}</td>
        <td>${esc(l.market)}</td><td>${esc(l.product)}</td><td>${esc(l.buyer_stage)}</td>
        <td><b>${l.qualification_score}</b></td><td>${statusChip(l.status === 'qualified' ? 'verified' : l.status === 'rfq_created' ? 'approved' : 'pending')}</td>
        <td>${l.rfq_id ? esc(l.rfq_id) : '<button class="btn small" data-rfq="' + l.id + '">生成 RFQ</button>'}</td></tr>`).join('') || '<tr><td colspan="8" class="muted">暂无询盘</td></tr>'}
      </tbody></table></div>
    <div class="card"><div class="card-head"><h3>GEO Revenue Attribution</h3></div>
      <p class="muted">${(analytics.attribution_chain || []).join(' → ')}</p>
      <pre>${esc(JSON.stringify({ level1_visibility: analytics.level1_visibility, level2_citation: analytics.level2_citation, level3_engagement: l3, level4_revenue: l4 }, null, 2))}</pre></div>`;
  $('#btnLead').addEventListener('click', async () => {
    await api('/api/leads', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_name: $('#lCompany').value, email: $('#lEmail').value,
        target_market: $('#lMarket').value, market: $('#lMarket').value,
        product: $('#lProduct').value, quantity: $('#lQty').value, timeline: $('#lTime').value,
        buyer_stage: $('#lStage').value, ai_platform: $('#lAi').value,
        intent: ['price_inquiry', 'supplier_search'], entity_id: 'ENT-VXF-001',
      }),
    });
    toast('询盘已创建');
    await renderCrm();
  });
  document.querySelectorAll('[data-rfq]').forEach((b) => b.addEventListener('click', async () => {
    await api(`/api/leads/${b.dataset.rfq}/rfq`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '[]' });
    toast('RFQ 已生成');
    await renderCrm();
  }));
}

/* ---------------- approvals ---------------- */
async function renderApproval() {
  const data = await api('/api/approvals?status=pending');
  $('#view-approval').innerHTML = `
    <div class="card"><div class="card-head"><h3>Human Approval Queue</h3>
      <span class="hint">认证 / 资质 / 案例 / 销售数据 / 排名 / 价格 / 交付 / 竞品比较 必须人工审核</span></div>
      <div class="muted">待审：${data.approvals.length} 项</div></div>
    <div class="card"><table><thead><tr><th>类别</th><th>内容</th><th>实体</th><th>状态</th><th>决策</th></tr></thead><tbody>
      ${data.approvals.map((a) => `<tr><td>${esc(a.category)}</td><td>${esc(a.content)}</td>
        <td class="muted">${esc(a.entity_id || '')}</td><td>${statusChip(a.status)}</td>
        <td><button class="btn small" data-ap="${a.id}" data-d="approved">通过</button>
            <button class="btn small" data-ap="${a.id}" data-d="rejected">驳回</button>
            <button class="btn small" data-ap="${a.id}" data-d="revision_required">需修改</button></td></tr>`).join('') || '<tr><td colspan="5" class="muted">队列为空</td></tr>'}
      </tbody></table></div>
    <div class="card"><div class="card-head"><h3>需人工审核的类别</h3></div>
      <div>${(data.required_categories || []).map((c) => `<span class="chip">${esc(c)}</span>`).join('')}</div></div>`;
  document.querySelectorAll('[data-ap]').forEach((b) => b.addEventListener('click', async () => {
    await api(`/api/approvals/${b.dataset.ap}/decision`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision: b.dataset.d, reviewer: 'console-user', note: 'console decision' }),
    });
    toast('审核已提交');
    await renderApproval();
  }));
}

/* ---------------- audit ---------------- */
async function renderAudit() {
  const data = await api('/api/audit?limit=120');
  $('#view-audit').innerHTML = `
    <div class="grid c3">
      <div class="kpi"><div class="label">审计事件</div><div class="value">${data.summary.total}</div></div>
      <div class="kpi warn"><div class="label">高风险事件</div><div class="value">${data.summary.by_risk.high || 0}</div></div>
      <div class="kpi"><div class="label">中风险事件</div><div class="value">${data.summary.by_risk.medium || 0}</div></div>
    </div>
    <div class="card"><table><thead><tr><th>时间</th><th>事件</th><th>Actor</th><th>Run</th><th>Risk</th></tr></thead><tbody>
      ${data.audit.map((a) => `<tr><td class="muted">${esc(a.timestamp)}</td><td>${esc(a.event)}</td>
        <td>${esc(a.actor)}</td><td class="muted">${esc(a.run_id || '')}</td>
        <td><span class="chip ${a.risk_level === 'high' ? 'bad' : a.risk_level === 'medium' ? 'warn' : 'info'}">${esc(a.risk_level)}</span></td></tr>`).join('')}
      </tbody></table></div>`;
}

/* ---------------- plugins ---------------- */
async function renderPlugins() {
  const st = await api('/api/plugins/redditgrow/status');
  $('#view-plugins').innerHTML = `
    <div class="grid c3">
      <div class="kpi ${st.enabled ? 'accent' : ''}"><div class="label">RedditGrow</div>
        <div class="value">${st.enabled ? 'ON' : 'OFF'}</div><div class="sub">${esc(st.mode)}</div></div>
      <div class="kpi blue"><div class="label">传输</div><div class="value" style="font-size:14px">${esc(st.transport)}</div>
        <div class="sub">${esc(st.mcp_url)}</div></div>
      <div class="kpi"><div class="label">Webhook</div><div class="value">${st.webhook_enabled ? 'ON' : 'OFF'}</div>
        <div class="sub">HMAC-SHA256</div></div>
    </div>
    ${st.note ? `<div class="notice">${esc(st.note)}</div>` : ''}
    <div class="card"><div class="card-head"><h3>接入配置</h3>
      <span class="hint">在 redditgrow.ai → Settings → Integrations 生成 rg_live_ 开头的 API Key（Growth / Agency 套餐）</span></div>
      <div class="form-grid">
        <label class="field span2"><span>API Key</span><input id="rgKey" placeholder="rg_live_..." value="" /></label>
        <label class="field"><span>MCP URL</span><input id="rgUrl" value="${esc(st.mcp_url)}" /></label>
        <label class="field"><span>Webhook Secret</span><input id="rgSecret" placeholder="订阅 webhook 时返回的 secret" /></label>
      </div>
      <div class="muted">当前已保存 Key：${esc(st.api_key_masked || '（未配置）')} · 配置写入 Shared Context settings</div>
      <div class="actions">
        <button class="btn primary" id="btnRgSave">保存配置</button>
        <button class="btn ghost" id="btnRgStatus">重新检测</button>
      </div></div>
    <div class="card"><div class="card-head"><h3>拉取 Reddit 机会并导入询盘</h3>
      <span class="hint">lead_source=RedditGrow · verification_status=unverified</span></div>
      <div class="form-grid">
        <label class="field"><span>最低机会分</span><input id="rgMin" type="number" step="0.1" value="7.0" /></label>
        <label class="field"><span>条数</span><input id="rgLimit" type="number" value="10" /></label>
        <label class="field"><span>项目 ID（可选）</span><input id="rgProject" /></label>
        <label class="field"><span>绑定实体 ID（可选）</span><input id="rgEntity" placeholder="ENT-VXF-001" /></label>
      </div>
      <div class="actions">
        <button class="btn primary" id="btnRgFetch">仅查询</button>
        <button class="btn primary" id="btnRgSync">同步为询盘</button>
        <button class="btn ghost" id="btnRgVis">AI 可见性</button>
        <button class="btn ghost" id="btnRgMentions">品牌提及</button>
      </div>
      <div id="rgOut" class="list"></div></div>
    <div class="card"><div class="card-head"><h3>可用能力（MCP tools）</h3></div>
      <div>${(st.tools || []).map((t) => `<span class="chip info">${esc(t)}</span>`).join('')}</div>
      <div class="muted">${esc(st.plan_note || '')}</div>
      <div class="muted">Webhook 接收地址：<code>/api/plugins/redditgrow/webhook</code>（签名头 X-RedditGrow-Signature）</div></div>`;

  $('#btnRgSave').addEventListener('click', async () => {
    await api('/api/plugins/redditgrow/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: $('#rgKey').value || undefined,
        mcp_url: $('#rgUrl').value || undefined,
        webhook_secret: $('#rgSecret').value || undefined,
      }),
    });
    toast('配置已保存');
    await renderPlugins();
  });
  $('#btnRgStatus').addEventListener('click', async () => { await renderPlugins(); });

  const rgBody = () => JSON.stringify({
    min_score: Number($('#rgMin').value || 7),
    limit: Number($('#rgLimit').value || 10),
    project_id: $('#rgProject').value || undefined,
    entity_id: $('#rgEntity').value || undefined,
  });
  const post = (path, body) => api(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body,
  });

  $('#btnRgFetch').addEventListener('click', async () => {
    const r = await post('/api/plugins/redditgrow/opportunities', rgBody());
    renderRgOut(r);
  });
  $('#btnRgSync').addEventListener('click', async () => {
    const r = await post('/api/plugins/redditgrow/sync', rgBody());
    renderRgOut(r);
    toast(`已导入 ${r.imported || 0} 条`);
  });
  $('#btnRgVis').addEventListener('click', async () => {
    renderRgOut(await post('/api/plugins/redditgrow/ai-visibility',
      JSON.stringify({ project_id: $('#rgProject').value || undefined })));
  });
  $('#btnRgMentions').addEventListener('click', async () => {
    renderRgOut(await post('/api/plugins/redditgrow/mentions', '{}'));
  });
}

function renderRgOut(r) {
  const items = r.opportunities || r.leads || [];
  $('#rgOut').innerHTML = `
    <div class="list-item"><div class="t">mode: ${esc(r.mode || r.result?.mode || 'n/a')}</div>
      <div class="m">${esc(r.note || r.error || r.result?.note || '')}</div></div>
    ${items.length ? items.map((o) => `<div class="list-item">
      <div class="t">${esc(o.query || o.title || o.id)}</div>
      <div class="m">${esc(o.metadata?.subreddit || o.subreddit || '')} ·
        score ${o.metadata?.opportunity_score ?? o.score ?? '-'} · ${esc(o.buyer_stage || '')}
        ${o.qualification_score != null ? `· 资质 ${o.qualification_score}` : ''}</div></div>`).join('')
      : `<div class="muted">无数据${r.mode === 'disabled' ? '（插件未启用）' : ''}</div>`}
    ${r.result?.error ? `<pre>${esc(String(r.result.error))}</pre>` : ''}`;
}

/* ---------------- system settings ---------------- */
async function renderSettings() {
  const s = await api('/api/settings');
  const llm = s.llm || {};
  const providers = llm.providers || [];
  const locals = Object.values(s.local || {});
  const readyCli = locals.filter((c) => c.ready).length;

  const row = (p) => `<tr>
    <td><b>${esc(p.name)}</b>
      ${p.is_default ? '<span class="chip ok">默认</span>' : ''}
      ${p.builtin ? '<span class="chip">内置</span>' : ''}</td>
    <td>${esc(p.type)}</td>
    <td>${esc(p.base_url || '—')}</td>
    <td>${esc(p.model || '—')}</td>
    <td>${esc(p.api_key_masked || '—')} <span class="muted">${esc(p.key_source || '')}</span></td>
    <td>${!p.enabled ? '<span class="chip">停用</span>'
      : (p.ready ? '<span class="chip ok">可用</span>' : '<span class="chip warn">缺 Key</span>')}</td>
    <td>
      <button class="btn small" data-act="default" data-id="${esc(p.id)}">设为默认</button>
      <button class="btn small ghost" data-act="toggle" data-id="${esc(p.id)}">${p.enabled ? '停用' : '启用'}</button>
      <button class="btn small ghost" data-act="test" data-id="${esc(p.id)}">测试</button>
      <button class="btn small ghost" data-act="edit" data-id="${esc(p.id)}">编辑</button>
      ${p.builtin ? '' : `<button class="btn small ghost" data-act="del" data-id="${esc(p.id)}">删除</button>`}
    </td></tr>`;

  const cliCard = (c) => `<div class="card cli-card" data-cli="${esc(c.id)}">
    <div class="card-head"><h3>${esc(c.name)} 本地接入</h3><span class="hint">${esc(c.desc)}</span></div>
    <div class="form-grid">
      <label class="field"><span>可执行文件 / 命令</span>
        <input data-f="command" value="${esc(c.command)}" placeholder="${esc(c.command)}" /></label>
      <label class="field"><span>探测参数</span><input data-f="probe_args" value="${esc(c.probe_args)}" /></label>
      <label class="field"><span>工作目录（可选）</span>
        <input data-f="workdir" value="${esc(c.workdir)}" placeholder="/Users/…" /></label>
      <label class="field"><span>超时（秒）</span>
        <input data-f="timeout" type="number" min="1" max="120" value="${Number(c.timeout) || 20}" /></label>
    </div>
    <div class="checks" style="margin-top:10px">
      <label><input type="checkbox" data-f="enabled" ${c.enabled ? 'checked' : ''} /> 启用 ${esc(c.name)} 本地连接器</label>
    </div>
    <div class="muted">解析路径：${esc(c.resolved || '未找到可执行文件')}</div>
    <div class="muted">${esc(c.install_hint || '')}</div>
    <div>${(c.capabilities || []).map((x) => `<span class="chip info">${esc(x)}</span>`).join('')}
      ${c.last_probe ? `<span class="muted">上次探测 ${esc(c.last_probe.at)} ${c.last_probe.ok ? '成功' : '失败'}</span>` : ''}</div>
    <div class="form-grid" style="margin-top:10px">
      <label class="field span2"><span>执行参数（可选；不启用 shell，参数按 shlex 解析）</span>
        <input data-f="args" placeholder="run --task …" /></label>
    </div>
    <div class="actions">
      <button class="btn primary" data-act="save">保存配置</button>
      <button class="btn ghost" data-act="probe">测试连接</button>
      <button class="btn ghost" data-act="run">执行</button>
    </div>
    <pre data-f="out" hidden></pre>
  </div>`;

  $('#view-settings').innerHTML = `
    <div class="grid c3">
      <div class="kpi ${llm.active ? 'accent' : ''}"><div class="label">默认大模型</div>
        <div class="value" style="font-size:16px">${esc(llm.active?.name || '未启用')}</div>
        <div class="sub">${esc(llm.active?.model || '规则化引擎 · 无 Key 也可完整运行')}</div></div>
      <div class="kpi blue"><div class="label">已配置提供商</div><div class="value">${providers.length}</div>
        <div class="sub">可用 ${providers.filter((p) => p.ready).length} · 启用 ${providers.filter((p) => p.enabled).length}</div></div>
      <div class="kpi"><div class="label">本地 CLI</div><div class="value">${readyCli}/${locals.length}</div>
        <div class="sub">OpenClaw · AnyGen · WorkBuddy</div></div>
    </div>
    ${llm.note ? `<div class="notice">${esc(llm.note)}</div>` : ''}

    <div class="card">
      <div class="card-head"><h3>自定义大模型提供商</h3>
        <span class="hint">Key 只保存在本机 Shared Context，接口仅返回掩码</span></div>
      <table><thead><tr><th>名称</th><th>类型</th><th>Base URL</th><th>模型</th><th>Key</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>${providers.map(row).join('')}</tbody></table>
    </div>

    <div class="card">
      <div class="card-head"><h3>新增 / 编辑提供商</h3>
        <span class="hint">OpenAI 兼容网关填写完整 base_url，例：https://api.deepseek.com/v1</span></div>
      <div class="form-grid">
        <label class="field"><span>标识 ID（留空自动生成）</span><input id="llmId" placeholder="custom-deepseek" /></label>
        <label class="field"><span>名称</span><input id="llmName" placeholder="DeepSeek" /></label>
        <label class="field"><span>类型</span><select id="llmType">
          ${(llm.types || ['openai', 'openai_compatible', 'anthropic']).map((t) =>
            `<option value="${esc(t)}" ${t === 'openai_compatible' ? 'selected' : ''}>${esc(t)} — ${esc((llm.type_hints || {})[t] || '')}</option>`).join('')}
        </select></label>
        <label class="field"><span>Base URL</span><input id="llmBase" placeholder="https://api.deepseek.com/v1" /></label>
        <label class="field"><span>模型</span><input id="llmModel" placeholder="deepseek-chat" /></label>
        <label class="field"><span>API Key</span><input id="llmKey" type="password" placeholder="sk-…" /></label>
        <label class="field"><span>环境变量名（Key 留空时使用）</span><input id="llmEnv" placeholder="DEEPSEEK_API_KEY" /></label>
      </div>
      <div class="actions">
        <button class="btn primary" id="btnLlmSave">保存</button>
        <button class="btn ghost" id="btnLlmTest">测试连接</button>
        <button class="btn ghost" id="btnLlmClear">清空表单</button>
      </div>
      <pre id="llmOut" hidden></pre>
    </div>

    <div class="card"><div class="card-head"><h3>本地 CLI 接入</h3>
      <span class="hint">全部在本机执行（shell=False，参数经 shlex 解析）· 产出标记 unverified，需人工审核</span></div>
      <div class="grid c1">${locals.map(cliCard).join('')}</div></div>`;

  state.llmProviders = providers;

  const llmForm = () => ({
    id: $('#llmId').value.trim() || undefined,
    name: $('#llmName').value.trim() || undefined,
    type: $('#llmType').value,
    base_url: $('#llmBase').value.trim() || undefined,
    model: $('#llmModel').value.trim() || undefined,
    api_key: $('#llmKey').value.trim() || undefined,
    env_var: $('#llmEnv').value.trim() || undefined,
  });
  const postJson = (path, obj, method = 'POST') => api(path, {
    method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj),
  });

  $('#btnLlmSave').addEventListener('click', async () => {
    const body = llmForm();
    if (!body.id && !body.name) { toast('请填写名称或 ID'); return; }
    await postJson('/api/settings/llm/providers', body);
    toast('提供商已保存');
    await renderSettings();
  });
  $('#btnLlmTest').addEventListener('click', async () => {
    const r = await postJson('/api/settings/llm/test', llmForm());
    const out = $('#llmOut');
    out.hidden = false;
    out.textContent = JSON.stringify(r, null, 2).slice(0, 4000);
    toast(r.ok ? '连接成功' : '连接失败：' + (r.error || '未知错误'));
  });
  $('#btnLlmClear').addEventListener('click', async () => {
    ['#llmId', '#llmName', '#llmBase', '#llmModel', '#llmKey', '#llmEnv']
      .forEach((s) => { $(s).value = ''; });
    $('#llmOut').hidden = true;
  });

  $('#view-settings').querySelectorAll('tbody [data-act]').forEach((btn) =>
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id;
      const act = btn.dataset.act;
      try {
        if (act === 'edit') {
          const p = (state.llmProviders || []).find((x) => x.id === id);
          if (!p) return;
          $('#llmId').value = p.id;
          $('#llmName').value = p.name || '';
          $('#llmType').value = p.type;
          $('#llmBase').value = p.base_url || '';
          $('#llmModel').value = p.model || '';
          $('#llmEnv').value = p.env_var || '';
          $('#llmKey').value = '';
          toast('已载入，填写 Key 后保存');
          return;
        }
        if (act === 'default') { await postJson('/api/settings/llm/default', { provider_id: id }); }
        if (act === 'toggle') {
          const p = (state.llmProviders || []).find((x) => x.id === id);
          await postJson('/api/settings/llm/providers', { id, enabled: !p.enabled });
        }
        if (act === 'test') {
          const r = await postJson('/api/settings/llm/test', { id });
          const out = $('#llmOut');
          out.hidden = false;
          out.textContent = JSON.stringify(r, null, 2).slice(0, 4000);
          toast(r.ok ? `${r.provider} 连接成功` : '连接失败：' + (r.error || '未知错误'));
          return;
        }
        if (act === 'del') {
          await api(`/api/settings/llm/providers/${encodeURIComponent(id)}`, { method: 'DELETE' });
        }
        await renderSettings();
      } catch (e) { toast('操作失败：' + e.message); }
    }));

  document.querySelectorAll('.cli-card').forEach((card) => {
    const cid = card.dataset.cli;
    const val = (f) => {
      const el = card.querySelector(`[data-f="${f}"]`);
      return el.type === 'checkbox' ? el.checked : el.value;
    };
    card.querySelectorAll('[data-act]').forEach((btn) => btn.addEventListener('click', async () => {
      const act = btn.dataset.act;
      try {
        if (act === 'save') {
          await postJson(`/api/settings/local/${cid}`, {
            enabled: val('enabled'), command: val('command').trim() || undefined,
            probe_args: val('probe_args').trim() || undefined,
            workdir: val('workdir').trim() || undefined,
            timeout: Number(val('timeout')) || 20,
          });
          toast('配置已保存');
          await renderSettings();
          return;
        }
        const result = act === 'probe'
          ? await api(`/api/settings/local/${cid}/probe`, { method: 'POST' })
          : await postJson(`/api/settings/local/${cid}/run`, { args: val('args') });
        if (act === 'probe') { await renderSettings(); }
        const card2 = document.querySelector(`.cli-card[data-cli="${cid}"]`);
        const out = card2.querySelector('[data-f="out"]');
        out.hidden = false;
        out.textContent = JSON.stringify(result, null, 2).slice(0, 4000);
        toast(result.ok ? `${result.name} 执行成功` : `${result.name} 失败：${result.error || 'exit ' + result.exit_code}`);
      } catch (e) { toast('操作失败：' + e.message); }
    }));
  });
}

/* ---------------- architecture ---------------- */
function renderArch() {
  const agents = [
    ['A01', 'Intent Intelligence', '识别真实采购意图与买家阶段'],
    ['A02', 'Market Intelligence', '国家/合规/术语/采购行为'],
    ['A03', 'Query Expansion', '10 类 Query Matrix'],
    ['A04', 'Candidate Retrieval', '向量+图谱+实体+证据+Web 混合召回'],
    ['A05', 'Entity Intelligence', '实体解析与清晰度'],
    ['A06', 'Evidence Verification', 'Claim→Evidence→Source 核验'],
    ['A07', 'GEO Scoring', '8 维度 100 分'],
    ['A08', 'Competitor Intelligence', '竞争矩阵与五类 Gap'],
    ['A09', 'AI Answer Optimization', 'AI Answer Ready Content'],
    ['A10', 'Schema & KG', 'JSON-LD 与知识图谱关系'],
    ['A11', 'Localization', '9 语言本地化重构'],
    ['A12', 'AI Visibility Monitoring', '可见性与引用监测'],
    ['A13', 'Lead Conversion', 'GEO→询盘→RFQ'],
    ['A14', 'GEO Analytics', '四层指标与收入归因'],
    ['A15', 'Feedback Learning', '反馈闭环与权重调优'],
  ];
  const steps = ['01 用户Query', '02 Intent', '03 Market', '04 Query Expansion', '05 Retrieval',
    '06 Entity', '07 Evidence', '08 GEO Score', '09 Competitor Gap', '10 Content',
    '11 Schema', '12 Monitoring', '13 Inquiry', '14 CRM', '15 RFQ', '16 Order',
    '17 Revenue Attribution', '18 Feedback', '19 再优化'];
  $('#view-arch').innerHTML = `
    <div class="card"><div class="card-head"><h3>系统定位</h3></div>
      <p class="muted">面向全球 B2B 企业、产业带、制造商、品牌商与跨境供应商的 <b>AI 搜索可见性、实体权威建设、生成式推荐优化与询盘转化基础设施</b>。
      系统不是传统 SEO 工具，而是「产业知识图谱 + AI 搜索 + GEO + Agent + CRM + 商业数据闭环」驱动的全球 B2B AI 获客基础设施。</p>
      <p class="muted">支持：ChatGPT / Gemini / Perplexity / Google AI Overviews / Microsoft Copilot / Claude 等具备搜索或 RAG 能力的生成式 AI 系统。</p>
    </div>
    <div class="card"><div class="card-head"><h3>19 步自动化闭环</h3></div>
      <div>${steps.map((s) => `<span class="chip info">${esc(s)}</span>`).join('')}</div></div>
    <div class="card"><div class="card-head"><h3>Agent Cluster</h3></div>
      <div class="grid c3">${agents.map(([id, name, desc]) =>
        `<div class="list-item"><div class="t"><b>${id}</b> ${name}</div><div class="m">${desc}</div></div>`).join('')}</div></div>
    <div class="card"><div class="card-head"><h3>核心原则</h3></div>
      <div class="grid c2">
        <div class="list-item"><div class="t">Evidence First</div><div class="m">Tier1 官方 → Tier2 政府/认证/协会 → Tier3 行业媒体 → Tier4 社区 → Tier5 UGC；禁止编造认证/客户/产能/市场份额</div></div>
        <div class="list-item"><div class="t">Shared Context</div><div class="m">所有 Agent 共享同一 Context，不得建立孤立事实库</div></div>
        <div class="list-item"><div class="t">Human-in-the-loop</div><div class="m">认证、资质、案例、销售数据、排名、竞品比较、价格与交付承诺必须人工审核</div></div>
        <div class="list-item"><div class="t">相关性优先于关键词</div><div class="m">证据优先于宣传；实体优先于流量；真实业务数据优先于虚假排名</div></div>
      </div></div>`;
}

boot();
