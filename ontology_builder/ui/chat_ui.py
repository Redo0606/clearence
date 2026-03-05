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
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Space Grotesk', system-ui, -apple-system, sans-serif; background: #0a0a0f; color: #e8e6e3; min-height: 100vh; }}
    .font-mono {{ font-family: 'JetBrains Mono', monospace; }}

    /* Scrollbar */
    ::-webkit-scrollbar {{ width: 4px; height: 4px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: #2a2a3a; border-radius: 4px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: rgba(236, 72, 153, 0.4); }}

    /* Animations */
    .loading-dots span {{ animation: wave 1.2s ease-in-out infinite both; }}
    .loading-dots span:nth-child(1) {{ animation-delay: 0s; }}
    .loading-dots span:nth-child(2) {{ animation-delay: 0.15s; }}
    .loading-dots span:nth-child(3) {{ animation-delay: 0.3s; }}
    @keyframes wave {{ 0%, 60%, 100% {{ transform: translateY(0); opacity: 0.5; }} 30% {{ transform: translateY(-6px); opacity: 1; }} }}
    @keyframes pulse-glow {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.7; }} }}
    @keyframes fadeSlideUp {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    @keyframes msgUserIn {{ from {{ opacity: 0; transform: translateX(10px) scale(0.98); }} to {{ opacity: 1; transform: translateX(0) scale(1); }} }}
    @keyframes msgAssistantIn {{ from {{ opacity: 0; transform: translateX(-10px) scale(0.99); }} to {{ opacity: 1; transform: translateX(0) scale(1); }} }}
    @keyframes modalIn {{ from {{ opacity: 0; transform: translate(-50%, -50%) scale(0.96); }} to {{ opacity: 1; transform: translate(-50%, -50%) scale(1); }} }}
    @keyframes slideInJob {{ from {{ opacity: 0; transform: translateY(-8px) scale(0.97); }} to {{ opacity: 1; transform: translateY(0) scale(1); }} }}
    @keyframes slideOutJob {{ 0% {{ opacity: 1; transform: translateY(0); max-height: 80px; }} 100% {{ opacity: 0; transform: translateY(6px); max-height: 0; padding: 0; margin: 0; border-width: 0; overflow: hidden; }} }}
    @keyframes stagePulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.35; }} }}
    @keyframes cardIn {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    @keyframes shimmer {{ 0% {{ background-position: -200% 0; }} 100% {{ background-position: 200% 0; }} }}

    /* Sidebar */
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

    /* Drop zone */
    .drop-zone.dragover {{ border-color: #ec4899; background: rgba(236, 72, 153, 0.08); box-shadow: 0 0 16px rgba(236, 72, 153, 0.35); }}
    .drop-zone:hover {{ border-color: rgba(236, 72, 153, 0.3) !important; background: rgba(236, 72, 153, 0.03) !important; }}
    .drop-zone:hover .drop-icon {{ background: rgba(236, 72, 153, 0.15); transform: scale(1.05); }}
    .drop-zone:hover .drop-icon svg {{ transform: translateY(-2px); }}
    .drop-icon {{ transition: all 0.25s ease; }}
    .drop-icon svg {{ transition: transform 0.25s ease; }}

    /* Chat bubbles */
    .bubble-assistant {{ border-left: 3px solid #ec4899; transition: box-shadow 0.2s; }}
    .bubble-assistant:hover {{ box-shadow: 0 0 12px rgba(236, 72, 153, 0.08); }}
    .msg-bubble {{ transition: box-shadow 0.2s, border-color 0.2s; }}
    .msg-bubble:hover {{ box-shadow: 0 0 12px rgba(236, 72, 153, 0.06); }}
    .msg-enter-user {{ animation: msgUserIn 0.3s cubic-bezier(0.22, 1, 0.36, 1) forwards; }}
    .msg-enter-assistant {{ animation: msgAssistantIn 0.35s cubic-bezier(0.22, 1, 0.36, 1) forwards; }}
    .msg-user-bubble {{ box-shadow: 0 2px 14px rgba(236, 72, 153, 0.18); }}
    .msg-user-bubble:hover {{ box-shadow: 0 2px 20px rgba(236, 72, 153, 0.25); }}

    /* Sticky ontology summary in chat */
    .chat-onto-sticky {{ backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); animation: fadeSlideUp 0.25s ease-out; }}
    .chat-onto-sticky-card {{ background: rgba(20,20,26,0.9); border: 1px solid rgba(236,72,153,0.2); box-shadow: 0 0 0 1px rgba(236,72,153,0.1), 0 8px 24px rgba(0,0,0,0.35); }}

    /* Stats */
    .stat-value {{ font-family: 'JetBrains Mono', monospace; color: #ec4899; }}
    .stat-label {{ color: #8a8a94; }}
    .process-step {{ border-left: 2px solid #1a1a24; padding-left: 0.75rem; }}
    .process-step::before {{ content: '▸'; color: #ec4899; margin-right: 0.25rem; }}

    /* Inputs */
    input:focus, select:focus, textarea:focus {{ outline: none; border-color: #ec4899 !important; box-shadow: 0 0 0 2px rgba(236, 72, 153, 0.2); }}
    .chat-input:hover:not(:disabled) {{ border-color: rgba(236, 72, 153, 0.35); transition: border-color 0.2s, box-shadow 0.2s; }}
    .chat-form-wrap {{ background: #1e1e28; border: 1px solid #1a1a24; border-radius: 0.5rem; transition: box-shadow 0.2s, border-color 0.2s; }}
    .chat-form-wrap:focus-within {{ border-color: rgba(236, 72, 153, 0.4); box-shadow: 0 0 0 1px rgba(236, 72, 153, 0.15); }}
    .chat-input {{ background: #14141a !important; }}

    /* Buttons */
    .btn-send {{ background: #ec4899; }}
    .btn-send:hover:not(:disabled) {{ background: #f472b6; box-shadow: 0 0 16px rgba(236, 72, 153, 0.4); }}
    .link-teal {{ color: #ec4899; }}
    .link-teal:hover {{ color: #f472b6; }}

    /* Status */
    .loading-pulse {{ animation: pulse-glow 1.5s ease-in-out infinite; }}
    .typing-pill {{ box-shadow: 0 0 12px rgba(236, 72, 153, 0.08); }}
    .status-badge.ready {{ background: rgba(236, 72, 153, 0.2); color: #ec4899; }}
    .status-badge.empty {{ background: #1a1a24; color: #8a8a94; }}
    .status-badge.processing {{ background: rgba(236, 72, 153, 0.15); color: #ec4899; animation: pulse-glow 1.5s ease-in-out infinite; }}
    .step-tag {{ padding: 0.125rem 0.5rem; border-radius: 4px; background: rgba(236, 72, 153, 0.1); color: #ec4899; font-size: 10px; }}
    .file-badge {{ padding: 2px 8px; border-radius: 4px; background: rgba(236, 72, 153, 0.08); color: #ec4899; font-size: 10px; font-family: 'JetBrains Mono', monospace; font-weight: 500; letter-spacing: 0.025em; }}

    /* Modals */
    .modal-enter {{ animation: modalIn 0.2s ease-out; }}
    .job-detail-modal .modal-content {{ max-height: 85vh; overflow-y: auto; }}

    /* Job cards */
    .job-card {{ background: rgba(20, 20, 26, 0.9); border: 1px solid #2a2a3a; border-radius: 0.5rem; padding: 0.75rem; animation: slideInJob 0.3s cubic-bezier(0.22, 1, 0.36, 1); transition: border-color 0.25s ease, box-shadow 0.25s ease, opacity 0.25s ease; }}
    .job-card:hover {{ border-color: rgba(236, 72, 153, 0.2); box-shadow: 0 0 12px rgba(236, 72, 153, 0.05); }}
    .job-card.removing {{ animation: slideOutJob 0.3s ease-in forwards; pointer-events: none; }}
    .job-card .stage-dot {{ width: 6px; height: 6px; border-radius: 50%; background: #ec4899; animation: stagePulse 1.5s ease-in-out infinite; flex-shrink: 0; }}
    .job-card.done .stage-dot {{ background: #22c55e; animation: none; }}
    .job-card.error .stage-dot {{ background: #ef4444; animation: none; }}
    .job-card.cancelled .stage-dot {{ background: #6b6b76; animation: none; }}
    .job-card.job-clickable {{ cursor: pointer; }}
    .job-cancel {{ opacity: 0; transition: opacity 0.15s ease; }}
    .job-card:hover .job-cancel {{ opacity: 1; }}

    /* Ontology info card */
    .onto-card {{ animation: cardIn 0.3s ease-out; }}
    .onto-stat-chip {{ background: #14141a; border: 1px solid #1a1a24; border-radius: 6px; padding: 6px 10px; transition: border-color 0.2s, background 0.2s; }}
    .onto-stat-chip:hover {{ border-color: rgba(236, 72, 153, 0.25); background: rgba(236, 72, 153, 0.04); }}
    .onto-card-glow {{ box-shadow: 0 0 0 1px rgba(236, 72, 153, 0.12), 0 4px 24px rgba(0,0,0,0.4); }}

    /* Empty state */
    .empty-state-card {{ transition: border-color 0.25s ease, box-shadow 0.25s ease; }}
    .empty-state-card:hover {{ border-color: rgba(236, 72, 153, 0.25); box-shadow: 0 0 16px rgba(236, 72, 153, 0.06); }}
    .empty-icon {{ transition: transform 0.25s ease, background 0.25s ease; }}
    .empty-state-card:hover .empty-icon {{ background: rgba(236, 72, 153, 0.15); transform: scale(1.05); }}

    /* Shimmer skeleton */
    .skeleton {{ background: linear-gradient(90deg, #1a1a24 25%, #22223a 50%, #1a1a24 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 4px; }}

    /* Modal mode tabs */
    .mode-tab-active {{ background: rgba(236,72,153,0.15); color: #ec4899; border-bottom: 2px solid #ec4899; }}
    .mode-tab-inactive {{ background: #14141a; color: #8a8a94; border-bottom: 2px solid transparent; }}
    .mode-tab-inactive:hover {{ color: #e8e6e3; background: rgba(255,255,255,0.04); }}
  </style>
</head>
<body class="flex">
  <!-- Sidebar -->
  <aside id="sidebar" class="sidebar w-80 flex flex-col shrink-0 overflow-y-auto" style="background: #14141a; border-right: 1px solid #1a1a24;">

    <!-- Brand -->
    <div class="px-5 py-4 flex items-center gap-3 shrink-0" style="border-bottom: 1px solid #1a1a24;">
      <div class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style="background: rgba(236, 72, 153, 0.15);">
        <svg class="w-4 h-4" style="color: #ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/>
        </svg>
      </div>
      <div>
        <p class="font-semibold text-sm" style="color: #e8e6e3;">Ontology Graph</p>
        <p class="text-xs" style="color: #8a8a94;">Knowledge Management</p>
      </div>
    </div>

    <!-- KB Selector -->
    <div class="px-5 py-4 shrink-0" style="border-bottom: 1px solid #1a1a24;">
      <div class="flex items-center justify-between mb-3">
        <p class="text-xs font-semibold uppercase tracking-widest" style="color: #8a8a94;">Knowledge Base</p>
        <span id="status-badge" class="status-badge px-2 py-0.5 rounded-full text-xs font-medium empty" style="background: #1a1a24; color: #8a8a94;">Empty</span>
      </div>
      <select id="kb-select" class="w-full rounded-lg px-3 py-2.5 text-sm font-mono border transition-all"
        style="background: #1e1e28; color: #e8e6e3; border-color: #2a2a3a;">
        <option value="">— Select knowledge base —</option>
        <option value="__upload__">＋ Upload new document</option>
      </select>
    </div>

    <!-- Ontology Info Card (hidden until KB selected) -->
    <div id="onto-info-panel" class="hidden px-5 py-4 shrink-0" style="border-bottom: 1px solid #1a1a24;">
      <div id="onto-card" class="onto-card onto-card-glow rounded-xl p-4" style="background: #1e1e28; border: 1px solid rgba(236,72,153,0.18);">
        <!-- Header row -->
        <div class="flex items-start gap-3">
          <div class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 mt-0.5" style="background: rgba(236, 72, 153, 0.15);">
            <svg class="w-4 h-4" style="color: #ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <p id="onto-card-name" class="font-semibold text-sm leading-snug" style="color: #e8e6e3;"></p>
            <p id="onto-card-desc" class="text-xs mt-0.5 leading-relaxed" style="color: #8a8a94; display: none;"></p>
          </div>
        </div>

        <!-- Stats grid -->
        <div id="onto-stats-grid" class="grid grid-cols-3 gap-1.5 mt-3"></div>

        <!-- Document info -->
        <div id="onto-doc-row" class="hidden flex items-center gap-2 mt-3 pt-3" style="border-top: 1px solid #1a1a24;">
          <svg class="w-3.5 h-3.5 shrink-0" style="color: #8a8a94;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          <span id="onto-doc-name" class="text-xs font-mono truncate" style="color: #8a8a94;"></span>
        </div>

        <!-- Footer -->
        <div class="flex items-center justify-between mt-3 pt-3" style="border-top: 1px solid #1a1a24;">
          <p id="onto-card-date" class="text-xs" style="color: #555;"></p>
          <div class="flex items-center gap-3">
            <a href="#" class="graph-viewer-link text-xs font-medium flex items-center gap-1 transition-colors link-teal" target="_blank" rel="noopener noreferrer">
              View graph
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
              </svg>
            </a>
            <button type="button" id="delete-kb-btn"
              class="text-xs font-medium flex items-center gap-1 transition-colors"
              style="color: #6b7280;"
              onmouseover="this.style.color='#ef4444'" onmouseout="this.style.color='#6b7280'"
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

    <!-- Add Documents -->
    <div class="px-5 py-4 shrink-0" style="border-bottom: 1px solid #1a1a24;">
      <p class="text-xs font-semibold uppercase tracking-widest mb-3" style="color: #8a8a94;">Add Documents</p>
      <div id="drop-zone" class="drop-zone border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all"
        style="border-color: #2a2a3a; color: #8a8a94; background: rgba(30, 30, 40, 0.4);">
        <div class="drop-icon mx-auto mb-2 w-10 h-10 rounded-full flex items-center justify-center" style="background: rgba(236, 72, 153, 0.1);">
          <svg class="w-5 h-5" style="color: #ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
        </div>
        <p class="text-sm font-medium" style="color: #e8e6e3;">Drop your document here</p>
        <p class="mt-0.5 text-xs">or <span class="link-teal font-medium cursor-pointer">browse files</span></p>
        <div class="flex justify-center gap-1.5 mt-2.5">
          <span class="file-badge">PDF</span>
          <span class="file-badge">DOCX</span>
          <span class="file-badge">TXT</span>
          <span class="file-badge">MD</span>
        </div>
        <input type="file" id="file-input" class="hidden" accept=".pdf,.docx,.txt,.md">
      </div>
      <div id="job-queue" class="mt-3 space-y-2"></div>
    </div>

    <!-- Spacer -->
    <div class="flex-1"></div>

    <!-- Footer links -->
    <div class="px-5 py-3 flex items-center gap-4 shrink-0" style="border-top: 1px solid #1a1a24;">
      <span class="text-xs" style="color: #555;">Clarence v1.0</span>
    </div>
  </aside>
  <div class="sidebar-overlay" id="sidebar-overlay" aria-hidden="true"></div>

  <!-- Ontology creation modal -->
  <div id="create-modal" class="fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="document.getElementById('create-modal').classList.add('hidden')"></div>
    <div class="modal-content modal-enter absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md rounded-xl p-6 shadow-2xl" style="background: #1e1e28; border: 1px solid #2a2a3a;" onclick="event.stopPropagation()">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style="background: rgba(236, 72, 153, 0.15);">
          <svg class="w-5 h-5" style="color: #ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
        </div>
        <div>
          <h3 id="modal-heading" class="font-semibold text-lg" style="color: #e8e6e3;">New Ontology</h3>
          <p id="modal-filename" class="text-xs mt-0.5" style="color: #8a8a94;"></p>
        </div>
      </div>
      <!-- Mode toggle: only visible when an active KB exists -->
      <div id="modal-mode-section" class="hidden mb-4 rounded-lg overflow-hidden" style="border: 1px solid #2a2a3a;">
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
          <label class="block text-xs font-medium mb-1.5 uppercase tracking-wider" style="color: #8a8a94;">Title</label>
          <input type="text" id="modal-title" class="w-full rounded-lg px-3.5 py-2.5 text-sm border transition-all" style="background: #14141a; color: #e8e6e3; border-color: #2a2a3a;" placeholder="e.g. Climate Science Ontology">
        </div>
        <div>
          <label class="block text-xs font-medium mb-1.5 uppercase tracking-wider" style="color: #8a8a94;">Description <span style="color: #555;">(optional)</span></label>
          <textarea id="modal-description" class="w-full rounded-lg px-3.5 py-2.5 text-sm border resize-none transition-all" rows="3" style="background: #14141a; color: #e8e6e3; border-color: #2a2a3a;" placeholder="What this ontology covers..."></textarea>
        </div>
        <div class="flex items-center gap-2">
          <input type="checkbox" id="modal-parallel" checked class="rounded border-2 w-4 h-4 accent-pink-500" style="border-color: #2a2a3a; background: #14141a;">
          <label for="modal-parallel" class="text-sm" style="color: #e8e6e3;">Parallel extraction (4 workers)</label>
        </div>
      </div>
      <div id="modal-extend-fields" class="hidden space-y-4">
        <div class="rounded-lg p-3" style="background: rgba(236,72,153,0.06); border: 1px solid rgba(236,72,153,0.18);">
          <p class="text-xs" style="color: #8a8a94;">The extracted knowledge from this document will be <span class="font-semibold" style="color:#e8e6e3;">merged into the active ontology</span>. Existing concepts and relations are preserved.</p>
        </div>
        <div class="flex items-center gap-2">
          <input type="checkbox" id="modal-parallel-extend" checked class="rounded border-2 w-4 h-4 accent-pink-500" style="border-color: #2a2a3a; background: #14141a;">
          <label for="modal-parallel-extend" class="text-sm" style="color: #e8e6e3;">Parallel extraction (4 workers)</label>
        </div>
      </div>
      <div class="mt-6 flex gap-3 justify-end">
        <button type="button" id="modal-cancel" class="px-4 py-2.5 rounded-lg text-sm transition-all" style="background: #14141a; color: #8a8a94; border: 1px solid #2a2a3a;">Cancel</button>
        <button type="button" id="modal-confirm" class="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-all btn-send">Create &amp; Build</button>
      </div>
    </div>
  </div>

  <!-- Job details modal -->
  <div id="job-detail-modal" class="job-detail-modal fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="document.getElementById('job-detail-modal').classList.add('hidden')"></div>
    <div class="modal-content modal-enter absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg rounded-xl p-6 shadow-2xl" style="background: #1e1e28; border: 1px solid #2a2a3a;" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between mb-5">
        <h3 id="job-detail-title" class="font-semibold text-lg" style="color: #e8e6e3;">Job Details</h3>
        <button type="button" id="job-detail-close" class="p-1.5 rounded-md transition-colors text-xl leading-none" style="color: #8a8a94;" aria-label="Close">×</button>
      </div>
      <div id="job-detail-content" class="space-y-4 text-sm" style="color: #e8e6e3;"></div>
    </div>
  </div>

  <!-- Delete confirmation modal -->
  <div id="delete-modal" class="fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="document.getElementById('delete-modal').classList.add('hidden')"></div>
    <div class="modal-content modal-enter absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-sm rounded-xl p-6 shadow-2xl" style="background: #1e1e28; border: 1px solid #2a2a3a;" onclick="event.stopPropagation()">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style="background: rgba(239, 68, 68, 0.15);">
          <svg class="w-5 h-5" style="color: #ef4444;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
        </div>
        <div>
          <h3 class="font-semibold text-base" style="color: #e8e6e3;">Delete Ontology</h3>
          <p class="text-xs mt-0.5" style="color: #8a8a94;">This action cannot be undone</p>
        </div>
      </div>
      <p class="text-sm mb-5" style="color: #8a8a94;">Are you sure you want to delete <span id="delete-modal-name" class="font-semibold" style="color:#e8e6e3;"></span>? All extracted knowledge will be permanently removed.</p>
      <div class="flex gap-3 justify-end">
        <button type="button" id="delete-modal-cancel" class="px-4 py-2.5 rounded-lg text-sm transition-all" style="background: #14141a; color: #8a8a94; border: 1px solid #2a2a3a;">Cancel</button>
        <button type="button" id="delete-modal-confirm" class="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-all" style="background: #ef4444; border: 1px solid #dc2626;">Delete</button>
      </div>
    </div>
  </div>

  <!-- Main chat area -->
  <main class="flex-1 flex flex-col min-h-screen overflow-hidden">
    <!-- Header -->
    <header class="shrink-0 px-6 py-3.5 flex items-center justify-between" style="background: #14141a; border-bottom: 1px solid #1a1a24;">
      <div class="flex items-center gap-3">
        <div>
          <h1 class="font-semibold text-base" style="color: #e8e6e3;">Clarence</h1>
          <p class="text-xs" style="color: #8a8a94;">Ontology Assistant</p>
        </div>
        <!-- Active ontology pill -->
        <div id="current-ontology-pill" class="hidden items-center gap-2 pl-3 ml-1" style="border-left: 1px solid #1a1a24;">
          <div class="w-1.5 h-1.5 rounded-full shrink-0" style="background: #ec4899;"></div>
          <div>
            <p class="text-xs font-medium leading-none" style="color: #e8e6e3;"><span id="current-ontology-name"></span></p>
            <p id="current-ontology-stats" class="text-xs mt-0.5 font-mono" style="color: #8a8a94;"></p>
          </div>
        </div>
      </div>
      <button id="sidebar-toggle" class="p-2 rounded-md transition-colors flex items-center justify-center" style="color: #8a8a94;" onmouseover="this.style.background='#1e1e28'" onmouseout="this.style.background='transparent'" type="button" aria-label="Toggle sidebar">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
      </button>
    </header>

    <!-- Messages -->
    <div id="messages" class="flex-1 overflow-y-auto p-6 space-y-5" style="scroll-behavior: smooth; background: #0a0a0f;">
      <!-- Sticky ontology summary (visible while chatting) -->
      <div id="chat-onto-sticky" class="chat-onto-sticky hidden sticky top-0 z-20 pb-3">
        <div class="chat-onto-sticky-card rounded-xl px-4 py-3 flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style="background: rgba(236, 72, 153, 0.15);">
            <svg class="w-4 h-4" style="color: #ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
            </svg>
          </div>
          <div class="min-w-0">
            <p id="chat-onto-sticky-name" class="text-sm font-semibold truncate" style="color: #e8e6e3;"></p>
            <p id="chat-onto-sticky-desc" class="text-xs mt-0.5 truncate" style="color: #8a8a94; display: none;"></p>
          </div>
          <div id="chat-onto-sticky-stats" class="ml-auto flex items-center gap-1.5"></div>
          <a href="#" class="graph-viewer-link text-xs font-medium link-teal shrink-0" target="_blank" rel="noopener noreferrer">View graph</a>
        </div>
      </div>

      <!-- Empty state: no ontology selected -->
      <div id="empty-state-no-kb" class="flex flex-col items-center justify-center py-16 text-center">
        <div class="w-16 h-16 rounded-2xl flex items-center justify-center mb-5" style="background: rgba(236, 72, 153, 0.08); border: 1px solid rgba(236, 72, 153, 0.15);">
          <svg class="w-8 h-8" style="color: #ec4899; opacity: 0.6;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/>
          </svg>
        </div>
        <p class="text-lg font-semibold" style="color: #e8e6e3;">No ontology selected</p>
        <p class="mt-2 text-sm max-w-xs" style="color: #8a8a94;">Select a knowledge base from the sidebar, or upload a document to get started.</p>
      </div>

      <!-- Empty state: ontology selected, ready to chat -->
      <div id="empty-state-ready" class="hidden flex-col items-center justify-center py-10 text-center">
        <!-- Ontology summary card in chat -->
        <div id="chat-onto-card" class="w-full max-w-lg rounded-2xl p-6 mb-8" style="background: #1e1e28; border: 1px solid rgba(236,72,153,0.18); box-shadow: 0 0 0 1px rgba(236,72,153,0.08), 0 8px 32px rgba(0,0,0,0.4);">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style="background: rgba(236, 72, 153, 0.15);">
              <svg class="w-5 h-5" style="color: #ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
              </svg>
            </div>
            <div class="text-left">
              <p id="chat-onto-name" class="font-semibold" style="color: #e8e6e3;"></p>
              <p id="chat-onto-desc" class="text-xs mt-0.5" style="color: #8a8a94; display: none;"></p>
            </div>
            <div class="ml-auto">
              <span class="px-2.5 py-1 rounded-full text-xs font-medium" style="background: rgba(34,197,94,0.15); color: #22c55e; border: 1px solid rgba(34,197,94,0.2);">Ready</span>
            </div>
          </div>
          <div id="chat-onto-stats" class="grid grid-cols-3 gap-2"></div>
          <p class="text-sm mt-5 text-center" style="color: #8a8a94;">Ask a question about this ontology to get started</p>
        </div>

        <!-- Prompt suggestions -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
          <button type="button" onclick="fillPrompt('What are the main classes in this ontology?')"
            class="suggestion-btn text-left px-4 py-3 rounded-xl text-sm transition-all"
            style="background: #1e1e28; border: 1px solid #2a2a3a; color: #e8e6e3;">
            <p class="font-medium text-xs mb-1" style="color: #ec4899;">Explore</p>
            What are the main classes?
          </button>
          <button type="button" onclick="fillPrompt('What instances exist in this ontology?')"
            class="suggestion-btn text-left px-4 py-3 rounded-xl text-sm transition-all"
            style="background: #1e1e28; border: 1px solid #2a2a3a; color: #e8e6e3;">
            <p class="font-medium text-xs mb-1" style="color: #ec4899;">Instances</p>
            What instances exist?
          </button>
          <button type="button" onclick="fillPrompt('How are entities related to each other?')"
            class="suggestion-btn text-left px-4 py-3 rounded-xl text-sm transition-all"
            style="background: #1e1e28; border: 1px solid #2a2a3a; color: #e8e6e3;">
            <p class="font-medium text-xs mb-1" style="color: #ec4899;">Relations</p>
            How are entities related?
          </button>
          <button type="button" onclick="fillPrompt('Summarize the key concepts in this knowledge base')"
            class="suggestion-btn text-left px-4 py-3 rounded-xl text-sm transition-all"
            style="background: #1e1e28; border: 1px solid #2a2a3a; color: #e8e6e3;">
            <p class="font-medium text-xs mb-1" style="color: #ec4899;">Summary</p>
            Summarize key concepts
          </button>
        </div>
      </div>

    </div>

    <!-- Typing indicator -->
    <div id="loading-indicator" class="hidden px-6 py-3 shrink-0">
      <div class="typing-pill flex items-center gap-3 px-4 py-2 rounded-full" style="background: #1e1e28; border: 1px solid #1a1a24; width: fit-content;">
        <div class="loading-dots flex gap-1.5 items-end">
          <span class="w-2 h-2 rounded-full" style="background: #ec4899;"></span>
          <span class="w-2 h-2 rounded-full" style="background: #f472b6;"></span>
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

    <!-- Chat input -->
    <div class="shrink-0 px-6 py-4" style="border-top: 1px solid #1a1a24; background: #14141a;">
      <form id="chat-form" class="chat-form-wrap flex gap-3 p-2.5 rounded-xl">
        <input type="text" id="question-input" placeholder="Ask a question about your ontology..." disabled
          class="chat-input flex-1 rounded-lg px-3.5 py-2.5 font-mono text-sm border transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          style="background: #14141a; color: #e8e6e3; border-color: #1a1a24;">
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
    const API = '{API_BASE}';
    let _kbData = [];

    function parseError(data) {{
      if (typeof data?.detail === 'string') return data.detail;
      if (Array.isArray(data?.detail)) return data.detail.map(d => d.msg || JSON.stringify(d)).join('; ');
      return data?.detail ? String(data.detail) : 'Request failed';
    }}

    // DOM refs
    const messagesEl = document.getElementById('messages');
    const emptyStateNoKb = document.getElementById('empty-state-no-kb');
    const emptyStateReady = document.getElementById('empty-state-ready');
    const chatOntoSticky = document.getElementById('chat-onto-sticky');
    const loadingIndicator = document.getElementById('loading-indicator');
    const chatForm = document.getElementById('chat-form');
    const questionInput = document.getElementById('question-input');
    const sendBtn = document.getElementById('send-btn');
    const kbSelect = document.getElementById('kb-select');
    const kbStatus = document.getElementById('kb-status');
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const jobQueue = document.getElementById('job-queue');
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const statusBadge = document.getElementById('status-badge');
    const ontoInfoPanel = document.getElementById('onto-info-panel');
    const currentOntologyPill = document.getElementById('current-ontology-pill');
    const currentOntologyName = document.getElementById('current-ontology-name');
    const currentOntologyStats = document.getElementById('current-ontology-stats');

    let lastReportTotals = null;
    let _hasMessages = false;

    function setStatusBadge(status) {{
      statusBadge.className = 'status-badge px-2 py-0.5 rounded-full text-xs font-medium ' + status;
      const labels = {{ ready: 'Active', empty: 'Empty', processing: 'Building' }};
      statusBadge.textContent = labels[status] || status;
    }}

    function setInputsEnabled(enabled) {{
      questionInput.disabled = !enabled;
      sendBtn.disabled = !enabled;
    }}

    function setStickySummaryVisible(visible) {{
      chatOntoSticky.classList.toggle('hidden', !visible);
    }}

    function formatDate(ts) {{
      if (!ts) return '';
      const d = new Date(ts * 1000);
      return d.toLocaleDateString(undefined, {{ month: 'short', day: 'numeric', year: 'numeric' }});
    }}

    function fmtNum(n) {{
      if (n === undefined || n === null) return '0';
      return Number(n).toLocaleString();
    }}

    function renderOntologyCard(kb) {{
      if (!kb) {{
        ontoInfoPanel.classList.add('hidden');
        currentOntologyPill.classList.add('hidden');
        currentOntologyPill.classList.remove('flex');
        return;
      }}
      const stats = kb.stats || {{}};
      const name = kb.name || kb.id;
      const desc = kb.description || '';

      // Sidebar card
      document.getElementById('onto-card-name').textContent = name;
      const descEl = document.getElementById('onto-card-desc');
      if (desc) {{
        descEl.textContent = desc;
        descEl.style.display = '';
      }} else {{
        descEl.style.display = 'none';
      }}

      // Stats grid
      const grid = document.getElementById('onto-stats-grid');
      grid.innerHTML = '';
      const statDefs = [
        ['Classes', stats.classes ?? 0, 'cls'],
        ['Instances', stats.instances ?? 0, 'inst'],
        ['Edges', stats.edges ?? 0, 'edges'],
        ['Axioms', stats.axioms ?? 0, 'ax'],
        ['Relations', stats.relations ?? 0, 'rel'],
        ['Data props', stats.data_properties ?? 0, 'dp'],
      ];
      const nonZero = statDefs.filter(([,v]) => v > 0);
      const show = nonZero.length > 0 ? nonZero : statDefs.slice(0, 3);
      show.forEach(([label, val]) => {{
        const chip = document.createElement('div');
        chip.className = 'onto-stat-chip text-center';
        chip.innerHTML = '<p class="stat-value text-sm font-semibold">' + fmtNum(val) + '</p>'
          + '<p class="text-xs mt-0.5" style="color:#555;">' + label + '</p>';
        grid.appendChild(chip);
      }});

      // Date
      document.getElementById('onto-card-date').textContent = kb.created_at ? formatDate(kb.created_at) : '';

      ontoInfoPanel.classList.remove('hidden');

      // Header pill
      currentOntologyPill.classList.remove('hidden');
      currentOntologyPill.classList.add('flex');
      currentOntologyName.textContent = name;
      const statParts = [];
      if (stats.classes) statParts.push(fmtNum(stats.classes) + ' cls');
      if (stats.edges) statParts.push(fmtNum(stats.edges) + ' edges');
      currentOntologyStats.textContent = statParts.join(' · ');

      // Chat empty state card
      document.getElementById('chat-onto-name').textContent = name;
      const chatDescEl = document.getElementById('chat-onto-desc');
      if (desc) {{
        chatDescEl.textContent = desc;
        chatDescEl.style.display = '';
      }} else {{
        chatDescEl.style.display = 'none';
      }}

      const chatStatsGrid = document.getElementById('chat-onto-stats');
      chatStatsGrid.innerHTML = '';
      const chatStatDefs = [
        ['Classes', stats.classes ?? 0],
        ['Instances', stats.instances ?? 0],
        ['Relations', stats.relations ?? 0],
        ['Edges', stats.edges ?? 0],
        ['Axioms', stats.axioms ?? 0],
        ['Data Properties', stats.data_properties ?? 0],
      ];
      chatStatDefs.forEach(([label, val]) => {{
        const chip = document.createElement('div');
        chip.className = 'rounded-lg px-3 py-2.5 text-center';
        chip.style.cssText = 'background:#14141a; border:1px solid #1a1a24;';
        chip.innerHTML = '<p class="stat-value text-base font-semibold">' + fmtNum(val) + '</p>'
          + '<p class="text-xs mt-0.5 stat-label">' + label + '</p>';
        chatStatsGrid.appendChild(chip);
      }});

      // Sticky chat summary
      document.getElementById('chat-onto-sticky-name').textContent = name;
      const stickyDescEl = document.getElementById('chat-onto-sticky-desc');
      if (desc) {{
        stickyDescEl.textContent = desc;
        stickyDescEl.style.display = '';
      }} else {{
        stickyDescEl.style.display = 'none';
      }}
      const stickyStats = document.getElementById('chat-onto-sticky-stats');
      stickyStats.innerHTML = '';
      const stickyStatDefs = [
        ['C', stats.classes ?? 0],
        ['I', stats.instances ?? 0],
        ['E', stats.edges ?? 0],
      ];
      stickyStatDefs.forEach(([label, val]) => {{
        const chip = document.createElement('span');
        chip.className = 'text-xs font-mono px-2 py-1 rounded-md';
        chip.style.cssText = 'background:#14141a; border:1px solid #1a1a24; color:#8a8a94;';
        chip.textContent = label + ': ' + fmtNum(val);
        stickyStats.appendChild(chip);
      }});
    }}

    function showEmptyState(hasKb) {{
      if (_hasMessages) {{
        emptyStateNoKb.classList.add('hidden');
        emptyStateReady.classList.add('hidden');
        setStickySummaryVisible(hasKb);
        return;
      }}
      setStickySummaryVisible(false);
      if (hasKb) {{
        emptyStateNoKb.classList.add('hidden');
        emptyStateReady.classList.remove('hidden');
        emptyStateReady.classList.add('flex');
      }} else {{
        emptyStateNoKb.classList.remove('hidden');
        emptyStateReady.classList.add('hidden');
        emptyStateReady.classList.remove('flex');
      }}
    }}

    async function fetchKBs() {{
      const res = await fetch(API + '/knowledge-bases');
      if (!res.ok) return {{ items: [], active_id: null }};
      return res.json();
    }}

    async function loadKBs() {{
      const data = await fetchKBs();
      _kbData = data.items || [];
      kbSelect.innerHTML = '<option value="">— Select knowledge base —</option><option value="__upload__">＋ Upload new document</option>';
      for (const kb of _kbData) {{
        const opt = document.createElement('option');
        opt.value = kb.id;
        opt.textContent = kb.name;
        if (kb.id === data.active_id) opt.selected = true;
        kbSelect.appendChild(opt);
      }}
      if (data.active_id) {{
        const activeKb = _kbData.find(k => k.id === data.active_id);
        setInputsEnabled(true);
        setStatusBadge('ready');
        renderOntologyCard(activeKb || {{ id: data.active_id, name: data.active_id }});
        showEmptyState(true);
      }} else {{
        setInputsEnabled(false);
        setStatusBadge('empty');
        renderOntologyCard(null);
        showEmptyState(false);
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
      if (id === '__upload__') {{
        fileInput.click();
        kbSelect.value = '';
        return;
      }}
      if (!id) {{
        renderOntologyCard(null);
        setInputsEnabled(false);
        setStatusBadge('empty');
        showEmptyState(false);
        return;
      }}
      try {{
        await activateKB(id);
      }} catch (e) {{
        kbStatus.textContent = 'Error: ' + e.message;
        kbStatus.style.display = '';
      }}
    }});

    function fillPrompt(text) {{
      questionInput.value = text;
      questionInput.focus();
    }}

    function hideEmptyStates() {{
      _hasMessages = true;
      emptyStateNoKb.classList.add('hidden');
      emptyStateReady.classList.add('hidden');
      emptyStateReady.classList.remove('flex');
      setStickySummaryVisible(Boolean(kbSelect.value && kbSelect.value !== '__upload__'));
    }}

    function renderInlineMarkdown(value) {{
      const text = esc(String(value || ''));
      return text
        .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded text-xs font-mono" style="background:#14141a;border:1px solid #1a1a24;color:#e8e6e3;">$1</code>')
        .replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>')
        .replace(/\\*([^*]+)\\*/g, '<em>$1</em>')
        .replace(/\\[([a-zA-Z_][a-zA-Z0-9_\\-]*:[^\\]\\n]+)\\]/g, '<span class="px-1.5 py-0.5 rounded text-xs font-mono align-middle" style="background:rgba(236,72,153,0.1); color:#ec4899;">[$1]</span>');
    }}

    function renderAssistantGuide(content) {{
      const wrapper = document.createElement('div');
      wrapper.className = 'space-y-2.5';
      const lines = String(content || '').split('\\n');
      let list = null;
      let paraParts = [];

      function flushParagraph() {{
        if (!paraParts.length) return;
        const p = document.createElement('p');
        p.className = 'text-sm leading-relaxed';
        p.innerHTML = renderInlineMarkdown(paraParts.join(' '));
        wrapper.appendChild(p);
        paraParts = [];
      }}

      function flushList() {{
        if (!list) return;
        wrapper.appendChild(list);
        list = null;
      }}

      lines.forEach((line) => {{
        const trimmed = line.trim();
        if (!trimmed) {{
          flushParagraph();
          flushList();
          return;
        }}

        if (trimmed.startsWith('### ')) {{
          flushParagraph();
          flushList();
          const h4 = document.createElement('h4');
          h4.className = 'text-sm font-semibold mt-1';
          h4.style.color = '#e8e6e3';
          h4.innerHTML = renderInlineMarkdown(trimmed.slice(4));
          wrapper.appendChild(h4);
          return;
        }}

        if (trimmed.startsWith('## ')) {{
          flushParagraph();
          flushList();
          const h3 = document.createElement('h3');
          h3.className = 'text-base font-semibold mt-1';
          h3.style.color = '#ec4899';
          h3.innerHTML = renderInlineMarkdown(trimmed.slice(3));
          wrapper.appendChild(h3);
          return;
        }}

        if (trimmed.startsWith('- ')) {{
          flushParagraph();
          if (!list) {{
            list = document.createElement('ul');
            list.className = 'text-sm leading-relaxed space-y-1 pl-5 list-disc';
          }}
          const li = document.createElement('li');
          li.innerHTML = renderInlineMarkdown(trimmed.slice(2));
          list.appendChild(li);
          return;
        }}

        flushList();
        paraParts.push(trimmed);
      }});

      flushParagraph();
      flushList();
      return wrapper;
    }}

    function appendMessage(role, content, sources, numFactsUsed) {{
      hideEmptyStates();
      const div = document.createElement('div');
      div.className = 'flex ' + (role === 'user' ? 'justify-end msg-enter-user' : 'justify-start msg-enter-assistant');
      const bubble = document.createElement('div');
      bubble.className = 'msg-bubble max-w-[85%] rounded-xl px-4 py-3.5 ' +
        (role === 'user' ? 'msg-user-bubble' : 'bubble-assistant');
      bubble.style.background = role === 'user' ? '#ec4899' : '#1e1e28';
      bubble.style.color = role === 'user' ? '#fff' : '#e8e6e3';
      bubble.style.border = '1px solid ' + (role === 'user' ? 'rgba(236,72,153,0.6)' : '#1a1a24');

      if (role === 'assistant') {{
        // Meta row
        const metaRow = document.createElement('div');
        metaRow.className = 'flex items-center gap-2 mb-2.5';
        const iconWrap = document.createElement('div');
        iconWrap.className = 'w-5 h-5 rounded flex items-center justify-center shrink-0';
        iconWrap.style.background = 'rgba(236,72,153,0.15)';
        iconWrap.innerHTML = '<svg class="w-3 h-3" style="color:#ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>';
        metaRow.appendChild(iconWrap);
        const metaLabel = document.createElement('span');
        metaLabel.className = 'text-xs font-medium';
        metaLabel.style.color = '#ec4899';
        metaLabel.textContent = 'Clarence';
        metaRow.appendChild(metaLabel);
        if (numFactsUsed > 0) {{
          const factsBadge = document.createElement('span');
          factsBadge.className = 'text-xs px-1.5 py-0.5 rounded font-mono';
          factsBadge.style.cssText = 'background:rgba(236,72,153,0.1); color:#ec4899;';
          factsBadge.textContent = numFactsUsed + ' facts';
          metaRow.appendChild(factsBadge);
        }}
        bubble.appendChild(metaRow);

        // Reasoning block
        const hasReasoning = (numFactsUsed !== undefined && numFactsUsed > 0) || (sources && sources.length > 0);
        if (hasReasoning) {{
          const reasonDiv = document.createElement('details');
          reasonDiv.className = 'mb-3 rounded-lg overflow-hidden';
          reasonDiv.style.cssText = 'border:1px solid #1a1a24; background:#14141a;';
          const summary = document.createElement('summary');
          summary.className = 'cursor-pointer px-3 py-2 text-xs font-medium flex items-center gap-2';
          summary.style.color = '#8a8a94';
          summary.innerHTML = '<svg class="w-3 h-3 shrink-0" style="color:#ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg> Reasoning trace';
          reasonDiv.appendChild(summary);
          const reasonContent = document.createElement('div');
          reasonContent.className = 'px-3 pb-2.5 pt-1 space-y-1.5 text-xs font-mono';
          reasonContent.style.color = '#8a8a94';
          const steps = [];
          steps.push('▸ Retrieve');
          if (numFactsUsed !== undefined) steps.push('  Retrieved ' + numFactsUsed + ' facts from ontology graph');
          steps.push('▸ Synthesize');
          if (sources && sources.length > 0) steps.push('  Used ' + sources.length + ' source' + (sources.length > 1 ? 's' : '') + ' in answer');
          steps.push('▸ Answer');
          steps.forEach(s => {{
            const p = document.createElement('p');
            p.textContent = s;
            reasonContent.appendChild(p);
          }});
          reasonDiv.appendChild(reasonContent);
          bubble.appendChild(reasonDiv);
        }}
      }}

      const text = document.createElement('div');
      text.className = 'whitespace-pre-wrap text-sm leading-relaxed';
      if (typeof content === 'string') {{
        if (role === 'assistant') {{
          text.className = 'text-sm leading-relaxed';
          text.appendChild(renderAssistantGuide(content));
        }} else {{
          text.textContent = content;
        }}
      }} else {{
        text.appendChild(content);
      }}
      bubble.appendChild(text);

      // Source tags
      if (sources && sources.length > 0 && role === 'assistant') {{
        const srcDiv = document.createElement('div');
        srcDiv.className = 'mt-3 pt-2.5 flex flex-wrap gap-1.5';
        srcDiv.style.borderTop = '1px solid #1a1a24';
        sources.slice(0, 5).forEach(ref => {{
          const tag = document.createElement('span');
          tag.className = 'px-2 py-0.5 rounded text-xs font-mono';
          tag.style.cssText = 'background:rgba(236,72,153,0.1); color:#ec4899;';
          tag.textContent = ref;
          srcDiv.appendChild(tag);
        }});
        if (sources.length > 5) {{
          const more = document.createElement('span');
          more.className = 'text-xs';
          more.style.color = '#555';
          more.textContent = '+' + (sources.length - 5) + ' more';
          srcDiv.appendChild(more);
        }}
        bubble.appendChild(srcDiv);
      }}

      div.appendChild(bubble);
      messagesEl.appendChild(div);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }}

    function appendOntologySummary(report) {{
      if (!report) return;
      hideEmptyStates();
      const div = document.createElement('div');
      div.className = 'flex justify-start msg-enter-assistant';
      const bubble = document.createElement('div');
      bubble.className = 'msg-bubble w-full max-w-2xl rounded-xl px-5 py-5 bubble-assistant';
      bubble.style.cssText = 'background:#1e1e28; color:#e8e6e3; border:1px solid #1a1a24;';

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
      wrap.className = 'space-y-5';

      // Header
      const header = document.createElement('div');
      header.className = 'flex items-center gap-3';
      header.innerHTML = '<div class="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style="background:rgba(34,197,94,0.15);">'
        + '<svg class="w-4.5 h-4.5" style="color:#22c55e;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>'
        + '</div>'
        + '<div><p class="font-semibold" style="color:#e8e6e3;">Ontology build complete</p>'
        + '<p class="text-xs font-mono mt-0.5" style="color:#8a8a94;">' + ontologyName + ' · ' + totalChunks + ' chunks · ' + elapsed.toFixed(1) + 's</p>'
        + '</div>'
        + '<span class="ml-auto px-2.5 py-1 rounded-full text-xs font-medium" style="background:rgba(34,197,94,0.15);color:#22c55e;border:1px solid rgba(34,197,94,0.2);">Done</span>';
      wrap.appendChild(header);

      // Stats grid
      const statsGrid = document.createElement('div');
      statsGrid.className = 'grid grid-cols-3 sm:grid-cols-6 gap-2';
      const statItems = [
        ['Classes', totals.classes ?? 0],
        ['Instances', totals.instances ?? 0],
        ['Relations', totals.relations ?? 0],
        ['Axioms', totals.axioms ?? 0],
        ['Data Props', totals.data_properties ?? 0],
        ['Edges', (totals.relations ?? 0) + (infEdges)],
      ];
      const keyMap = {{ 'Classes': 'classes', 'Instances': 'instances', 'Relations': 'relations', 'Axioms': 'axioms', 'Data Props': 'data_properties', 'Edges': 'edges' }};
      statItems.forEach(([label, val]) => {{
        const key = keyMap[label] || label.toLowerCase();
        const prev = lastReportTotals ? (lastReportTotals[key] ?? 0) : null;
        const delta = prev !== null && val !== prev ? (val - prev) : null;
        const deltaHtml = delta !== null
          ? (delta > 0
            ? '<span style="color:#ec4899;font-size:9px;margin-left:2px;">+' + delta + '</span>'
            : '<span style="color:#555;font-size:9px;margin-left:2px;">' + delta + '</span>')
          : '';
        const card = document.createElement('div');
        card.className = 'rounded-lg px-2 py-2 text-center';
        card.style.cssText = 'background:#14141a; border:1px solid #1a1a24;';
        card.innerHTML = '<p class="stat-value text-sm font-semibold">' + fmtNum(val) + deltaHtml + '</p>'
          + '<p class="text-xs mt-0.5 stat-label">' + label + '</p>';
        statsGrid.appendChild(card);
      }});
      lastReportTotals = {{ classes: totals.classes ?? 0, instances: totals.instances ?? 0, relations: totals.relations ?? 0, axioms: totals.axioms ?? 0, data_properties: totals.data_properties ?? 0 }};
      wrap.appendChild(statsGrid);

      // Pipeline steps
      const pipelineDiv = document.createElement('details');
      pipelineDiv.className = 'rounded-lg overflow-hidden';
      pipelineDiv.style.cssText = 'border:1px solid #1a1a24; background:#14141a;';
      const pipelineSummary = document.createElement('summary');
      pipelineSummary.className = 'cursor-pointer px-4 py-2.5 text-xs font-medium flex items-center gap-2';
      pipelineSummary.style.color = '#8a8a94';
      pipelineSummary.innerHTML = '<svg class="w-3 h-3 shrink-0" style="color:#ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg> Pipeline trace';
      pipelineDiv.appendChild(pipelineSummary);
      const pipelineContent = document.createElement('div');
      pipelineContent.className = 'px-4 pb-3 pt-1 space-y-1 text-xs font-mono';
      pipelineContent.style.color = '#8a8a94';
      const steps = [
        '1. Chunking: ' + totalChunks + ' chunks created',
        '2. Extraction: ' + enhancedChunks + ' of ' + totalChunks + ' chunks enhanced (' + mode + ' mode)',
        '3. Merge: ' + extCls + ' classes, ' + extInst + ' instances, ' + extRel + ' relations, ' + extAx + ' axioms',
        '4. LLM inference: ' + (llmInferred > 0 ? llmInferred + ' relations inferred' : 'Skipped'),
        '5. OWL 2 RL reasoning: ' + (infEdges > 0 ? infEdges + ' edges in ' + iter + ' iterations' : 'Skipped'),
        '6. Final totals: ' + (totals.classes ?? 0) + ' cls, ' + (totals.instances ?? 0) + ' inst, ' + (totals.relations ?? 0) + ' rel, ' + (totals.axioms ?? 0) + ' ax',
      ];
      steps.forEach(s => {{
        const p = document.createElement('p');
        p.className = 'process-step';
        p.textContent = s;
        pipelineContent.appendChild(p);
      }});
      pipelineDiv.appendChild(pipelineContent);
      wrap.appendChild(pipelineDiv);

      // Per-chunk
      if (chunkStats.length > 0) {{
        const toggle = document.createElement('button');
        toggle.className = 'text-xs link-teal cursor-pointer font-mono';
        toggle.textContent = '[+] Per-chunk details';
        toggle.type = 'button';
        const detailsDiv = document.createElement('div');
        detailsDiv.className = 'hidden mt-2 text-xs font-mono overflow-x-auto rounded-lg p-3';
        detailsDiv.style.cssText = 'background:#0a0a0f; border:1px solid #1a1a24; max-height:120px; overflow-y:auto;';
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

    const QA_STEPS = ['Retrieving facts...', 'Synthesizing answer...'];
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
        const sourceTags = (data.source_labels && data.source_labels.length) ? data.source_labels : (data.source_refs || []);
        appendMessage('assistant', data.answer, sourceTags, data.num_facts_used);
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
    let _modalMode = 'new'; // 'new' | 'extend'
    const createModal = document.getElementById('create-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalDescription = document.getElementById('modal-description');
    const modalFilename = document.getElementById('modal-filename');
    const modalCancel = document.getElementById('modal-cancel');
    const modalConfirm = document.getElementById('modal-confirm');
    const modalModeSection = document.getElementById('modal-mode-section');
    const modalNewFields = document.getElementById('modal-new-fields');
    const modalExtendFields = document.getElementById('modal-extend-fields');
    const modalHeading = document.getElementById('modal-heading');

    function setModalMode(mode) {{
      _modalMode = mode;
      const tabNew = document.getElementById('modal-mode-new');
      const tabExtend = document.getElementById('modal-mode-extend');
      if (mode === 'new') {{
        tabNew.className = 'w-1/2 px-4 py-2 text-xs font-medium transition-all mode-tab-active';
        tabExtend.className = 'w-1/2 px-4 py-2 text-xs font-medium transition-all mode-tab-inactive';
        modalNewFields.classList.remove('hidden');
        modalExtendFields.classList.add('hidden');
        modalHeading.textContent = 'New Ontology';
        modalConfirm.textContent = 'Create & Build';
      }} else {{
        tabNew.className = 'w-1/2 px-4 py-2 text-xs font-medium transition-all mode-tab-inactive';
        tabExtend.className = 'w-1/2 px-4 py-2 text-xs font-medium transition-all mode-tab-active';
        modalNewFields.classList.add('hidden');
        modalExtendFields.classList.remove('hidden');
        modalHeading.textContent = 'Add Documents';
        modalConfirm.textContent = 'Add & Merge';
      }}
    }}

    function showCreateModal(file) {{
      pendingFile = file;
      const stem = file.name.replace(/\\.[^.]+$/, '') || file.name;
      modalTitle.value = stem;
      modalDescription.value = '';
      modalFilename.textContent = 'File: ' + file.name;

      const activeId = kbSelect.value && kbSelect.value !== '__upload__' ? kbSelect.value : null;
      if (activeId) {{
        const activeKb = _kbData.find(k => k.id === activeId);
        const kbName = activeKb ? activeKb.name : activeId;
        document.getElementById('modal-mode-kb-name').textContent = kbName;
        modalModeSection.classList.remove('hidden');
        setModalMode('extend');
      }} else {{
        modalModeSection.classList.add('hidden');
        setModalMode('new');
      }}

      createModal.classList.remove('hidden');
      if (_modalMode === 'new') modalTitle.focus();
    }}

    function hideCreateModal() {{
      createModal.classList.add('hidden');
      pendingFile = null;
    }}

    modalCancel.addEventListener('click', hideCreateModal);
    createModal.querySelector('.modal-backdrop').addEventListener('click', hideCreateModal);

    // Delete KB modal
    const deleteModal = document.getElementById('delete-modal');
    let _pendingDeleteId = null;
    let _pendingDeleteName = null;

    function deleteActiveKB() {{
      const activeId = kbSelect.value && kbSelect.value !== '__upload__' ? kbSelect.value : null;
      if (!activeId) return;
      const activeKb = _kbData.find(k => k.id === activeId);
      _pendingDeleteId = activeId;
      _pendingDeleteName = activeKb ? activeKb.name : activeId;
      document.getElementById('delete-modal-name').textContent = _pendingDeleteName;
      deleteModal.classList.remove('hidden');
    }}

    document.getElementById('delete-modal-cancel').addEventListener('click', () => {{
      deleteModal.classList.add('hidden');
      _pendingDeleteId = null;
    }});
    deleteModal.querySelector('.modal-backdrop').addEventListener('click', () => {{
      deleteModal.classList.add('hidden');
      _pendingDeleteId = null;
    }});
    document.getElementById('delete-modal-confirm').addEventListener('click', async () => {{
      if (!_pendingDeleteId) return;
      const idToDelete = _pendingDeleteId;
      deleteModal.classList.add('hidden');
      _pendingDeleteId = null;
      try {{
        const res = await fetch(API + '/knowledge-bases/' + idToDelete, {{ method: 'DELETE' }});
        if (!res.ok) {{
          const data = await res.json().catch(() => ({{}}));
          throw new Error(parseError(data) || res.statusText);
        }}
        await loadKBs();
        kbStatus.style.display = 'none';
      }} catch (e) {{
        kbStatus.textContent = 'Delete failed: ' + e.message;
        kbStatus.style.display = '';
      }}
    }});

    // Job details modal
    const jobDetailModal = document.getElementById('job-detail-modal');
    const jobDetailContent = document.getElementById('job-detail-content');
    const jobDetailTitle = document.getElementById('job-detail-title');

    modalConfirm.addEventListener('click', () => {{
      if (pendingFile) {{
        const parallel = _modalMode === 'extend'
          ? document.getElementById('modal-parallel-extend').checked
          : document.getElementById('modal-parallel').checked;
        if (_modalMode === 'extend') {{
          const activeId = kbSelect.value && kbSelect.value !== '__upload__' ? kbSelect.value : null;
          if (activeId) {{
            doExtend(pendingFile, activeId, parallel);
            hideCreateModal();
            return;
          }}
        }}
        const title = modalTitle.value.trim() || pendingFile.name.replace(/\\.[^.]+$/, '');
        const description = modalDescription.value.trim();
        doUpload(pendingFile, title, description, parallel);
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

    const jobs = [];

    function esc(s) {{ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }}

    function createJobCard(job) {{
      job.progress = job.progress || {{}};
      const card = document.createElement('div');
      card.className = 'job-card job-clickable';
      card.dataset.jobId = job.localId;
      card.innerHTML = '<div class="flex items-center justify-between gap-2">'
        + '<p class="text-sm font-medium truncate flex-1 min-w-0" style="color:#e8e6e3;">' + esc(job.title) + '</p>'
        + '<button type="button" class="job-cancel shrink-0 w-5 h-5 rounded flex items-center justify-center" style="color:#8a8a94;">'
        + '<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>'
        + '</button></div>'
        + (job.description ? '<p class="text-xs mt-0.5 truncate" style="color:#6b6b76;">' + esc(job.description) + '</p>' : '')
        + '<div class="flex items-center gap-2 mt-1.5">'
        + '<span class="stage-dot"></span>'
        + '<span class="stage-label text-xs font-mono" style="color:#8a8a94;">Starting...</span>'
        + '</div>';
      card.querySelector('.job-cancel').addEventListener('click', (e) => {{ e.stopPropagation(); cancelJob(job); }});
      card.addEventListener('click', (e) => {{ if (!e.target.closest('.job-cancel')) showJobDetailModal(job); }});
      return card;
    }}

    function updateJobStage(job, ev) {{
      const step = ev.step;
      const d = ev.data || ev;
      if (!job.progress) job.progress = {{}};
      job.progress[step] = d;
      const label = job.card?.querySelector('.stage-label');
      if (!label) return;
      const stageMap = {{
        'load': 'Loading...', 'load_done': 'Loaded',
        'chunk': 'Chunking...', 'chunk_done': (d.total_chunks || 0) + ' chunks',
        'extract': 'Extract ' + (d.current || 0) + '/' + (d.total || 0),
        'merge_done': 'Merged',
        'inference': 'Inferring...', 'inference_done': 'Inferred',
        'inference_skip': 'Skipped inference',
        'reasoning': 'Reasoning...', 'reasoning_done': 'Reasoned',
        'reasoning_skip': 'Skipped reasoning',
      }};
      label.textContent = stageMap[step] || step;
    }}

    function showJobDetailModal(job) {{
      jobDetailTitle.textContent = job.title || 'Job Details';
      const report = job.pipeline_report || {{}};
      const progress = job.progress || {{}};
      const totals = report.totals || {{}};
      const ext = report.extraction_totals || {{}};
      const reasoning = report.reasoning || {{}};
      const chunkStats = report.chunk_stats || [];
      const totalChunks = report.total_chunks ?? progress.chunk_done?.total_chunks ?? 0;
      const docChars = progress.load_done?.chars ?? 0;
      const elapsed = report.elapsed_seconds ?? 0;
      const mode = report.extraction_mode || job.extraction_mode || 'sequential';
      const ontologyName = report.ontology_name || job.title || '—';
      const llmInferred = report.llm_inferred_relations ?? 0;
      const infEdges = reasoning.inferred_edges ?? 0;
      const iter = reasoning.iterations ?? 0;

      let html = '<div class="space-y-4">';

      html += '<div class="rounded-lg p-3" style="background:#14141a; border:1px solid #1a1a24;">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:#8a8a94;">Status</p>';
      html += '<p class="font-mono text-sm"><span class="stat-value">' + (job.status || 'running') + '</span></p>';
      if (ontologyName !== '—') html += '<p class="text-xs mt-1" style="color:#8a8a94;">Ontology: ' + esc(ontologyName) + '</p>';
      html += '</div>';

      html += '<div class="rounded-lg p-3" style="background:#14141a; border:1px solid #1a1a24;">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:#8a8a94;">Document &amp; Chunking</p>';
      html += '<ul class="space-y-1 text-xs font-mono" style="color:#e8e6e3;">';
      html += '<li>Document size: <span class="stat-value">' + (docChars ? docChars.toLocaleString() + ' chars' : '—') + '</span></li>';
      html += '<li>Total chunks: <span class="stat-value">' + totalChunks + '</span></li>';
      html += '<li>Extraction mode: <span class="stat-value">' + mode + '</span></li>';
      if (elapsed > 0) html += '<li>Elapsed: <span class="stat-value">' + elapsed.toFixed(1) + 's</span></li>';
      html += '</ul></div>';

      html += '<div class="rounded-lg p-3" style="background:#14141a; border:1px solid #1a1a24;">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:#8a8a94;">Entities &amp; Relations</p>';
      html += '<div class="grid grid-cols-2 gap-2 text-xs font-mono">';
      const cls = totals.classes ?? ext.classes ?? 0;
      const inst = totals.instances ?? ext.instances ?? 0;
      const rel = totals.relations ?? ext.relations ?? 0;
      const ax = totals.axioms ?? ext.axioms ?? 0;
      const dp = totals.data_properties ?? 0;
      html += '<div><span style="color:#8a8a94;">Classes:</span> <span class="stat-value">' + cls + '</span></div>';
      html += '<div><span style="color:#8a8a94;">Instances:</span> <span class="stat-value">' + inst + '</span></div>';
      html += '<div><span style="color:#8a8a94;">Relations:</span> <span class="stat-value">' + rel + '</span></div>';
      html += '<div><span style="color:#8a8a94;">Axioms:</span> <span class="stat-value">' + ax + '</span></div>';
      html += '<div><span style="color:#8a8a94;">Data properties:</span> <span class="stat-value">' + dp + '</span></div>';
      html += '</div></div>';

      html += '<div class="rounded-lg p-3" style="background:#14141a; border:1px solid #1a1a24;">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:#8a8a94;">Pipeline Steps</p>';
      html += '<ol class="space-y-1.5 text-xs" style="list-style:none; padding-left:0;">';
      html += '<li class="process-step">1. Load: ' + (docChars ? docChars.toLocaleString() + ' chars loaded' : '—') + '</li>';
      html += '<li class="process-step">2. Chunk: ' + totalChunks + ' chunks created</li>';
      const enhancedChunks = chunkStats.filter(c => ((c.classes ?? 0) + (c.instances ?? 0) + (c.relations ?? 0) + (c.axioms ?? 0)) > 0).length;
      html += '<li class="process-step">3. Extract: ' + (chunkStats.length ? enhancedChunks + ' of ' + totalChunks + ' chunks enhanced' : '—') + '</li>';
      html += '<li class="process-step">4. Merge: ' + (ext.classes ?? cls) + ' cls, ' + (ext.instances ?? inst) + ' inst, ' + (ext.relations ?? rel) + ' rel</li>';
      html += '<li class="process-step">5. LLM inference: ' + (llmInferred > 0 ? llmInferred + ' relations inferred' : 'Skipped') + '</li>';
      html += '<li class="process-step">6. OWL reasoning: ' + (infEdges > 0 ? infEdges + ' edges in ' + iter + ' iterations' : 'Skipped') + '</li>';
      html += '</ol></div>';

      if (chunkStats.length > 0) {{
        html += '<div class="rounded-lg p-3" style="background:#14141a; border:1px solid #1a1a24;">';
        html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:#8a8a94;">Per-chunk Stats</p>';
        html += '<div class="font-mono text-xs overflow-x-auto" style="max-height:120px; overflow-y:auto;">';
        chunkStats.forEach((c, i) => {{
          const line = 'Chunk ' + (i + 1) + ': ' + (c.chunk_length ?? 0) + ' chars → ' + (c.classes ?? 0) + ' cls, ' + (c.instances ?? 0) + ' inst, ' + (c.relations ?? 0) + ' rel' + (c.axioms ? ', ' + c.axioms + ' ax' : '');
          html += '<div class="py-0.5" style="color:#8a8a94;">' + esc(line) + '</div>';
        }});
        html += '</div></div>';
      }}

      html += '</div>';
      jobDetailContent.innerHTML = html;
      jobDetailModal.classList.remove('hidden');
    }}

    function hideJobDetailModal() {{
      jobDetailModal.classList.add('hidden');
    }}

    document.getElementById('job-detail-close')?.addEventListener('click', hideJobDetailModal);
    jobDetailModal?.querySelector('.modal-backdrop')?.addEventListener('click', hideJobDetailModal);

    function setJobStatus(job, status, label) {{
      job.status = status;
      if (!job.card) return;
      job.card.className = 'job-card ' + status;
      const sl = job.card.querySelector('.stage-label');
      if (sl) sl.textContent = label;
      const cancelBtn = job.card.querySelector('.job-cancel');
      if (cancelBtn && (status === 'done' || status === 'error' || status === 'cancelled')) {{
        cancelBtn.style.display = 'none';
      }}
    }}

    async function cancelJob(job) {{
      if (job.serverJobId) {{
        try {{ await fetch(API + '/cancel_job/' + job.serverJobId, {{ method: 'POST' }}); }} catch(e) {{}}
      }}
      if (job.abortController) job.abortController.abort();
    }}

    function removeJobCard(job, delay) {{
      setTimeout(() => {{
        if (!job.card) return;
        job.card.classList.add('removing');
        setTimeout(() => {{
          job.card.remove();
          const idx = jobs.indexOf(job);
          if (idx > -1) jobs.splice(idx, 1);
        }}, 300);
      }}, delay || 0);
    }}

    async function doUpload(file, title, description, parallel = true) {{
      const job = {{
        localId: Date.now(),
        title: title || file.name,
        description: description || '',
        status: 'running',
        serverJobId: null,
        abortController: new AbortController(),
        card: null,
      }};
      jobs.push(job);
      job.card = createJobCard(job);
      jobQueue.appendChild(job.card);
      setStatusBadge('processing');

      const fd = new FormData();
      fd.append('file', file);
      if (title) fd.append('title', title);
      if (description) fd.append('description', description);
      try {{
        const parallelParam = parallel ? 'true' : 'false';
        const res = await fetch(API + '/build_ontology_stream?run_inference=true&sequential=true&run_reasoning=true&parallel=' + parallelParam, {{
          method: 'POST',
          body: fd,
          signal: job.abortController.signal,
        }});
        if (!res.ok) {{
          const data = await res.json().catch(() => ({{}}));
          throw new Error(parseError(data) || res.statusText);
        }}
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let result = null;
        while (true) {{
          const {{ done, value }} = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, {{ stream: true }});
          const parts = buffer.split('\\n\\n');
          buffer = parts.pop() || '';
          for (const part of parts) {{
            const line = part.split('\\n').find(l => l.startsWith('data: '));
            if (!line) continue;
            try {{
              const ev = JSON.parse(line.slice(6));
              if (ev.type === 'job_started') {{ job.serverJobId = ev.job_id; job.extraction_mode = ev.extraction_mode; continue; }}
              if (ev.type === 'error') throw new Error(ev.message || 'Pipeline failed');
              if (ev.type === 'complete') {{ result = ev; job.pipeline_report = ev.pipeline_report; break; }}
              if (ev.step) updateJobStage(job, ev);
            }} catch (e) {{
              if (e instanceof SyntaxError) continue;
              throw e;
            }}
          }}
          if (result) break;
        }}
        if (result) {{
          setJobStatus(job, 'done', 'Complete');
          await loadKBs();
          if (result.kb_id) kbSelect.value = result.kb_id;
          if (result.pipeline_report) appendOntologySummary(result.pipeline_report);
          removeJobCard(job, 3000);
        }}
      }} catch (e) {{
        if (e.name === 'AbortError') {{
          setJobStatus(job, 'cancelled', 'Cancelled');
        }} else {{
          setJobStatus(job, 'error', e.message);
        }}
        removeJobCard(job, 4000);
      }} finally {{
        const hasRunning = jobs.some(j => j.status === 'running');
        if (!hasRunning) setStatusBadge(kbSelect.value ? 'ready' : 'empty');
      }}
    }}

    async function doExtend(file, kbId, parallel = true) {{
      const activeKb = _kbData.find(k => k.id === kbId);
      const kbName = activeKb ? activeKb.name : kbId;
      const job = {{
        localId: Date.now(),
        title: 'Adding to ' + kbName,
        description: file.name,
        status: 'running',
        serverJobId: null,
        abortController: new AbortController(),
        card: null,
      }};
      jobs.push(job);
      job.card = createJobCard(job);
      jobQueue.appendChild(job.card);
      setStatusBadge('processing');

      const fd = new FormData();
      fd.append('file', file);
      try {{
        const parallelParam = parallel ? 'true' : 'false';
        const res = await fetch(API + '/knowledge-bases/' + kbId + '/extend_stream?run_inference=true&sequential=true&run_reasoning=true&parallel=' + parallelParam, {{
          method: 'POST',
          body: fd,
          signal: job.abortController.signal,
        }});
        if (!res.ok) {{
          const data = await res.json().catch(() => ({{}}));
          throw new Error(parseError(data) || res.statusText);
        }}
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let result = null;
        while (true) {{
          const {{ done, value }} = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, {{ stream: true }});
          const parts = buffer.split('\\n\\n');
          buffer = parts.pop() || '';
          for (const part of parts) {{
            const line = part.split('\\n').find(l => l.startsWith('data: '));
            if (!line) continue;
            try {{
              const ev = JSON.parse(line.slice(6));
              if (ev.type === 'job_started') {{ job.serverJobId = ev.job_id; job.extraction_mode = ev.extraction_mode; continue; }}
              if (ev.type === 'error') throw new Error(ev.message || 'Pipeline failed');
              if (ev.type === 'complete') {{ result = ev; job.pipeline_report = ev.pipeline_report; break; }}
              if (ev.step) updateJobStage(job, ev);
            }} catch (e) {{
              if (e instanceof SyntaxError) continue;
              throw e;
            }}
          }}
          if (result) break;
        }}
        if (result) {{
          setJobStatus(job, 'done', 'Merged');
          await loadKBs();
          if (result.kb_id) kbSelect.value = result.kb_id;
          if (result.pipeline_report) appendOntologySummary(result.pipeline_report);
          removeJobCard(job, 3000);
        }}
      }} catch (e) {{
        if (e.name === 'AbortError') {{
          setJobStatus(job, 'cancelled', 'Cancelled');
        }} else {{
          setJobStatus(job, 'error', e.message);
        }}
        removeJobCard(job, 4000);
      }} finally {{
        const hasRunning = jobs.some(j => j.status === 'running');
        if (!hasRunning) setStatusBadge(kbSelect.value ? 'ready' : 'empty');
      }}
    }}

    // Suggestion button hover effect
    document.querySelectorAll('.suggestion-btn').forEach(btn => {{
      btn.addEventListener('mouseenter', () => {{
        btn.style.borderColor = 'rgba(236,72,153,0.3)';
        btn.style.background = 'rgba(236,72,153,0.04)';
      }});
      btn.addEventListener('mouseleave', () => {{
        btn.style.borderColor = '#2a2a3a';
        btn.style.background = '#1e1e28';
      }});
    }});

    sidebarToggle?.addEventListener('click', () => sidebar.classList.toggle('open'));
    document.getElementById('sidebar-overlay')?.addEventListener('click', () => sidebar.classList.remove('open'));

    if (window.matchMedia('(min-width: 769px)').matches) {{
      sidebar.classList.add('open');
    }}

    // Ensure graph viewer links use current origin (fixes about:blank when opened in new tab)
    const viewerUrl = window.location.origin + API + '/graph/viewer';
    document.querySelectorAll('a.graph-viewer-link').forEach(function(a) {{ a.href = viewerUrl; }});

    loadKBs();
  </script>
</body>
</html>"""
