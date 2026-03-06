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

    <!-- Sidebar tabs -->
    <div class="flex shrink-0 border-b" style="border-color: var(--border);">
      <button type="button" id="tab-knowledge" class="sidebar-tab sidebar-tab-active flex-1 px-4 py-3 text-xs font-semibold uppercase tracking-wider transition-all">
        Knowledge
      </button>
      <button type="button" id="tab-documents" class="sidebar-tab sidebar-tab-inactive flex-1 px-4 py-3 text-xs font-semibold uppercase tracking-wider transition-all">
        Documents
      </button>
      <button type="button" id="tab-evaluate" class="sidebar-tab sidebar-tab-inactive flex-1 px-4 py-3 text-xs font-semibold uppercase tracking-wider transition-all">
        Evaluate
      </button>
    </div>

    <!-- Knowledge tab content: single scrollable area so everything fits the tab -->
    <div id="tab-knowledge-content" class="flex flex-col flex-1 min-h-0 overflow-y-auto">
      <div class="px-5 py-4 shrink-0" style="border-bottom: 1px solid var(--border);">
        <div class="flex items-center justify-between mb-3">
          <p class="text-xs font-semibold uppercase tracking-widest" style="color: var(--text-muted);">Knowledge Bases</p>
          <span id="status-badge" class="status-badge px-2 py-0.5 rounded-full text-xs font-medium empty" style="background: var(--border-subtle); color: var(--text-muted);">Empty</span>
        </div>
        <label for="file-input-create" id="kb-create-btn" class="w-full rounded-lg px-3 py-2.5 text-sm font-medium border transition-all flex items-center justify-center gap-2 cursor-pointer"
          style="background: var(--accent-12); color: var(--accent); border-color: var(--accent-4);">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/></svg>
          Create new KB
        </label>
        <input type="file" id="file-input-create" class="sr-only" accept=".pdf,.docx,.txt,.md" multiple tabindex="-1">
      </div>
      <!-- KB management list: compact cards, all KBs -->
      <div class="px-3 py-3 shrink-0">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs font-medium" style="color: var(--text-muted);">All knowledge bases <span id="kb-count" class="font-mono" style="color: var(--text-muted-2);"></span></p>
          <button type="button" id="kb-refresh-btn" class="text-xs font-medium link-teal hover:opacity-80" title="Refresh list">↻</button>
        </div>
        <div id="kb-list" class="flex flex-col gap-1.5"></div>
        <div id="kb-list-empty" class="hidden py-6 text-center">
          <p class="text-sm" style="color: var(--text-muted-2);">No knowledge bases yet</p>
          <p class="text-xs mt-1" style="color: #555;">Create one with the button above</p>
        </div>
      </div>

    <!-- Ontology Info Card (hidden until KB selected, compact) -->
    <div id="onto-info-panel" class="hidden px-5 py-3 shrink-0 relative" style="border-top: 1px solid var(--border);">
      <div id="onto-card-loading" class="hidden absolute inset-0 flex items-center justify-center z-10 rounded-xl" style="background: var(--bg-overlay);">
        <div class="kb-load-spinner"></div>
      </div>
      <div id="onto-card" class="onto-card onto-card-glow rounded-xl p-3 collapsed" style="background: var(--bg-card); border: 1px solid var(--accent-25);">
        <!-- Header row (clickable: expand + open modal) -->
        <div id="onto-card-header" class="flex items-start gap-3">
          <div class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 mt-0.5" style="background: var(--accent-2);">
            <svg class="w-4 h-4" style="color: var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <p id="onto-card-name" class="font-semibold text-sm leading-snug" style="color: var(--text-primary);"></p>
              <span id="onto-card-ready" class="hidden flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded shrink-0 whitespace-nowrap" style="color:var(--success); background:var(--success-15);">
                <span class="kb-ready-dot"></span>Ready
              </span>
            </div>
            <p id="onto-card-summary" class="text-xs mt-0.5" style="color: var(--text-muted);"></p>
          </div>
          <button type="button" id="onto-card-expand-btn" class="shrink-0 p-1 rounded transition-colors" style="color: var(--text-muted);" aria-label="Expand/collapse">
            <svg id="onto-card-chevron" class="w-4 h-4 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </button>
        </div>

        <!-- Expandable content -->
        <div id="onto-card-expandable" class="onto-card-expandable">
          <p id="onto-card-desc" class="text-xs mt-2 leading-relaxed" style="color: var(--text-muted); display: none;"></p>
          <div id="onto-stats-grid" class="grid grid-cols-3 gap-1.5 mt-3"></div>
          <div id="onto-doc-row" class="hidden flex items-center gap-2 mt-3 pt-3" style="border-top: 1px solid var(--border);">
            <svg class="w-3.5 h-3.5 shrink-0" style="color: var(--text-muted);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
            </svg>
            <span id="onto-doc-name" class="text-xs font-mono truncate" style="color: var(--text-muted);"></span>
          </div>
          <div class="flex items-center justify-between mt-3 pt-3" style="border-top: 1px solid var(--border);">
            <p id="onto-card-date" class="text-xs" style="color: #555;"></p>
            <div class="flex items-center gap-3" onclick="event.stopPropagation()">
              <a href="#" class="graph-viewer-link text-xs font-medium flex items-center gap-1 transition-colors link-teal" target="_blank" rel="noopener noreferrer">
                View graph
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                </svg>
              </a>
              <a href="#" id="download-ontology-link" class="text-xs font-medium flex items-center gap-1 transition-colors link-teal" target="_blank" rel="noopener noreferrer" style="display: none;">
                Download
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
              </a>
              <button type="button" id="delete-kb-btn"
                class="text-xs font-medium flex items-center gap-1 transition-colors"
                style="color: var(--text-muted-2);"
                onmouseover="this.style.color='var(--error)'" onmouseout="this.style.color='var(--text-muted-2)'"
                onclick="deleteActiveKB()">
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
                Delete
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
    </div>

    <!-- Document Management tab content -->
    <div id="tab-documents-content" class="hidden flex flex-col flex-1 min-h-0 overflow-hidden">
    <div class="px-5 py-4 flex-1 min-h-0 overflow-y-auto">
      <p class="text-xs font-semibold uppercase tracking-widest mb-3" style="color: var(--text-muted);">Add Documents</p>
      <p class="text-xs mb-3" style="color: var(--text-muted);">Add documents to the active KB. Select a KB in the Knowledge tab first.</p>
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
      <div id="job-queue-section" class="job-queue-section mt-3">
        <button type="button" id="job-queue-toggle" class="job-queue-toggle w-full flex items-center justify-between py-2 text-xs font-medium" style="color: var(--text-muted);">
          <span>Documents &amp; jobs</span>
          <svg class="job-queue-chevron w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </button>
        <div id="job-queue" class="job-queue-content mt-2 space-y-2 transition-opacity duration-200"></div>
      </div>
    </div>
    </div>

    <!-- Evaluate tab content -->
    <div id="tab-evaluate-content" class="hidden flex flex-col flex-1 min-h-0 overflow-hidden">
      <div class="px-5 py-4 flex flex-col flex-1 min-h-0 overflow-y-auto">
        <p class="text-xs font-semibold uppercase tracking-widest mb-3" style="color: var(--text-muted);">Graph Health &amp; Repair</p>
        <div class="mb-3">
          <label class="block text-xs font-medium mb-1.5" style="color: var(--text-muted);">Knowledge base</label>
          <select id="eval-kb-select" class="w-full rounded-lg px-3 py-2.5 text-sm border transition-all" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);">
            <option value="">Select a KB</option>
          </select>
        </div>
        <div id="eval-panel-state-a" class="rounded-xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
          <div class="flex items-center justify-between mb-3">
            <h4 class="font-semibold text-sm" style="color: var(--text-primary);">Graph Health</h4>
            <span id="eval-health-badge" class="text-xs font-medium px-2 py-0.5 rounded" style="background: var(--border-subtle); color: var(--text-muted);">—</span>
          </div>
          <div id="eval-health-stats" class="text-xs space-y-1 font-mono" style="color: var(--text-muted);">
            <p>Select a KB to view health</p>
          </div>
          <div id="eval-health-warnings" class="mt-3 text-xs" style="color: var(--warning);"></div>
          <div class="mt-3 flex items-center gap-2">
            <button type="button" id="eval-refresh-btn" class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all" style="background: var(--accent-15); color: var(--accent); border: 1px solid var(--accent-4);">Rerun to refresh</button>
            <button type="button" id="eval-repair-btn" class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5" style="background: var(--success-15); color: var(--success); border: 1px solid var(--success-2);" title="Infer missing edges to connect orphans and bridge components">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
              Repair
            </button>
          </div>
        </div>
        <div id="eval-panel-state-b" class="hidden rounded-xl p-4 flex flex-col" style="background: var(--bg-card); border: 1px solid var(--border);">
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

        <!-- Evaluation section (same style as health) -->
        <div id="eval-eval-panel" class="mt-4 rounded-xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
          <div class="flex items-center justify-between mb-3">
            <h4 class="font-semibold text-sm" style="color: var(--text-primary);">QA Evaluation</h4>
            <span id="eval-eval-badge" class="text-xs font-medium px-2 py-0.5 rounded" style="background: var(--border-subtle); color: var(--text-muted);">—</span>
          </div>
          <div class="mb-2 flex items-center gap-2">
            <label class="text-xs" style="color: var(--text-muted);">Questions</label>
            <input type="number" id="eval-num-questions" value="5" min="1" max="500" class="w-16 rounded px-2 py-1 text-xs font-mono border" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);">
          </div>
          <div id="eval-eval-stats" class="text-xs space-y-1 font-mono" style="color: var(--text-muted);">
            <p>Run evaluation to view scores</p>
          </div>
          <div class="mt-3">
            <button type="button" id="eval-run-btn" class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5" style="background: var(--accent-15); color: var(--accent); border: 1px solid var(--accent-4);" title="Run QA evaluation">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
              Run Evaluation
            </button>
          </div>
        </div>
        <div id="eval-eval-progress" class="hidden mt-4 rounded-xl p-4 flex flex-col" style="background: var(--bg-card); border: 1px solid var(--border);">
          <div class="flex items-center gap-2 mb-2">
            <div class="kb-load-spinner w-4 h-4"></div>
            <span id="eval-eval-stage-label" class="text-sm font-medium" style="color: var(--text-primary);">Evaluating...</span>
          </div>
          <div class="h-1.5 rounded-full mb-3 overflow-hidden" style="background: var(--border-subtle);">
            <div id="eval-eval-progress-bar" class="h-full rounded-full transition-all duration-300" style="background: var(--accent); width: 0%;"></div>
          </div>
          <div id="eval-eval-log" class="min-h-[80px] overflow-y-auto text-xs font-mono space-y-1 break-words" style="color: var(--text-muted); max-height: 150px;"></div>
          <div id="eval-eval-error" class="hidden mt-2 px-3 py-2 rounded-lg text-xs" style="background: var(--error-15); color: var(--error);"></div>
        </div>

        <!-- Evaluation Records -->
        <div id="eval-records-panel" class="mt-4 rounded-xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
          <div class="flex items-center justify-between mb-3">
            <h4 class="font-semibold text-sm" style="color: var(--text-primary);">Records</h4>
          </div>
          <div id="eval-records-list" class="space-y-2 max-h-[280px] overflow-y-auto" style="color: var(--text-muted);">
            <p class="text-xs">Select a KB to view evaluation history</p>
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
      <div id="modal-new-fields" class="space-y-4">
        <div>
          <label class="block text-xs font-medium mb-1.5 uppercase tracking-wider" style="color: var(--text-muted);">Title</label>
          <input type="text" id="modal-title" class="w-full rounded-lg px-3.5 py-2.5 text-sm border transition-all" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);" placeholder="e.g. Climate Science Ontology">
        </div>
        <div>
          <label class="block text-xs font-medium mb-1.5 uppercase tracking-wider" style="color: var(--text-muted);">Description <span style="color: #555;">(optional)</span></label>
          <textarea id="modal-description" class="w-full rounded-lg px-3.5 py-2.5 text-sm border resize-none transition-all" rows="3" style="background: var(--bg-input); color: var(--text-primary); border-color: var(--border);" placeholder="What this ontology covers..."></textarea>
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

  <!-- Job details modal -->
  <div id="job-detail-modal" class="job-detail-modal fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="document.getElementById('job-detail-modal').classList.add('hidden')"></div>
    <div class="modal-content modal-enter absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl rounded-xl p-6 shadow-2xl" style="background: var(--bg-card); border: 1px solid var(--border);" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between mb-5">
        <h3 id="job-detail-title" class="font-semibold text-lg" style="color: var(--text-primary);">Job Details</h3>
        <button type="button" id="job-detail-close" class="p-1.5 rounded-md transition-colors text-xl leading-none" style="color: var(--text-muted);" aria-label="Close">×</button>
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

  <!-- Main chat area -->
  <main class="flex-1 flex flex-col min-h-0 overflow-hidden">
    <!-- Header -->
    <header class="shrink-0 px-6 py-3.5 flex items-center justify-between" style="background: var(--bg-sidebar); border-bottom: 1px solid var(--border);">
      <div class="flex items-center gap-3">
        <div>
          <h1 class="font-semibold text-base" style="color: var(--text-primary);">Clearence</h1>
          <p class="text-xs" style="color: var(--text-muted);">Ontology Assistant · Reda Sarehane</p>
        </div>
        <!-- Active ontology pill -->
        <div id="current-ontology-pill" class="hidden items-center gap-2 pl-3 ml-1" style="border-left: 1px solid var(--border);">
          <div class="w-1.5 h-1.5 rounded-full shrink-0" style="background: var(--accent);"></div>
          <div>
            <p class="text-xs font-medium leading-none" style="color: var(--text-primary);"><span id="current-ontology-name"></span></p>
            <p id="current-ontology-stats" class="text-xs mt-0.5 font-mono" style="color: var(--text-muted);"></p>
          </div>
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
      <!-- Sticky ontology summary (visible while chatting) -->
      <div id="chat-onto-sticky" class="chat-onto-sticky hidden sticky top-0 z-20 pb-3">
        <div class="chat-onto-sticky-card rounded-xl px-4 py-3 flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style="background: var(--accent-2);">
            <svg class="w-4 h-4" style="color: var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
            </svg>
          </div>
          <div class="min-w-0">
            <p id="chat-onto-sticky-name" class="text-sm font-semibold truncate" style="color: var(--text-primary);"></p>
            <p id="chat-onto-sticky-desc" class="text-xs mt-0.5 truncate" style="color: var(--text-muted); display: none;"></p>
          </div>
          <div id="chat-onto-sticky-stats" class="ml-auto flex items-center gap-1.5"></div>
          <a href="#" class="graph-viewer-link text-xs font-medium link-teal shrink-0" target="_blank" rel="noopener noreferrer">View graph</a>
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
        <!-- Ontology summary card in chat -->
        <div id="chat-onto-card" class="w-full max-w-lg rounded-2xl p-6 mb-8" style="background: var(--bg-card); border: 1px solid var(--accent-25); box-shadow: 0 0 0 1px var(--accent-12), 0 8px 32px var(--black-45);">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style="background: var(--accent-2);">
              <svg class="w-5 h-5" style="color: var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
              </svg>
            </div>
            <div class="text-left">
              <p id="chat-onto-name" class="font-semibold" style="color: var(--text-primary);"></p>
              <p id="chat-onto-desc" class="text-xs mt-0.5" style="color: var(--text-muted); display: none;"></p>
            </div>
            <div class="ml-auto">
              <span class="px-2.5 py-1 rounded-full text-xs font-medium" style="background: var(--success-15); color: var(--success); border: 1px solid var(--success-2);">Ready</span>
            </div>
          </div>
          <div id="chat-onto-stats" class="grid grid-cols-3 gap-2"></div>
          <div id="chat-onto-docs" class="hidden mt-4 pt-4" style="border-top: 1px solid var(--border);">
            <p class="text-xs font-semibold uppercase tracking-wider mb-2" style="color: var(--text-muted);">Documents</p>
            <div id="chat-onto-docs-list" class="flex flex-wrap gap-2"></div>
          </div>
          <p class="text-sm mt-5 text-center" style="color: var(--text-muted);">Ask a question about this ontology to get started</p>
        </div>

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

    <!-- Typing indicator -->
    <div id="loading-indicator" class="hidden px-6 py-3 shrink-0">
      <div class="typing-pill flex items-center gap-3 px-4 py-2 rounded-full" style="background: var(--bg-card); border: 1px solid var(--border); width: fit-content;">
        <div class="loading-dots flex gap-1.5 items-end">
          <span class="w-2 h-2 rounded-full" style="background: var(--accent);"></span>
          <span class="w-2 h-2 rounded-full" style="background: var(--accent-secondary);"></span>
          <span class="w-2 h-2 rounded-full" style="background: var(--accent);"></span>
        </div>
        <div class="flex items-center gap-2">
          <span id="qa-step-label" class="text-sm" style="color: var(--text-muted);">Retrieving facts...</span>
          <span class="qa-step-dots flex gap-1">
            <span class="w-1.5 h-1.5 rounded-full" data-step="0" style="background: var(--accent);"></span>
            <span class="w-1.5 h-1.5 rounded-full" data-step="1" style="background: var(--border-subtle);"></span>
          </span>
        </div>
      </div>
    </div>

    <!-- Chat input -->
    <div class="shrink-0 px-6 py-4" style="border-top: 1px solid var(--border); background: var(--bg-sidebar);">
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

  <script>
    window.APP_CONFIG = {{ "apiBase": "{api_base}" }};
  </script>
  <script src="/static/js/app.bundle.js"></script>
</body>
</html>"""