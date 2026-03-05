"""Chat UI: single-page app with chat, KB selector, and document upload."""

from __future__ import annotations

API_BASE = "/api/v1"


def generate_chat_ui_html() -> str:
    """Generate standalone HTML page for the ontology chat interface."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Clarence · Ontology Assistant</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Space Grotesk', system-ui, -apple-system, sans-serif; background: #0a0a0f; color: #e8e6e3; min-height: 100vh; }}
    .font-mono {{ font-family: 'JetBrains Mono', monospace; }}
    .loading-dots span {{ animation: wave 1.2s ease-in-out infinite both; }}
    .loading-dots span:nth-child(1) {{ animation-delay: 0s; }}
    .loading-dots span:nth-child(2) {{ animation-delay: 0.15s; }}
    .loading-dots span:nth-child(3) {{ animation-delay: 0.3s; }}
    @keyframes wave {{ 0%, 60%, 100% {{ transform: translateY(0); opacity: 0.5; }} 30% {{ transform: translateY(-6px); opacity: 1; }} }}
    @keyframes pulse-glow {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.7; }} }}
    .sidebar {{ transition: transform 0.2s, width 0.2s; }}
    @media (max-width: 768px) {{
      .sidebar {{ transform: translateX(-100%); position: fixed; z-index: 50; height: 100vh; left: 0; top: 0; }}
      .sidebar.open {{ transform: translateX(0); }}
      .sidebar-overlay {{ display: none; }}
      .sidebar.open ~ .sidebar-overlay {{ display: block; position: fixed; inset: 0; background: rgba(0,0,0,0.5); backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px); z-index: 40; cursor: pointer; }}
    }}
    @media (min-width: 769px) {{
      .sidebar-overlay {{ display: none !important; }}
      .sidebar:not(.open) {{ transform: translateX(-100%); position: fixed; z-index: 50; height: 100vh; left: 0; top: 0; }}
      .sidebar.open {{ transform: translateX(0); position: relative; z-index: auto; }}
    }}
    .drop-zone.dragover {{ border-color: #ec4899; background: rgba(236, 72, 153, 0.08); box-shadow: 0 0 16px rgba(236, 72, 153, 0.35); }}
    .bubble-assistant {{ border-left: 3px solid #ec4899; transition: box-shadow 0.2s; }}
    .bubble-assistant:hover {{ box-shadow: 0 0 12px rgba(236, 72, 153, 0.08); }}
    .stat-value {{ font-family: 'JetBrains Mono', monospace; color: #ec4899; }}
    .stat-label {{ color: #8a8a94; }}
    .process-step {{ border-left: 2px solid #1a1a24; padding-left: 0.75rem; }}
    .process-step::before {{ content: '▸'; color: #ec4899; margin-right: 0.25rem; }}
    input:focus, select:focus {{ outline: none; border-color: #ec4899; box-shadow: 0 0 0 2px rgba(236, 72, 153, 0.2); }}
    .btn-send {{ background: #7521ee; }}
    .btn-send:hover:not(:disabled) {{ background: #8b3cf5; box-shadow: 0 0 16px rgba(117, 33, 238, 0.4); }}
    .link-teal {{ color: #ec4899; }}
    .link-teal:hover {{ color: #f472b6; }}
    .loading-pulse {{ animation: pulse-glow 1.5s ease-in-out infinite; }}
    .typing-pill {{ box-shadow: 0 0 12px rgba(236, 72, 153, 0.08); }}
    .status-badge.ready {{ background: rgba(236, 72, 153, 0.2); color: #ec4899; }}
    .status-badge.empty {{ background: #1a1a24; color: #8a8a94; }}
    .status-badge.processing {{ background: rgba(236, 72, 153, 0.15); color: #ec4899; animation: pulse-glow 1.5s ease-in-out infinite; }}
    .step-tag {{ padding: 0.125rem 0.5rem; border-radius: 4px; background: rgba(236, 72, 153, 0.1); color: #ec4899; font-size: 10px; }}
    .msg-enter {{ animation: fadeSlideUp 0.35s ease-out forwards; }}
    @keyframes fadeSlideUp {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  </style>
</head>
<body class="flex">
  <!-- Sidebar -->
  <aside id="sidebar" class="sidebar w-72 flex flex-col shrink-0" style="background: #14141a; border-right: 1px solid #1a1a24;">
    <div class="p-5 border-b" style="border-color: #1a1a24;">
      <h2 class="font-semibold text-lg" style="color: #e8e6e3;">Knowledge Base</h2>
      <select id="kb-select" class="mt-3 w-full rounded-md px-3 py-2.5 text-sm font-mono border transition-colors"
        style="background: #1e1e28; color: #e8e6e3; border-color: #1a1a24;">
        <option value="">-- Select or upload --</option>
      </select>
      <div class="mt-2 flex items-center gap-2">
        <span id="status-badge" class="status-badge px-2 py-0.5 rounded-full text-xs font-medium" style="background: #1a1a24; color: #8a8a94;">Empty</span>
        <p id="kb-status" class="text-xs" style="color: #8a8a94;">No knowledge base selected</p>
      </div>
    </div>
    <div class="p-5 border-b" style="border-color: #1a1a24;">
      <h2 class="font-semibold text-lg" style="color: #e8e6e3;">Add Documents</h2>
      <div id="drop-zone" class="drop-zone mt-3 border-2 border-dashed rounded-md p-6 text-center text-sm cursor-pointer transition-all"
        style="border-color: #1a1a24; color: #8a8a94;">
        <p>Drop PDF, DOCX, TXT, or MD here</p>
        <p class="mt-1 text-xs">or click to browse</p>
        <input type="file" id="file-input" class="hidden" accept=".pdf,.docx,.txt,.md">
      </div>
      <div id="upload-progress" class="mt-3 hidden">
        <div class="upload-steps flex flex-col gap-2">
          <div class="flex items-center gap-2 text-sm" style="color: #ec4899;">
            <svg class="animate-spin h-4 w-4 shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span id="upload-step-label">Chunking...</span>
          </div>
          <div class="flex gap-1">
            <span class="upload-step-dot w-2 h-1 rounded-full" data-step="0" style="background: #ec4899;"></span>
            <span class="upload-step-dot w-2 h-1 rounded-full" data-step="1" style="background: #1a1a24;"></span>
            <span class="upload-step-dot w-2 h-1 rounded-full" data-step="2" style="background: #1a1a24;"></span>
            <span class="upload-step-dot w-2 h-1 rounded-full" data-step="3" style="background: #1a1a24;"></span>
          </div>
        </div>
      </div>
      <div id="upload-error" class="mt-3 hidden text-sm" style="color: #e74c3c;"></div>
    </div>
    <div class="p-5 flex-1">
      <a href="{API_BASE}/graph/viewer" target="_blank" class="text-sm link-teal">View graph</a>
    </div>
  </aside>
  <div class="sidebar-overlay" id="sidebar-overlay" aria-hidden="true"></div>

  <!-- Ontology creation modal -->
  <div id="create-modal" class="fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/50 backdrop-blur-sm" onclick="document.getElementById('create-modal').classList.add('hidden')"></div>
    <div class="modal-content absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md rounded-lg p-6 shadow-xl" style="background: #1e1e28; border: 1px solid #1a1a24;" onclick="event.stopPropagation()">
      <h3 class="font-semibold text-lg mb-4" style="color: #e8e6e3;">Create Ontology</h3>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1" style="color: #8a8a94;">Title</label>
          <input type="text" id="modal-title" class="w-full rounded-md px-3 py-2.5 text-sm font-mono border" style="background: #14141a; color: #e8e6e3; border-color: #1a1a24;" placeholder="Ontology name">
        </div>
        <div>
          <label class="block text-sm font-medium mb-1" style="color: #8a8a94;">Description (optional)</label>
          <textarea id="modal-description" class="w-full rounded-md px-3 py-2.5 text-sm font-mono border resize-none" rows="3" style="background: #14141a; color: #e8e6e3; border-color: #1a1a24;" placeholder="Brief description of this ontology"></textarea>
        </div>
        <p id="modal-filename" class="text-xs" style="color: #8a8a94;"></p>
      </div>
      <div class="mt-6 flex gap-3 justify-end">
        <button type="button" id="modal-cancel" class="px-4 py-2 rounded-md text-sm transition-colors" style="background: #1a1a24; color: #8a8a94;">Cancel</button>
        <button type="button" id="modal-confirm" class="px-4 py-2 rounded-md text-sm font-medium text-white transition-all btn-send">Create</button>
      </div>
    </div>
  </div>

  <!-- Main chat area -->
  <main class="flex-1 flex flex-col min-h-screen">
    <header class="shrink-0 px-6 py-4 flex items-center justify-between" style="background: #14141a; border-bottom: 1px solid #1a1a24;">
      <div class="flex items-center gap-4">
        <div>
          <h1 class="font-semibold text-xl" style="color: #e8e6e3;">Clarence</h1>
          <p class="text-xs mt-0.5" style="color: #8a8a94;">Ontology Assistant</p>
        </div>
        <div id="current-ontology-pill" class="hidden px-3 py-1.5 rounded-full text-xs font-medium" style="background: rgba(236, 72, 153, 0.15); color: #ec4899; border: 1px solid rgba(236, 72, 153, 0.3);">
          <span style="color: #8a8a94;">Using:</span> <span id="current-ontology-name"></span>
        </div>
      </div>
      <button id="sidebar-toggle" class="p-2 rounded-md transition-colors flex items-center justify-center" style="color: #8a8a94;" onmouseover="this.style.background='#1e1e28'" onmouseout="this.style.background='transparent'" type="button" aria-label="Toggle sidebar">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
      </button>
    </header>

    <div id="messages" class="flex-1 overflow-y-auto p-6 space-y-5" style="scroll-behavior: smooth;">
      <div id="empty-state" class="flex flex-col items-center justify-center py-20 text-center" style="color: #8a8a94;">
        <p class="text-lg font-medium" style="color: #e8e6e3;">Ask a question about your ontology</p>
        <p class="mt-2 text-sm">Select a knowledge base and upload documents first</p>
      </div>
    </div>

    <div id="loading-indicator" class="hidden px-6 py-3">
      <div class="typing-pill flex items-center gap-3 px-4 py-2 rounded-full" style="background: #1e1e28; border: 1px solid #1a1a24; width: fit-content;">
        <div class="loading-dots flex gap-1.5 items-end">
          <span class="w-2 h-2 rounded-full" style="background: #ec4899;"></span>
          <span class="w-2 h-2 rounded-full" style="background: #7521ee;"></span>
          <span class="w-2 h-2 rounded-full" style="background: #ec4899;"></span>
        </div>
        <div class="flex items-center gap-2">
          <span id="qa-step-label" class="text-sm" style="color: #8a8a94;">Retrieving facts...</span>
          <span class="qa-step-dots flex gap-1">
            <span class="w-1.5 h-1.5 rounded-full" data-step="0" style="background: #ec4899;"></span>
            <span class="w-1.5 h-1.5 rounded-full" data-step="1" style="background: #1a1a24;"></span>
          </span>
        </div>
      </div>
    </div>

    <div class="shrink-0 p-6" style="border-top: 1px solid #1a1a24;">
      <form id="chat-form" class="flex gap-3">
        <input type="text" id="question-input" placeholder="Ask a question..." disabled
          class="flex-1 rounded-md px-4 py-3 font-mono text-sm border transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          style="background: #1e1e28; color: #e8e6e3; border-color: #1a1a24;">
        <button type="submit" id="send-btn" disabled
          class="px-5 py-3 rounded-md font-medium btn-send text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-none">
          Send
        </button>
      </form>
    </div>
  </main>

  <script>
    const API = '{API_BASE}';

    function parseError(data) {{
      if (typeof data?.detail === 'string') return data.detail;
      if (Array.isArray(data?.detail)) return data.detail.map(d => d.msg || JSON.stringify(d)).join('; ');
      return data?.detail ? String(data.detail) : 'Request failed';
    }}

    // DOM refs
    const messagesEl = document.getElementById('messages');
    const emptyState = document.getElementById('empty-state');
    const loadingIndicator = document.getElementById('loading-indicator');
    const chatForm = document.getElementById('chat-form');
    const questionInput = document.getElementById('question-input');
    const sendBtn = document.getElementById('send-btn');
    const kbSelect = document.getElementById('kb-select');
    const kbStatus = document.getElementById('kb-status');
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadProgress = document.getElementById('upload-progress');
    const uploadError = document.getElementById('upload-error');
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const statusBadge = document.getElementById('status-badge');

    let lastReportTotals = null;

    function setStatusBadge(status) {{
      statusBadge.className = 'status-badge px-2 py-0.5 rounded-full text-xs font-medium ' + status;
      statusBadge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    }}

    function setInputsEnabled(enabled) {{
      questionInput.disabled = !enabled;
      sendBtn.disabled = !enabled;
    }}

    async function fetchKBs() {{
      const res = await fetch(API + '/knowledge-bases');
      if (!res.ok) return {{ items: [], active_id: null }};
      return res.json();
    }}

    async function loadKBs() {{
      const data = await fetchKBs();
      kbSelect.innerHTML = '<option value="">-- Select or upload --</option>';
      for (const kb of data.items) {{
        const opt = document.createElement('option');
        opt.value = kb.id;
        opt.textContent = kb.name + ' (' + (kb.stats?.edges ?? 0) + ' edges)';
        if (kb.id === data.active_id) opt.selected = true;
        kbSelect.appendChild(opt);
      }}
      if (data.active_id) {{
        const activeName = data.items.find(k => k.id === data.active_id)?.name ?? data.active_id;
        kbStatus.textContent = 'Active: ' + activeName;
        setInputsEnabled(true);
        setStatusBadge('ready');
        currentOntologyPill.classList.remove('hidden');
        currentOntologyName.textContent = activeName;
      }} else {{
        kbStatus.textContent = 'No knowledge base selected';
        setInputsEnabled(false);
        setStatusBadge('empty');
        currentOntologyPill.classList.add('hidden');
      }}
    }}

    async function activateKB(id) {{
      const res = await fetch(API + '/knowledge-bases/' + id + '/activate', {{ method: 'POST' }});
      if (!res.ok) {{
        const err = await res.json().catch(() => ({{}}));
        throw new Error(parseError(err) || res.statusText);
      }}
      await loadKBs();
    }}

    kbSelect.addEventListener('change', async () => {{
      const id = kbSelect.value;
      if (!id) return;
      try {{
        await activateKB(id);
      }} catch (e) {{
        kbStatus.textContent = 'Error: ' + e.message;
      }}
    }});

    function appendMessage(role, content, sources, numFactsUsed) {{
      emptyState?.classList.add('hidden');
      const div = document.createElement('div');
      div.className = 'flex msg-enter ' + (role === 'user' ? 'justify-end' : 'justify-start');
      const bubble = document.createElement('div');
      bubble.className = 'max-w-[85%] rounded-md px-4 py-3 ' +
        (role === 'user' ? '' : 'bubble-assistant');
      bubble.style.background = role === 'user' ? '#7521ee' : '#1e1e28';
      bubble.style.color = role === 'user' ? '#fff' : '#e8e6e3';
      bubble.style.border = '1px solid ' + (role === 'user' ? '#7521ee' : '#1a1a24');
      const hasReasoning = (numFactsUsed !== undefined && numFactsUsed > 0) || (sources && sources.length > 0);
      if (role === 'assistant' && hasReasoning) {{
        const stepsDiv = document.createElement('div');
        stepsDiv.className = 'flex flex-wrap gap-2 mb-2 text-xs';
        stepsDiv.style.color = '#8a8a94';
        stepsDiv.innerHTML = '<span class="step-tag">Retrieve</span><span class="step-tag">Synthesize</span><span class="step-tag">Answer</span>';
        bubble.appendChild(stepsDiv);
        const reasonDiv = document.createElement('details');
        reasonDiv.className = 'reasoning-block mb-3';
        reasonDiv.open = true;
        const summary = document.createElement('summary');
        summary.className = 'cursor-pointer text-xs font-medium';
        summary.style.color = '#ec4899';
        summary.textContent = 'Reasoning';
        reasonDiv.appendChild(summary);
        const reasonContent = document.createElement('div');
        reasonContent.className = 'mt-2 pl-3 text-xs space-y-1';
        reasonContent.style.borderLeft = '2px solid #1a1a24';
        reasonContent.style.color = '#8a8a94';
        const parts = [];
        if (numFactsUsed !== undefined) parts.push('Retrieved ' + numFactsUsed + ' facts from ontology');
        if (sources && sources.length > 0) {{
          parts.push('Used ' + sources.length + ' sources in answer');
          parts.push('Sources: ' + sources.slice(0, 5).join(', ') + (sources.length > 5 ? '...' : ''));
        }}
        reasonContent.textContent = parts.join(' • ');
        reasonDiv.appendChild(reasonContent);
        bubble.appendChild(reasonDiv);
      }}
      const text = document.createElement('div');
      text.className = 'whitespace-pre-wrap';
      if (typeof content === 'string') {{
        text.textContent = content;
      }} else {{
        text.appendChild(content);
      }}
      bubble.appendChild(text);
      if (sources && sources.length > 0 && role === 'assistant') {{
        const srcDiv = document.createElement('div');
        srcDiv.className = 'mt-2 pt-2 flex flex-wrap gap-1.5 text-xs';
        srcDiv.style.borderTop = '1px solid #1a1a24';
        srcDiv.style.color = '#8a8a94';
        sources.slice(0, 5).forEach(ref => {{
          const tag = document.createElement('span');
          tag.className = 'px-2 py-0.5 rounded';
          tag.style.background = 'rgba(236, 72, 153, 0.15)';
          tag.style.color = '#ec4899';
          tag.textContent = ref;
          srcDiv.appendChild(tag);
        }});
        if (sources.length > 5) srcDiv.appendChild(document.createTextNode(' +' + (sources.length - 5) + ' more'));
        bubble.appendChild(srcDiv);
      }}
      div.appendChild(bubble);
      messagesEl.appendChild(div);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }}

    function appendOntologySummary(report) {{
      if (!report) return;
      emptyState?.classList.add('hidden');
      const div = document.createElement('div');
      div.className = 'flex justify-start msg-enter';
      const bubble = document.createElement('div');
      bubble.className = 'max-w-[90%] rounded-md px-4 py-4 bubble-assistant';
      bubble.style.background = '#1e1e28';
      bubble.style.color = '#e8e6e3';
      bubble.style.border = '1px solid #1a1a24';

      const totals = report.totals || {{}};
      const extractionTotals = report.extraction_totals || {{}};
      const reasoning = report.reasoning || {{}};
      const chunkStats = report.chunk_stats || [];
      const elapsed = report.elapsed_seconds ?? 0;
      const totalChunks = report.total_chunks ?? 0;
      const mode = report.extraction_mode || 'sequential';
      const ontologyName = report.ontology_name || 'Untitled';
      const llmInferred = report.llm_inferred_relations ?? 0;
      const infEdges = reasoning.inferred_edges ?? 0;
      const iter = reasoning.iterations ?? 0;

      const enhancedChunks = chunkStats.filter(c => ((c.classes ?? 0) + (c.instances ?? 0) + (c.relations ?? 0) + (c.axioms ?? 0)) > 0).length;
      const extCls = extractionTotals.classes ?? totals.classes ?? 0;
      const extInst = extractionTotals.instances ?? totals.instances ?? 0;
      const extRel = extractionTotals.relations ?? totals.relations ?? 0;
      const extAx = extractionTotals.axioms ?? totals.axioms ?? 0;

      const wrap = document.createElement('div');
      wrap.className = 'space-y-4';

      const title = document.createElement('p');
      title.className = 'font-semibold text-base';
      title.style.color = '#e8e6e3';
      title.textContent = 'Ontology build complete';
      wrap.appendChild(title);

      const ontologyLabel = document.createElement('p');
      ontologyLabel.className = 'text-sm';
      ontologyLabel.style.color = '#8a8a94';
      ontologyLabel.innerHTML = 'Ontology: <span class="stat-value">' + ontologyName + '</span>';
      wrap.appendChild(ontologyLabel);

      const processDiv = document.createElement('div');
      processDiv.className = 'space-y-1 text-sm';
      const steps = [
        '1. Chunking: ' + totalChunks + ' chunks created',
        '2. Extraction: ' + enhancedChunks + ' of ' + totalChunks + ' chunks enhanced (' + mode + ' mode)',
        '3. Merge: ' + extCls + ' classes, ' + extInst + ' instances, ' + extRel + ' relations, ' + extAx + ' axioms added',
        '4. LLM inference: ' + (llmInferred > 0 ? llmInferred + ' relations inferred' : 'Skipped'),
        '5. OWL 2 RL reasoning: ' + (infEdges > 0 ? infEdges + ' edges inferred in ' + iter + ' iterations' : 'Skipped'),
        '6. Final: ' + (totals.classes ?? 0) + ' classes, ' + (totals.instances ?? 0) + ' instances, ' + (totals.relations ?? 0) + ' relations, ' + (totals.axioms ?? 0) + ' axioms, ' + (totals.data_properties ?? 0) + ' data properties'
      ];
      steps.forEach(s => {{
        const p = document.createElement('p');
        p.className = 'process-step';
        p.textContent = s;
        processDiv.appendChild(p);
      }});
      const elapsedP = document.createElement('p');
      elapsedP.className = 'text-xs mt-2';
      elapsedP.style.color = '#8a8a94';
      elapsedP.textContent = 'Completed in ' + elapsed.toFixed(1) + 's';
      processDiv.appendChild(elapsedP);
      wrap.appendChild(processDiv);

      const statsGrid = document.createElement('div');
      statsGrid.className = 'grid grid-cols-2 sm:grid-cols-3 gap-3 mt-3';
      const statItems = [
        ['Classes', totals.classes ?? 0],
        ['Instances', totals.instances ?? 0],
        ['Relations', totals.relations ?? 0],
        ['Axioms', totals.axioms ?? 0],
        ['Data properties', totals.data_properties ?? 0],
      ];
      const keyMap = {{ 'Classes': 'classes', 'Instances': 'instances', 'Relations': 'relations', 'Axioms': 'axioms', 'Data properties': 'data_properties' }};
      statItems.forEach(([label, val]) => {{
        const key = keyMap[label] || label.toLowerCase();
        const prev = lastReportTotals ? (lastReportTotals[key] ?? 0) : null;
        const delta = prev !== null && val !== prev ? (val - prev) : null;
        const deltaStr = delta !== null ? (delta > 0 ? ' <span style="color:#ec4899;font-size:10px">+' + delta + '</span>' : ' <span style="color:#8a8a94;font-size:10px">' + delta + '</span>') : '';
        const card = document.createElement('div');
        card.className = 'rounded-md px-3 py-2';
        card.style.background = '#14141a';
        card.style.border = '1px solid #1a1a24';
        card.innerHTML = '<span class="stat-label text-xs">' + label + '</span><br><span class="stat-value font-mono text-sm">' + val + deltaStr + '</span>';
        statsGrid.appendChild(card);
      }});
      lastReportTotals = {{ classes: totals.classes ?? 0, instances: totals.instances ?? 0, relations: totals.relations ?? 0, axioms: totals.axioms ?? 0, data_properties: totals.data_properties ?? 0 }};
      wrap.appendChild(statsGrid);

      const infEdges = reasoning.inferred_edges ?? 0;
      const iter = reasoning.iterations ?? 0;
      if (infEdges > 0 || iter > 0) {{
        const reasonDiv = document.createElement('div');
        reasonDiv.className = 'text-sm mt-2';
        reasonDiv.style.color = '#8a8a94';
        reasonDiv.innerHTML = 'Reasoning: <span class="stat-value">' + infEdges + '</span> edges inferred in <span class="stat-value">' + iter + '</span> iterations';
        wrap.appendChild(reasonDiv);
      }}

      if (chunkStats.length > 0) {{
        const toggle = document.createElement('button');
        toggle.className = 'text-xs mt-2 link-teal cursor-pointer font-mono';
        toggle.textContent = '[+] Per-chunk details';
        toggle.type = 'button';
        const detailsDiv = document.createElement('div');
        detailsDiv.className = 'hidden mt-2 text-xs font-mono overflow-x-auto';
        detailsDiv.style.background = '#0a0a0f';
        detailsDiv.style.border = '1px solid #1a1a24';
        detailsDiv.style.borderRadius = '4px';
        detailsDiv.style.padding = '0.5rem';
        detailsDiv.style.maxHeight = '120px';
        const rows = chunkStats.map((c, i) => 'Chunk ' + (i + 1) + ': ' + (c.classes ?? 0) + ' cls, ' + (c.instances ?? 0) + ' inst, ' + (c.relations ?? 0) + ' rel' + (c.axioms ? ', ' + c.axioms + ' ax' : '')).join('\\n');
        detailsDiv.textContent = rows;
        toggle.addEventListener('click', () => {{
          detailsDiv.classList.toggle('hidden');
          toggle.textContent = detailsDiv.classList.contains('hidden') ? '[+] Per-chunk details' : '[-] Per-chunk details';
        }});
        wrap.appendChild(toggle);
        wrap.appendChild(detailsDiv);
      }}

      bubble.appendChild(wrap);
      div.appendChild(bubble);
      messagesEl.appendChild(div);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }}

    const UPLOAD_STEPS = ['Chunking...', 'Extracting...', 'Merging...', 'Reasoning...'];
    const QA_STEPS = ['Retrieving facts...', 'Synthesizing answer...'];
    let uploadStepInterval = null;
    let qaStepInterval = null;

    function showLoading(show) {{
      loadingIndicator.classList.toggle('hidden', !show);
      const qaLabel = document.getElementById('qa-step-label');
      const qaDots = loadingIndicator.querySelectorAll('.qa-step-dots span');
      if (show) {{
        qaLabel.textContent = QA_STEPS[0];
        qaDots.forEach((d, i) => {{ d.style.background = i === 0 ? '#ec4899' : '#1a1a24'; }});
        qaStepInterval = setInterval(() => {{
          const idx = QA_STEPS.indexOf(qaLabel.textContent);
          const next = (idx + 1) % QA_STEPS.length;
          qaLabel.textContent = QA_STEPS[next];
          qaDots.forEach((d, i) => {{ d.style.background = i === next ? '#ec4899' : '#1a1a24'; }});
        }}, 1800);
      }} else {{
        if (qaStepInterval) {{ clearInterval(qaStepInterval); qaStepInterval = null; }}
      }}
    }}

    chatForm.addEventListener('submit', async (e) => {{
      e.preventDefault();
      const q = questionInput.value.trim();
      if (!q) return;
      questionInput.value = '';
      appendMessage('user', q);
      showLoading(true);
      setInputsEnabled(false);
      try {{
        const res = await fetch(API + '/qa/ask', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ question: q }})
        }});
        const data = await res.json().catch(() => ({{}}));
        if (!res.ok) throw new Error(parseError(data) || res.statusText);
        appendMessage('assistant', data.answer, data.source_refs, data.num_facts_used);
      }} catch (e) {{
        appendMessage('assistant', 'Error: ' + e.message);
      }} finally {{
        showLoading(false);
        setInputsEnabled(true);
      }}
    }});

    // Upload
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => {{ e.preventDefault(); dropZone.classList.add('dragover'); }});
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    let pendingFile = null;
    const createModal = document.getElementById('create-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalDescription = document.getElementById('modal-description');
    const modalFilename = document.getElementById('modal-filename');
    const modalCancel = document.getElementById('modal-cancel');
    const modalConfirm = document.getElementById('modal-confirm');
    const currentOntologyPill = document.getElementById('current-ontology-pill');
    const currentOntologyName = document.getElementById('current-ontology-name');

    function showCreateModal(file) {{
      pendingFile = file;
      const stem = file.name.replace(/\\.[^.]+$/, '') || file.name;
      modalTitle.value = stem;
      modalDescription.value = '';
      modalFilename.textContent = 'File: ' + file.name;
      createModal.classList.remove('hidden');
      modalTitle.focus();
    }}

    function hideCreateModal() {{
      createModal.classList.add('hidden');
      pendingFile = null;
    }}

    modalCancel.addEventListener('click', hideCreateModal);
    createModal.querySelector('.modal-backdrop').addEventListener('click', hideCreateModal);
    modalConfirm.addEventListener('click', () => {{
      if (pendingFile) {{
        const title = modalTitle.value.trim() || pendingFile.name.replace(/\\.[^.]+$/, '');
        const description = modalDescription.value.trim();
        doUpload(pendingFile, title, description);
        hideCreateModal();
      }}
    }});

    dropZone.addEventListener('drop', (e) => {{
      e.preventDefault();
      dropZone.classList.remove('dragover');
      const files = e.dataTransfer?.files;
      if (files?.length) showCreateModal(files[0]);
    }});
    fileInput.addEventListener('change', () => {{
      if (fileInput.files?.length) showCreateModal(fileInput.files[0]);
      fileInput.value = '';
    }});

    async function doUpload(file, title, description) {{
      uploadError.classList.add('hidden');
      uploadError.textContent = '';
      uploadProgress.classList.remove('hidden');
      setStatusBadge('processing');
      const uploadLabel = document.getElementById('upload-step-label');
      const uploadDots = document.querySelectorAll('.upload-step-dot');
      let stepIdx = 0;
      uploadLabel.textContent = UPLOAD_STEPS[0];
      uploadDots.forEach((d, i) => {{ d.style.background = i === 0 ? '#ec4899' : '#1a1a24'; }});
      const stepInterval = setInterval(() => {{
        stepIdx = (stepIdx + 1) % UPLOAD_STEPS.length;
        uploadLabel.textContent = UPLOAD_STEPS[stepIdx];
        uploadDots.forEach((d, i) => {{ d.style.background = i === stepIdx ? '#ec4899' : '#1a1a24'; }});
      }}, 2500);
      const fd = new FormData();
      fd.append('file', file);
      if (title) fd.append('title', title);
      if (description) fd.append('description', description);
      try {{
        const res = await fetch(API + '/build_ontology?run_inference=true&sequential=true&run_reasoning=true', {{
          method: 'POST',
          body: fd
        }});
        const data = await res.json().catch(() => ({{}}));
        if (!res.ok) throw new Error(parseError(data) || res.statusText);
        await loadKBs();
        if (data.kb_id) kbSelect.value = data.kb_id;
        if (data.pipeline_report) appendOntologySummary(data.pipeline_report);
      }} catch (e) {{
        uploadError.textContent = e.message;
        uploadError.classList.remove('hidden');
      }} finally {{
        clearInterval(stepInterval);
        uploadProgress.classList.add('hidden');
        setStatusBadge(kbSelect.value ? 'ready' : 'empty');
      }}
    }}

    sidebarToggle?.addEventListener('click', () => sidebar.classList.toggle('open'));
    document.getElementById('sidebar-overlay')?.addEventListener('click', () => sidebar.classList.remove('open'));

    // Desktop: sidebar open by default. Mobile: closed by default.
    if (window.matchMedia('(min-width: 769px)').matches) {{
      sidebar.classList.add('open');
    }}

    loadKBs();
  </script>
</body>
</html>"""
