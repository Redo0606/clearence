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
  <title>Clearence · Ontology Assistant</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    .sr-only {{ position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }}
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
    .job-card.job-create {{ border-left: 3px solid #14b8a6; }}
    .job-card.job-create .job-type-badge {{ background: rgba(20, 184, 166, 0.2); color: #14b8a6; }}
    .job-card.job-extend {{ border-left: 3px solid #f59e0b; }}
    .job-card.job-extend .job-type-badge {{ background: rgba(245, 158, 11, 0.2); color: #f59e0b; }}
    .onto-card {{ cursor: pointer; transition: all 0.2s ease; }}
    .onto-card .onto-card-expandable {{ overflow: hidden; max-height: 500px; transition: max-height 0.25s ease, opacity 0.2s ease; }}
    .onto-card.collapsed .onto-card-expandable {{ max-height: 0; opacity: 0; margin-top: 0 !important; padding-top: 0 !important; }}
    .onto-card.collapsed #onto-card-chevron {{ transform: rotate(-90deg); }}
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

    /* KB loading animation */
    @keyframes kb-load-pulse {{ 0%, 100% {{ opacity: 0.6; }} 50% {{ opacity: 1; }} }}
    @keyframes kb-load-spin {{ to {{ transform: rotate(360deg); }} }}
    .kb-loading {{ position: relative; pointer-events: none; }}
    .kb-loading::after {{
      content: ''; position: absolute; inset: 0; background: rgba(20, 20, 26, 0.85); border-radius: 0.75rem;
      display: flex; align-items: center; justify-content: center;
    }}
    .kb-load-spinner {{
      width: 36px; height: 36px; border: 3px solid #2a2a3a; border-top-color: #ec4899; border-radius: 50%;
      animation: kb-load-spin 0.8s linear infinite;
    }}
    .job-queue-content {{ max-height: 320px; overflow-y: auto; transition: max-height 0.25s ease, opacity 0.2s ease; }}
    .job-queue-section.collapsed .job-queue-content {{ max-height: 0; overflow: hidden; opacity: 0; margin-top: 0; }}
    .job-queue-toggle .job-queue-chevron {{ transition: transform 0.2s ease; }}
    .job-queue-section.collapsed .job-queue-chevron {{ transform: rotate(-90deg); }}

    /* Modal mode tabs */
    .mode-tab-active {{ background: rgba(236,72,153,0.15); color: #ec4899; border-bottom: 2px solid #ec4899; }}
    .mode-tab-inactive {{ background: #14141a; color: #8a8a94; border-bottom: 2px solid transparent; }}
    .mode-tab-inactive:hover {{ color: #e8e6e3; background: rgba(255,255,255,0.04); }}

    /* Sidebar tabs */
    .sidebar-tab-active {{ color: #ec4899; border-bottom: 2px solid #ec4899; }}
    .sidebar-tab-inactive {{ color: #8a8a94; border-bottom: 2px solid transparent; }}
    .sidebar-tab-inactive:hover {{ color: #e8e6e3; }}
    .kb-list-card {{ transition: border-color 0.2s, background 0.2s; cursor: pointer; flex-shrink: 0; }}
    .kb-list-card:hover {{ border-color: rgba(236,72,153,0.3); background: rgba(236,72,153,0.04); }}
    .kb-list-card.active {{ border-color: rgba(236,72,153,0.5); background: rgba(236,72,153,0.08); box-shadow: 0 0 0 1px rgba(236,72,153,0.2); }}
    .kb-ready-dot {{ width: 6px; height: 6px; border-radius: 50%; background: #22c55e; flex-shrink: 0; }}
    .kb-building-dot {{ width: 6px; height: 6px; border-radius: 50%; background: #f59e0b; flex-shrink: 0; animation: pulse-glow 1.2s ease-in-out infinite; }}
    .kb-ready-badge {{ flex-shrink: 0; white-space: nowrap; }}
    .kb-list-scrollable {{ max-height: 320px; overflow-y: auto; overflow-x: hidden; }}

    /* Chat tabs */
    .chat-tab {{ padding: 0.5rem 1rem; font-size: 0.8125rem; border-radius: 0.5rem; transition: all 0.2s; white-space: nowrap; max-width: 140px; overflow: hidden; text-overflow: ellipsis; }}
    .chat-tab:hover {{ background: rgba(236,72,153,0.08); color: #ec4899; }}
    .chat-tab.active {{ background: rgba(236,72,153,0.15); color: #ec4899; }}
    .chat-tab-add {{ padding: 0.5rem 0.75rem; color: #8a8a94; }}
    .chat-tab-add:hover {{ color: #ec4899; background: rgba(236,72,153,0.08); }}
    .chat-tab-delete {{ opacity: 0; padding: 0.25rem; margin-left: 0.25rem; border-radius: 4px; transition: opacity 0.15s, color 0.15s; cursor: pointer; }}
    .chat-tab-wrap:hover .chat-tab-delete {{ opacity: 1; }}
    .chat-tab-wrap .chat-tab.active ~ .chat-tab-delete {{ opacity: 0.7; }}
    .chat-tab-delete:hover {{ color: #ef4444 !important; background: rgba(239,68,68,0.15); }}

    /* KB management list */
    .kb-mgmt-row {{ transition: all 0.2s; }}
    .kb-mgmt-row:hover {{ background: rgba(236,72,153,0.04); }}
    .kb-mgmt-row.active {{ border-left: 3px solid #ec4899; }}
    .kb-mgmt-delete {{ opacity: 0.7; transition: opacity 0.15s; }}
    .kb-mgmt-delete:hover {{ opacity: 1; color: #ef4444 !important; }}

    /* New chat modal */
    .new-chat-modal {{ max-height: 70vh; overflow-y: auto; }}
    .new-chat-modal button:hover {{ border-color: rgba(236,72,153,0.3); background: rgba(236,72,153,0.06); }}

    /* Chat tab wrap */
    .chat-tab-wrap {{ border-radius: 0.5rem; }}
    .chat-tab-wrap .chat-tab {{ border-radius: 0.5rem 0 0 0.5rem; padding-right: 0.25rem; }}
    .chat-tab-wrap .chat-tab-delete {{ border-radius: 0 0.5rem 0.5rem 0; padding: 0.5rem 0.5rem; }}
  </style>
</head>
<body class="flex h-screen overflow-hidden">
  <!-- Sidebar -->
  <aside id="sidebar" class="sidebar w-80 flex flex-col shrink-0 min-h-0 overflow-y-auto" style="background: #14141a; border-right: 1px solid #1a1a24;">

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

    <!-- Sidebar tabs -->
    <div class="flex shrink-0 border-b" style="border-color: #1a1a24;">
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
      <div class="px-5 py-4 shrink-0" style="border-bottom: 1px solid #1a1a24;">
        <div class="flex items-center justify-between mb-3">
          <p class="text-xs font-semibold uppercase tracking-widest" style="color: #8a8a94;">Knowledge Bases</p>
          <span id="status-badge" class="status-badge px-2 py-0.5 rounded-full text-xs font-medium empty" style="background: #1a1a24; color: #8a8a94;">Empty</span>
        </div>
        <label for="file-input-create" id="kb-create-btn" class="w-full rounded-lg px-3 py-2.5 text-sm font-medium border transition-all flex items-center justify-center gap-2 cursor-pointer"
          style="background: rgba(236,72,153,0.08); color: #ec4899; border-color: rgba(236,72,153,0.3);">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/></svg>
          Create new KB
        </label>
        <input type="file" id="file-input-create" class="sr-only" accept=".pdf,.docx,.txt,.md" tabindex="-1">
      </div>
      <!-- KB management list: compact cards, all KBs -->
      <div class="px-3 py-3 shrink-0">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs font-medium" style="color: #8a8a94;">All knowledge bases <span id="kb-count" class="font-mono" style="color: #6b6b76;"></span></p>
          <button type="button" id="kb-refresh-btn" class="text-xs font-medium link-teal hover:opacity-80" title="Refresh list">↻</button>
        </div>
        <div id="kb-list" class="flex flex-col gap-1.5"></div>
        <div id="kb-list-empty" class="hidden py-6 text-center">
          <p class="text-sm" style="color: #6b6b76;">No knowledge bases yet</p>
          <p class="text-xs mt-1" style="color: #555;">Create one with the button above</p>
        </div>
      </div>

    <!-- Ontology Info Card (hidden until KB selected, compact) -->
    <div id="onto-info-panel" class="hidden px-5 py-3 shrink-0 relative" style="border-top: 1px solid #1a1a24;">
      <div id="onto-card-loading" class="hidden absolute inset-0 flex items-center justify-center z-10 rounded-xl" style="background: rgba(20, 20, 26, 0.9);">
        <div class="kb-load-spinner"></div>
      </div>
      <div id="onto-card" class="onto-card onto-card-glow rounded-xl p-3 collapsed" style="background: #1e1e28; border: 1px solid rgba(236,72,153,0.18);">
        <!-- Header row (clickable: expand + open modal) -->
        <div id="onto-card-header" class="flex items-start gap-3">
          <div class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 mt-0.5" style="background: rgba(236, 72, 153, 0.15);">
            <svg class="w-4 h-4" style="color: #ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <p id="onto-card-name" class="font-semibold text-sm leading-snug" style="color: #e8e6e3;"></p>
              <span id="onto-card-ready" class="hidden flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded shrink-0 whitespace-nowrap" style="color:#22c55e; background:rgba(34,197,94,0.15);">
                <span class="kb-ready-dot"></span>Ready
              </span>
            </div>
            <p id="onto-card-summary" class="text-xs mt-0.5" style="color: #8a8a94;"></p>
          </div>
          <button type="button" id="onto-card-expand-btn" class="shrink-0 p-1 rounded transition-colors" style="color: #8a8a94;" aria-label="Expand/collapse">
            <svg id="onto-card-chevron" class="w-4 h-4 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </button>
        </div>

        <!-- Expandable content -->
        <div id="onto-card-expandable" class="onto-card-expandable">
          <p id="onto-card-desc" class="text-xs mt-2 leading-relaxed" style="color: #8a8a94; display: none;"></p>
          <div id="onto-stats-grid" class="grid grid-cols-3 gap-1.5 mt-3"></div>
          <div id="onto-doc-row" class="hidden flex items-center gap-2 mt-3 pt-3" style="border-top: 1px solid #1a1a24;">
            <svg class="w-3.5 h-3.5 shrink-0" style="color: #8a8a94;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
            </svg>
            <span id="onto-doc-name" class="text-xs font-mono truncate" style="color: #8a8a94;"></span>
          </div>
          <div class="flex items-center justify-between mt-3 pt-3" style="border-top: 1px solid #1a1a24;">
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
    </div>
    </div>

    <!-- Document Management tab content -->
    <div id="tab-documents-content" class="hidden flex flex-col flex-1 min-h-0 overflow-hidden">
    <div class="px-5 py-4 flex-1 min-h-0 overflow-y-auto">
      <p class="text-xs font-semibold uppercase tracking-widest mb-3" style="color: #8a8a94;">Add Documents</p>
      <p class="text-xs mb-3" style="color: #8a8a94;">Add documents to the active KB. Select a KB in the Knowledge tab first.</p>
      <label for="file-input" id="drop-zone" class="drop-zone border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all block"
        style="border-color: #2a2a3a; color: #8a8a94; background: rgba(30, 30, 40, 0.4);">
        <div class="drop-icon mx-auto mb-2 w-10 h-10 rounded-full flex items-center justify-center" style="background: rgba(236, 72, 153, 0.1);">
          <svg class="w-5 h-5" style="color: #ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
        </div>
        <p class="text-sm font-medium" style="color: #e8e6e3;">Drop your document here</p>
        <p class="mt-0.5 text-xs">or <span class="link-teal font-medium">browse files</span></p>
        <div class="flex justify-center gap-1.5 mt-2.5">
          <span class="file-badge">PDF</span>
          <span class="file-badge">DOCX</span>
          <span class="file-badge">TXT</span>
          <span class="file-badge">MD</span>
        </div>
        <input type="file" id="file-input" class="sr-only" accept=".pdf,.docx,.txt,.md" tabindex="-1">
      </label>
      <div id="job-queue-section" class="job-queue-section mt-3">
        <button type="button" id="job-queue-toggle" class="job-queue-toggle w-full flex items-center justify-between py-2 text-xs font-medium" style="color: #8a8a94;">
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
        <p class="text-xs font-semibold uppercase tracking-widest mb-3" style="color: #8a8a94;">Graph Health &amp; Repair</p>
        <div class="mb-3">
          <label class="block text-xs font-medium mb-1.5" style="color: #8a8a94;">Knowledge base</label>
          <select id="eval-kb-select" class="w-full rounded-lg px-3 py-2.5 text-sm border transition-all" style="background: #14141a; color: #e8e6e3; border-color: #2a2a3a;">
            <option value="">Select a KB</option>
          </select>
        </div>
        <div id="eval-panel-state-a" class="rounded-xl p-4" style="background: #1e1e28; border: 1px solid #2a2a3a;">
          <div class="flex items-center justify-between mb-3">
            <h4 class="font-semibold text-sm" style="color: #e8e6e3;">Graph Health</h4>
            <span id="eval-health-badge" class="text-xs font-medium px-2 py-0.5 rounded" style="background: #1a1a24; color: #8a8a94;">—</span>
          </div>
          <div id="eval-health-stats" class="text-xs space-y-1 font-mono" style="color: #8a8a94;">
            <p>Select a KB to view health</p>
          </div>
          <div id="eval-health-warnings" class="mt-3 text-xs" style="color: #f59e0b;"></div>
          <div class="mt-3 flex items-center gap-2">
            <button type="button" id="eval-refresh-btn" class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all" style="background: rgba(236,72,153,0.1); color: #ec4899; border: 1px solid rgba(236,72,153,0.3);">Rerun to refresh</button>
            <button type="button" id="eval-repair-btn" class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5" style="background: rgba(34,197,94,0.12); color: #22c55e; border: 1px solid rgba(34,197,94,0.25);" title="Infer missing edges to connect orphans and bridge components">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
              Repair
            </button>
          </div>
        </div>
        <div id="eval-panel-state-b" class="hidden rounded-xl p-4 flex flex-col" style="background: #1e1e28; border: 1px solid #2a2a3a;">
          <div class="flex items-center gap-2 mb-2">
            <div class="kb-load-spinner w-4 h-4"></div>
            <span id="eval-stage-label" class="text-sm font-medium" style="color: #e8e6e3;">Repairing...</span>
          </div>
          <div class="h-1.5 rounded-full mb-3 overflow-hidden" style="background: #1a1a24;">
            <div id="eval-progress-bar" class="h-full rounded-full transition-all duration-300" style="background: #22c55e; width: 0%;"></div>
          </div>
          <div id="eval-log-feed" class="flex-1 min-h-[120px] overflow-y-auto text-xs font-mono space-y-1 break-words overflow-x-hidden" style="color: #8a8a94; max-height: 200px;"></div>
          <div id="eval-error-banner" class="hidden mt-2 px-3 py-2 rounded-lg text-xs" style="background: rgba(239,68,68,0.15); color: #ef4444;"></div>
        </div>

        <!-- Evaluation section (same style as health) -->
        <div id="eval-eval-panel" class="mt-4 rounded-xl p-4" style="background: #1e1e28; border: 1px solid #2a2a3a;">
          <div class="flex items-center justify-between mb-3">
            <h4 class="font-semibold text-sm" style="color: #e8e6e3;">QA Evaluation</h4>
            <span id="eval-eval-badge" class="text-xs font-medium px-2 py-0.5 rounded" style="background: #1a1a24; color: #8a8a94;">—</span>
          </div>
          <div class="mb-2 flex items-center gap-2">
            <label class="text-xs" style="color: #8a8a94;">Questions</label>
            <input type="number" id="eval-num-questions" value="5" min="1" max="500" class="w-16 rounded px-2 py-1 text-xs font-mono border" style="background: #14141a; color: #e8e6e3; border-color: #2a2a3a;">
          </div>
          <div id="eval-eval-stats" class="text-xs space-y-1 font-mono" style="color: #8a8a94;">
            <p>Run evaluation to view scores</p>
          </div>
          <div class="mt-3">
            <button type="button" id="eval-run-btn" class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5" style="background: rgba(236,72,153,0.12); color: #ec4899; border: 1px solid rgba(236,72,153,0.3);" title="Run QA evaluation">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
              Run Evaluation
            </button>
          </div>
        </div>
        <div id="eval-eval-progress" class="hidden mt-4 rounded-xl p-4 flex flex-col" style="background: #1e1e28; border: 1px solid #2a2a3a;">
          <div class="flex items-center gap-2 mb-2">
            <div class="kb-load-spinner w-4 h-4"></div>
            <span id="eval-eval-stage-label" class="text-sm font-medium" style="color: #e8e6e3;">Evaluating...</span>
          </div>
          <div class="h-1.5 rounded-full mb-3 overflow-hidden" style="background: #1a1a24;">
            <div id="eval-eval-progress-bar" class="h-full rounded-full transition-all duration-300" style="background: #ec4899; width: 0%;"></div>
          </div>
          <div id="eval-eval-log" class="min-h-[80px] overflow-y-auto text-xs font-mono space-y-1 break-words" style="color: #8a8a94; max-height: 150px;"></div>
          <div id="eval-eval-error" class="hidden mt-2 px-3 py-2 rounded-lg text-xs" style="background: rgba(239,68,68,0.15); color: #ef4444;"></div>
        </div>

        <!-- Evaluation Records -->
        <div id="eval-records-panel" class="mt-4 rounded-xl p-4" style="background: #1e1e28; border: 1px solid #2a2a3a;">
          <div class="flex items-center justify-between mb-3">
            <h4 class="font-semibold text-sm" style="color: #e8e6e3;">Records</h4>
          </div>
          <div id="eval-records-list" class="space-y-2 max-h-[280px] overflow-y-auto" style="color: #8a8a94;">
            <p class="text-xs">Select a KB to view evaluation history</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Footer links -->
    <div class="px-5 py-3 flex items-center gap-4 shrink-0" style="border-top: 1px solid #1a1a24;">
      <span class="text-xs" style="color: #555;">Clearence v1.0 · by Reda Sarehane</span>
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

  <!-- KB summary/edit modal -->
  <div id="kb-summary-modal" class="fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="hideKbSummaryModal()"></div>
    <div class="modal-content modal-enter absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg rounded-xl p-6 shadow-2xl" style="background: #1e1e28; border: 1px solid #2a2a3a;" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between mb-5">
        <h3 class="font-semibold text-lg" style="color: #e8e6e3;">Knowledge Base Summary</h3>
        <button type="button" id="kb-summary-close" class="p-1.5 rounded-md transition-colors text-xl leading-none" style="color: #8a8a94;" aria-label="Close">×</button>
      </div>
      <div id="kb-summary-content" class="space-y-4">
        <div>
          <label class="block text-xs font-medium mb-1.5 uppercase tracking-wider" style="color: #8a8a94;">Name</label>
          <input type="text" id="kb-summary-name" class="w-full rounded-lg px-3.5 py-2.5 text-sm border transition-all" style="background: #14141a; color: #e8e6e3; border-color: #2a2a3a;" placeholder="Ontology name">
        </div>
        <div>
          <label class="block text-xs font-medium mb-1.5 uppercase tracking-wider" style="color: #8a8a94;">Description</label>
          <textarea id="kb-summary-desc" class="w-full rounded-lg px-3.5 py-2.5 text-sm border resize-none transition-all" rows="4" style="background: #14141a; color: #e8e6e3; border-color: #2a2a3a;" placeholder="What this ontology covers..."></textarea>
        </div>
        <div id="kb-summary-stats" class="rounded-lg p-3" style="background: #14141a; border: 1px solid #1a1a24;"></div>
      </div>
      <div class="mt-6 flex gap-3 justify-end">
        <button type="button" id="kb-summary-cancel" class="px-4 py-2.5 rounded-lg text-sm transition-all" style="background: #14141a; color: #8a8a94; border: 1px solid #2a2a3a;">Cancel</button>
        <button type="button" id="kb-summary-save" class="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-all btn-send">Save</button>
      </div>
    </div>
  </div>

  <!-- New chat KB selection modal -->
  <div id="new-chat-modal" class="fixed inset-0 z-50 hidden" aria-hidden="true">
    <div class="modal-backdrop absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="document.getElementById('new-chat-modal').classList.add('hidden')"></div>
    <div class="modal-content modal-enter new-chat-modal absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md rounded-xl p-6 shadow-2xl" style="background: #1e1e28; border: 1px solid #2a2a3a;" onclick="event.stopPropagation()">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style="background: rgba(236, 72, 153, 0.15);">
          <svg class="w-5 h-5" style="color: #ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
        </div>
        <div>
          <h3 class="font-semibold text-lg" style="color: #e8e6e3;">New Chat</h3>
          <p class="text-xs mt-0.5" style="color: #8a8a94;">Choose a knowledge base to chat with</p>
        </div>
      </div>
      <div id="new-chat-kb-list" class="space-y-2 max-h-64 overflow-y-auto mb-4"></div>
      <div class="flex gap-3 justify-end">
        <button type="button" id="new-chat-modal-cancel" class="px-4 py-2.5 rounded-lg text-sm transition-all" style="background: #14141a; color: #8a8a94; border: 1px solid #2a2a3a;">Cancel</button>
      </div>
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
  <main class="flex-1 flex flex-col min-h-0 overflow-hidden">
    <!-- Header -->
    <header class="shrink-0 px-6 py-3.5 flex items-center justify-between" style="background: #14141a; border-bottom: 1px solid #1a1a24;">
      <div class="flex items-center gap-3">
        <div>
          <h1 class="font-semibold text-base" style="color: #e8e6e3;">Clearence</h1>
          <p class="text-xs" style="color: #8a8a94;">Ontology Assistant · Reda Sarehane</p>
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
      <div class="flex items-center gap-2">
        <button id="sidebar-toggle" class="p-2 rounded-md transition-colors flex items-center justify-center" style="color: #8a8a94;" onmouseover="this.style.background='#1e1e28'" onmouseout="this.style.background='transparent'" type="button" aria-label="Toggle sidebar">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
        </button>
      </div>
    </header>

    <!-- Chat tabs -->
    <div id="chat-tabs-bar" class="shrink-0 flex items-center gap-1 px-4 py-2 overflow-x-auto" style="background: #14141a; border-bottom: 1px solid #1a1a24;">
      <div id="chat-tabs" class="flex items-center gap-1 min-w-0"></div>
      <button type="button" id="new-chat-btn" class="chat-tab chat-tab-add shrink-0 flex items-center gap-1.5" title="New chat">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
        <span>New</span>
      </button>
    </div>

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
          <div id="chat-onto-docs" class="hidden mt-4 pt-4" style="border-top: 1px solid #1a1a24;">
            <p class="text-xs font-semibold uppercase tracking-wider mb-2" style="color: #8a8a94;">Documents</p>
            <div id="chat-onto-docs-list" class="flex flex-wrap gap-2"></div>
          </div>
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
    const kbList = document.getElementById('kb-list');
    const kbCreateBtn = document.getElementById('kb-create-btn');
    const fileInputCreate = document.getElementById('file-input-create');
    const tabKnowledge = document.getElementById('tab-knowledge');
    const tabDocuments = document.getElementById('tab-documents');
    const tabEvaluate = document.getElementById('tab-evaluate');
    const tabKnowledgeContent = document.getElementById('tab-knowledge-content');
    const tabDocumentsContent = document.getElementById('tab-documents-content');
    const tabEvaluateContent = document.getElementById('tab-evaluate-content');
    const kbStatus = document.getElementById('kb-status');
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const jobQueue = document.getElementById('job-queue');
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const statusBadge = document.getElementById('status-badge');
    const ontoInfoPanel = document.getElementById('onto-info-panel');
    const ontoCardLoading = document.getElementById('onto-card-loading');
    const jobQueueSection = document.getElementById('job-queue-section');
    const jobQueueToggle = document.getElementById('job-queue-toggle');
    const currentOntologyPill = document.getElementById('current-ontology-pill');
    const currentOntologyName = document.getElementById('current-ontology-name');
    const currentOntologyStats = document.getElementById('current-ontology-stats');

    let lastReportTotals = null;
    let _hasMessages = false;
    let _activeKbId = null;
    let _chats = [];
    let _activeChatId = null;
    let _chatIdSeq = 0;

    function getActiveKbId() {{ return _activeKbId && _activeKbId !== '__upload__' ? _activeKbId : null; }}
    function setActiveKbId(id) {{ _activeKbId = id; }}
    function getActiveChat() {{ return _chats.find(c => c.id === _activeChatId); }}
    function getChatById(id) {{ return _chats.find(c => c.id === id); }}
    function getKbStatus(kbId) {{
      const running = jobs.some(j => j.status === 'running' && j.kbId === kbId);
      return running ? 'building' : 'ready';
    }}

    function createNewChat(kbId) {{
      const idToUse = kbId || getActiveKbId();
      const kb = _kbData.find(k => k.id === idToUse);
      const kbName = kb ? (kb.name || kb.id) : 'No KB';
      const id = 'chat-' + (++_chatIdSeq);
      const chat = {{ id, kbId: idToUse, kbName, messages: [] }};
      _chats.push(chat);
      _activeChatId = id;
      if (idToUse) setActiveKbId(idToUse);
      renderChatTabs();
      switchToChat(id);
      return chat;
    }}

    async function switchToChat(id) {{
      _activeChatId = id;
      const chat = getActiveChat();
      renderChatTabs();
      renderChatMessages(chat);
      updateEmptyStatesForChat(chat);
      if (chat?.kbId) {{
        setActiveKbId(chat.kbId);
        try {{
          const res = await fetch(API + '/knowledge-bases/' + chat.kbId + '/activate', {{ method: 'POST' }});
          if (res.ok) addRecentKB(chat.kbId);
        }} catch (_) {{}}
        setStickySummaryVisible(true);
        const kb = _kbData.find(k => k.id === chat.kbId);
        if (kb) {{
          currentOntologyPill.classList.remove('hidden');
          currentOntologyPill.classList.add('flex');
          currentOntologyName.textContent = kb.name || kb.id;
          const stats = kb.stats || {{}};
          const relCount = stats.relations ?? stats.edges ?? 0;
          const parts = [];
          if (stats.classes) parts.push(fmtNum(stats.classes) + ' cls');
          if (relCount) parts.push(fmtNum(relCount) + ' rel');
          currentOntologyStats.textContent = parts.join(' · ');
          const viewerUrl = window.location.origin + API + '/graph/viewer?kb_id=' + encodeURIComponent(chat.kbId);
          document.querySelectorAll('a.graph-viewer-link').forEach(a => {{ a.href = viewerUrl; }});
          document.getElementById('chat-onto-sticky-name').textContent = kb.name || kb.id;
          const stickyDesc = document.getElementById('chat-onto-sticky-desc');
          if (kb.description) {{ stickyDesc.textContent = kb.description; stickyDesc.style.display = ''; }} else {{ stickyDesc.style.display = 'none'; }}
          const stickyStats = document.getElementById('chat-onto-sticky-stats');
          stickyStats.innerHTML = '';
          [['Classes', stats.classes], ['Instances', stats.instances], ['Relations', relCount]].forEach(([l,v]) => {{
            const chip = document.createElement('div');
            chip.className = 'text-xs font-mono';
            chip.style.color = '#8a8a94';
            chip.textContent = l + ': ' + fmtNum(v ?? 0);
            stickyStats.appendChild(chip);
          }});
        }}
      }} else {{
        currentOntologyPill.classList.add('hidden');
        currentOntologyPill.classList.remove('flex');
      }}
    }}

    function renderChatTabs() {{
      const container = document.getElementById('chat-tabs');
      if (!container) return;
      container.innerHTML = '';
      _chats.forEach(c => {{
        const wrap = document.createElement('div');
        wrap.className = 'chat-tab-wrap flex items-center shrink-0';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'chat-tab shrink-0 flex items-center' + (c.id === _activeChatId ? ' active' : '');
        btn.innerHTML = '<span class="truncate max-w-[100px]">' + esc((c.kbName || 'Chat').substring(0, 20)) + (c.messages.length ? ' (' + c.messages.length + ')' : '') + '</span>';
        btn.title = c.kbName + (c.messages.length ? ' · ' + c.messages.length + ' messages' : '');
        btn.addEventListener('click', () => switchToChat(c.id));
        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'chat-tab-delete shrink-0';
        delBtn.style.color = '#8a8a94';
        delBtn.title = 'Delete chat';
        delBtn.innerHTML = '<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>';
        delBtn.addEventListener('click', (e) => {{ e.stopPropagation(); deleteChat(c.id); }});
        wrap.appendChild(btn);
        wrap.appendChild(delBtn);
        container.appendChild(wrap);
      }});
    }}

    function deleteChat(chatId) {{
      const idx = _chats.findIndex(c => c.id === chatId);
      if (idx < 0) return;
      _chats.splice(idx, 1);
      if (_activeChatId === chatId) {{
        _activeChatId = _chats.length ? _chats[0].id : null;
        if (_chats.length) {{
          switchToChat(_chats[0].id);
        }} else {{
          renderChatTabs();
          messagesEl.querySelectorAll('[data-chat-message]').forEach(el => el.remove());
          const hasKb = !!getActiveKbId();
          updateEmptyStatesForChat(hasKb ? {{ kbId: getActiveKbId(), messages: [] }} : {{ kbId: null, messages: [] }});
          setInputsEnabled(hasKb);
          setStickySummaryVisible(hasKb);
          if (hasKb) {{
            currentOntologyPill?.classList.remove('hidden');
            currentOntologyPill?.classList.add('flex');
            const kb = _kbData.find(k => k.id === getActiveKbId());
            if (kb) {{
              currentOntologyName.textContent = kb.name || kb.id;
              const stats = kb.stats || {{}};
              const relCount = stats.relations ?? stats.edges ?? 0;
              currentOntologyStats.textContent = [stats.classes, relCount].filter(Boolean).map(v => fmtNum(v)).join(' · ') || '';
            }}
          }} else {{
            currentOntologyPill?.classList.add('hidden');
            currentOntologyPill?.classList.remove('flex');
          }}
        }}
      }} else {{
        renderChatTabs();
      }}
    }}

    function updateEmptyStatesForChat(chat) {{
      const hasKb = chat && chat.kbId;
      const hasMsgs = chat && chat.messages.length > 0;
      emptyStateNoKb.classList.toggle('hidden', hasKb || _chats.length > 0);
      emptyStateNoKb.classList.toggle('flex', !hasKb && _chats.length === 0);
      emptyStateReady.classList.toggle('hidden', !hasKb || hasMsgs);
      emptyStateReady.classList.toggle('flex', hasKb && !hasMsgs);
      setInputsEnabled(!!hasKb);
      setStatusBadge(hasKb ? 'ready' : 'empty');
      setStickySummaryVisible(!!hasKb);
      if (hasKb && chat) {{
        const kb = _kbData.find(k => k.id === chat.kbId);
        if (kb) {{
          document.getElementById('chat-onto-name').textContent = kb.name || kb.id;
          const descEl = document.getElementById('chat-onto-desc');
          if (kb.description) {{ descEl.textContent = kb.description; descEl.style.display = ''; }} else {{ descEl.style.display = 'none'; }}
          const grid = document.getElementById('chat-onto-stats');
          grid.innerHTML = '';
          const stats = kb.stats || {{}};
          const relCount = stats.relations ?? stats.edges ?? 0;
          [['Classes', stats.classes], ['Instances', stats.instances], ['Relations', relCount]].forEach(([l,v]) => {{
            const chip = document.createElement('div');
            chip.className = 'rounded-lg px-3 py-2.5 text-center';
            chip.innerHTML = '<p class="stat-value text-base font-semibold">' + fmtNum(v ?? 0) + '</p><p class="text-xs mt-0.5 stat-label">' + l + '</p>';
            grid.appendChild(chip);
          }});
          const chatDocsEl = document.getElementById('chat-onto-docs');
          const chatDocsList = document.getElementById('chat-onto-docs-list');
          const docs = kb.documents || [];
          if (docs.length) {{
            chatDocsEl.classList.remove('hidden');
            chatDocsList.innerHTML = '';
            docs.forEach(d => {{
              const pill = document.createElement('span');
              pill.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium';
              pill.style.cssText = 'background: rgba(236,72,153,0.08); color: #e8e6e3; border: 1px solid rgba(236,72,153,0.2);';
              pill.innerHTML = '<svg class="w-3.5 h-3.5 shrink-0" style="color:#ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>'
                + '<span class="truncate max-w-[180px]">' + esc(d) + '</span>';
              chatDocsList.appendChild(pill);
            }});
          }} else {{
            chatDocsEl.classList.add('hidden');
          }}
        }}
      }}
    }}

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
        const downloadLink = document.getElementById('download-ontology-link');
        if (downloadLink) downloadLink.style.display = 'none';
        const readyEl = document.getElementById('onto-card-ready');
        if (readyEl) {{ readyEl.classList.add('hidden'); readyEl.classList.remove('flex'); }}
        return;
      }}
      const stats = kb.stats || {{}};
      const name = kb.name || kb.id;
      const desc = kb.description || '';
      const relCount = stats.relations ?? stats.edges ?? 0;

      // Sidebar card
      document.getElementById('onto-card-name').textContent = name;
      const readyEl = document.getElementById('onto-card-ready');
      if (readyEl) {{
        readyEl.classList.remove('hidden');
        readyEl.classList.add('flex');
        const building = getKbStatus(kb.id) === 'building';
        readyEl.innerHTML = building
          ? '<span class="kb-building-dot"></span>Building'
          : '<span class="kb-ready-dot"></span>Ready';
        readyEl.style.color = building ? '#f59e0b' : '#22c55e';
        readyEl.style.background = building ? 'rgba(245,158,11,0.15)' : 'rgba(34,197,94,0.15)';
      }}
      const summaryParts = [];
      if (stats.classes) summaryParts.push(fmtNum(stats.classes) + ' cls');
      if (stats.instances) summaryParts.push(fmtNum(stats.instances) + ' inst');
      if (relCount) summaryParts.push(fmtNum(relCount) + ' rel');
      document.getElementById('onto-card-summary').textContent = summaryParts.length ? summaryParts.join(' · ') : '';
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
        ['Relations', relCount, 'rel'],
        ['Axioms', stats.axioms ?? 0, 'ax'],
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

      // Download & View graph links (use active kb_id)
      const downloadLink = document.getElementById('download-ontology-link');
      if (downloadLink) {{
        downloadLink.href = API + '/ontology/export?format=owl&kb_id=' + encodeURIComponent(kb.id);
        downloadLink.style.display = '';
      }}
      const viewerLinks = document.querySelectorAll('a.graph-viewer-link');
      const viewerUrl = window.location.origin + API + '/graph/viewer?kb_id=' + encodeURIComponent(kb.id);
      viewerLinks.forEach(a => {{ a.href = viewerUrl; }});

      ontoInfoPanel.classList.remove('hidden');

      // Header pill
      currentOntologyPill.classList.remove('hidden');
      currentOntologyPill.classList.add('flex');
      currentOntologyName.textContent = name;
      const statParts = [];
      if (stats.classes) statParts.push(fmtNum(stats.classes) + ' cls');
      if (relCount) statParts.push(fmtNum(relCount) + ' rel');
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
        ['Relations', relCount],
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

      // Documents list
      const chatDocsEl = document.getElementById('chat-onto-docs');
      const chatDocsList = document.getElementById('chat-onto-docs-list');
      const docs = kb.documents || [];
      if (docs.length) {{
        chatDocsEl.classList.remove('hidden');
        chatDocsList.innerHTML = '';
        docs.forEach(d => {{
          const pill = document.createElement('span');
          pill.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium';
          pill.style.cssText = 'background: rgba(236,72,153,0.08); color: #e8e6e3; border: 1px solid rgba(236,72,153,0.2);';
          pill.innerHTML = '<svg class="w-3.5 h-3.5 shrink-0" style="color:#ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>'
            + '<span class="truncate max-w-[180px]">' + esc(d) + '</span>';
          chatDocsList.appendChild(pill);
        }});
      }} else {{
        chatDocsEl.classList.add('hidden');
      }}

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
        ['R', relCount],
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
      try {{
        const res = await fetch(API + '/knowledge-bases', {{ cache: 'no-store' }});
        if (!res.ok) return {{ items: [], active_id: null }};
        const data = await res.json();
        return data && typeof data === 'object' ? data : {{ items: [], active_id: null }};
      }} catch (e) {{
        console.error('[fetchKBs]', e);
        return {{ items: [], active_id: null }};
      }}
    }}

    function renderKbList(items, activeId) {{
      if (!kbList) return;
      const countEl = document.getElementById('kb-count');
      if (countEl) countEl.textContent = '(' + items.length + ')';
      const emptyEl = document.getElementById('kb-list-empty');
      if (emptyEl) emptyEl.classList.toggle('hidden', items.length > 0);
      kbList.innerHTML = '';
      for (const kb of items) {{
        const stats = kb.stats || {{}};
        const relCount = stats.relations ?? stats.edges ?? 0;
        const parts = [];
        if (stats.classes) parts.push(fmtNum(stats.classes) + ' cls');
        if (stats.instances) parts.push(fmtNum(stats.instances) + ' inst');
        if (relCount) parts.push(fmtNum(relCount) + ' rel');
        const summary = parts.length ? parts.join(' · ') : '—';
        const isActive = kb.id === activeId;
        const status = getKbStatus(kb.id);
        const docs = kb.documents || [];
        const docSummary = docs.length
          ? (docs.length === 1 ? docs[0] : docs.length + ' docs: ' + docs.slice(0, 3).map(d => esc(d)).join(', ') + (docs.length > 3 ? '…' : ''))
          : '—';
        const createdStr = kb.created_at ? formatDate(kb.created_at) : '';
        const card = document.createElement('div');
        card.className = 'kb-mgmt-row kb-list-card rounded-lg px-3 py-2.5 border flex flex-col gap-2' + (isActive ? ' active' : '');
        card.style.background = isActive ? 'rgba(236,72,153,0.08)' : 'rgba(20, 20, 26, 0.9)';
        card.style.borderColor = isActive ? 'rgba(236,72,153,0.5)' : '#2a2a3a';
        card.dataset.kbId = kb.id;
        const viewerUrl = window.location.origin + API + '/graph/viewer?kb_id=' + encodeURIComponent(kb.id);
        const statusBadge = status === 'building'
          ? '<span class="flex items-center gap-1 text-xs font-medium shrink-0" style="color:#f59e0b;"><span class="kb-building-dot"></span>Building</span>'
          : '<span class="kb-ready-badge flex items-center gap-1 text-xs font-medium shrink-0" style="color:#22c55e;"><span class="kb-ready-dot"></span>Ready</span>';
        const activeLabel = isActive ? '<span class="text-xs font-medium shrink-0 px-1.5 py-0.5 rounded" style="background:rgba(236,72,153,0.2);color:#ec4899;">Active</span>' : '';
        const subtextParts = [summary];
        if (docSummary !== '—') subtextParts.push(docSummary);
        if (createdStr) subtextParts.push(createdStr);
        const subtext = subtextParts.join(' · ');
        card.innerHTML = '<div class="flex items-center gap-2 min-w-0 flex-wrap">'
          + '<div class="flex-1 min-w-0">'
          + '<p class="text-sm font-medium truncate" style="color:#e8e6e3;">' + esc(kb.name || kb.id) + '</p>'
          + '<p class="text-xs truncate mt-0.5" style="color:#8a8a94;">' + esc(subtext) + '</p></div>'
          + statusBadge
          + activeLabel
          + '<div class="flex items-center gap-1 shrink-0" onclick="event.stopPropagation()">'
          + '<button type="button" class="kb-new-chat-btn text-xs font-medium px-2 py-1 rounded transition-colors" style="color:#8a8a94; background:#1a1a24;">+ Chat</button>'
          + '<a href="' + viewerUrl + '" target="_blank" rel="noopener noreferrer" class="text-xs font-medium link-teal opacity-70 hover:opacity-100 px-1.5 py-1">Open</a>'
          + '<button type="button" class="kb-mgmt-delete kb-delete-btn p-1 rounded shrink-0" style="color:#8a8a94;" title="Delete KB" data-kb-id="' + esc(kb.id) + '">'
          + '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>'
          + '</button></div>';
        card.querySelector('.kb-new-chat-btn').addEventListener('click', (e) => {{
          e.stopPropagation();
          createNewChat(kb.id);
        }});
        card.addEventListener('click', async (e) => {{
          if (e.target.closest('a') || e.target.closest('button')) return;
          const existing = _chats.find(c => c.kbId === kb.id);
          if (existing) {{
            await switchToChat(existing.id);
          }} else {{
            createNewChat(kb.id);
            await switchToChat(_activeChatId);
          }}
        }});
        const delBtn = card.querySelector('.kb-delete-btn');
        if (delBtn) delBtn.addEventListener('click', (e) => {{
          e.stopPropagation();
          const kid = delBtn.dataset.kbId;
          const k = _kbData.find(x => x.id === kid);
          _pendingDeleteId = kid;
          _pendingDeleteName = k ? (k.name || kid) : kid;
          document.getElementById('delete-modal-name').textContent = _pendingDeleteName;
          document.getElementById('delete-modal').classList.remove('hidden');
        }});
        kbList.appendChild(card);
      }}
    }}

    async function loadKBs() {{
      const data = await fetchKBs();
      let items = data.items || [];
      const recentIds = getRecentKBIds().filter(id => items.some(k => k.id === id));
      items = [...items].sort((a, b) => {{
        const ai = recentIds.indexOf(a.id);
        const bi = recentIds.indexOf(b.id);
        if (ai >= 0 && bi >= 0) return ai - bi;
        if (ai >= 0) return -1;
        if (bi >= 0) return 1;
        return 0;
      }});
      _kbData = items;
      _activeKbId = data.active_id || null;
      renderKbList(items, _activeKbId);
      if (data.active_id) {{
        addRecentKB(data.active_id);
        const activeKb = _kbData.find(k => k.id === data.active_id);
        setInputsEnabled(true);
        setStatusBadge('ready');
        renderOntologyCard(activeKb || {{ id: data.active_id, name: data.active_id }});
        showEmptyState(true);
        if (_chats.length === 0) {{
          createNewChat();
        }}
      }} else {{
        setInputsEnabled(false);
        setStatusBadge('empty');
        renderOntologyCard(null);
        showEmptyState(false);
      }}
      populateEvalKbSelector();
    }}

    function populateEvalKbSelector() {{
      const sel = document.getElementById('eval-kb-select');
      if (!sel) return;
      const items = _kbData || [];
      const activeId = getActiveKbId();
      sel.innerHTML = '<option value="">Select a KB</option>' + items.map(k => {{
        const docs = k.documents || [];
        const label = k.name + (docs.length ? ' (' + docs.length + ')' : '');
        return '<option value="' + esc(k.id) + '"' + (k.id === activeId ? ' selected' : '') + '>' + esc(label) + '</option>';
      }}).join('');
    }}

    async function fetchEvalHealth(kbId) {{
      if (!kbId) return;
      const statsEl = document.getElementById('eval-health-stats');
      const badgeEl = document.getElementById('eval-health-badge');
      const warningsEl = document.getElementById('eval-health-warnings');
      if (statsEl) statsEl.innerHTML = '<span style="color:#8a8a94;">Loading…</span>';
      try {{
        const res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/health');
        if (!res.ok) {{
          if (statsEl) statsEl.innerHTML = '<span style="color:#ef4444;">Failed to load health</span>';
          return;
        }}
        const h = await res.json();
        const s = h.structural || {{}};
        const badge = h.badge || '—';
        const score = h.overall_score ?? '—';
        if (badgeEl) {{
          badgeEl.textContent = badge + (typeof score === 'number' ? ' (' + score + ')' : '');
          badgeEl.style.background = badge === 'Healthy' ? 'rgba(34,197,94,0.2)' : badge === 'Critical' ? 'rgba(239,68,68,0.2)' : 'rgba(245,158,11,0.2)';
          badgeEl.style.color = badge === 'Healthy' ? '#22c55e' : badge === 'Critical' ? '#ef4444' : '#f59e0b';
        }}
        if (statsEl) {{
          statsEl.innerHTML = 'Nodes: ' + (s.node_count ?? '—') + '<br>Edges: ' + (s.edge_count ?? '—') + '<br>Density: ' + (s.density ?? '—') + '<br>Components: ' + (s.connected_components ?? '—') + '<br>Orphans: ' + (s.orphan_nodes ?? '—') + '<br>Relation types: ' + (h.semantic?.unique_relation_types ?? '—') + '<br>Facts/node: ' + (h.retrieval?.facts_per_node ?? '—') + '<br>Hyperedge coverage: ' + (h.retrieval?.hyperedge_coverage ?? '—');
        }}
        const orphans = s.orphan_nodes ?? 0;
        const comps = s.connected_components ?? 0;
        const warn = [];
        if (orphans > 0) warn.push(orphans + ' nodes are isolated.');
        if (comps > 1) warn.push('Graph has ' + comps + ' disconnected subgraphs.');
        if (warningsEl) {{
          warningsEl.innerHTML = warn.length ? warn.join('<br>') : '';
          warningsEl.style.display = warn.length ? '' : 'none';
        }}
      }} catch (e) {{
        console.error('[fetchEvalHealth]', e);
        if (statsEl) statsEl.innerHTML = '<span style="color:#ef4444;">Error loading health</span>';
      }}
    }}

    async function fetchEvalRecords(kbId) {{
      const listEl = document.getElementById('eval-records-list');
      if (!listEl) return;
      if (!kbId) {{
        listEl.innerHTML = '<p class="text-xs">Select a KB to view evaluation history</p>';
        return;
      }}
      listEl.innerHTML = '<p class="text-xs" style="color:#8a8a94;">Loading records…</p>';
      try {{
        const res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/evaluation-records');
        if (!res.ok) {{
          listEl.innerHTML = '<p class="text-xs" style="color:#ef4444;">Failed to load records</p>';
          return;
        }}
        const records = await res.json();
        if (!records || !records.length) {{
          listEl.innerHTML = '<p class="text-xs">No evaluation records yet</p>';
          return;
        }}
        listEl.innerHTML = records.map((r, idx) => {{
          const ts = r.timestamp ? new Date(r.timestamp).toLocaleString() : '—';
          const scores = r.scores || {{}};
          const metrics = ['context_recall', 'entity_recall', 'answer_correctness', 'faithfulness', 'answer_relevancy'];
          const vals = metrics.map(m => scores[m]).filter(v => v != null);
          const avg = vals.length ? (vals.reduce((a, b) => a + b, 0) / vals.length * 100).toFixed(0) : '—';
          const ac = scores.answer_correctness != null ? (scores.answer_correctness * 100).toFixed(0) : '—';
          const n = r.num_questions ?? 0;
          const id = 'eval-record-' + idx;
          const detailId = 'eval-record-detail-' + idx;
          const perQ = (scores.per_question || []);
          const detailRows = perQ.slice(0, 50).map(pq => {{
            const q = (pq.question || '').substring(0, 60) + (pq.question && pq.question.length > 60 ? '…' : '');
            const cr = pq.context_recall != null ? (pq.context_recall * 100).toFixed(0) : '—';
            const er = pq.entity_recall != null ? (pq.entity_recall * 100).toFixed(0) : '—';
            const acq = pq.answer_correctness != null ? (pq.answer_correctness * 100).toFixed(0) : '—';
            return '<tr><td class="py-1 pr-2 text-left" style="max-width:180px; overflow:hidden; text-overflow:ellipsis;" title="' + esc(pq.question || '') + '">' + esc(q) + '</td><td class="py-1 px-1 text-right">' + cr + '%</td><td class="py-1 px-1 text-right">' + er + '%</td><td class="py-1 px-1 text-right">' + acq + '%</td></tr>';
          }}).join('');
          const more = perQ.length > 50 ? '<p class="text-xs mt-1" style="color:#8a8a94;">… and ' + (perQ.length - 50) + ' more</p>' : '';
          return '<div class="rounded-lg border overflow-hidden" style="border-color:#2a2a3a; background:#14141a;"><button type="button" class="eval-record-header w-full px-3 py-2 flex items-center justify-between text-left hover:opacity-90 transition-opacity" data-id="' + id + '" data-detail="' + detailId + '"><div class="flex flex-col items-start"><span class="text-xs font-medium" style="color:#e8e6e3;">' + esc(ts) + '</span><span class="text-xs mt-0.5" style="color:#8a8a94;">' + n + ' questions · avg ' + avg + '% · AC ' + ac + '%</span></div><svg class="eval-record-chevron w-4 h-4 shrink-0 transition-transform" style="color:#8a8a94;" data-id="' + id + '" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg></button><div id="' + detailId + '" class="eval-record-detail hidden px-3 pb-3 pt-1 border-t" style="border-color:#2a2a3a;"><div class="text-xs space-y-1 mb-2" style="color:#8a8a94;">context_recall: ' + (scores.context_recall != null ? (scores.context_recall * 100).toFixed(1) : '—') + '% · entity_recall: ' + (scores.entity_recall != null ? (scores.entity_recall * 100).toFixed(1) : '—') + '% · answer_correctness: ' + (scores.answer_correctness != null ? (scores.answer_correctness * 100).toFixed(1) : '—') + '% · faithfulness: ' + (scores.faithfulness != null ? (scores.faithfulness * 100).toFixed(1) : '—') + '% · answer_relevancy: ' + (scores.answer_relevancy != null ? (scores.answer_relevancy * 100).toFixed(1) : '—') + '%</div><div class="overflow-x-auto max-h-[200px] overflow-y-auto"><table class="w-full text-xs" style="color:#8a8a94;"><thead><tr><th class="text-left py-1 pr-2">Question</th><th class="text-right py-1 px-1">CR</th><th class="text-right py-1 px-1">ER</th><th class="text-right py-1 px-1">AC</th></tr></thead><tbody>' + detailRows + '</tbody></table></div>' + more + '</div></div>';
        }}).join('');
        listEl.querySelectorAll('.eval-record-header').forEach(btn => {{
          btn.addEventListener('click', () => {{
            const detailId = btn.getAttribute('data-detail');
            const chevron = btn.querySelector('.eval-record-chevron');
            const detail = document.getElementById(detailId);
            if (detail?.classList.contains('hidden')) {{
              detail.classList.remove('hidden');
              if (chevron) chevron.style.transform = 'rotate(180deg)';
            }} else {{
              detail?.classList.add('hidden');
              if (chevron) chevron.style.transform = '';
            }}
          }});
        }});
      }} catch (e) {{
        console.error('[fetchEvalRecords]', e);
        listEl.innerHTML = '<p class="text-xs" style="color:#ef4444;">Error loading records</p>';
      }}
    }}

    const RECENT_KB_KEY = 'clarence_recent_kb_ids';
    function addRecentKB(id) {{
      try {{
        let ids = JSON.parse(localStorage.getItem(RECENT_KB_KEY) || '[]');
        ids = [id].concat(ids.filter(x => x !== id)).slice(0, 20);
        localStorage.setItem(RECENT_KB_KEY, JSON.stringify(ids));
      }} catch (_) {{}}
    }}
    function getRecentKBIds() {{
      try {{
        return JSON.parse(localStorage.getItem(RECENT_KB_KEY) || '[]');
      }} catch (_) {{ return []; }}
    }}

    async function activateKB(id) {{
      ontoInfoPanel.classList.remove('hidden');
      if (ontoCardLoading) ontoCardLoading.classList.remove('hidden');
      try {{
        const res = await fetch(API + '/knowledge-bases/' + id + '/activate', {{ method: 'POST' }});
        if (!res.ok) {{
          const err = await res.json().catch(() => ({{}}));
          throw new Error(parseError(err) || res.statusText);
        }}
        addRecentKB(id);
        await loadKBs();
      }} finally {{
        if (ontoCardLoading) ontoCardLoading.classList.add('hidden');
      }}
    }}

    document.getElementById('kb-refresh-btn')?.addEventListener('click', () => loadKBs());

    tabKnowledge?.addEventListener('click', () => {{
      tabKnowledge.classList.add('sidebar-tab-active');
      tabKnowledge.classList.remove('sidebar-tab-inactive');
      tabDocuments?.classList.remove('sidebar-tab-active');
      tabDocuments?.classList.add('sidebar-tab-inactive');
      tabEvaluate?.classList.remove('sidebar-tab-active');
      tabEvaluate?.classList.add('sidebar-tab-inactive');
      tabKnowledgeContent?.classList.remove('hidden');
      tabDocumentsContent?.classList.add('hidden');
      tabEvaluateContent?.classList.add('hidden');
    }});
    tabDocuments?.addEventListener('click', () => {{
      tabDocuments?.classList.add('sidebar-tab-active');
      tabDocuments?.classList.remove('sidebar-tab-inactive');
      tabKnowledge?.classList.remove('sidebar-tab-active');
      tabKnowledge?.classList.add('sidebar-tab-inactive');
      tabEvaluate?.classList.remove('sidebar-tab-active');
      tabEvaluate?.classList.add('sidebar-tab-inactive');
      tabDocumentsContent?.classList.remove('hidden');
      tabKnowledgeContent?.classList.add('hidden');
      tabEvaluateContent?.classList.add('hidden');
    }});
    tabEvaluate?.addEventListener('click', () => {{
      tabEvaluate?.classList.add('sidebar-tab-active');
      tabEvaluate?.classList.remove('sidebar-tab-inactive');
      tabKnowledge?.classList.remove('sidebar-tab-active');
      tabKnowledge?.classList.add('sidebar-tab-inactive');
      tabDocuments?.classList.remove('sidebar-tab-active');
      tabDocuments?.classList.add('sidebar-tab-inactive');
      tabEvaluateContent?.classList.remove('hidden');
      tabKnowledgeContent?.classList.add('hidden');
      tabDocumentsContent?.classList.add('hidden');
      populateEvalKbSelector();
      const sel = document.getElementById('eval-kb-select');
      if (sel?.value) {{ fetchEvalHealth(sel.value); fetchEvalRecords(sel.value); }}
    }});

    if (jobQueueToggle && jobQueueSection) {{
      jobQueueToggle.addEventListener('click', () => jobQueueSection.classList.toggle('collapsed'));
    }}

    document.getElementById('eval-kb-select')?.addEventListener('change', (e) => {{
      const kbId = e.target?.value;
      if (kbId) {{ fetchEvalHealth(kbId); fetchEvalRecords(kbId); }}
      else {{
        document.getElementById('eval-health-stats').innerHTML = 'Select a KB to view health';
        document.getElementById('eval-health-badge').textContent = '—';
        document.getElementById('eval-health-warnings').innerHTML = '';
        fetchEvalRecords('');
      }}
    }});
    document.getElementById('eval-refresh-btn')?.addEventListener('click', () => {{
      const kbId = document.getElementById('eval-kb-select')?.value;
      if (kbId) fetchEvalHealth(kbId);
    }});
    document.getElementById('eval-repair-btn')?.addEventListener('click', runRepair);
    document.getElementById('eval-run-btn')?.addEventListener('click', runEvaluation);

    async function runEvaluation() {{
      const kbId = document.getElementById('eval-kb-select')?.value;
      if (!kbId) return;
      const numQuestions = Math.min(500, Math.max(1, parseInt(document.getElementById('eval-num-questions')?.value || '5', 10) || 5));
      const evalPanel = document.getElementById('eval-eval-panel');
      const progressPanel = document.getElementById('eval-eval-progress');
      const logEl = document.getElementById('eval-eval-log');
      const stageLabel = document.getElementById('eval-eval-stage-label');
      const progressBar = document.getElementById('eval-eval-progress-bar');
      const errorEl = document.getElementById('eval-eval-error');
      const runBtn = document.getElementById('eval-run-btn');
      if (!evalPanel || !progressPanel || !logEl) return;
      evalPanel.classList.add('hidden');
      progressPanel.classList.remove('hidden');
      logEl.innerHTML = '';
      errorEl?.classList.add('hidden');
      if (runBtn) runBtn.disabled = true;
      function addLog(icon, msg) {{
        const div = document.createElement('div');
        div.innerHTML = (icon || '▸') + ' ' + (msg || '');
        logEl.appendChild(div);
        logEl.scrollTop = logEl.scrollHeight;
      }}
      try {{
        const res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/evaluate?num_questions=' + numQuestions, {{ method: 'POST' }});
        if (!res.ok) {{
          const err = await res.json().catch(() => ({{}}));
          throw new Error(parseError(err) || res.statusText);
        }}
        const reader = res.body?.getReader();
        const dec = new TextDecoder();
        if (reader) {{
          let buf = '';
          while (true) {{
            const {{ done, value }} = await reader.read();
            if (done) break;
            buf += dec.decode(value, {{ stream: true }});
            const lines = buf.split('\\n');
            buf = lines.pop() || '';
            for (const line of lines) {{
              if (line.startsWith('data: ')) {{
                try {{
                  const data = JSON.parse(line.slice(6));
                  if (data.type === 'step') {{
                    stageLabel.textContent = data.message || 'Evaluating...';
                    addLog('✓', data.message);
                  }} else if (data.type === 'progress') {{
                    const pct = data.total ? (100 * data.current / data.total) : 0;
                    progressBar.style.width = pct + '%';
                    addLog('▸', data.question ? 'Q: ' + data.question.substring(0, 50) + '...' : '');
                  }} else if (data.type === 'complete') {{
                    stageLabel.textContent = 'Done';
                    progressBar.style.width = '100%';
                    addLog('✓', 'Evaluation complete');
                    const scores = data.scores || {{}};
                    const statsEl = document.getElementById('eval-eval-stats');
                    const badgeEl = document.getElementById('eval-eval-badge');
                    if (statsEl) {{
                      const parts = [];
                      if (scores.context_recall != null) parts.push('context_recall: ' + (scores.context_recall * 100).toFixed(1) + '%');
                      if (scores.entity_recall != null) parts.push('entity_recall: ' + (scores.entity_recall * 100).toFixed(1) + '%');
                      if (scores.answer_correctness != null) parts.push('answer_correctness: ' + (scores.answer_correctness * 100).toFixed(1) + '%');
                      if (scores.faithfulness != null) parts.push('faithfulness: ' + (scores.faithfulness * 100).toFixed(1) + '%');
                      if (scores.answer_relevancy != null) parts.push('answer_relevancy: ' + (scores.answer_relevancy * 100).toFixed(1) + '%');
                      statsEl.innerHTML = parts.join('<br>') || '—';
                    }}
                    if (badgeEl) {{
                      const avg = scores.answer_correctness != null ? (scores.answer_correctness * 100).toFixed(0) : '—';
                      badgeEl.textContent = avg + '%';
                      badgeEl.style.background = 'rgba(236,72,153,0.2)';
                      badgeEl.style.color = '#ec4899';
                    }}
                    await fetchEvalHealth(kbId);
                    fetchEvalRecords(kbId);
                    populateEvalKbSelector();
                  }} else if (data.type === 'error') {{
                    errorEl.textContent = data.message || 'Error';
                    errorEl.classList.remove('hidden');
                    addLog('✗', data.message || 'Error');
                  }}
                }} catch (_) {{}}
              }}
            }}
          }}
        }}
      }} catch (e) {{
        errorEl.textContent = e.message || 'Evaluation failed';
        errorEl.classList.remove('hidden');
        addLog('✗', e.message || 'Evaluation failed');
      }} finally {{
        if (runBtn) runBtn.disabled = false;
        setTimeout(() => {{
          progressPanel.classList.add('hidden');
          evalPanel.classList.remove('hidden');
          progressBar.style.width = '0%';
        }}, 1500);
      }}
    }}

    async function runRepair() {{
      const kbId = document.getElementById('eval-kb-select')?.value;
      if (!kbId) return;
      const panelA = document.getElementById('eval-panel-state-a');
      const panelB = document.getElementById('eval-panel-state-b');
      const logFeed = document.getElementById('eval-log-feed');
      const stageLabel = document.getElementById('eval-stage-label');
      const progressBar = document.getElementById('eval-progress-bar');
      const errorBanner = document.getElementById('eval-error-banner');
      const repairBtn = document.getElementById('eval-repair-btn');
      if (!panelA || !panelB || !logFeed) return;
      panelA.classList.add('hidden');
      panelB.classList.remove('hidden');
      logFeed.innerHTML = '';
      errorBanner?.classList.add('hidden');
      if (repairBtn) repairBtn.disabled = true;
      const steps = ['Loading graph', 'Adding root concept', 'Linking orphans', 'Bridging components', 'Running inference', 'Computing health', 'Saving', 'Rebuilding index', 'Done'];
      let stepIdx = 0;
      function addLog(icon, msg) {{
        const div = document.createElement('div');
        div.innerHTML = (icon || '▸') + ' ' + (msg || '');
        logFeed.appendChild(div);
        logFeed.scrollTop = logFeed.scrollHeight;
      }}
      try {{
        const res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/repair', {{ method: 'POST' }});
        if (!res.ok) {{
          const err = await res.json().catch(() => ({{}}));
          throw new Error(parseError(err) || res.statusText);
        }}
        const reader = res.body?.getReader();
        const dec = new TextDecoder();
        if (reader) {{
          let buf = '';
          while (true) {{
            const {{ done, value }} = await reader.read();
            if (done) break;
            buf += dec.decode(value, {{ stream: true }});
            const lines = buf.split('\\n');
            buf = lines.pop() || '';
            for (const line of lines) {{
              if (line.startsWith('data: ')) {{
                try {{
                  const data = JSON.parse(line.slice(6));
                  if (data.type === 'step') {{
                    stepIdx = Math.min(stepIdx + 1, steps.length - 1);
                    stageLabel.textContent = data.message || steps[stepIdx];
                    progressBar.style.width = (100 * stepIdx / (steps.length - 1)) + '%';
                    addLog('✓', data.message || steps[stepIdx]);
                  }} else if (data.type === 'done') {{
                    stageLabel.textContent = 'Done' + (data.edges_added ? ' (' + data.edges_added + ' edges added)' : '');
                    progressBar.style.width = '100%';
                    addLog('✓', 'Repair complete');
                    await fetchEvalHealth(kbId);
                    populateEvalKbSelector();
                  }} else if (data.type === 'error') {{
                    errorBanner.textContent = data.message || 'Error';
                    errorBanner.classList.remove('hidden');
                    addLog('✗', data.message || 'Error');
                  }}
                }} catch (_) {{}}
              }}
            }}
          }}
        }} else {{
          const data = await res.json();
          stageLabel.textContent = 'Done' + (data.report?.edges_added ? ' (' + data.report.edges_added + ' edges added)' : '');
          progressBar.style.width = '100%';
          addLog('✓', 'Repair complete');
          await fetchEvalHealth(kbId);
          populateEvalKbSelector();
        }}
      }} catch (e) {{
        errorBanner.textContent = e.message || 'Repair failed';
        errorBanner.classList.remove('hidden');
        addLog('✗', e.message || 'Repair failed');
      }} finally {{
        if (repairBtn) repairBtn.disabled = false;
        setTimeout(() => {{
          panelB.classList.add('hidden');
          panelA.classList.remove('hidden');
          progressBar.style.width = '0%';
        }}, 1500);
      }}
    }}

    function fillPrompt(text) {{
      questionInput.value = text;
      questionInput.focus();
    }}

    function hideEmptyStates() {{
      _hasMessages = true;
      emptyStateNoKb.classList.add('hidden');
      emptyStateReady.classList.add('hidden');
      emptyStateReady.classList.remove('flex');
      setStickySummaryVisible(Boolean(getActiveKbId()));
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

    function buildMessageElement(role, content, sources, numFactsUsed, rawFacts, reasoning) {{
      const hasRawFacts = role === 'assistant' && rawFacts && Array.isArray(rawFacts) && rawFacts.length > 0;
      const hasReasoning = role === 'assistant' && reasoning && typeof reasoning === 'string' && reasoning.trim().length > 0;
      const div = document.createElement('div');
      div.dataset.chatMessage = '1';
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
        metaLabel.textContent = 'Clearence';
        metaRow.appendChild(metaLabel);
        if (numFactsUsed > 0) {{
          const factsBadge = document.createElement('span');
          factsBadge.className = 'text-xs px-1.5 py-0.5 rounded font-mono';
          factsBadge.style.cssText = 'background:rgba(236,72,153,0.1); color:#ec4899;';
          factsBadge.textContent = numFactsUsed + ' facts';
          metaRow.appendChild(factsBadge);
        }}
        bubble.appendChild(metaRow);

        // Explainable reasoning: Raw facts (expandable)
        if (hasRawFacts) {{
          const rawFactsDiv = document.createElement('details');
          rawFactsDiv.className = 'mb-3 rounded-lg overflow-hidden';
          rawFactsDiv.style.cssText = 'border:1px solid #1a1a24; background:#14141a;';
          const summary = document.createElement('summary');
          summary.className = 'cursor-pointer px-3 py-2 text-xs font-medium flex items-center gap-2';
          summary.style.color = '#8a8a94';
          summary.innerHTML = '<svg class="w-3 h-3 shrink-0" style="color:#ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"/></svg> Raw facts used';
          rawFactsDiv.appendChild(summary);
          const rawContent = document.createElement('div');
          rawContent.className = 'px-3 pb-2.5 pt-1 space-y-2 text-xs font-mono';
          rawContent.style.cssText = 'color:#8a8a94; max-height:200px; overflow-y:auto;';
          rawFacts.forEach((fact, i) => {{
            const p = document.createElement('p');
            p.style.cssText = 'margin:0; padding:0.25rem 0; border-bottom:1px solid #1a1a24;';
            p.textContent = '[' + (i + 1) + '] ' + (typeof fact === 'string' ? fact : String(fact));
            rawContent.appendChild(p);
          }});
          rawFactsDiv.appendChild(rawContent);
          bubble.appendChild(rawFactsDiv);
        }}

        // Reasoning: in-depth interpretation of the facts (expandable)
        if (hasReasoning) {{
          const reasonDiv = document.createElement('details');
          reasonDiv.className = 'mb-3 rounded-lg overflow-hidden';
          reasonDiv.style.cssText = 'border:1px solid #1a1a24; background:#14141a;';
          const summary = document.createElement('summary');
          summary.className = 'cursor-pointer px-3 py-2 text-xs font-medium flex items-center gap-2';
          summary.style.color = '#8a8a94';
          summary.innerHTML = '<svg class="w-3 h-3 shrink-0" style="color:#ec4899;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg> Reasoning';
          reasonDiv.appendChild(summary);
          const reasonContent = document.createElement('div');
          reasonContent.className = 'px-3 pb-2.5 pt-1 text-sm leading-relaxed';
          reasonContent.style.cssText = 'color:#b8b8c0; max-height:300px; overflow-y:auto; white-space:pre-wrap;';
          reasonContent.appendChild(renderAssistantGuide(reasoning));
          reasonDiv.appendChild(reasonContent);
          bubble.appendChild(reasonDiv);
        }}
      }}

      const text = document.createElement('div');
      text.className = 'whitespace-pre-wrap text-sm leading-relaxed';
      if (typeof content === 'string') {{
        if (role === 'assistant') {{
          text.className = 'text-sm leading-relaxed';
          if (hasRawFacts || hasReasoning) {{
            const explLabel = document.createElement('div');
            explLabel.className = 'text-xs font-medium mb-2';
            explLabel.style.color = '#ec4899';
            explLabel.textContent = 'Answer';
            text.appendChild(explLabel);
          }}
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
      return div;
    }}

    function buildOntologySummaryElement(report, prevTotals) {{
      if (!report) return null;
      const div = document.createElement('div');
      div.dataset.chatMessage = '1';
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

      const statsGrid = document.createElement('div');
      statsGrid.className = 'grid grid-cols-3 sm:grid-cols-6 gap-2';
      const totalRel = totals.relations ?? totals.edges ?? 0;
      const statItems = [
        ['Classes', totals.classes ?? 0],
        ['Instances', totals.instances ?? 0],
        ['Relations', totalRel],
        ['Axioms', totals.axioms ?? 0],
        ['Data Props', totals.data_properties ?? 0],
      ];
      const keyMap = {{ 'Classes': 'classes', 'Instances': 'instances', 'Relations': 'relations', 'Axioms': 'axioms', 'Data Props': 'data_properties' }};
      statItems.forEach(([label, val]) => {{
        const key = keyMap[label] || label.toLowerCase();
        const prev = prevTotals ? (prevTotals[key] ?? 0) : null;
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
      wrap.appendChild(statsGrid);

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
        '5. OWL 2 RL reasoning: ' + (infEdges > 0 ? infEdges + ' relations in ' + iter + ' iterations' : 'Skipped'),
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
      return div;
    }}

    function renderChatMessages(chat) {{
      messagesEl.querySelectorAll('[data-chat-message]').forEach(el => el.remove());
      if (!chat || !chat.messages) return;
      const insertBefore = messagesEl.querySelector('#empty-state-no-kb') || messagesEl.querySelector('#empty-state-ready');
      let lastOntologyTotals = null;
      chat.messages.forEach(m => {{
        let el;
        if (m.type === 'ontology_summary') {{
          el = buildOntologySummaryElement(m.report, lastOntologyTotals);
          const totals = m.report?.totals || {{}};
          lastOntologyTotals = {{ classes: totals.classes ?? 0, instances: totals.instances ?? 0, relations: totals.relations ?? totals.edges ?? 0, axioms: totals.axioms ?? 0, data_properties: totals.data_properties ?? 0 }};
        }} else {{
          el = buildMessageElement(m.role, m.content, m.sources, m.numFactsUsed, m.rawFacts, m.reasoning);
        }}
        if (el) messagesEl.insertBefore(el, insertBefore);
      }});
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }}

    function appendMessage(role, content, sources, numFactsUsed, chatId, rawFacts, reasoning) {{
      let chat = chatId ? getChatById(chatId) : getActiveChat();
      if (!chat) {{
        if (chatId) return;
        if (!getActiveKbId()) return;
        chat = createNewChat();
      }}
      chat.messages.push({{ role, content, sources, numFactsUsed, rawFacts, reasoning }});
      if (chat.id === _activeChatId) {{
        hideEmptyStates();
        const el = buildMessageElement(role, content, sources, numFactsUsed, rawFacts, reasoning);
        const before = messagesEl.querySelector('#empty-state-no-kb') || messagesEl.querySelector('#empty-state-ready');
        messagesEl.insertBefore(el, before);
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }}
      renderChatTabs();
    }}

    function appendOntologySummary(report, kbId) {{
      if (!report || !kbId) return;
      let chat = _chats.find(c => c.kbId === kbId);
      if (!chat) chat = createNewChat(kbId);
      chat.messages.push({{ type: 'ontology_summary', report }});
      if (chat.id === _activeChatId) {{
        hideEmptyStates();
        const el = buildOntologySummaryElement(report, lastReportTotals);
        if (el) {{
          const before = messagesEl.querySelector('#empty-state-no-kb') || messagesEl.querySelector('#empty-state-ready');
          messagesEl.insertBefore(el, before);
        }}
        const totals = report.totals || {{}};
        const totalRel = totals.relations ?? totals.edges ?? 0;
        lastReportTotals = {{ classes: totals.classes ?? 0, instances: totals.instances ?? 0, relations: totalRel, axioms: totals.axioms ?? 0, data_properties: totals.data_properties ?? 0 }};
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }}
      renderChatTabs();
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
      if (!getActiveChat() && getActiveKbId()) createNewChat();
      if (!getActiveChat()) return;
      const submitChatId = getActiveChat().id;
      questionInput.value = '';
      appendMessage('user', q, null, null, submitChatId);
      showLoading(true);
      setInputsEnabled(false);
      const controller = new AbortController();
      const qaTimeoutMs = 90000;
      const timeoutId = setTimeout(() => controller.abort(), qaTimeoutMs);
      try {{
        const chat = getChatById(submitChatId);
        const kbId = (chat && chat.kbId) ? chat.kbId : getActiveKbId();
        if (!kbId) {{ setInputsEnabled(true); return; }}
        const body = {{ question: q, kb_id: kbId }};
        const res = await fetch(API + '/qa/ask', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(body),
          signal: controller.signal,
        }});
        const data = await res.json().catch(() => ({{}}));
        if (!res.ok) throw new Error(parseError(data) || res.statusText);
        const sourceTags = (data.source_labels && data.source_labels.length) ? data.source_labels : (data.source_refs || []);
        const rawFacts = data.sources || [];
        const reasoning = data.reasoning || '';
        appendMessage('assistant', data.answer, sourceTags, data.num_facts_used, submitChatId, rawFacts, reasoning);
      }} catch (e) {{
        const msg = e && e.name === 'AbortError'
          ? 'Request timed out. The model may be overloaded; try again.'
          : e.message;
        appendMessage('assistant', 'Error: ' + msg, null, null, submitChatId, null, null);
      }} finally {{
        clearTimeout(timeoutId);
        showLoading(false);
        setInputsEnabled(true);
      }}
    }});

    // Upload (label handles click; drop handlers for drag-and-drop)
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

    function showCreateModal(file, source) {{
      pendingFile = file;
      const stem = file.name.replace(/\\.[^.]+$/, '') || file.name;
      modalTitle.value = stem;
      modalDescription.value = '';
      modalFilename.textContent = 'File: ' + file.name;

      const activeId = getActiveKbId();
      if (activeId) {{
        const activeKb = _kbData.find(k => k.id === activeId);
        const kbName = activeKb ? activeKb.name : activeId;
        document.getElementById('modal-mode-kb-name').textContent = kbName;
        modalModeSection.classList.remove('hidden');
        setModalMode(source === 'document' ? 'extend' : 'new');
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
      const activeId = getActiveKbId();
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
        _chats = _chats.filter(c => c.kbId !== idToDelete);
        if (_activeChatId && _chats.every(c => c.id !== _activeChatId)) {{
          _activeChatId = _chats[0]?.id || null;
        }}
        try {{
          let recent = JSON.parse(localStorage.getItem(RECENT_KB_KEY) || '[]');
          recent = recent.filter(id => id !== idToDelete);
          localStorage.setItem(RECENT_KB_KEY, JSON.stringify(recent));
        }} catch (_) {{}}
        await loadKBs();
        renderChatTabs();
        if (_chats.length && _activeChatId) switchToChat(_activeChatId);
        else if (!_chats.length) {{
          renderChatMessages(null);
          updateEmptyStatesForChat({{ kbId: null, messages: [] }});
          setInputsEnabled(false);
        }}
        kbStatus.textContent = 'Knowledge base deleted successfully';
        kbStatus.style.color = '#22c55e';
        kbStatus.style.display = '';
        setTimeout(() => {{ kbStatus.style.display = 'none'; }}, 3000);
      }} catch (e) {{
        kbStatus.textContent = 'Delete failed: ' + e.message;
        kbStatus.style.color = '#ef4444';
        kbStatus.style.display = '';
      }}
    }});

    // KB summary/edit modal
    const kbSummaryModal = document.getElementById('kb-summary-modal');
    const kbSummaryName = document.getElementById('kb-summary-name');
    const kbSummaryDesc = document.getElementById('kb-summary-desc');
    const kbSummaryStats = document.getElementById('kb-summary-stats');

    function showKbSummaryModal() {{
      const activeId = getActiveKbId();
      if (!activeId) return;
      const kb = _kbData.find(k => k.id === activeId);
      if (!kb) return;
      kbSummaryName.value = kb.name || kb.id;
      kbSummaryDesc.value = kb.description || '';
      const stats = kb.stats || {{}};
      const relCount = stats.relations ?? stats.edges ?? 0;
      kbSummaryStats.innerHTML = '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:#8a8a94;">Stats</p>'
        + '<div class="grid grid-cols-2 gap-2 text-xs font-mono" style="color:#e8e6e3;">'
        + '<div><span style="color:#8a8a94;">Classes:</span> ' + fmtNum(stats.classes ?? 0) + '</div>'
        + '<div><span style="color:#8a8a94;">Instances:</span> ' + fmtNum(stats.instances ?? 0) + '</div>'
        + '<div><span style="color:#8a8a94;">Relations:</span> ' + fmtNum(relCount) + '</div>'
        + '<div><span style="color:#8a8a94;">Axioms:</span> ' + fmtNum(stats.axioms ?? 0) + '</div>'
        + '<div><span style="color:#8a8a94;">Data props:</span> ' + fmtNum(stats.data_properties ?? 0) + '</div>'
        + '</div>';
      kbSummaryModal.dataset.kbId = activeId;
      kbSummaryModal.classList.remove('hidden');
    }}

    function hideKbSummaryModal() {{
      kbSummaryModal.classList.add('hidden');
      delete kbSummaryModal.dataset.kbId;
    }}

    document.getElementById('kb-summary-close').addEventListener('click', hideKbSummaryModal);
    kbSummaryModal.querySelector('.modal-backdrop').addEventListener('click', hideKbSummaryModal);
    document.getElementById('kb-summary-cancel').addEventListener('click', hideKbSummaryModal);
    document.getElementById('kb-summary-save').addEventListener('click', async () => {{
      const kbId = kbSummaryModal.dataset.kbId;
      if (!kbId) return;
      const name = kbSummaryName.value.trim();
      const description = kbSummaryDesc.value.trim();
      const body = {{}};
      if (name) body.name = name;
      body.description = description;
      try {{
        const res = await fetch(API + '/knowledge-bases/' + kbId, {{
          method: 'PATCH',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(body),
        }});
        if (!res.ok) {{
          const data = await res.json().catch(() => ({{}}));
          throw new Error(parseError(data) || res.statusText);
        }}
        hideKbSummaryModal();
        await loadKBs();
      }} catch (e) {{
        kbStatus.textContent = 'Update failed: ' + e.message;
        kbStatus.style.display = '';
      }}
    }});

    // Ontology card: expand/collapse + click to open summary modal
    const ontoCard = document.getElementById('onto-card');
    const ontoCardExpandBtn = document.getElementById('onto-card-expand-btn');
    let _ontoCardExpanded = false;
    if (ontoCard) {{
      ontoCardExpandBtn?.addEventListener('click', (e) => {{
        e.stopPropagation();
        _ontoCardExpanded = !_ontoCardExpanded;
        ontoCard.classList.toggle('collapsed', !_ontoCardExpanded);
      }});
      ontoCard.addEventListener('click', (e) => {{
        if (e.target.closest('#onto-card-expand-btn') || e.target.closest('a') || e.target.closest('button')) return;
        showKbSummaryModal();
      }});
    }}

    // Job details modal
    const jobDetailModal = document.getElementById('job-detail-modal');
    const jobDetailContent = document.getElementById('job-detail-content');
    const jobDetailTitle = document.getElementById('job-detail-title');

    modalConfirm?.addEventListener('click', () => {{
      if (!pendingFile) return;
      const parallel = _modalMode === 'extend'
        ? document.getElementById('modal-parallel-extend').checked
        : document.getElementById('modal-parallel').checked;
      const file = pendingFile;
      hideCreateModal();
      if (_modalMode === 'extend') {{
        const activeId = getActiveKbId();
        if (activeId) {{
          doExtend(file, activeId, parallel);
          return;
        }}
      }}
      const title = modalTitle.value.trim() || file.name.replace(/\\.[^.]+$/, '');
      const description = modalDescription.value.trim();
      doUpload(file, title, description, parallel);
    }});

    dropZone?.addEventListener('drop', (e) => {{
      e.preventDefault();
      dropZone.classList.remove('dragover');
      const files = e.dataTransfer?.files;
      if (files?.length) {{
        showCreateModal(files[0], 'document');
      }}
    }});
    fileInput?.addEventListener('change', () => {{
      if (fileInput.files?.length) {{
        showCreateModal(fileInput.files[0], 'document');
        fileInput.value = '';
      }}
    }});
    if (fileInputCreate) fileInputCreate.addEventListener('change', () => {{
      if (fileInputCreate.files?.length) {{
        showCreateModal(fileInputCreate.files[0], 'create');
      }}
      fileInputCreate.value = '';
    }});

    const jobs = [];

    function esc(s) {{ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }}

    function createJobCard(job) {{
      job.progress = job.progress || {{}};
      const isCreate = job.jobType === 'create';
      const typeClass = isCreate ? 'job-create' : 'job-extend';
      const typeLabel = isCreate ? 'New KB' : 'Expanding';
      const card = document.createElement('div');
      card.className = 'job-card job-clickable ' + typeClass;
      card.dataset.jobId = job.localId;
      card.innerHTML = '<div class="flex items-center justify-between gap-2">'
        + '<div class="flex items-center gap-2 min-w-0 flex-1">'
        + '<span class="job-type-badge text-xs font-medium px-1.5 py-0.5 rounded shrink-0">' + typeLabel + '</span>'
        + '<p class="text-sm font-medium truncate min-w-0" style="color:#e8e6e3;">' + esc(job.title) + '</p>'
        + '</div>'
        + '<button type="button" class="job-cancel shrink-0 w-5 h-5 rounded flex items-center justify-center" style="color:#8a8a94;">'
        + '<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>'
        + '</button></div>'
        + (job.description ? '<p class="text-xs mt-0.5 truncate" style="color:#6b6b76;">' + esc(job.description) + '</p>' : '')
        + '<div class="flex items-center gap-2 mt-1.5">'
        + '<span class="stage-dot"></span>'
        + '<span class="stage-label text-xs font-mono" style="color:#8a8a94;">Starting...</span>'
        + '</div>'
        + '<div class="job-metrics text-xs font-mono mt-1" style="color:#6b6b76; min-height:1em;"></div>';
      card.querySelector('.job-cancel').addEventListener('click', (e) => {{ e.stopPropagation(); cancelJob(job); }});
      card.addEventListener('click', (e) => {{ if (!e.target.closest('.job-cancel')) showJobDetailModal(job); }});
      return card;
    }}

    let _modalJob = null;

    function updateJobStage(job, ev) {{
      const step = ev.step;
      const d = ev.data || ev;
      if (!job.progress) job.progress = {{}};
      job.progress[step] = d;
      if (!job.liveMetrics) job.liveMetrics = {{ classes: 0, instances: 0, relations: 0, axioms: 0, data_properties: 0 }};
      if (step === 'extract') {{
        job.chunksCompleted = (job.chunksCompleted || 0) + 1;
        job.liveMetrics.classes += d.classes ?? 0;
        job.liveMetrics.instances += d.instances ?? 0;
        job.liveMetrics.relations += d.relations ?? 0;
        job.liveMetrics.axioms += d.axioms ?? 0;
      }} else if (step === 'chunk_done') {{
        job.chunksTotal = d.total_chunks ?? 0;
      }} else if (step === 'merge_done') {{
        job.liveMetrics.classes = d.classes ?? 0;
        job.liveMetrics.instances = d.instances ?? 0;
        job.liveMetrics.relations = d.relations ?? 0;
        job.liveMetrics.axioms = d.axioms ?? 0;
      }} else if (step === 'inference_done' && d.inferred) {{
        job.liveMetrics.relations = (job.liveMetrics.relations || 0) + (d.inferred || 0);
      }} else if (step === 'reasoning_done' && d.inferred_edges) {{
        job.liveMetrics.relations = (job.liveMetrics.relations || 0) + (d.inferred_edges || 0);
      }}
      const label = job.card?.querySelector('.stage-label');
      if (label) {{
        const chunksDone = step === 'extract' ? (job.chunksCompleted || 0) : (job.chunksCompleted || 0);
        const chunksTotal = job.chunksTotal ?? d.total ?? 0;
        const stageMap = {{
          'load': 'Loading...', 'load_done': 'Loaded',
          'chunk': 'Chunking...', 'chunk_done': (d.total_chunks || 0) + ' chunks',
          'extract': chunksTotal > 0 ? chunksDone + ' of ' + chunksTotal + ' chunks' : 'Extracting...',
          'merge_done': 'Merged',
          'taxonomy': 'Building taxonomy...', 'taxonomy_done': 'Taxonomy built', 'taxonomy_skip': 'Skipped taxonomy',
          'inference': 'Inferring...', 'inference_done': 'Inferred',
          'inference_skip': 'Skipped inference',
          'reasoning': 'Reasoning...', 'reasoning_done': 'Reasoned',
          'reasoning_skip': 'Skipped reasoning',
        }};
        label.textContent = stageMap[step] || step;
      }}
      const metricsEl = job.card?.querySelector('.job-metrics');
      if (metricsEl) {{
        if (step === 'load_done' && d.chars) {{
          metricsEl.textContent = (d.chars || 0).toLocaleString() + ' chars';
        }} else if (step === 'chunk_done' && d.total_chunks) {{
          metricsEl.textContent = (d.total_chunks || 0) + ' chunks';
        }} else if (step === 'extract' && (job.chunksCompleted || 0) > 0 && (job.chunksTotal || 0) > 0) {{
          metricsEl.textContent = (job.chunksCompleted || 0) + ' of ' + (job.chunksTotal || 0) + ' chunks';
        }} else if (step === 'merge_done') {{
          const cls = d.classes ?? 0, inst = d.instances ?? 0, rel = d.relations ?? 0;
          metricsEl.textContent = cls + ' cls, ' + inst + ' inst, ' + rel + ' rel';
        }} else if (step === 'inference_done' && d.inferred) {{
          metricsEl.textContent = '+ ' + (d.inferred || 0) + ' inferred relations';
        }} else if (step === 'reasoning_done') {{
          const inf = d.inferred_edges ?? 0, iter = d.iterations ?? 0;
          if (inf > 0) metricsEl.textContent = inf + ' relations in ' + iter + ' reasoning iterations';
        }}
      }}
      if (_modalJob && _modalJob.localId === job.localId) {{
        showJobDetailModal(job);
      }}
    }}

    function showJobDetailModal(job) {{
      _modalJob = job;
      jobDetailTitle.textContent = job.title || 'Job Details';
      const report = job.pipeline_report || {{}};
      const progress = job.progress || {{}};
      const live = job.liveMetrics || {{}};
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

      const cls = totals.classes ?? ext.classes ?? live.classes ?? 0;
      const inst = totals.instances ?? ext.instances ?? live.instances ?? 0;
      const rel = totals.relations ?? ext.relations ?? live.relations ?? 0;
      const ax = totals.axioms ?? ext.axioms ?? live.axioms ?? 0;
      const dp = totals.data_properties ?? live.data_properties ?? 0;

      const hasLoad = !!progress.load_done;
      const hasChunk = !!progress.chunk_done;
      const chunksDone = job.chunksCompleted ?? 0;
      const chunksTotal = job.chunksTotal ?? progress.chunk_done?.total_chunks ?? totalChunks;
      const hasExtract = !!progress.merge_done || chunksDone > 0;
      const hasMerge = !!progress.merge_done;
      const hasInference = !!progress.inference_done || !!progress.inference_skip;
      const hasReasoning = !!progress.reasoning_done || !!progress.reasoning_skip;
      const isLoad = !!progress.load && !hasLoad;
      const isChunk = !!progress.chunk && !hasChunk;
      const isExtract = (!!progress.extract || !!progress.taxonomy) && !hasMerge;
      const extractCur = chunksDone;
      const extractTot = chunksTotal;
      const isInference = !!progress.inference && !hasInference;
      const isReasoning = !!progress.reasoning && !hasReasoning;

      let html = '<div class="space-y-4">';

      html += '<div class="rounded-lg p-3" style="background:#14141a; border:1px solid #1a1a24;">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:#8a8a94;">Status</p>';
      html += '<p class="font-mono text-sm"><span class="stat-value">' + (job.status || 'running') + '</span></p>';
      if (ontologyName !== '—') html += '<p class="text-xs mt-1" style="color:#8a8a94;">Ontology: ' + esc(ontologyName) + '</p>';
      html += '</div>';

      const docPath = report.document_path || job.description || '';
      html += '<div class="rounded-lg p-3" style="background:#14141a; border:1px solid #1a1a24;">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:#8a8a94;">Document &amp; Chunking</p>';
      html += '<ul class="space-y-1 text-xs font-mono" style="color:#e8e6e3;">';
      if (docPath) html += '<li>Document: <span class="stat-value">' + esc(docPath) + '</span></li>';
      html += '<li>Document size: <span class="stat-value">' + (docChars ? docChars.toLocaleString() + ' chars' : '—') + '</span></li>';
      html += '<li>Total chunks: <span class="stat-value">' + totalChunks + '</span></li>';
      html += '<li>Extraction mode: <span class="stat-value">' + mode + '</span></li>';
      if (elapsed > 0) html += '<li>Elapsed: <span class="stat-value">' + elapsed.toFixed(1) + 's</span></li>';
      html += '</ul></div>';

      html += '<div class="rounded-lg p-3" style="background:#14141a; border:1px solid #1a1a24;">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:#8a8a94;">Entities &amp; Relations</p>';
      html += '<div class="grid grid-cols-2 gap-2 text-xs font-mono">';
      html += '<div><span style="color:#8a8a94;">Classes:</span> <span class="stat-value">' + cls + '</span></div>';
      html += '<div><span style="color:#8a8a94;">Instances:</span> <span class="stat-value">' + inst + '</span></div>';
      html += '<div><span style="color:#8a8a94;">Relations:</span> <span class="stat-value">' + rel + '</span></div>';
      html += '<div><span style="color:#8a8a94;">Axioms:</span> <span class="stat-value">' + ax + '</span></div>';
      html += '<div><span style="color:#8a8a94;">Data properties:</span> <span class="stat-value">' + dp + '</span></div>';
      html += '</div></div>';

      html += '<div class="rounded-lg p-3" style="background:#14141a; border:1px solid #1a1a24;">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:#8a8a94;">Pipeline Breakdown</p>';
      html += '<ol class="space-y-2 text-xs" style="list-style:none; padding-left:0;">';
      const stepStatus = (done, running) => done ? '<span style="color:#22c55e;">✓</span>' : (running ? '<span style="color:#ec4899;">●</span>' : '<span style="color:#555;">○</span>');
      html += '<li class="flex items-start gap-2">' + stepStatus(hasLoad, isLoad) + '<span><strong>1. Load</strong>: ' + (hasLoad ? docChars.toLocaleString() + ' chars loaded' : (isLoad ? 'Loading document...' : 'Pending')) + '</span></li>';
      html += '<li class="flex items-start gap-2">' + stepStatus(hasChunk, isChunk) + '<span><strong>2. Chunk</strong>: ' + (hasChunk ? totalChunks + ' chunks created' : (isChunk ? 'Chunking text...' : 'Pending')) + '</span></li>';
      const extractDetail = hasMerge ? (chunkStats.length ? chunkStats.filter(c => ((c.classes ?? 0) + (c.instances ?? 0) + (c.relations ?? 0) + (c.axioms ?? 0)) > 0).length + ' of ' + totalChunks + ' chunks enhanced' : 'Extracted') : (extractCur ? 'Chunk ' + extractCur + '/' + extractTot : (progress.taxonomy ? 'Building taxonomy...' : 'Pending'));
      html += '<li class="flex items-start gap-2">' + stepStatus(hasExtract, isExtract) + '<span><strong>3. Extract</strong>: ' + extractDetail + '</span></li>';
      const mergeDetail = hasMerge ? (ext.classes ?? cls) + ' cls, ' + (ext.instances ?? inst) + ' inst, ' + (ext.relations ?? rel) + ' rel merged' : 'Pending';
      html += '<li class="flex items-start gap-2">' + stepStatus(hasMerge, false) + '<span><strong>4. Merge</strong>: ' + mergeDetail + '</span></li>';
      const infDetail = hasInference ? (progress.inference_skip ? 'Skipped' : (llmInferred > 0 ? llmInferred + ' relations inferred' : 'No new relations')) : (progress.inference ? 'Inferring relations...' : 'Pending');
      html += '<li class="flex items-start gap-2">' + stepStatus(hasInference, isInference) + '<span><strong>5. LLM inference</strong>: ' + infDetail + '</span></li>';
      const reasonDetail = hasReasoning ? (progress.reasoning_skip ? 'Skipped' : (infEdges > 0 ? infEdges + ' relations in ' + iter + ' iterations' : 'Complete')) : (progress.reasoning ? 'Running OWL 2 RL...' : 'Pending');
      html += '<li class="flex items-start gap-2">' + stepStatus(hasReasoning, isReasoning) + '<span><strong>6. OWL reasoning</strong>: ' + reasonDetail + '</span></li>';
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

      const violations = reasoning.consistency_violations || [];
      if (violations.length > 0) {{
        html += '<div class="rounded-lg p-3" style="background:#1a1414; border:1px solid #3a2424;">';
        html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:#ef4444;">Consistency Violations</p>';
        html += '<ul class="text-xs font-mono space-y-1" style="color:#e8e6e3;">';
        violations.forEach(v => {{ html += '<li>' + esc(String(v)) + '</li>'; }});
        html += '</ul></div>';
      }}

      html += '</div>';
      jobDetailContent.innerHTML = html;
      jobDetailModal.classList.remove('hidden');
    }}

    function hideJobDetailModal() {{
      _modalJob = null;
      jobDetailModal.classList.add('hidden');
    }}

    document.getElementById('job-detail-close')?.addEventListener('click', hideJobDetailModal);
    jobDetailModal?.querySelector('.modal-backdrop')?.addEventListener('click', hideJobDetailModal);

    function setJobStatus(job, status, label) {{
      job.status = status;
      if (!job.card) return;
      const typeClass = job.jobType === 'create' ? 'job-create' : 'job-extend';
      job.card.className = 'job-card job-clickable ' + typeClass + ' ' + status;
      const sl = job.card.querySelector('.stage-label');
      if (sl) sl.textContent = label;
      const cancelBtn = job.card.querySelector('.job-cancel');
      if (cancelBtn && (status === 'done' || status === 'error' || status === 'cancelled')) {{
        cancelBtn.style.display = 'none';
      }}
      if (_kbData && _kbData.length) renderKbList(_kbData, _activeKbId);
      if (status === 'done' && job.pipeline_report) {{
        const report = job.pipeline_report;
        const totals = report.totals || report.extraction_totals || {{}};
        const cls = totals.classes ?? 0, inst = totals.instances ?? 0, rel = totals.relations ?? 0;
        const elapsed = report.elapsed_seconds ?? 0;
        const metricsEl = job.card.querySelector('.job-metrics');
        if (metricsEl) {{
          let txt = cls + ' cls, ' + inst + ' inst, ' + rel + ' rel';
          if (elapsed > 0) txt += ' · ' + elapsed.toFixed(1) + 's';
          metricsEl.textContent = txt;
        }}
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
          if (_kbData && _kbData.length) renderKbList(_kbData, _activeKbId);
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
        jobType: 'create',
      }};
      jobs.push(job);
      job.card = createJobCard(job);
      if (jobQueue) jobQueue.appendChild(job.card);
      if (jobQueueSection) jobQueueSection.classList.remove('collapsed');
      setStatusBadge('processing');
      tabDocuments?.click();

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
          job.kbId = result.kb_id;
          setJobStatus(job, 'done', 'Complete');
          await loadKBs();
          if (result.kb_id) setActiveKbId(result.kb_id);
          if (result.pipeline_report && result.kb_id) appendOntologySummary(result.pipeline_report, result.kb_id);
          removeJobCard(job, 3000);
          if (kbStatus) {{ kbStatus.style.display = 'none'; }}
        }}
      }} catch (e) {{
        if (e.name === 'AbortError') {{
          setJobStatus(job, 'cancelled', 'Cancelled');
        }} else {{
          setJobStatus(job, 'error', e.message);
          if (kbStatus) {{ kbStatus.textContent = 'Job failed: ' + e.message; kbStatus.style.display = ''; kbStatus.style.color = '#ef4444'; }}
        }}
        removeJobCard(job, 4000);
      }} finally {{
        const hasRunning = jobs.some(j => j.status === 'running');
        if (!hasRunning) setStatusBadge(getActiveKbId() ? 'ready' : 'empty');
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
        kbId: kbId,
        jobType: 'extend',
      }};
      jobs.push(job);
      job.card = createJobCard(job);
      if (jobQueue) jobQueue.appendChild(job.card);
      if (jobQueueSection) jobQueueSection.classList.remove('collapsed');
      setStatusBadge('processing');
      tabDocuments?.click();
      if (_kbData && _kbData.length) renderKbList(_kbData, _activeKbId);
      if (activeKb) renderOntologyCard(activeKb);

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
          if (result.kb_id) setActiveKbId(result.kb_id);
          if (result.pipeline_report && result.kb_id) appendOntologySummary(result.pipeline_report, result.kb_id);
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
        if (!hasRunning) setStatusBadge(getActiveKbId() ? 'ready' : 'empty');
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

    function showNewChatModal() {{
      const modal = document.getElementById('new-chat-modal');
      const listEl = document.getElementById('new-chat-kb-list');
      if (!listEl) return;
      listEl.innerHTML = '';
      if (_kbData.length === 0) {{
        listEl.innerHTML = '<p class="text-sm py-4 text-center" style="color:#8a8a94;">No knowledge bases. Create one first.</p>';
      }} else {{
        for (const kb of _kbData) {{
          const stats = kb.stats || {{}};
          const relCount = stats.relations ?? stats.edges ?? 0;
          const parts = [];
          if (stats.classes) parts.push(fmtNum(stats.classes) + ' cls');
          if (stats.instances) parts.push(fmtNum(stats.instances) + ' inst');
          if (relCount) parts.push(fmtNum(relCount) + ' rel');
          const summary = parts.length ? parts.join(' · ') : '—';
          const isActive = kb.id === getActiveKbId();
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'w-full text-left px-4 py-3 rounded-lg transition-all flex items-center justify-between gap-2';
          btn.style.cssText = 'background:#14141a; border:1px solid #2a2a3a; color:#e8e6e3;';
          btn.innerHTML = '<div class="min-w-0"><p class="font-medium truncate text-sm">' + esc(kb.name || kb.id) + '</p><p class="text-xs mt-0.5 truncate" style="color:#8a8a94;">' + esc(summary) + '</p></div>'
            + (isActive ? '<span class="text-xs shrink-0 px-1.5 py-0.5 rounded" style="background:rgba(236,72,153,0.2);color:#ec4899;">Active</span>' : '');
          btn.addEventListener('click', () => {{
            createNewChat(kb.id);
            modal.classList.add('hidden');
          }});
          listEl.appendChild(btn);
        }}
      }}
      modal.classList.remove('hidden');
    }}

    document.getElementById('new-chat-btn')?.addEventListener('click', () => {{
      showNewChatModal();
    }});
    document.getElementById('new-chat-modal-cancel')?.addEventListener('click', () => {{
      document.getElementById('new-chat-modal').classList.add('hidden');
    }});
    document.getElementById('new-chat-modal')?.querySelector('.modal-backdrop')?.addEventListener('click', () => {{
      document.getElementById('new-chat-modal').classList.add('hidden');
    }});
    sidebarToggle?.addEventListener('click', () => sidebar.classList.toggle('open'));
    document.getElementById('sidebar-overlay')?.addEventListener('click', () => sidebar.classList.remove('open'));

    if (window.matchMedia('(min-width: 769px)').matches) {{
      sidebar.classList.add('open');
    }}

    // Ensure graph viewer links use current origin (fixes about:blank when opened in new tab)
    const viewerUrl = window.location.origin + API + '/graph/viewer';
    document.querySelectorAll('a.graph-viewer-link').forEach(function(a) {{ a.href = viewerUrl; }});

    (async function init() {{
      try {{
        await loadKBs();
        const params = new URLSearchParams(window.location.search);
        const urlKbId = params.get('kb_id');
        if (urlKbId && _kbData.some(k => k.id === urlKbId) && urlKbId !== getActiveKbId()) {{
          try {{ await activateKB(urlKbId); }} catch (_) {{}}
          history.replaceState(null, '', window.location.pathname);
        }}
      }} catch (e) {{
        console.error('[init]', e);
        if (statusBadge) {{ statusBadge.textContent = 'Error loading'; statusBadge.className = 'status-badge px-2 py-0.5 rounded-full text-xs font-medium empty'; }}
      }}
    }})();
    document.addEventListener('visibilitychange', () => {{ if (document.visibilityState === 'visible') loadKBs(); }});
  </script>
</body>
</html>"""
