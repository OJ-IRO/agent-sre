"""Agent SRE judge-facing dashboard.

FastAPI app that:
  - Serves a Mission-Control-style HTML dashboard at /
  - Streams the 8-phase pipeline as Server-Sent Events at /api/run
  - Health check at /healthz for Cloud Run

Run locally:    uv run uvicorn dashboard.server:app --host 0.0.0.0 --port 8080
Or via Make:    make serve-dashboard
"""
from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from sse_starlette.sse import EventSourceResponse

from dashboard.runner import run_pipeline

app = FastAPI(title="Agent SRE")


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz() -> str:
    return "ok"


@app.get("/api/run")
async def api_run(request: Request):
    """SSE stream of pipeline events. Each click of 'Run' starts a fresh run."""

    async def event_generator() -> AsyncGenerator[dict, None]:
        async for event in run_pipeline():
            if await request.is_disconnected():
                break
            yield {"event": event.get("type", "message"), "data": json.dumps(event)}

    return EventSourceResponse(event_generator())


@app.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
    return HTMLResponse(content=INDEX_HTML)


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Agent SRE — Mission Control</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  :root {
    --bg: #050608;
    --panel: #0d1117;
    --panel-2: #161b22;
    --gridline: rgba(120, 160, 200, 0.08);
    --teal: #00d9ff;
    --teal-soft: rgba(0, 217, 255, 0.18);
    --green: #2dffa6;
    --amber: #ffc857;
    --red: #ff5c5c;
    --text: #e6edf3;
    --muted: #7d8590;
  }
  * { box-sizing: border-box; }
  body {
    background:
      radial-gradient(800px 400px at 10% 0%, rgba(0,217,255,0.06), transparent 60%),
      radial-gradient(700px 400px at 100% 100%, rgba(255,92,92,0.04), transparent 60%),
      var(--bg);
    color: var(--text);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    min-height: 100vh;
    margin: 0;
  }
  .mono { font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace; }
  .panel {
    background: var(--panel);
    border: 1px solid var(--gridline);
    border-radius: 10px;
  }
  .panel-glow { box-shadow: 0 0 0 1px var(--teal-soft), 0 0 40px -10px var(--teal-soft); }
  .gridline { border-color: var(--gridline); }
  .pulse-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--teal);
    box-shadow: 0 0 12px var(--teal);
    animation: pulse 1.4s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 0.4; transform: scale(0.9); }
    50% { opacity: 1; transform: scale(1.1); }
  }
  .sev-high   { background: rgba(255,92,92,0.12);  color: #ff8585; border: 1px solid rgba(255,92,92,0.35); }
  .sev-medium { background: rgba(255,200,87,0.10); color: #ffd17a; border: 1px solid rgba(255,200,87,0.35); }
  .sev-low    { background: rgba(45,255,166,0.08); color: #6effc4; border: 1px solid rgba(45,255,166,0.35); }
  .badge {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 2px 10px; border-radius: 999px;
    font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase;
    font-family: 'JetBrains Mono', monospace;
  }
  .phase-card {
    transition: all 280ms ease;
  }
  .phase-card.active { border-color: var(--teal); box-shadow: 0 0 0 1px var(--teal-soft), 0 0 25px -8px var(--teal-soft); }
  .phase-card.done { border-color: rgba(45,255,166,0.35); }
  .phase-card.error { border-color: rgba(255,92,92,0.55); }
  .score-bar {
    height: 8px; background: var(--panel-2); border-radius: 4px; overflow: hidden;
  }
  .score-bar-fill {
    height: 100%; background: linear-gradient(90deg, var(--teal), var(--green));
    transition: width 700ms cubic-bezier(0.16, 1, 0.3, 1);
  }
  .score-bar-fill.bad { background: linear-gradient(90deg, var(--red), var(--amber)); }
  .grid-bg {
    background-image:
      linear-gradient(var(--gridline) 1px, transparent 1px),
      linear-gradient(90deg, var(--gridline) 1px, transparent 1px);
    background-size: 32px 32px;
  }
  button.run-btn {
    background: linear-gradient(135deg, #00d9ff 0%, #0ea5e9 100%);
    color: #001218;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    transition: transform 120ms ease, box-shadow 120ms ease;
    box-shadow: 0 0 0 1px rgba(0,217,255,0.4), 0 8px 30px -8px rgba(0,217,255,0.5);
  }
  button.run-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 0 0 1px rgba(0,217,255,0.6), 0 12px 40px -10px rgba(0,217,255,0.7); }
  button.run-btn:disabled { opacity: 0.55; cursor: not-allowed; }
  .delta-pos { color: var(--green); }
  .delta-neg { color: var(--red); }
  .stream-line {
    font-family: 'JetBrains Mono', monospace; font-size: 12.5px;
    color: var(--muted); padding: 4px 0;
    border-bottom: 1px dashed var(--gridline);
    animation: fade-in 280ms ease;
  }
  .stream-line .ok { color: var(--green); }
  .stream-line .fail { color: var(--red); }
  @keyframes fade-in { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: none; } }
  .num-readout { font-family: 'JetBrains Mono', monospace; font-weight: 700; }
</style>
</head>
<body>

<header class="border-b gridline px-8 py-5 grid-bg">
  <div class="max-w-7xl mx-auto flex items-center justify-between">
    <div>
      <div class="text-xs mono uppercase tracking-widest" style="color: var(--teal);">Agent SRE · Mission Control</div>
      <h1 class="text-2xl font-bold mt-1">Autonomous Site Reliability Engineer for AI Agents</h1>
    </div>
    <div class="flex items-center gap-3 text-sm mono" style="color: var(--muted);">
      <div class="pulse-dot"></div>
      <div id="status-text">IDLE</div>
    </div>
  </div>
</header>

<main class="max-w-7xl mx-auto px-8 py-8">

  <!-- Hero / run button -->
  <section class="panel p-6 mb-6 panel-glow">
    <div class="flex items-center justify-between gap-6 flex-wrap">
      <div class="max-w-xl">
        <div class="text-xs mono uppercase tracking-widest" style="color: var(--teal);">Target: Match2026 Travel Co</div>
        <h2 class="text-lg font-semibold mt-1">Observe production traces. Cluster failures. Ship the fix. Never sleep.</h2>
        <p class="text-sm mt-2" style="color: var(--muted);">
          Click <strong style="color: var(--teal);">Run</strong> to launch the 8-phase autonomous loop against live Phoenix traces from the demo target agent.
          Watch Agent SRE discover failures, synthesize adversarial evals, propose a prompt fix, and validate the delta — all without human input.
        </p>
      </div>
      <button id="run-btn" class="run-btn px-6 py-3 rounded-lg text-sm">▶  Run Agent SRE</button>
    </div>
  </section>

  <div class="grid grid-cols-12 gap-6">

    <!-- Phase pipeline (left, 8 cards) -->
    <section class="col-span-12 lg:col-span-7 space-y-3">
      <h3 class="text-xs mono uppercase tracking-widest mb-2" style="color: var(--muted);">Pipeline</h3>
      <div id="phases" class="space-y-3">
        <!-- Phase cards injected by JS -->
      </div>
    </section>

    <!-- Right column: clusters + scores + ship -->
    <section class="col-span-12 lg:col-span-5 space-y-6">

      <!-- Failure clusters -->
      <div class="panel p-5">
        <h3 class="text-xs mono uppercase tracking-widest mb-3" style="color: var(--muted);">Failure clusters discovered</h3>
        <div id="clusters" class="space-y-2 text-sm">
          <div class="mono" style="color: var(--muted);">— waiting for Phase 2 —</div>
        </div>
      </div>

      <!-- Score panel -->
      <div class="panel p-5">
        <h3 class="text-xs mono uppercase tracking-widest mb-3" style="color: var(--muted);">Validation score</h3>
        <div class="space-y-3">
          <div>
            <div class="flex justify-between text-xs mono mb-1"><span>BEFORE</span><span id="score-before" class="num-readout">—</span></div>
            <div class="score-bar"><div id="bar-before" class="score-bar-fill bad" style="width: 0%;"></div></div>
          </div>
          <div>
            <div class="flex justify-between text-xs mono mb-1"><span>AFTER</span><span id="score-after" class="num-readout">—</span></div>
            <div class="score-bar"><div id="bar-after" class="score-bar-fill" style="width: 0%;"></div></div>
          </div>
          <div class="flex justify-between items-center pt-2 border-t gridline">
            <span class="text-xs mono uppercase" style="color: var(--muted);">Delta</span>
            <span id="score-delta" class="num-readout text-2xl">—</span>
          </div>
        </div>
      </div>

      <!-- Ship decision -->
      <div class="panel p-5">
        <h3 class="text-xs mono uppercase tracking-widest mb-3" style="color: var(--muted);">Ship decision</h3>
        <div id="ship" class="text-sm">
          <div class="mono" style="color: var(--muted);">— waiting for Phase 7 —</div>
        </div>
      </div>

    </section>
  </div>

  <!-- Activity stream (full width) -->
  <section class="panel p-5 mt-6">
    <h3 class="text-xs mono uppercase tracking-widest mb-3" style="color: var(--muted);">Activity stream</h3>
    <div id="stream" class="max-h-80 overflow-y-auto"></div>
  </section>

  <footer class="mt-10 text-center text-xs mono" style="color: var(--muted);">
    Built with Google ADK · Gemini · Arize Phoenix MCP · Cloud Run
  </footer>
</main>

<script>
  const PHASES = [
    {id: 1, name: 'Observe',        desc: 'Pull recent production spans from Phoenix'},
    {id: 2, name: 'Cluster',        desc: 'Group failures into root-cause patterns'},
    {id: 3, name: 'Diagnose',       desc: 'Form hypotheses with cited trace IDs'},
    {id: 4, name: 'Synthesize',     desc: 'Generate adversarial evals into a Phoenix dataset'},
    {id: 5, name: 'Propose Fix',    desc: 'Draft a targeted prompt revision'},
    {id: 6, name: 'Validate',       desc: 'Run before/after via Gemini-as-judge'},
    {id: 7, name: 'Ship',           desc: 'Tag prompt production + draft postmortem'},
    {id: 8, name: 'Drift Watch',    desc: 'Re-validate on schedule. Re-enter if it slips'},
  ];

  function renderPhases() {
    const el = document.getElementById('phases');
    el.innerHTML = PHASES.map(p => `
      <div class="panel phase-card p-4 flex items-start gap-4" id="phase-${p.id}">
        <div class="mono num-readout text-2xl w-10 text-right" style="color: var(--muted);">${p.id}</div>
        <div class="flex-1">
          <div class="flex items-center justify-between gap-2">
            <div class="font-semibold text-base">${p.name}</div>
            <span class="badge" id="phase-${p.id}-status" style="color: var(--muted); border:1px solid var(--gridline);">PENDING</span>
          </div>
          <div class="text-xs mt-0.5" style="color: var(--muted);">${p.desc}</div>
          <div class="text-xs mono mt-2" id="phase-${p.id}-summary" style="color: var(--text);"></div>
        </div>
      </div>
    `).join('');
  }
  renderPhases();

  const sevClass = s => 'sev-' + s;
  function pushStream(text, klass='') {
    const stream = document.getElementById('stream');
    const div = document.createElement('div');
    div.className = 'stream-line';
    div.innerHTML = text;
    stream.appendChild(div);
    stream.scrollTop = stream.scrollHeight;
  }
  function setPhase(id, state, summary) {
    const card = document.getElementById('phase-' + id);
    const status = document.getElementById('phase-' + id + '-status');
    if (!card || !status) return;
    card.classList.remove('active', 'done', 'error');
    if (state === 'running') {
      card.classList.add('active');
      status.textContent = 'RUNNING';
      status.style.color = 'var(--teal)';
      status.style.borderColor = 'var(--teal)';
    } else if (state === 'done') {
      card.classList.add('done');
      status.textContent = 'DONE';
      status.style.color = 'var(--green)';
      status.style.borderColor = 'rgba(45,255,166,0.4)';
    } else if (state === 'error') {
      card.classList.add('error');
      status.textContent = 'ERROR';
      status.style.color = 'var(--red)';
      status.style.borderColor = 'var(--red)';
    }
    if (summary) document.getElementById('phase-' + id + '-summary').textContent = summary;
  }
  function setStatus(text, color='var(--teal)') {
    const el = document.getElementById('status-text');
    el.textContent = text;
    el.style.color = color;
  }

  document.getElementById('run-btn').addEventListener('click', () => {
    // Reset UI
    PHASES.forEach(p => setPhase(p.id, 'pending'));
    document.getElementById('clusters').innerHTML = '<div class="mono" style="color: var(--muted);">— waiting for Phase 2 —</div>';
    document.getElementById('ship').innerHTML = '<div class="mono" style="color: var(--muted);">— waiting for Phase 7 —</div>';
    document.getElementById('stream').innerHTML = '';
    document.getElementById('score-before').textContent = '—';
    document.getElementById('score-after').textContent = '—';
    document.getElementById('score-delta').textContent = '—';
    document.getElementById('score-delta').className = 'num-readout text-2xl';
    document.getElementById('bar-before').style.width = '0%';
    document.getElementById('bar-after').style.width = '0%';

    const btn = document.getElementById('run-btn');
    btn.disabled = true;
    btn.textContent = '⋯ RUNNING';
    setStatus('RUNNING', 'var(--teal)');

    let clustersList = [];

    const es = new EventSource('/api/run');

    es.addEventListener('pipeline_start', () => {
      pushStream('<span class="ok">Pipeline started.</span>');
    });
    es.addEventListener('phase_start', (e) => {
      const d = JSON.parse(e.data);
      setPhase(d.phase, 'running');
      pushStream('▶ Phase ' + d.phase + ' — ' + d.name);
    });
    es.addEventListener('phase_complete', (e) => {
      const d = JSON.parse(e.data);
      setPhase(d.phase, 'done', d.summary || '');
      pushStream('<span class="ok">✓</span> Phase ' + d.phase + ' — ' + (d.summary || 'done'));
    });
    es.addEventListener('cluster_found', (e) => {
      const d = JSON.parse(e.data);
      clustersList.push(d);
      const html = clustersList.map(c => `
        <div class="flex items-start gap-2">
          <span class="badge ${sevClass(c.severity)}">${c.severity}</span>
          <div class="flex-1">
            <div class="font-medium">${c.label} <span class="mono text-xs" style="color: var(--muted);">(n=${c.count})</span></div>
            <div class="text-xs mt-0.5" style="color: var(--muted);">${c.description || ''}</div>
          </div>
        </div>
      `).join('');
      document.getElementById('clusters').innerHTML = html;
      pushStream('<span class="ok">●</span> Cluster: <b>' + c.label + '</b> (' + c.severity + ', n=' + c.count + ')');
    });
    es.addEventListener('diagnosis_done', (e) => {
      const d = JSON.parse(e.data);
      pushStream('🔬 Diagnosed <b>' + d.cluster_label + '</b> — ' + d.eval_cases_generated + ' adversarial cases');
    });
    es.addEventListener('candidate_proposed', (e) => {
      const d = JSON.parse(e.data);
      pushStream('✎ Candidate prompt drafted (' + d.prompt_length_chars + ' chars)');
    });
    es.addEventListener('validation_case', (e) => {
      const d = JSON.parse(e.data);
      const o = d.original_passed ? '<span class="ok">✓</span>' : '<span class="fail">✗</span>';
      const c = d.candidate_passed ? '<span class="ok">✓</span>' : '<span class="fail">✗</span>';
      const flag = d.verdict === 'FIXED' ? ' <span class="ok">[FIXED]</span>' :
                   d.verdict === 'REGRESSED' ? ' <span class="fail">[REGRESSED]</span>' : '';
      pushStream('Case ' + d.case_idx + ': ' + o + '→' + c + flag + ' &nbsp;' + d.input.slice(0, 70));
    });
    es.addEventListener('validation_complete', (e) => {
      const d = JSON.parse(e.data);
      const fmt = pct => Math.round(pct * 100) + '%';
      document.getElementById('score-before').textContent = fmt(d.before);
      document.getElementById('score-after').textContent = fmt(d.after);
      document.getElementById('bar-before').style.width = (d.before * 100) + '%';
      document.getElementById('bar-after').style.width = (d.after * 100) + '%';
      const dEl = document.getElementById('score-delta');
      dEl.textContent = (d.delta >= 0 ? '+' : '') + fmt(d.delta);
      dEl.className = 'num-readout text-2xl ' + (d.delta >= 0 ? 'delta-pos' : 'delta-neg');
    });
    es.addEventListener('ship_decision', (e) => {
      const d = JSON.parse(e.data);
      const cls = d.shipped ? 'sev-low' : 'sev-medium';
      document.getElementById('ship').innerHTML = `
        <span class="badge ${cls}">${d.shipped ? 'SHIPPED' : 'BLOCKED'}</span>
        <div class="mt-2 text-sm">${d.reason}</div>
        ${d.postmortem_path ? '<div class="mt-2 text-xs mono" style="color: var(--muted);">Postmortem: ' + d.postmortem_path + '</div>' : ''}
      `;
      pushStream((d.shipped ? '🚀 <span class="ok">SHIPPED</span>' : '⏸ <span class="fail">NOT SHIPPED</span>') + ' — ' + d.reason);
    });
    es.addEventListener('drift_report', (e) => {
      const d = JSON.parse(e.data);
      pushStream('👁 Drift check: baseline ' + (d.baseline*100).toFixed(0) + '% → current ' + (d.current*100).toFixed(0) + '% ' + (d.regression ? '<span class="fail">[REGRESSION]</span>' : '<span class="ok">[STABLE]</span>'));
    });
    es.addEventListener('pipeline_complete', (e) => {
      setStatus('COMPLETE', 'var(--green)');
      btn.disabled = false;
      btn.textContent = '▶  Run Again';
      es.close();
      pushStream('<span class="ok">━━━ pipeline complete ━━━</span>');
    });
    es.addEventListener('pipeline_error', (e) => {
      const d = JSON.parse(e.data);
      setStatus('ERROR', 'var(--red)');
      btn.disabled = false;
      btn.textContent = '▶  Retry';
      es.close();
      pushStream('<span class="fail">⨯ ERROR: ' + d.message + '</span>');
    });
    es.onerror = () => {
      // Sometimes browsers fire onerror right before pipeline_complete; if we're already done, ignore.
      // Otherwise show as an error.
      if (btn.disabled) {
        setStatus('DISCONNECTED', 'var(--red)');
        btn.disabled = false;
        btn.textContent = '▶  Retry';
      }
      es.close();
    };
  });
</script>
</body>
</html>
"""
