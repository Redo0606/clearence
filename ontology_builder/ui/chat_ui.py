"""Chat UI: single-page app with chat, KB selector, and document upload."""

from __future__ import annotations

from ontology_builder.ui.theme import get_css_root_block


def generate_chat_ui_html(api_base: str = "/api/v1") -> str:
    """Generate standalone HTML page for the ontology chat interface."""
    root_block = get_css_root_block()
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Clearence · Ontology Assistant</title>
  <style>
{root_block}

  </style>
  <link rel="stylesheet" href="/static/css/base.css">
  <link rel="stylesheet" href="/static/css/components.css">
  <link rel="stylesheet" href="/static/css/layout.css">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="flex h-screen overflow-hidden">
  <!-- Sidebar -->
  <aside id="sidebar" class="sidebar open w-80 flex flex-col shrink-0 min-h-0 overflow-y-auto" style="background: var(--bg-sidebar); border-right: 1px solid var(--border);">

    <!-- Brand -->
    <div class="px-5 py-4 flex items-center gap-3 shrink-0" style="border-bottom: 1px solid var(--border);">
      <div class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style="background: var(--accent-2);">
        <svg class="w-4 h-4" style="color: var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/>
        </svg>
      </div>
      <div>
        <p class="font-semibold text-sm" style="color: var(--text-primary);">Ontology Graph</p>
        <p class="text-xs" style="color: var(--text-muted);">Knowledge Management</p>
      </div>
    </div>

    <!-- Sidebar tabs: Documents + Evaluate only -->
    <div class="flex shrink-0 border-b" style="border-color: var(--border);">
      <button type="button" id="tab-documents" class="sidebar-tab sidebar-tab-active flex-1 px-4 py-3 text-xs font-semibold uppercase tracking-wider transition-all">
        Documents
      </button>
      <button type="button" id="tab-evaluate" class="sidebar-tab sidebar-tab-inactive flex-1 px-4 py-3 text-xs font-semibold uppercase tracking-wider transition-all">
        Evaluate
      </button>
    </div>

    <!-- Document Management tab content -->
    <div id="tab-documents-content" class="flex flex-col flex-1 min-h-0 overflow-hidden">
    <div class="px-5 py-4 flex-1 min-h-0 overflow-y-auto">
      <p class="text-xs font-semibold uppercase tracking-widest mb-3" style="color: var(--text-muted);">Add Documents</p>
      <p class="text-xs mb-3" style="color: var(--text-muted);">Add documents to the active KB, or create a new ontology. Start a new chat to choose a knowledge base.</p>
      <label for="file-input-create" id="kb-create-btn" class="w-full rounded-lg px-3 py-2.5 text-sm font-medium border transition-all flex items-center justify-center gap-2 cursor-pointer mb-3"
        style="background: var(--accent-12); color: var(--accent); border-color: var(--accent-4);">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/></svg>
        Create new ontology
      </label>
      <input type="file" id="file-input-create" class="sr-only" accept=".pdf,.docx,.txt,.md" multiple tabindex="-1">
      <label for="file-input" id="drop-zone" class="drop-zone border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all block"
        style="border-color: var(--border); color: var(--text-muted); background: var(--bg-card);">
        <div class="drop-icon mx-auto mb-2 w-10 h-10 rounded-full flex items-center justify-center" style="background: var(--accent-1);">
          <svg class="w-5 h-5" style="color: var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
        </div>
        <p class="text-sm font-medium" style="color: var(--text-primary);">Drop documents here</p>
        <p class="mt-0.5 text-xs">or <span class="link-teal font-medium">browse files</span> — multiple files supported</p>
        <div class="flex justify-center gap-1.5 mt-2.5">
          <span class="file-badge">PDF</span>
          <span class="file-badge">DOCX</span>
          <span class="file-badge">TXT</span>
          <span class="file-badge">MD</span>
        </div>
        <input type="file" id="file-input" class="sr-only" accept=".pdf,.docx,.txt,.md" multiple tabindex="-1">
      </label>
      <button type="button" id="web-enrichment-btn" class="w-full rounded-lg px-3 py-2.5 text-sm font-medium border transition-all flex items-center justify-center gap-2 mt-3"
        style="background: var(--accent-08); color: var(--accent); border-color: var(--accent-4);">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"/></svg>
        Web Enrichment
      </button>
      <div id="job-queue-section" class="job-queue-section collapsed mt-3">
        <button type="button" id="job-queue-toggle" class="job-queue-toggle w-full flex items-center justify-between py-2 text-xs font-medium" style="color: var(--text-muted);">
          <span class="flex items-center gap-2">
            <span>Documents &amp; jobs</span>
            <span id="job-queue-running-indicator" class="job-queue-running-dot hidden" aria-hidden="true" title="Jobs running"></span>
          </span>
          <svg class="job-queue-chevron w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </button>
        <div id="job-queue" class="job-queue-content mt-2 space-y-2 transition-opacity duration-200"></div>
        <button type="button" id="job-queue-clear" class="mt-2 text-xs py-1 px-2 rounded" style="color: var(--text-muted);" title="Clear job history">Clear history</button>
      </div>
    </div>
    </div>

    <!-- Evaluate tab content -->
    <div id="tab-evaluate-content" class="hidden flex flex-col flex-1 min-h-0 overflow-hidden">
      <div class="px-5 py-4 flex flex-col flex-1 min-h-0 overflow-y-auto">
        <div class="kb-selector mb-3">
          <label class="section-label">Knowledge base</label>
          <select id="eval-kb-select" class="w-full rounded-lg px-3 py-2.5 text-sm border transition-all" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);">
            <option value="">Select a KB</option>
          </select>
        </div>

        <div id="eval-panel-state-a">
        <!-- Graph Health Card (non-collapsible, no graph name) -->
        <div id="graph-health-card" class="job-card-eval accent-attention" onclick="window.openGraphHealthModal && window.openGraphHealthModal()">
          <div class="job-card-header">
            <span id="graph-health-badge" class="badge badge-attention">—</span>
          </div>
          <div class="job-card-meta">
            <div class="meta-line" id="graph-health-meta">Select a KB to view health</div>
          </div>
          <div class="job-card-body graph-health-body-always-visible" id="health-body">
            <div id="health-disconnect-row" class="health-disconnect-compact"></div>
            <button type="button" class="btn-primary-eval full-width" style="margin-top:12px" onclick="event.stopPropagation(); (window.evalOpenRepairModal||function(){{document.getElementById('eval-repair-btn')?.click()}})()">⚙ Repair</button>
          </div>
        </div>
        <button type="button" id="eval-repair-btn" class="sr-only" aria-hidden="true" title="Opens repair modal"></button>

        <!-- Repair progress (hidden, shown by app.bundle when repair runs) -->
        <div id="eval-panel-state-b" class="hidden rounded-xl p-4 flex flex-col mt-4" style="background: var(--bg-card); border: 1px solid var(--border);">
          <div class="flex items-center gap-2 mb-2">
            <div class="kb-load-spinner w-4 h-4"></div>
            <span id="eval-stage-label" class="text-sm font-medium" style="color: var(--text-primary);">Repairing...</span>
          </div>
          <div class="h-1.5 rounded-full mb-3 overflow-hidden" style="background: var(--border-subtle);">
            <div id="eval-progress-bar" class="h-full rounded-full transition-all duration-300" style="background: var(--success); width: 0%;"></div>
          </div>
          <div id="eval-log-feed" class="flex-1 min-h-[120px] overflow-y-auto text-xs font-mono space-y-1 break-words overflow-x-hidden" style="color: var(--text-muted); max-height: 200px;"></div>
          <div id="eval-error-banner" class="hidden mt-2 px-3 py-2 rounded-lg text-xs" style="background: var(--error-15); color: var(--error);"></div>
        </div>

        <!-- QA Evaluation Card (non-expandable) -->
        <div class="job-card-eval accent-new mt-4" style="cursor:default">
          <div class="job-card-header">
            <span class="badge badge-new">QA Eval</span>
          </div>
          <div class="job-card-body graph-health-body-always-visible" id="qa-eval-body">
            <p style="font-size:12px; color:var(--text-muted); margin-bottom:12px">Measures answer quality by asking questions against the ontology. Higher scores indicate better retrieval and reasoning.</p>
            <div style="display:flex; align-items:center; gap:10px; margin:12px 0 8px">
              <label class="section-label" style="margin:0">Questions</label>
              <input type="number" id="eval-num-questions" class="field-input" value="5" min="1" max="500" title="Number of questions to generate (1–500)">
            </div>
            <p style="font-size:11px; color:var(--text-muted); margin-bottom:12px">Run evaluation to view scores (avg, answer correctness, retrieval quality).</p>
            <button type="button" class="btn-primary-eval full-width" id="eval-run-btn" onclick="window.evalTabRunEvaluation && window.evalTabRunEvaluation()">▶ Run Evaluation</button>
            <div id="eval-progress" style="display:none; margin-top:10px">
              <div class="status-dot running" id="eval-status-dot">
                <span id="eval-status-text">Starting evaluation…</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Evaluation Records -->
        <div class="section-header collapsed" id="eval-records-header" onclick="window.toggleEvalSection && window.toggleEvalSection('eval-records-list', 'eval-records-header')">
          <span>Evaluation Records</span>
          <span class="chevron">∨</span>
        </div>
        <div class="section-content collapsed" id="eval-records-list">
          <p style="color:var(--text-muted);font-size:13px;padding:8px 0">Select a KB to view evaluation history</p>
        </div>

        <!-- Repair Records -->
        <div class="section-header collapsed" id="repair-records-header" onclick="window.toggleEvalSection && window.toggleEvalSection('repair-records-list', 'repair-records-header')">
          <span>Repair Records</span>
          <span class="chevron">∨</span>
        </div>
        <div class="section-content collapsed" id="repair-records-list">
          <p style="color:var(--text-muted);font-size:13px;padding:8px 0">Select a KB to view repair history</p>
        </div>
        </div>
      </div>
    </div>

    <!-- Footer links -->
    <div class="px-5 py-3 flex items-center gap-4 shrink-0" style="border-top: 1px solid var(--border);">
      <span class="text-xs" style="color: #555;">Clearence v1.0 · by Reda Sarehane</span>
    </div>
  </aside>
  <div class="sidebar-overlay" id="sidebar-overlay" aria-hidden="true"></div>

  <!-- Ontology creation modal -->
  <div id="create-modal" class="fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="document.getElementById('create-modal').classList.add('hidden')"></div>
    <div class="modal-content modal-enter absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md rounded-xl p-6 shadow-2xl" style="background: var(--bg-card); border: 1px solid var(--border);" onclick="event.stopPropagation()">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style="background: var(--accent-2);">
          <svg class="w-5 h-5" style="color: var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
        </div>
        <div>
          <h3 id="modal-heading" class="font-semibold text-lg" style="color: var(--text-primary);">New Ontology</h3>
          <p id="modal-filename" class="text-xs mt-0.5" style="color: var(--text-muted);"></p>
        </div>
      </div>
      <!-- Mode toggle: only visible when an active KB exists -->
      <div id="modal-mode-section" class="hidden mb-4 rounded-lg overflow-hidden" style="border: 1px solid var(--border);">
        <button type="button" id="modal-mode-new"
          class="w-1/2 px-4 py-2 text-xs font-medium transition-all mode-tab-active"
          onclick="setModalMode('new')">
          New ontology
        </button><button type="button" id="modal-mode-extend"
          class="w-1/2 px-4 py-2 text-xs font-medium transition-all mode-tab-inactive"
          onclick="setModalMode('extend')">
          Add to <span id="modal-mode-kb-name" class="truncate"></span>
        </button>
      </div>
      <div id="modal-shared-options" class="space-y-4 mb-4">
        <div>
          <label class="block text-xs font-medium mb-1.5 uppercase tracking-wider" style="color: var(--text-muted);">Min quality grade <span style="color: #555;">(optional)</span></label>
          <select id="modal-min-quality-grade" class="w-full rounded-lg px-3.5 py-2.5 text-sm border transition-all" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);" title="Skip merge if extraction reliability is below this grade">
            <option value="">Accept all (no gate)</option>
            <option value="D">D — minimum</option>
            <option value="C">C</option>
            <option value="B">B</option>
            <option value="A">A — strict</option>
          </select>
          <p class="text-xs mt-1" style="color: var(--text-muted);">Documents below this grade are not merged into the ontology.</p>
        </div>
      </div>
      <div id="modal-new-fields" class="space-y-4">
        <div>
          <label class="block text-xs font-medium mb-1.5 uppercase tracking-wider" style="color: var(--text-muted);">Title</label>
          <input type="text" id="modal-title" class="w-full rounded-lg px-3.5 py-2.5 text-sm border transition-all" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);" placeholder="e.g. Climate Science Ontology">
        </div>
        <div>
          <label class="block text-xs font-medium mb-1.5 uppercase tracking-wider" style="color: var(--text-muted);">Description <span style="color: #555;">(optional)</span></label>
          <textarea id="modal-description" class="w-full rounded-lg px-3.5 py-2.5 text-sm border resize-none transition-all" rows="3" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);" placeholder="What this ontology covers..."></textarea>
        </div>
        <div>
          <label class="block text-xs font-medium mb-1.5 uppercase tracking-wider" style="color: var(--text-muted);">Ontology language</label>
          <select id="modal-ontology-language" class="w-full rounded-lg px-3.5 py-2.5 text-sm border transition-all" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);" title="All class/instance names and descriptions will be in this language">
            <option value="en">English</option>
            <option value="fr">French</option>
            <option value="de">German</option>
            <option value="es">Spanish</option>
            <option value="it">Italian</option>
            <option value="pt">Portuguese</option>
            <option value="nl">Dutch</option>
            <option value="ar">Arabic</option>
            <option value="zh">Chinese</option>
            <option value="ja">Japanese</option>
            <option value="ko">Korean</option>
            <option value="ru">Russian</option>
          </select>
          <p class="text-xs mt-1" style="color: var(--text-muted);">Concepts and relations will be extracted in this language. Answers in chat can still be in your language.</p>
        </div>
        <div class="flex items-center gap-2">
          <input type="checkbox" id="modal-parallel" checked class="rounded border-2 w-4 h-4 accent-pink-500" style="border-color: var(--border); background: var(--bg-input);">
          <label for="modal-parallel" class="text-sm" style="color: var(--text-primary);">Parallel extraction (4 workers)</label>
        </div>
      </div>
      <div id="modal-extend-fields" class="hidden space-y-4">
        <div class="rounded-lg p-3" style="background: var(--accent-06); border: 1px solid var(--accent-18);">
          <p class="text-xs" style="color: var(--text-muted);">The extracted knowledge from this document will be <span class="font-semibold" style="color:var(--text-primary);">merged into the active ontology</span>. Existing concepts and relations are preserved.</p>
        </div>
        <div class="flex items-center gap-2">
          <input type="checkbox" id="modal-parallel-extend" checked class="rounded border-2 w-4 h-4 accent-pink-500" style="border-color: var(--border); background: var(--bg-input);">
          <label for="modal-parallel-extend" class="text-sm" style="color: var(--text-primary);">Parallel extraction (4 workers)</label>
        </div>
      </div>
      <div class="mt-6 flex gap-3 justify-end">
        <button type="button" id="modal-cancel" class="px-4 py-2.5 rounded-lg text-sm transition-all" style="background: var(--bg-input); color: var(--text-muted); border: 1px solid var(--border);">Cancel</button>
        <button type="button" id="modal-confirm" class="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-all btn-send">Create &amp; Build</button>
      </div>
    </div>
  </div>

  <!-- Job details modal (matches Web Enrichment modal style) -->
  <div id="job-detail-modal" class="job-detail-modal fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="document.getElementById('job-detail-modal').classList.add('hidden')"></div>
    <div class="modal-content modal-enter absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl p-6 shadow-2xl" style="background: var(--bg-card); border: 1px solid var(--border);" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between gap-3 mb-4">
        <div class="flex items-center gap-3 min-w-0 flex-1">
          <div id="job-detail-icon" class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style="background: var(--accent-12);">
            <svg class="w-5 h-5" style="color: var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
          </div>
          <div class="min-w-0 flex-1">
            <h3 id="job-detail-title" class="font-semibold text-base truncate" style="color: var(--text-primary);">Job Details</h3>
            <p id="job-detail-subtitle" class="text-xs mt-0.5 truncate" style="color: var(--text-muted);">Document processing and extraction</p>
          </div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <button type="button" id="job-detail-cancel-job" class="hidden px-3 py-1.5 rounded-lg text-xs font-medium transition-all" style="background: var(--error-15); color: var(--error); border: 1px solid var(--error);" aria-label="Cancel job">Cancel job</button>
          <button type="button" id="job-detail-close" class="p-1.5 rounded-md transition-colors text-xl leading-none hover:opacity-80" style="color: var(--text-muted);" aria-label="Close">×</button>
        </div>
      </div>
      <div id="job-detail-content" class="space-y-4 text-sm" style="color: var(--text-primary);"></div>
    </div>
  </div>

  <!-- KB summary/edit modal -->
  <div id="kb-summary-modal" class="fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="hideKbSummaryModal()"></div>
    <div class="modal-content modal-enter absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg rounded-xl p-6 shadow-2xl" style="background: var(--bg-card); border: 1px solid var(--border);" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between mb-5">
        <h3 class="font-semibold text-lg" style="color: var(--text-primary);">Knowledge Base Summary</h3>
        <button type="button" id="kb-summary-close" class="p-1.5 rounded-md transition-colors text-xl leading-none" style="color: var(--text-muted);" aria-label="Close">×</button>
      </div>
      <div id="kb-summary-content" class="space-y-4">
        <div>
          <label class="block text-xs font-medium mb-1.5 uppercase tracking-wider" style="color: var(--text-muted);">Name</label>
          <input type="text" id="kb-summary-name" class="w-full rounded-lg px-3.5 py-2.5 text-sm border transition-all" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);" placeholder="Ontology name">
        </div>
        <div>
          <label class="block text-xs font-medium mb-1.5 uppercase tracking-wider" style="color: var(--text-muted);">Description</label>
          <textarea id="kb-summary-desc" class="w-full rounded-lg px-3.5 py-2.5 text-sm border resize-none transition-all" rows="4" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);" placeholder="What this ontology covers..."></textarea>
        </div>
        <div id="kb-summary-stats" class="rounded-lg p-3" style="background: var(--bg-input); border: 1px solid var(--border);"></div>
      </div>
      <div class="mt-6 flex gap-3 justify-end">
        <button type="button" id="kb-summary-cancel" class="px-4 py-2.5 rounded-lg text-sm transition-all" style="background: var(--bg-input); color: var(--text-muted); border: 1px solid var(--border);">Cancel</button>
        <button type="button" id="kb-summary-save" class="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-all btn-send">Save</button>
      </div>
    </div>
  </div>

  <!-- New chat KB selection modal -->
  <div id="new-chat-modal" class="fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="document.getElementById('new-chat-modal').classList.add('hidden')"></div>
    <div class="modal-content modal-enter new-chat-modal absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md rounded-xl p-6 shadow-2xl" style="background: var(--bg-card); border: 1px solid var(--border);" onclick="event.stopPropagation()">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style="background: var(--accent-2);">
          <svg class="w-5 h-5" style="color: var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
        </div>
        <div>
          <h3 class="font-semibold text-lg" style="color: var(--text-primary);">New Chat</h3>
          <p class="text-xs mt-0.5" style="color: var(--text-muted);">Choose a knowledge base to chat with</p>
        </div>
      </div>
      <div id="new-chat-kb-list" class="space-y-2 max-h-64 overflow-y-auto mb-4"></div>
      <div class="flex gap-3 justify-end">
        <button type="button" id="new-chat-modal-cancel" class="px-4 py-2.5 rounded-lg text-sm transition-all" style="background: var(--bg-input); color: var(--text-muted); border: 1px solid var(--border);">Cancel</button>
      </div>
    </div>
  </div>

  <!-- Delete confirmation modal -->
  <div id="delete-modal" class="fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="document.getElementById('delete-modal').classList.add('hidden')"></div>
    <div class="modal-content modal-enter absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-sm rounded-xl p-6 shadow-2xl" style="background: var(--bg-card); border: 1px solid var(--border);" onclick="event.stopPropagation()">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style="background: var(--error-15);">
          <svg class="w-5 h-5" style="color: var(--error);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
        </div>
        <div>
          <h3 class="font-semibold text-base" style="color: var(--text-primary);">Delete Ontology</h3>
          <p class="text-xs mt-0.5" style="color: var(--text-muted);">This action cannot be undone</p>
        </div>
      </div>
      <p class="text-sm mb-5" style="color: var(--text-muted);">Are you sure you want to delete <span id="delete-modal-name" class="font-semibold" style="color:var(--text-primary);"></span>? All extracted knowledge will be permanently removed.</p>
      <div class="flex gap-3 justify-end">
        <button type="button" id="delete-modal-cancel" class="px-4 py-2.5 rounded-lg text-sm transition-all" style="background: var(--bg-input); color: var(--text-muted); border: 1px solid var(--border);">Cancel</button>
        <button type="button" id="delete-modal-confirm" class="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-all" style="background: var(--error); border: 1px solid var(--error-border);">Delete</button>
      </div>
    </div>
  </div>

  <!-- Web Enrichment modal -->
  <div id="web-enrichment-modal" class="fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="hideWebEnrichmentModal()"></div>
    <div class="modal-content modal-enter absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg rounded-xl p-6 shadow-2xl" style="background: var(--bg-card); border: 1px solid var(--border);" onclick="event.stopPropagation()">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style="background: var(--accent-12);">
          <svg class="w-5 h-5" style="color: var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"/></svg>
        </div>
        <div>
          <h3 class="font-semibold text-base" style="color: var(--text-primary);">Web Enrichment</h3>
          <p class="text-xs mt-0.5" style="color: var(--text-muted);">Fetch web content and merge into the ontology</p>
        </div>
      </div>
      <div id="web-enrichment-form" class="space-y-4">
        <div>
          <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted);">Knowledge base</label>
          <select id="web-enrichment-kb-select" class="w-full rounded-lg px-3 py-2.5 text-sm border transition-all" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);">
            <option value="">Select a KB</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted);">Min. fidelity <span id="web-enrichment-fidelity-value" class="font-mono">0.30</span></label>
          <input type="range" id="web-enrichment-fidelity" min="0.15" max="1" step="0.05" value="0.3" class="w-full h-2 rounded-lg accent-pink-500" style="background: var(--bg-input);">
          <p class="text-xs mt-0.5" style="color: var(--text-muted);">Drop sources below this score (academic=1.0, docs=0.85, forums=0.30)</p>
        </div>
        <div>
          <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted);">Max queries (optional)</label>
          <input type="number" id="web-enrichment-max-queries" min="1" max="50" placeholder="Auto" class="w-full rounded-lg px-3 py-2.5 text-sm border transition-all" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);">
        </div>
      </div>
      <div id="web-enrichment-progress" class="hidden mt-4 space-y-2 rounded-lg p-3" style="background: var(--bg-input); border: 1px solid var(--border);">
        <p class="text-xs font-medium" style="color: var(--text-muted);">Progress</p>
        <p id="web-enrichment-stage" class="text-sm font-mono" style="color: var(--text-primary);">Starting...</p>
        <p id="web-enrichment-metrics" class="text-xs font-mono" style="color: var(--text-muted);"></p>
      </div>
      <div class="flex gap-3 justify-end mt-5">
        <button type="button" id="web-enrichment-cancel" class="px-4 py-2.5 rounded-lg text-sm transition-all" style="background: var(--bg-input); color: var(--text-muted); border: 1px solid var(--border);">Cancel</button>
        <button type="button" id="web-enrichment-start" class="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-all btn-send">Start Enrichment</button>
      </div>
    </div>
  </div>

  <!-- Repair modal (mirrors Web Enrichment modal structure) -->
  <div id="repair-modal" class="fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="document.getElementById('repair-modal').classList.add('hidden')"></div>
    <div class="modal-content modal-enter absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg rounded-xl p-6 shadow-2xl max-h-[90vh] overflow-y-auto" style="background: var(--bg-card); border: 1px solid var(--border);" onclick="event.stopPropagation()">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style="background: var(--success-15);">
          <svg class="w-5 h-5" style="color: var(--success);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
        </div>
        <div>
          <h3 class="font-semibold text-base" style="color: var(--text-primary);">Graph Repair</h3>
          <p class="text-xs mt-0.5" style="color: var(--text-muted);">Link orphans, bridge components, optionally fill missing definitions</p>
        </div>
      </div>
      <div id="repair-form" class="space-y-4">
        <div>
          <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted);">Knowledge base</label>
          <select id="repair-kb-select" class="w-full rounded-lg px-3 py-2.5 text-sm border transition-all" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);">
            <option value="">Select a KB</option>
          </select>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div class="flex items-center gap-2">
            <input type="checkbox" id="repair-internet-definitions" class="rounded border-2 w-4 h-4 accent-pink-500" style="border-color: var(--border); background: var(--bg-input);">
            <label for="repair-internet-definitions" class="text-sm" style="color: var(--text-primary);">Internet definitions</label>
          </div>
          <div id="repair-confidence-wrap" class="hidden">
            <label class="block text-xs font-medium mb-1" style="color: var(--text-muted);">Confidence threshold</label>
            <input type="number" id="repair-min-fidelity" min="0" max="1" step="0.1" value="0.3" class="w-full rounded-lg px-3 py-2.5 text-sm border transition-all" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);" title="Min score (0–1) for web sources; higher = stricter, less bad data">
          </div>
          <div>
            <label class="block text-xs font-medium mb-1" style="color: var(--text-muted);">Iterations</label>
            <select id="repair-iterations" class="w-full rounded-lg px-3 py-2.5 text-sm border transition-all" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);">
              <option value="1">1</option>
              <option value="2">2</option>
              <option value="3">3</option>
            </select>
          </div>
        </div>
        <p class="text-[11px]" style="color: var(--text-muted);">2+ iterations: rescan graph after each pass, then repair again. Confidence threshold filters low-quality web definitions.</p>
        <div class="repair-details-section rounded-lg overflow-hidden" style="border: 1px solid var(--border);">
          <button type="button" id="repair-details-toggle" class="repair-details-toggle w-full flex items-center justify-between px-3 py-2.5 text-left text-sm font-medium transition-colors" style="background: var(--bg-input); color: var(--text-primary);">
            <span>Graph details &amp; recommendations</span>
            <svg id="repair-details-chevron" class="w-4 h-4 shrink-0 transition-transform" style="color: var(--text-muted);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
          </button>
          <div id="repair-details-content" class="repair-details-content hidden border-t overflow-hidden" style="border-color: var(--border); background: var(--bg-body);">
            <div id="repair-details-body" class="repair-details-body p-3 text-xs space-y-3 max-h-[280px] overflow-y-auto" style="color: var(--text-muted);">
              <p class="text-xs" style="color: var(--text-muted);">Select a KB to load graph health, gaps, and repair recommendations.</p>
            </div>
          </div>
        </div>
      </div>
      <div id="repair-progress" class="hidden mt-4 space-y-2 rounded-lg p-3" style="background: var(--bg-input); border: 1px solid var(--border);">
        <p class="text-xs font-medium" style="color: var(--text-muted);">Progress</p>
        <p id="repair-stage" class="text-sm font-mono" style="color: var(--text-primary);">Starting...</p>
        <p id="repair-metrics" class="text-xs font-mono" style="color: var(--text-muted);"></p>
      </div>
      <div class="flex gap-3 justify-end mt-5">
        <button type="button" id="repair-modal-cancel" class="px-4 py-2.5 rounded-lg text-sm transition-all" style="background: var(--bg-input); color: var(--text-muted); border: 1px solid var(--border);">Cancel</button>
        <button type="button" id="repair-modal-start" class="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-all btn-send">Start Repair</button>
      </div>
    </div>
  </div>

  <!-- Graph Health detail modal (single unified card, no graph name) -->
  <div class="modal-overlay eval-modal" id="modal-graph-health">
    <div class="modal-box modal-graph-health-unified" onclick="event.stopPropagation()">
      <button type="button" class="modal-close" onclick="window.evalCloseModal && window.evalCloseModal('modal-graph-health')">×</button>
      <div class="modal-header">
        <div class="modal-icon" style="background:rgba(184,19,101,0.15)">🕸</div>
      </div>
      <div class="mgh-unified-content">
        <div class="mgh-row mgh-status-row">
          <span id="mgh-status"></span>
        </div>
        <div class="mgh-stat-grid" id="mgh-stat-grid"></div>
        <div class="mgh-score-row">
          <span id="mgh-score-badge" class="badge"></span>
          <div class="progress-track-eval" style="flex:1">
            <div class="progress-fill-eval" id="mgh-score-bar" style="width:0%"></div>
          </div>
          <span id="mgh-score-val" style="font-family:var(--font-mono);font-size:14px;color:var(--text-value)"></span>
        </div>
        <div class="mgh-connectivity-row" id="mgh-connectivity"></div>
        <div class="mgh-actions-row" id="mgh-actions"></div>
      </div>
    </div>
  </div>

  <!-- Evaluation Record detail modal -->
  <div class="modal-overlay eval-modal" id="modal-eval-detail">
    <div class="modal-box" onclick="event.stopPropagation()">
      <button type="button" class="modal-close" onclick="window.evalCloseModal && window.evalCloseModal('modal-eval-detail')">×</button>
      <div class="modal-header">
        <div class="modal-icon" style="background:rgba(107,127,168,0.15)">📊</div>
        <div>
          <div class="modal-title-eval">Evaluation Record</div>
          <div class="modal-subtitle" id="med-subtitle"></div>
        </div>
      </div>
      <div class="inner-card">
        <div class="section-label">Status</div>
        <div id="med-status"></div>
      </div>
      <div class="inner-card">
        <div class="section-label">Evaluation Config</div>
        <div class="stat-grid" id="med-config"></div>
      </div>
      <div class="inner-card">
        <div class="section-label">Metrics</div>
        <div id="med-metrics"></div>
      </div>
      <div class="inner-card">
        <div class="section-label">Aggregate Scores</div>
        <div class="stat-grid" id="med-aggregate"></div>
      </div>
      <div id="med-warnings-wrap" class="inner-card" style="display:none">
        <div class="section-label">Warnings</div>
        <div id="med-warnings"></div>
      </div>
      <div class="inner-card">
        <div class="section-header" onclick="window.toggleEvalSection && window.toggleEvalSection('med-qlog','med-qlog-hdr')" id="med-qlog-hdr" style="border:none;margin:0;padding:0 0 10px">
          <span class="section-label" style="margin:0">Question Log</span>
          <span class="chevron" style="font-size:11px">∨</span>
        </div>
        <div id="med-qlog" class="section-content collapsed">
          <table class="question-table" id="med-qlog-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Question</th>
                <th>Score</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody id="med-qlog-body"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <!-- Repair Record detail modal -->
  <div class="modal-overlay eval-modal" id="modal-repair-detail">
    <div class="modal-box" onclick="event.stopPropagation()">
      <button type="button" class="modal-close" onclick="window.evalCloseModal && window.evalCloseModal('modal-repair-detail')">×</button>
      <div class="modal-header">
        <div class="modal-icon" style="background:rgba(248,198,48,0.15)">⚙</div>
        <div>
          <div class="modal-title-eval">Repair Record</div>
          <div class="modal-subtitle" id="mrd-subtitle"></div>
        </div>
      </div>
      <div class="inner-card">
        <div class="section-label">Status</div>
        <div id="mrd-status"></div>
      </div>
      <div class="inner-card">
        <div class="section-label">Config</div>
        <div class="stat-grid" id="mrd-config"></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div class="inner-card">
          <div class="section-label">Before</div>
          <div class="stat-grid" id="mrd-before"></div>
        </div>
        <div class="inner-card" id="mrd-after-card">
          <div class="section-label">After</div>
          <div class="stat-grid" id="mrd-after"></div>
        </div>
      </div>
      <div class="inner-card">
        <div class="section-label">Pipeline Breakdown</div>
        <div id="mrd-pipeline"></div>
      </div>
      <div class="inner-card" id="mrd-elements-card" style="display:none">
        <div class="section-label">Elements Added</div>
        <div id="mrd-elements"></div>
      </div>
      <div class="inner-card" id="mrd-actions-card" style="display:none">
        <div class="section-label">Recommended Actions</div>
        <div id="mrd-actions"></div>
      </div>
    </div>
  </div>

  <!-- Main chat area -->
  <main class="flex-1 flex flex-col min-h-0 overflow-hidden">
    <!-- Header -->
    <header class="shrink-0 px-6 py-3.5 flex items-center justify-between" style="background: var(--bg-sidebar); border-bottom: 1px solid var(--border);">
      <div class="flex items-center gap-3">
        <div>
          <h1 class="font-semibold text-base" style="color: var(--text-primary);">Clearence</h1>
          <p class="text-xs" style="color: var(--text-muted);">Ontology Assistant · Reda Sarehane</p>
        </div>
        <!-- Active ontology: name, status, full stats -->
        <div id="current-ontology-pill" class="hidden flex items-center gap-3 flex-wrap pl-3 ml-1" style="border-left: 1px solid var(--border);">
          <div class="flex items-center gap-2">
            <div class="w-1.5 h-1.5 rounded-full shrink-0" style="background: var(--accent);"></div>
            <span id="current-ontology-name" class="text-xs font-medium cursor-pointer hover:opacity-80 transition-opacity" style="color: var(--text-primary);" title="Open graph viewer"></span>
          </div>
          <span id="current-ontology-status-badge" class="text-xs font-medium px-2 py-0.5 rounded-full hidden" style="background: var(--border-subtle); color: var(--text-muted);"></span>
          <span class="text-xs" style="color: var(--border);">|</span>
          <span id="current-ontology-stats" class="text-xs font-mono" style="color: var(--text-muted);"></span>
          <span class="text-xs" style="color: var(--border);">|</span>
          <span id="current-ontology-docs-count" class="text-xs font-mono" style="color: var(--text-muted);"></span>
          <span id="current-ontology-ready-badge" class="hidden flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full shrink-0" style="color:var(--success); background:var(--success-15); border: 1px solid var(--success-2);">
            <span class="kb-ready-dot"></span>Ready
          </span>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button id="sidebar-toggle" class="p-2 rounded-md transition-colors flex items-center justify-center" style="color: var(--text-muted);" onmouseover="this.style.background='var(--bg-card)'" onmouseout="this.style.background='transparent'" type="button" aria-label="Toggle sidebar">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
        </button>
      </div>
    </header>

    <!-- Chat tabs -->
    <div id="chat-tabs-bar" class="shrink-0 flex items-center gap-1 px-4 py-2 overflow-x-auto" style="background: var(--bg-sidebar); border-bottom: 1px solid var(--border);">
      <div id="chat-tabs" class="flex items-center gap-1 min-w-0"></div>
      <button type="button" id="new-chat-btn" class="chat-tab chat-tab-add shrink-0 flex items-center gap-1.5" title="New chat">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
        <span>New</span>
      </button>
    </div>

    <!-- Messages -->
    <div id="messages" class="flex-1 overflow-y-auto p-6 space-y-5" style="scroll-behavior: smooth; background: var(--bg-body);">
      <!-- Thinking / loading indicator (inside messages so it flows with conversation) -->
      <div id="loading-indicator" class="hidden loading-in-messages flex flex-col mt-4">
        <div class="agent-loading-card rounded-xl overflow-hidden" style="background: var(--bg-card); border: 1px solid var(--border); width: fit-content; max-width: 100%;">
          <div class="thinking-pill flex items-center rounded-t-xl gap-3 px-4 py-2.5" style="background: var(--bg-card);">
            <div class="thinking-orb-wrap">
              <span class="thinking-ring thinking-ring-1" aria-hidden="true"></span>
              <span class="thinking-ring thinking-ring-2" aria-hidden="true"></span>
              <span class="thinking-core" aria-hidden="true"></span>
              <div class="thinking-orbit" aria-hidden="true">
                <span class="thinking-particle"></span>
                <span class="thinking-particle"></span>
                <span class="thinking-particle"></span>
                <span class="thinking-particle"></span>
              </div>
            </div>
            <div class="thinking-label">
              <span class="thinking-word">QUERYING</span>
              <span class="thinking-ellipsis thinking-e1">.</span><span class="thinking-ellipsis thinking-e2">.</span><span class="thinking-ellipsis thinking-e3">.</span>
            </div>
          </div>
          <div id="reasoning-steps-log" class="reasoning-steps-log hidden px-4 py-2.5 shrink-0" style="border-top: 1px solid var(--border-subtle); background: rgba(0,0,0,0.15);"></div>
        </div>
      </div>
      <!-- Empty state: no ontology selected -->
      <div id="empty-state-no-kb" class="flex flex-col items-center justify-center py-16 text-center">
        <div class="w-16 h-16 rounded-2xl flex items-center justify-center mb-5" style="background: var(--accent-08); border: 1px solid var(--accent-15);">
          <svg class="w-8 h-8" style="color: var(--accent); opacity: 0.6;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/>
          </svg>
        </div>
        <p class="text-lg font-semibold" style="color: var(--text-primary);">No ontology selected</p>
        <p class="mt-2 text-sm max-w-xs" style="color: var(--text-muted);">Select a knowledge base from the sidebar, or upload a document to get started.</p>
      </div>

      <!-- Empty state: ontology selected, ready to chat -->
      <div id="empty-state-ready" class="hidden flex-col items-center justify-center py-10 text-center">
        <!-- Prompt suggestions -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
          <button type="button" onclick="fillPrompt('What are the main classes in this ontology?')"
            class="suggestion-btn text-left px-4 py-3 rounded-xl text-sm transition-all"
            style="background: var(--bg-card); border: 1px solid var(--border); color: var(--text-primary);">
            <p class="font-medium text-xs mb-1" style="color: var(--accent);">Explore</p>
            What are the main classes?
          </button>
          <button type="button" onclick="fillPrompt('What instances exist in this ontology?')"
            class="suggestion-btn text-left px-4 py-3 rounded-xl text-sm transition-all"
            style="background: var(--bg-card); border: 1px solid var(--border); color: var(--text-primary);">
            <p class="font-medium text-xs mb-1" style="color: var(--accent);">Instances</p>
            What instances exist?
          </button>
          <button type="button" onclick="fillPrompt('How are entities related to each other?')"
            class="suggestion-btn text-left px-4 py-3 rounded-xl text-sm transition-all"
            style="background: var(--bg-card); border: 1px solid var(--border); color: var(--text-primary);">
            <p class="font-medium text-xs mb-1" style="color: var(--accent);">Relations</p>
            How are entities related?
          </button>
          <button type="button" onclick="fillPrompt('Summarize the key concepts in this knowledge base')"
            class="suggestion-btn text-left px-4 py-3 rounded-xl text-sm transition-all"
            style="background: var(--bg-card); border: 1px solid var(--border); color: var(--text-primary);">
            <p class="font-medium text-xs mb-1" style="color: var(--accent);">Summary</p>
            Summarize key concepts
          </button>
        </div>
      </div>

    </div>

    <!-- Chat input -->
    <div class="shrink-0 px-6 py-4" style="border-top: 1px solid var(--border); background: var(--bg-sidebar);">
      <!-- Mode selector: clickable tag that expands to toggle bar -->
      <div class="flex items-center justify-end mb-3">
        <div id="mode-selector" class="mode-selector relative">
          <button type="button" id="mode-tag" class="mode-tag text-xs font-medium px-3 py-1.5 rounded-lg shrink-0 cursor-pointer transition-all duration-200 flex items-center gap-1.5" style="background: var(--border-subtle); color: var(--text-muted); border: 1px solid var(--border);" title="Click to change mode">
            <span id="mode-tag-label">Ontology</span>
            <svg class="mode-tag-chevron w-3.5 h-3.5 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
          </button>
          <div id="mode-toggle-bar" class="mode-toggle-bar hidden absolute right-0 top-full mt-1.5 z-10 rounded-xl overflow-hidden shadow-xl flex flex-col" style="background: var(--bg-card); border: 1px solid var(--border); min-width: 200px;">
            <div class="flex rounded-lg overflow-hidden" style="background: var(--bg-input);">
              <button type="button" id="mode-option-ontology" class="mode-option flex-1 px-4 py-2.5 text-xs font-medium transition-all" style="color: var(--text-muted);">Ontology</button>
              <button type="button" id="mode-option-agent" class="mode-option flex-1 px-4 py-2.5 text-xs font-medium transition-all" style="color: var(--text-muted);">Agent</button>
            </div>
            <div id="mode-agent-options" class="hidden px-3 py-2.5" style="border-top: 1px solid var(--border);">
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" id="assistant-mode-toggle" class="rounded border-2 w-3.5 h-3.5 accent-pink-500" style="border-color: var(--border); background: var(--bg-input);">
                <span class="text-xs" style="color: var(--text-muted);">Hide reasoning</span>
              </label>
            </div>
          </div>
        </div>
      </div>
      <form id="chat-form" class="chat-form-wrap flex gap-3 p-2.5 rounded-xl">
        <input type="text" id="question-input" placeholder="Ask a question about your ontology..." disabled
          class="chat-input flex-1 rounded-lg px-3.5 py-2.5 font-mono text-sm border transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);">
        <button type="submit" id="send-btn" disabled
          class="px-5 py-2.5 rounded-lg font-medium text-sm btn-send text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-none flex items-center gap-2">
          <span>Send</span>
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
          </svg>
        </button>
      </form>
      <p id="kb-status" class="text-xs mt-2 px-1" style="color: #555; display: none;"></p>
    </div>
  </main>

  <!-- Reasoning viewer modal (agent mode) -->
  <div id="reasoning-modal" class="fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="document.getElementById('reasoning-modal').classList.add('hidden')"></div>
    <div class="modal-content modal-enter absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl max-h-[85vh] rounded-xl p-6 shadow-2xl flex flex-col" style="background: var(--bg-card); border: 1px solid var(--border);" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between mb-4 shrink-0">
        <h3 class="font-semibold text-lg" style="color: var(--text-primary);">Reasoning Steps</h3>
        <button type="button" id="reasoning-modal-close" class="p-1.5 rounded-md transition-colors text-xl leading-none" style="color: var(--text-muted);" aria-label="Close">×</button>
      </div>
      <div id="reasoning-modal-content" class="flex-1 overflow-y-auto text-sm space-y-4" style="color: var(--text-primary);"></div>
    </div>
  </div>

  <script>
    window.APP_CONFIG = {{ "apiBase": "{api_base}" }};
  </script>
  <script src="/static/js/app.bundle.js"></script>
  <script src="/static/js/evaluate.js"></script>
</body>
</html>"""