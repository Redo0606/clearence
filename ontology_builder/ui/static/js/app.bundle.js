// === CONFIG ===
    const API = window.APP_CONFIG?.apiBase ?? '/api/v1';
    let _kbData = [];

    function logClick(action, detail) {
      try { console.log('[UI]', action, detail !== undefined ? detail : ''); } catch (_) {}
    }

    function parseError(data) {
      if (typeof data?.detail === 'string') return data.detail;
      if (Array.isArray(data?.detail)) return data.detail.map(d => d.msg || JSON.stringify(d)).join('; ');
      return data?.detail ? String(data.detail) : 'Request failed';
    }

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

    function getActiveKbId() { return _activeKbId && _activeKbId !== '__upload__' ? _activeKbId : null; }
    function setActiveKbId(id) { _activeKbId = id; }
    function getActiveChat() { return _chats.find(c => c.id === _activeChatId); }
    function getChatById(id) { return _chats.find(c => c.id === id); }
    function getKbStatus(kbId) {
      const running = jobs.some(j => j.status === 'running' && j.kbId === kbId);
      return running ? 'building' : 'ready';
    }

    function createNewChat(kbId) {
      const idToUse = kbId || getActiveKbId();
      const kb = _kbData.find(k => k.id === idToUse);
      const kbName = kb ? (kb.name || kb.id) : 'No KB';
      const id = 'chat-' + (++_chatIdSeq);
      const chat = { id, kbId: idToUse, kbName, messages: [] };
      _chats.push(chat);
      _activeChatId = id;
      if (idToUse) setActiveKbId(idToUse);
      renderChatTabs();
      switchToChat(id);
      return chat;
    }

    async function switchToChat(id) {
      _activeChatId = id;
      const chat = getActiveChat();
      renderChatTabs();
      renderChatMessages(chat);
      updateEmptyStatesForChat(chat);
      if (chat?.kbId) {
        setActiveKbId(chat.kbId);
        try {
          const res = await fetch(API + '/knowledge-bases/' + chat.kbId + '/activate', { method: 'POST' });
          if (res.ok) addRecentKB(chat.kbId);
        } catch (_) {}
        setStickySummaryVisible(true);
        const kb = _kbData.find(k => k.id === chat.kbId);
        if (kb) {
          currentOntologyPill.classList.remove('hidden');
          currentOntologyPill.classList.add('flex');
          currentOntologyName.textContent = kb.name || kb.id;
          const stats = kb.stats || {};
          const relCount = stats.relations ?? stats.edges ?? 0;
          const parts = [];
          if (stats.classes) parts.push(fmtNum(stats.classes) + ' cls');
          if (relCount) parts.push(fmtNum(relCount) + ' rel');
          currentOntologyStats.textContent = parts.join(' · ');
          const viewerUrl = window.location.origin + API + '/graph/viewer?kb_id=' + encodeURIComponent(chat.kbId);
          document.querySelectorAll('a.graph-viewer-link').forEach(a => { a.href = viewerUrl; });
          document.getElementById('chat-onto-sticky-name').textContent = kb.name || kb.id;
          const stickyDesc = document.getElementById('chat-onto-sticky-desc');
          if (kb.description) { stickyDesc.textContent = kb.description; stickyDesc.style.display = ''; } else { stickyDesc.style.display = 'none'; }
          const stickyStats = document.getElementById('chat-onto-sticky-stats');
          stickyStats.innerHTML = '';
          [['Classes', stats.classes], ['Instances', stats.instances], ['Relations', relCount]].forEach(([l,v]) => {
            const chip = document.createElement('div');
            chip.className = 'text-xs font-mono';
            chip.style.color = 'var(--text-muted)';
            chip.textContent = l + ': ' + fmtNum(v ?? 0);
            stickyStats.appendChild(chip);
          });
        }
      } else {
        currentOntologyPill.classList.add('hidden');
        currentOntologyPill.classList.remove('flex');
      }
    }

    function renderChatTabs() {
      const container = document.getElementById('chat-tabs');
      if (!container) return;
      container.innerHTML = '';
      _chats.forEach(c => {
        const wrap = document.createElement('div');
        wrap.className = 'chat-tab-wrap flex items-center shrink-0';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'chat-tab shrink-0 flex items-center' + (c.id === _activeChatId ? ' active' : '');
        btn.innerHTML = '<span class="truncate max-w-[100px]">' + esc((c.kbName || 'Chat').substring(0, 20)) + (c.messages.length ? ' (' + c.messages.length + ')' : '') + '</span>';
        btn.title = c.kbName + (c.messages.length ? ' · ' + c.messages.length + ' messages' : '');
        btn.addEventListener('click', () => { logClick('chat-tab', c.id); switchToChat(c.id); });
        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'chat-tab-delete shrink-0';
        delBtn.style.color = 'var(--text-muted)';
        delBtn.title = 'Delete chat';
        delBtn.innerHTML = '<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>';
        delBtn.addEventListener('click', (e) => { e.stopPropagation(); logClick('chat-delete', c.id); deleteChat(c.id); });
        wrap.appendChild(btn);
        wrap.appendChild(delBtn);
        container.appendChild(wrap);
      });
    }

    function deleteChat(chatId) {
      const idx = _chats.findIndex(c => c.id === chatId);
      if (idx < 0) return;
      _chats.splice(idx, 1);
      if (_activeChatId === chatId) {
        _activeChatId = _chats.length ? _chats[0].id : null;
        if (_chats.length) {
          switchToChat(_chats[0].id);
        } else {
          renderChatTabs();
          messagesEl.querySelectorAll('[data-chat-message]').forEach(el => el.remove());
          const hasKb = !!getActiveKbId();
          updateEmptyStatesForChat(hasKb ? { kbId: getActiveKbId(), messages: [] } : { kbId: null, messages: [] });
          setInputsEnabled(hasKb);
          setStickySummaryVisible(hasKb);
          if (hasKb) {
            currentOntologyPill?.classList.remove('hidden');
            currentOntologyPill?.classList.add('flex');
            const kb = _kbData.find(k => k.id === getActiveKbId());
            if (kb) {
              currentOntologyName.textContent = kb.name || kb.id;
              const stats = kb.stats || {};
              const relCount = stats.relations ?? stats.edges ?? 0;
              currentOntologyStats.textContent = [stats.classes, relCount].filter(Boolean).map(v => fmtNum(v)).join(' · ') || '';
            }
          } else {
            currentOntologyPill?.classList.add('hidden');
            currentOntologyPill?.classList.remove('flex');
          }
        }
      } else {
        renderChatTabs();
      }
    }

    function updateEmptyStatesForChat(chat) {
      const hasKb = chat && chat.kbId;
      const hasMsgs = chat && chat.messages.length > 0;
      emptyStateNoKb.classList.toggle('hidden', hasKb || _chats.length > 0);
      emptyStateNoKb.classList.toggle('flex', !hasKb && _chats.length === 0);
      emptyStateReady.classList.toggle('hidden', !hasKb || hasMsgs);
      emptyStateReady.classList.toggle('flex', hasKb && !hasMsgs);
      setInputsEnabled(!!hasKb);
      setStatusBadge(hasKb ? 'ready' : 'empty');
      setStickySummaryVisible(!!hasKb);
      if (hasKb && chat) {
        const kb = _kbData.find(k => k.id === chat.kbId);
        if (kb) {
          document.getElementById('chat-onto-name').textContent = kb.name || kb.id;
          const descEl = document.getElementById('chat-onto-desc');
          if (kb.description) { descEl.textContent = kb.description; descEl.style.display = ''; } else { descEl.style.display = 'none'; }
          const grid = document.getElementById('chat-onto-stats');
          grid.innerHTML = '';
          const stats = kb.stats || {};
          const relCount = stats.relations ?? stats.edges ?? 0;
          [['Classes', stats.classes], ['Instances', stats.instances], ['Relations', relCount]].forEach(([l,v]) => {
            const chip = document.createElement('div');
            chip.className = 'rounded-lg px-3 py-2.5 text-center';
            chip.innerHTML = '<p class="stat-value text-base font-semibold">' + fmtNum(v ?? 0) + '</p><p class="text-xs mt-0.5 stat-label">' + l + '</p>';
            grid.appendChild(chip);
          });
          const chatDocsEl = document.getElementById('chat-onto-docs');
          const chatDocsList = document.getElementById('chat-onto-docs-list');
          const docs = kb.documents || [];
          if (docs.length) {
            chatDocsEl.classList.remove('hidden');
            chatDocsList.innerHTML = '';
            docs.forEach(d => {
              const pill = document.createElement('span');
              pill.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium';
              pill.style.cssText = 'background: var(--accent-12); color: var(--text-primary); border: 1px solid var(--accent-3);';
              pill.innerHTML = '<svg class="w-3.5 h-3.5 shrink-0" style="color:var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>'
                + '<span class="truncate max-w-[180px]">' + esc(d) + '</span>';
              chatDocsList.appendChild(pill);
            });
          } else {
            chatDocsEl.classList.add('hidden');
          }
        }
      }
    }

    function setStatusBadge(status) {
      statusBadge.className = 'status-badge px-2 py-0.5 rounded-full text-xs font-medium ' + status;
      const labels = { ready: 'Active', empty: 'Empty', processing: 'Building' };
      statusBadge.textContent = labels[status] || status;
    }

    function setInputsEnabled(enabled) {
      questionInput.disabled = !enabled;
      sendBtn.disabled = !enabled;
    }

    function setStickySummaryVisible(visible) {
      chatOntoSticky.classList.toggle('hidden', !visible);
    }

    function formatDate(ts) {
      if (!ts) return '';
      const d = new Date(ts * 1000);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    }

    function fmtNum(n) {
      if (n === undefined || n === null) return '0';
      return Number(n).toLocaleString();
    }

    function renderOntologyCard(kb) {
      if (!kb) {
        ontoInfoPanel.classList.add('hidden');
        currentOntologyPill.classList.add('hidden');
        currentOntologyPill.classList.remove('flex');
        const downloadLink = document.getElementById('download-ontology-link');
        if (downloadLink) downloadLink.style.display = 'none';
        const readyEl = document.getElementById('onto-card-ready');
        if (readyEl) { readyEl.classList.add('hidden'); readyEl.classList.remove('flex'); }
        return;
      }
      const stats = kb.stats || {};
      const name = kb.name || kb.id;
      const desc = kb.description || '';
      const relCount = stats.relations ?? stats.edges ?? 0;

      // Sidebar card
      document.getElementById('onto-card-name').textContent = name;
      const readyEl = document.getElementById('onto-card-ready');
      if (readyEl) {
        readyEl.classList.remove('hidden');
        readyEl.classList.add('flex');
        const building = getKbStatus(kb.id) === 'building';
        readyEl.innerHTML = building
          ? '<span class="kb-building-dot"></span>Building'
          : '<span class="kb-ready-dot"></span>Ready';
        readyEl.style.color = building ? 'var(--warning)' : 'var(--success)';
        readyEl.style.background = building ? 'var(--warning-15)' : 'var(--success-15)';
      }
      const summaryParts = [];
      if (stats.classes) summaryParts.push(fmtNum(stats.classes) + ' cls');
      if (stats.instances) summaryParts.push(fmtNum(stats.instances) + ' inst');
      if (relCount) summaryParts.push(fmtNum(relCount) + ' rel');
      document.getElementById('onto-card-summary').textContent = summaryParts.length ? summaryParts.join(' · ') : '';
      const descEl = document.getElementById('onto-card-desc');
      if (desc) {
        descEl.textContent = desc;
        descEl.style.display = '';
      } else {
        descEl.style.display = 'none';
      }

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
      show.forEach(([label, val]) => {
        const chip = document.createElement('div');
        chip.className = 'onto-stat-chip text-center';
        chip.innerHTML = '<p class="stat-value text-sm font-semibold">' + fmtNum(val) + '</p>'
          + '<p class="text-xs mt-0.5" style="color:#555;">' + label + '</p>';
        grid.appendChild(chip);
      });

      // Date
      document.getElementById('onto-card-date').textContent = kb.created_at ? formatDate(kb.created_at) : '';

      // Download & View graph links (use active kb_id)
      const downloadLink = document.getElementById('download-ontology-link');
      if (downloadLink) {
        downloadLink.href = API + '/ontology/export?format=owl&kb_id=' + encodeURIComponent(kb.id);
        downloadLink.style.display = '';
      }
      const viewerLinks = document.querySelectorAll('a.graph-viewer-link');
      const viewerUrl = window.location.origin + API + '/graph/viewer?kb_id=' + encodeURIComponent(kb.id);
      viewerLinks.forEach(a => { a.href = viewerUrl; });

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
      if (desc) {
        chatDescEl.textContent = desc;
        chatDescEl.style.display = '';
      } else {
        chatDescEl.style.display = 'none';
      }

      const chatStatsGrid = document.getElementById('chat-onto-stats');
      chatStatsGrid.innerHTML = '';
      const chatStatDefs = [
        ['Classes', stats.classes ?? 0],
        ['Instances', stats.instances ?? 0],
        ['Relations', relCount],
        ['Axioms', stats.axioms ?? 0],
        ['Data Properties', stats.data_properties ?? 0],
      ];
      chatStatDefs.forEach(([label, val]) => {
        const chip = document.createElement('div');
        chip.className = 'rounded-lg px-3 py-2.5 text-center';
        chip.style.cssText = 'background:var(--bg-input); border:1px solid var(--border);';
        chip.innerHTML = '<p class="stat-value text-base font-semibold">' + fmtNum(val) + '</p>'
          + '<p class="text-xs mt-0.5 stat-label">' + label + '</p>';
        chatStatsGrid.appendChild(chip);
      });

      // Documents list
      const chatDocsEl = document.getElementById('chat-onto-docs');
      const chatDocsList = document.getElementById('chat-onto-docs-list');
      const docs = kb.documents || [];
      if (docs.length) {
        chatDocsEl.classList.remove('hidden');
        chatDocsList.innerHTML = '';
        docs.forEach(d => {
          const pill = document.createElement('span');
          pill.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium';
          pill.style.cssText = 'background: var(--accent-12); color: var(--text-primary); border: 1px solid var(--accent-3);';
          pill.innerHTML = '<svg class="w-3.5 h-3.5 shrink-0" style="color:var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>'
            + '<span class="truncate max-w-[180px]">' + esc(d) + '</span>';
          chatDocsList.appendChild(pill);
        });
      } else {
        chatDocsEl.classList.add('hidden');
      }

      // Sticky chat summary
      document.getElementById('chat-onto-sticky-name').textContent = name;
      const stickyDescEl = document.getElementById('chat-onto-sticky-desc');
      if (desc) {
        stickyDescEl.textContent = desc;
        stickyDescEl.style.display = '';
      } else {
        stickyDescEl.style.display = 'none';
      }
      const stickyStats = document.getElementById('chat-onto-sticky-stats');
      stickyStats.innerHTML = '';
      const stickyStatDefs = [
        ['C', stats.classes ?? 0],
        ['I', stats.instances ?? 0],
        ['R', relCount],
      ];
      stickyStatDefs.forEach(([label, val]) => {
        const chip = document.createElement('span');
        chip.className = 'text-xs font-mono px-2 py-1 rounded-md';
        chip.style.cssText = 'background:var(--bg-input); border:1px solid var(--border); color:var(--text-muted);';
        chip.textContent = label + ': ' + fmtNum(val);
        stickyStats.appendChild(chip);
      });
    }

    function showEmptyState(hasKb) {
      if (_hasMessages) {
        emptyStateNoKb.classList.add('hidden');
        emptyStateReady.classList.add('hidden');
        setStickySummaryVisible(hasKb);
        return;
      }
      setStickySummaryVisible(false);
      if (hasKb) {
        emptyStateNoKb.classList.add('hidden');
        emptyStateReady.classList.remove('hidden');
        emptyStateReady.classList.add('flex');
      } else {
        emptyStateNoKb.classList.remove('hidden');
        emptyStateReady.classList.add('hidden');
        emptyStateReady.classList.remove('flex');
      }
    }

    async function fetchKBs() {
      const res = await fetch(API + '/knowledge-bases', { cache: 'no-store' });
      if (!res.ok) {
        const errText = await res.text();
        let msg = res.status + ' ' + res.statusText;
        try {
          const errJson = JSON.parse(errText);
          if (errJson.detail) msg = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
        } catch (_) {}
        throw new Error(msg);
      }
      const data = await res.json();
      return data && typeof data === 'object' ? data : { items: [], active_id: null };
    }

    function renderKbList(items, activeId) {
      if (!kbList) return;
      const countEl = document.getElementById('kb-count');
      if (countEl) countEl.textContent = '(' + items.length + ')';
      const emptyEl = document.getElementById('kb-list-empty');
      if (emptyEl) emptyEl.classList.toggle('hidden', items.length > 0);
      kbList.innerHTML = '';
      for (const kb of items) {
        const stats = kb.stats || {};
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
        card.style.background = isActive ? 'var(--accent-08)' : 'var(--bg-overlay)';
        card.style.borderColor = isActive ? 'var(--accent-6)' : 'var(--border)';
        card.dataset.kbId = kb.id;
        const viewerUrl = window.location.origin + API + '/graph/viewer?kb_id=' + encodeURIComponent(kb.id);
        const statusBadge = status === 'building'
          ? '<span class="flex items-center gap-1 text-xs font-medium shrink-0" style="color:var(--warning);"><span class="kb-building-dot"></span>Building</span>'
          : '<span class="kb-ready-badge flex items-center gap-1 text-xs font-medium shrink-0" style="color:var(--success);"><span class="kb-ready-dot"></span>Ready</span>';
        const activeLabel = isActive ? '<span class="text-xs font-medium shrink-0 px-1.5 py-0.5 rounded" style="background:var(--accent-25);color:var(--accent);">Active</span>' : '';
        const subtextParts = [summary];
        if (docSummary !== '—') subtextParts.push(docSummary);
        if (createdStr) subtextParts.push(createdStr);
        const subtext = subtextParts.join(' · ');
        card.innerHTML = '<div class="flex items-center gap-2 min-w-0 flex-wrap">'
          + '<div class="flex-1 min-w-0">'
          + '<p class="text-sm font-medium truncate" style="color:var(--text-primary);">' + esc(kb.name || kb.id) + '</p>'
          + '<p class="text-xs truncate mt-0.5" style="color:var(--text-muted);">' + esc(subtext) + '</p></div>'
          + statusBadge
          + activeLabel
          + '<div class="flex items-center gap-1 shrink-0" onclick="event.stopPropagation()">'
          + '<button type="button" class="kb-new-chat-btn text-xs font-medium px-2 py-1 rounded transition-colors" style="color:var(--text-muted); background:var(--border-subtle);">+ Chat</button>'
          + '<a href="' + viewerUrl + '" target="_blank" rel="noopener noreferrer" class="text-xs font-medium link-teal opacity-70 hover:opacity-100 px-1.5 py-1">Open</a>'
          + '<button type="button" class="kb-mgmt-delete kb-delete-btn p-1 rounded shrink-0" style="color:var(--text-muted);" title="Delete KB" data-kb-id="' + esc(kb.id) + '">'
          + '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>'
          + '</button></div>';
        card.querySelector('.kb-new-chat-btn').addEventListener('click', (e) => {
          e.stopPropagation();
          logClick('kb-new-chat', kb.id);
          createNewChat(kb.id);
        });
        card.addEventListener('click', async (e) => {
          if (e.target.closest('a') || e.target.closest('button')) return;
          logClick('kb-select', kb.id);
          const existing = _chats.find(c => c.kbId === kb.id);
          if (existing) {
            await switchToChat(existing.id);
          } else {
            createNewChat(kb.id);
            await switchToChat(_activeChatId);
          }
        });
        const delBtn = card.querySelector('.kb-delete-btn');
        if (delBtn) delBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          logClick('kb-delete-open', delBtn.dataset.kbId);
          const kid = delBtn.dataset.kbId;
          const k = _kbData.find(x => x.id === kid);
          _pendingDeleteId = kid;
          _pendingDeleteName = k ? (k.name || kid) : kid;
          document.getElementById('delete-modal-name').textContent = _pendingDeleteName;
          document.getElementById('delete-modal').classList.remove('hidden');
        });
        kbList.appendChild(card);
      }
    }

    async function loadKBs() {
      let data;
      try {
        data = await fetchKBs();
      } catch (e) {
        console.error('[loadKBs]', e);
        _kbData = [];
        renderKbList([], null);
        setStatusBadge('empty');
        if (statusBadge) { statusBadge.textContent = 'Error loading'; statusBadge.classList.add('empty'); }
        setInputsEnabled(false);
        renderOntologyCard(null);
        const emptyEl = document.getElementById('kb-list-empty');
        if (emptyEl) {
          emptyEl.classList.remove('hidden');
          emptyEl.innerHTML = '<p class="text-sm" style="color:var(--text-muted-2);">Could not load knowledge bases</p><p class="text-xs mt-1" style="color:#555;">' + esc(e.message || 'Check console') + '</p>';
        }
        document.getElementById('kb-list')?.replaceChildren?.();
        populateEvalKbSelector();
        return;
      }
      let items = data.items || [];
      const recentIds = getRecentKBIds().filter(id => items.some(k => k.id === id));
      items = [...items].sort((a, b) => {
        const ai = recentIds.indexOf(a.id);
        const bi = recentIds.indexOf(b.id);
        if (ai >= 0 && bi >= 0) return ai - bi;
        if (ai >= 0) return -1;
        if (bi >= 0) return 1;
        return 0;
      });
      _kbData = items;
      _activeKbId = data.active_id || null;
      renderKbList(items, _activeKbId);
      if (data.active_id) {
        addRecentKB(data.active_id);
        const activeKb = _kbData.find(k => k.id === data.active_id);
        setInputsEnabled(true);
        setStatusBadge('ready');
        renderOntologyCard(activeKb || { id: data.active_id, name: data.active_id });
        showEmptyState(true);
        if (_chats.length === 0) {
          createNewChat();
        }
      } else {
        setInputsEnabled(false);
        setStatusBadge('empty');
        renderOntologyCard(null);
        showEmptyState(false);
      }
      populateEvalKbSelector();
    }

    function populateEvalKbSelector() {
      const sel = document.getElementById('eval-kb-select');
      if (!sel) return;
      const items = _kbData || [];
      const activeId = getActiveKbId();
      sel.innerHTML = '<option value="">Select a KB</option>' + items.map(k => {
        const docs = k.documents || [];
        const label = k.name + (docs.length ? ' (' + docs.length + ')' : '');
        return '<option value="' + esc(k.id) + '"' + (k.id === activeId ? ' selected' : '') + '>' + esc(label) + '</option>';
      }).join('');
    }

    async function fetchEvalHealth(kbId) {
      if (!kbId) return;
      const statsEl = document.getElementById('eval-health-stats');
      const badgeEl = document.getElementById('eval-health-badge');
      const warningsEl = document.getElementById('eval-health-warnings');
      if (statsEl) statsEl.innerHTML = '<span style="color:var(--text-muted);">Loading…</span>';
      try {
        const res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/health');
        if (!res.ok) {
          if (statsEl) statsEl.innerHTML = '<span style="color:var(--error);">Failed to load health</span>';
          return;
        }
        const h = await res.json();
        const s = h.structural || {};
        const badge = h.badge || '—';
        const score = h.overall_score ?? '—';
        if (badgeEl) {
          badgeEl.textContent = badge + (typeof score === 'number' ? ' (' + score + ')' : '');
          badgeEl.style.background = badge === 'Healthy' ? 'var(--success-2)' : badge === 'Critical' ? 'var(--error-15)' : 'var(--warning-2)';
          badgeEl.style.color = badge === 'Healthy' ? 'var(--success)' : badge === 'Critical' ? 'var(--error)' : 'var(--warning)';
        }
        if (statsEl) {
          statsEl.innerHTML = 'Nodes: ' + (s.node_count ?? '—') + '<br>Edges: ' + (s.edge_count ?? '—') + '<br>Density: ' + (s.density ?? '—') + '<br>Components: ' + (s.connected_components ?? '—') + '<br>Orphans: ' + (s.orphan_nodes ?? '—') + '<br>Relation types: ' + (h.semantic?.unique_relation_types ?? '—') + '<br>Facts/node: ' + (h.retrieval?.facts_per_node ?? '—') + '<br>Hyperedge coverage: ' + (h.retrieval?.hyperedge_coverage ?? '—');
        }
        const orphans = s.orphan_nodes ?? 0;
        const comps = s.connected_components ?? 0;
        const warn = [];
        if (orphans > 0) warn.push(orphans + ' nodes are isolated.');
        if (comps > 1) warn.push('Graph has ' + comps + ' disconnected subgraphs.');
        if (warningsEl) {
          warningsEl.innerHTML = warn.length ? warn.join('<br>') : '';
          warningsEl.style.display = warn.length ? '' : 'none';
        }
      } catch (e) {
        console.error('[fetchEvalHealth]', e);
        if (statsEl) statsEl.innerHTML = '<span style="color:var(--error);">Error loading health</span>';
      }
    }

    async function fetchEvalRecords(kbId) {
      const listEl = document.getElementById('eval-records-list');
      if (!listEl) return;
      if (!kbId) {
        listEl.innerHTML = '<p class="text-xs">Select a KB to view evaluation history</p>';
        return;
      }
      listEl.innerHTML = '<p class="text-xs" style="color:var(--text-muted);">Loading records…</p>';
      try {
        const res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/evaluation-records');
        if (!res.ok) {
          listEl.innerHTML = '<p class="text-xs" style="color:var(--error);">Failed to load records</p>';
          return;
        }
        const records = await res.json();
        if (!records || !records.length) {
          listEl.innerHTML = '<p class="text-xs">No evaluation records yet</p>';
          return;
        }
        listEl.innerHTML = records.map((r, idx) => {
          const ts = r.timestamp ? new Date(r.timestamp).toLocaleString() : '—';
          const scores = r.scores || {};
          const metrics = ['context_recall', 'entity_recall', 'answer_correctness', 'faithfulness', 'answer_relevancy'];
          const vals = metrics.map(m => scores[m]).filter(v => v != null);
          const avg = vals.length ? (vals.reduce((a, b) => a + b, 0) / vals.length * 100).toFixed(0) : '—';
          const ac = scores.answer_correctness != null ? (scores.answer_correctness * 100).toFixed(0) : '—';
          const n = r.num_questions ?? 0;
          const id = 'eval-record-' + idx;
          const detailId = 'eval-record-detail-' + idx;
          const perQ = (scores.per_question || []);
          const detailRows = perQ.slice(0, 50).map(pq => {
            const q = (pq.question || '').substring(0, 60) + (pq.question && pq.question.length > 60 ? '…' : '');
            const cr = pq.context_recall != null ? (pq.context_recall * 100).toFixed(0) : '—';
            const er = pq.entity_recall != null ? (pq.entity_recall * 100).toFixed(0) : '—';
            const acq = pq.answer_correctness != null ? (pq.answer_correctness * 100).toFixed(0) : '—';
            return '<tr><td class="py-1 pr-2 text-left" style="max-width:180px; overflow:hidden; text-overflow:ellipsis;" title="' + esc(pq.question || '') + '">' + esc(q) + '</td><td class="py-1 px-1 text-right">' + cr + '%</td><td class="py-1 px-1 text-right">' + er + '%</td><td class="py-1 px-1 text-right">' + acq + '%</td></tr>';
          }).join('');
          const more = perQ.length > 50 ? '<p class="text-xs mt-1" style="color:var(--text-muted);">… and ' + (perQ.length - 50) + ' more</p>' : '';
          return '<div class="rounded-lg border overflow-hidden" style="border-color:var(--border); background:var(--bg-input);"><button type="button" class="eval-record-header w-full px-3 py-2 flex items-center justify-between text-left hover:opacity-90 transition-opacity" data-id="' + id + '" data-detail="' + detailId + '"><div class="flex flex-col items-start"><span class="text-xs font-medium" style="color:var(--text-primary);">' + esc(ts) + '</span><span class="text-xs mt-0.5" style="color:var(--text-muted);">' + n + ' questions · avg ' + avg + '% · AC ' + ac + '%</span></div><svg class="eval-record-chevron w-4 h-4 shrink-0 transition-transform" style="color:var(--text-muted);" data-id="' + id + '" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg></button><div id="' + detailId + '" class="eval-record-detail hidden px-3 pb-3 pt-1 border-t" style="border-color:var(--border);"><div class="text-xs space-y-1 mb-2" style="color:var(--text-muted);">context_recall: ' + (scores.context_recall != null ? (scores.context_recall * 100).toFixed(1) : '—') + '% · entity_recall: ' + (scores.entity_recall != null ? (scores.entity_recall * 100).toFixed(1) : '—') + '% · answer_correctness: ' + (scores.answer_correctness != null ? (scores.answer_correctness * 100).toFixed(1) : '—') + '% · faithfulness: ' + (scores.faithfulness != null ? (scores.faithfulness * 100).toFixed(1) : '—') + '% · answer_relevancy: ' + (scores.answer_relevancy != null ? (scores.answer_relevancy * 100).toFixed(1) : '—') + '%</div><div class="overflow-x-auto max-h-[200px] overflow-y-auto"><table class="w-full text-xs" style="color:#8a8a94;"><thead><tr><th class="text-left py-1 pr-2">Question</th><th class="text-right py-1 px-1">CR</th><th class="text-right py-1 px-1">ER</th><th class="text-right py-1 px-1">AC</th></tr></thead><tbody>' + detailRows + '</tbody></table></div>' + more + '</div></div>';
        }).join('');
        listEl.querySelectorAll('.eval-record-header').forEach(btn => {
          btn.addEventListener('click', () => {
            const detailId = btn.getAttribute('data-detail');
            const chevron = btn.querySelector('.eval-record-chevron');
            const detail = document.getElementById(detailId);
            if (detail?.classList.contains('hidden')) {
              detail.classList.remove('hidden');
              if (chevron) chevron.style.transform = 'rotate(180deg)';
            } else {
              detail?.classList.add('hidden');
              if (chevron) chevron.style.transform = '';
            }
          });
        });
      } catch (e) {
        console.error('[fetchEvalRecords]', e);
        listEl.innerHTML = '<p class="text-xs" style="color:var(--error);">Error loading records</p>';
      }
    }

    const RECENT_KB_KEY = 'clarence_recent_kb_ids';
    function addRecentKB(id) {
      try {
        let ids = JSON.parse(localStorage.getItem(RECENT_KB_KEY) || '[]');
        ids = [id].concat(ids.filter(x => x !== id)).slice(0, 20);
        localStorage.setItem(RECENT_KB_KEY, JSON.stringify(ids));
      } catch (_) {}
    }
    function getRecentKBIds() {
      try {
        return JSON.parse(localStorage.getItem(RECENT_KB_KEY) || '[]');
      } catch (_) { return []; }
    }

    async function activateKB(id) {
      ontoInfoPanel.classList.remove('hidden');
      if (ontoCardLoading) ontoCardLoading.classList.remove('hidden');
      try {
        const res = await fetch(API + '/knowledge-bases/' + id + '/activate', { method: 'POST' });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(parseError(err) || res.statusText);
        }
        addRecentKB(id);
        await loadKBs();
      } finally {
        if (ontoCardLoading) ontoCardLoading.classList.add('hidden');
      }
    }

    document.getElementById('kb-refresh-btn')?.addEventListener('click', () => { logClick('refresh', 'kb-list'); loadKBs(); });

    tabKnowledge?.addEventListener('click', () => {
      logClick('tab', 'knowledge');
      tabKnowledge.classList.add('sidebar-tab-active');
      tabKnowledge.classList.remove('sidebar-tab-inactive');
      tabDocuments?.classList.remove('sidebar-tab-active');
      tabDocuments?.classList.add('sidebar-tab-inactive');
      tabEvaluate?.classList.remove('sidebar-tab-active');
      tabEvaluate?.classList.add('sidebar-tab-inactive');
      tabKnowledgeContent?.classList.remove('hidden');
      tabDocumentsContent?.classList.add('hidden');
      tabEvaluateContent?.classList.add('hidden');
    });
    tabDocuments?.addEventListener('click', () => {
      logClick('tab', 'documents');
      tabDocuments?.classList.add('sidebar-tab-active');
      tabDocuments?.classList.remove('sidebar-tab-inactive');
      tabKnowledge?.classList.remove('sidebar-tab-active');
      tabKnowledge?.classList.add('sidebar-tab-inactive');
      tabEvaluate?.classList.remove('sidebar-tab-active');
      tabEvaluate?.classList.add('sidebar-tab-inactive');
      tabDocumentsContent?.classList.remove('hidden');
      tabKnowledgeContent?.classList.add('hidden');
      tabEvaluateContent?.classList.add('hidden');
    });
    tabEvaluate?.addEventListener('click', () => {
      logClick('tab', 'evaluate');
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
      if (sel?.value) { fetchEvalHealth(sel.value); fetchEvalRecords(sel.value); }
    });

    jobQueueToggle?.addEventListener('click', () => { logClick('job-queue', 'toggle'); jobQueueSection?.classList.toggle('collapsed'); });

    document.getElementById('eval-kb-select')?.addEventListener('change', (e) => {
      const kbId = e.target?.value;
      logClick('eval-kb-select', kbId || 'none');
      if (kbId) { fetchEvalHealth(kbId); fetchEvalRecords(kbId); }
      else {
        document.getElementById('eval-health-stats').innerHTML = 'Select a KB to view health';
        document.getElementById('eval-health-badge').textContent = '—';
        document.getElementById('eval-health-warnings').innerHTML = '';
        fetchEvalRecords('');
      }
    });
    document.getElementById('eval-refresh-btn')?.addEventListener('click', () => {
      logClick('eval-refresh');
      const kbId = document.getElementById('eval-kb-select')?.value;
      if (kbId) fetchEvalHealth(kbId);
    });
    document.getElementById('eval-repair-btn')?.addEventListener('click', () => { logClick('eval-repair'); runRepair(); });
    document.getElementById('eval-run-btn')?.addEventListener('click', () => { logClick('eval-run'); runEvaluation(); });

    async function runEvaluation() {
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
      function addLog(icon, msg) {
        const div = document.createElement('div');
        div.innerHTML = (icon || '▸') + ' ' + (msg || '');
        logEl.appendChild(div);
        logEl.scrollTop = logEl.scrollHeight;
      }
      try {
        const res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/evaluate?num_questions=' + numQuestions, { method: 'POST' });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(parseError(err) || res.statusText);
        }
        const reader = res.body?.getReader();
        const dec = new TextDecoder();
        if (reader) {
          let buf = '';
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += dec.decode(value, { stream: true });
            const lines = buf.split('\n');
            buf = lines.pop() || '';
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.type === 'step') {
                    stageLabel.textContent = data.message || 'Evaluating...';
                    addLog('✓', data.message);
                  } else if (data.type === 'progress') {
                    const pct = data.total ? (100 * data.current / data.total) : 0;
                    progressBar.style.width = pct + '%';
                    addLog('▸', data.question ? 'Q: ' + data.question.substring(0, 50) + '...' : '');
                  } else if (data.type === 'complete') {
                    stageLabel.textContent = 'Done';
                    progressBar.style.width = '100%';
                    addLog('✓', 'Evaluation complete');
                    const scores = data.scores || {};
                    const statsEl = document.getElementById('eval-eval-stats');
                    const badgeEl = document.getElementById('eval-eval-badge');
                    if (statsEl) {
                      const parts = [];
                      if (scores.context_recall != null) parts.push('context_recall: ' + (scores.context_recall * 100).toFixed(1) + '%');
                      if (scores.entity_recall != null) parts.push('entity_recall: ' + (scores.entity_recall * 100).toFixed(1) + '%');
                      if (scores.answer_correctness != null) parts.push('answer_correctness: ' + (scores.answer_correctness * 100).toFixed(1) + '%');
                      if (scores.faithfulness != null) parts.push('faithfulness: ' + (scores.faithfulness * 100).toFixed(1) + '%');
                      if (scores.answer_relevancy != null) parts.push('answer_relevancy: ' + (scores.answer_relevancy * 100).toFixed(1) + '%');
                      statsEl.innerHTML = parts.join('<br>') || '—';
                    }
                    if (badgeEl) {
                      const avg = scores.answer_correctness != null ? (scores.answer_correctness * 100).toFixed(0) : '—';
                      badgeEl.textContent = avg + '%';
                      badgeEl.style.background = 'var(--accent-2)';
                      badgeEl.style.color = 'var(--accent)';
                    }
                    await fetchEvalHealth(kbId);
                    fetchEvalRecords(kbId);
                    populateEvalKbSelector();
                  } else if (data.type === 'error') {
                    errorEl.textContent = data.message || 'Error';
                    errorEl.classList.remove('hidden');
                    addLog('✗', data.message || 'Error');
                  }
                } catch (_) {}
              }
            }
          }
        }
      } catch (e) {
        errorEl.textContent = e.message || 'Evaluation failed';
        errorEl.classList.remove('hidden');
        addLog('✗', e.message || 'Evaluation failed');
      } finally {
        if (runBtn) runBtn.disabled = false;
        setTimeout(() => {
          progressPanel.classList.add('hidden');
          evalPanel.classList.remove('hidden');
          progressBar.style.width = '0%';
        }, 1500);
      }
    }

    async function runRepair() {
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
      function addLog(icon, msg) {
        const div = document.createElement('div');
        div.innerHTML = (icon || '▸') + ' ' + (msg || '');
        logFeed.appendChild(div);
        logFeed.scrollTop = logFeed.scrollHeight;
      }
      try {
        const res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/repair', { method: 'POST' });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(parseError(err) || res.statusText);
        }
        const reader = res.body?.getReader();
        const dec = new TextDecoder();
        if (reader) {
          let buf = '';
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += dec.decode(value, { stream: true });
            const lines = buf.split('\n');
            buf = lines.pop() || '';
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.type === 'step') {
                    stepIdx = Math.min(stepIdx + 1, steps.length - 1);
                    stageLabel.textContent = data.message || steps[stepIdx];
                    progressBar.style.width = (100 * stepIdx / (steps.length - 1)) + '%';
                    addLog('✓', data.message || steps[stepIdx]);
                  } else if (data.type === 'done') {
                    stageLabel.textContent = 'Done' + (data.edges_added ? ' (' + data.edges_added + ' edges added)' : '');
                    progressBar.style.width = '100%';
                    addLog('✓', 'Repair complete');
                    await fetchEvalHealth(kbId);
                    populateEvalKbSelector();
                  } else if (data.type === 'error') {
                    errorBanner.textContent = data.message || 'Error';
                    errorBanner.classList.remove('hidden');
                    addLog('✗', data.message || 'Error');
                  }
                } catch (_) {}
              }
            }
          }
        } else {
          const data = await res.json();
          stageLabel.textContent = 'Done' + (data.report?.edges_added ? ' (' + data.report.edges_added + ' edges added)' : '');
          progressBar.style.width = '100%';
          addLog('✓', 'Repair complete');
          await fetchEvalHealth(kbId);
          populateEvalKbSelector();
        }
      } catch (e) {
        errorBanner.textContent = e.message || 'Repair failed';
        errorBanner.classList.remove('hidden');
        addLog('✗', e.message || 'Repair failed');
      } finally {
        if (repairBtn) repairBtn.disabled = false;
        setTimeout(() => {
          panelB.classList.add('hidden');
          panelA.classList.remove('hidden');
          progressBar.style.width = '0%';
        }, 1500);
      }
    }

    function fillPrompt(text) {
      questionInput.value = text;
      questionInput.focus();
    }

    function hideEmptyStates() {
      _hasMessages = true;
      emptyStateNoKb.classList.add('hidden');
      emptyStateReady.classList.add('hidden');
      emptyStateReady.classList.remove('flex');
      setStickySummaryVisible(Boolean(getActiveKbId()));
    }

    function renderInlineMarkdown(value) {
      const text = esc(String(value || ''));
      return text
        .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded text-xs font-mono" style="background:var(--bg-input);border:1px solid var(--border);color:var(--text-primary);">$1</code>')
        .replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>')
        .replace(/\\*([^*]+)\\*/g, '<em>$1</em>')
        .replace(/\[([a-zA-Z_][a-zA-Z0-9_\-]*:[^\]\n]+)\]/g, '<span class="px-1.5 py-0.5 rounded text-xs font-mono align-middle" style="background:var(--accent-15); color:var(--accent);">[$1]</span>');
    }

    function renderAssistantGuide(content) {
      const wrapper = document.createElement('div');
      wrapper.className = 'space-y-2.5';
      const lines = String(content || '').split('\n');
      let list = null;
      let paraParts = [];

      function flushParagraph() {
        if (!paraParts.length) return;
        const p = document.createElement('p');
        p.className = 'text-sm leading-relaxed';
        p.innerHTML = renderInlineMarkdown(paraParts.join(' '));
        wrapper.appendChild(p);
        paraParts = [];
      }

      function flushList() {
        if (!list) return;
        wrapper.appendChild(list);
        list = null;
      }

      lines.forEach((line) => {
        const trimmed = line.trim();
        if (!trimmed) {
          flushParagraph();
          flushList();
          return;
        }

        if (trimmed.startsWith('### ')) {
          flushParagraph();
          flushList();
          const h4 = document.createElement('h4');
          h4.className = 'text-sm font-semibold mt-1';
          h4.style.color = 'var(--text-primary)';
          h4.innerHTML = renderInlineMarkdown(trimmed.slice(4));
          wrapper.appendChild(h4);
          return;
        }

        if (trimmed.startsWith('## ')) {
          flushParagraph();
          flushList();
          const h3 = document.createElement('h3');
          h3.className = 'text-base font-semibold mt-1';
          h3.style.color = 'var(--accent)';
          h3.innerHTML = renderInlineMarkdown(trimmed.slice(3));
          wrapper.appendChild(h3);
          return;
        }

        if (trimmed.startsWith('- ')) {
          flushParagraph();
          if (!list) {
            list = document.createElement('ul');
            list.className = 'text-sm leading-relaxed space-y-1 pl-5 list-disc';
          }
          const li = document.createElement('li');
          li.innerHTML = renderInlineMarkdown(trimmed.slice(2));
          list.appendChild(li);
          return;
        }

        flushList();
        paraParts.push(trimmed);
      });

      flushParagraph();
      flushList();
      return wrapper;
    }

    function buildMessageElement(role, content, sources, numFactsUsed, rawFacts, reasoning) {
      const hasRawFacts = role === 'assistant' && rawFacts && Array.isArray(rawFacts) && rawFacts.length > 0;
      const hasReasoning = role === 'assistant' && reasoning && typeof reasoning === 'string' && reasoning.trim().length > 0;
      const div = document.createElement('div');
      div.dataset.chatMessage = '1';
      div.className = 'flex ' + (role === 'user' ? 'justify-end msg-enter-user' : 'justify-start msg-enter-assistant');
      const bubble = document.createElement('div');
      bubble.className = 'msg-bubble max-w-[85%] rounded-xl px-4 py-3.5 ' +
        (role === 'user' ? 'msg-user-bubble' : 'bubble-assistant');
      bubble.style.background = role === 'user' ? 'var(--accent)' : 'var(--bg-card)';
      bubble.style.color = role === 'user' ? '#fff' : 'var(--text-primary)';
      bubble.style.border = '1px solid ' + (role === 'user' ? 'var(--accent-7)' : 'var(--border)');

      if (role === 'assistant') {
        // Meta row
        const metaRow = document.createElement('div');
        metaRow.className = 'flex items-center gap-2 mb-2.5';
        const iconWrap = document.createElement('div');
        iconWrap.className = 'w-5 h-5 rounded flex items-center justify-center shrink-0';
        iconWrap.style.background = 'var(--accent-15)';
        iconWrap.innerHTML = '<svg class="w-3 h-3" style="color:var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>';
        metaRow.appendChild(iconWrap);
        const metaLabel = document.createElement('span');
        metaLabel.className = 'text-xs font-medium';
        metaLabel.style.color = 'var(--accent)';
        metaLabel.textContent = 'Clearence';
        metaRow.appendChild(metaLabel);
        if (numFactsUsed > 0) {
          const factsBadge = document.createElement('span');
          factsBadge.className = 'text-xs px-1.5 py-0.5 rounded font-mono';
          factsBadge.style.cssText = 'background:var(--accent-15); color:var(--accent);';
          factsBadge.textContent = numFactsUsed + ' facts';
          metaRow.appendChild(factsBadge);
        }
        bubble.appendChild(metaRow);

        // Explainable reasoning: Raw facts (expandable)
        if (hasRawFacts) {
          const rawFactsDiv = document.createElement('details');
          rawFactsDiv.className = 'mb-3 rounded-lg overflow-hidden';
          rawFactsDiv.style.cssText = 'border:1px solid var(--border); background:var(--bg-input);';
          const summary = document.createElement('summary');
          summary.className = 'cursor-pointer px-3 py-2 text-xs font-medium flex items-center gap-2';
          summary.style.color = 'var(--text-muted)';
          summary.innerHTML = '<svg class="w-3 h-3 shrink-0" style="color:var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"/></svg> Raw facts used';
          rawFactsDiv.appendChild(summary);
          const rawContent = document.createElement('div');
          rawContent.className = 'px-3 pb-2.5 pt-1 space-y-2 text-xs font-mono';
          rawContent.style.cssText = 'color:var(--text-muted); max-height:200px; overflow-y:auto;';
          rawFacts.forEach((fact, i) => {
            const p = document.createElement('p');
            p.style.cssText = 'margin:0; padding:0.25rem 0; border-bottom:1px solid var(--border);';
            p.textContent = '[' + (i + 1) + '] ' + (typeof fact === 'string' ? fact : String(fact));
            rawContent.appendChild(p);
          });
          rawFactsDiv.appendChild(rawContent);
          bubble.appendChild(rawFactsDiv);
        }

        // Reasoning: in-depth interpretation of the facts (expandable)
        if (hasReasoning) {
          const reasonDiv = document.createElement('details');
          reasonDiv.className = 'mb-3 rounded-lg overflow-hidden';
          reasonDiv.style.cssText = 'border:1px solid var(--border); background:var(--bg-input);';
          const summary = document.createElement('summary');
          summary.className = 'cursor-pointer px-3 py-2 text-xs font-medium flex items-center gap-2';
          summary.style.color = 'var(--text-muted)';
          summary.innerHTML = '<svg class="w-3 h-3 shrink-0" style="color:var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg> Reasoning';
          reasonDiv.appendChild(summary);
          const reasonContent = document.createElement('div');
          reasonContent.className = 'px-3 pb-2.5 pt-1 text-sm leading-relaxed';
          reasonContent.style.cssText = 'color:var(--text-muted); max-height:300px; overflow-y:auto; white-space:pre-wrap;';
          reasonContent.appendChild(renderAssistantGuide(reasoning));
          reasonDiv.appendChild(reasonContent);
          bubble.appendChild(reasonDiv);
        }
      }

      const text = document.createElement('div');
      text.className = 'whitespace-pre-wrap text-sm leading-relaxed';
      if (typeof content === 'string') {
        if (role === 'assistant') {
          text.className = 'text-sm leading-relaxed';
          if (hasRawFacts || hasReasoning) {
            const explLabel = document.createElement('div');
            explLabel.className = 'text-xs font-medium mb-2';
            explLabel.style.color = 'var(--accent)';
            explLabel.textContent = 'Answer';
            text.appendChild(explLabel);
          }
          text.appendChild(renderAssistantGuide(content));
        } else {
          text.textContent = content;
        }
      } else {
        text.appendChild(content);
      }
      bubble.appendChild(text);

      // Source tags
      if (sources && sources.length > 0 && role === 'assistant') {
        const srcDiv = document.createElement('div');
        srcDiv.className = 'mt-3 pt-2.5 flex flex-wrap gap-1.5';
        srcDiv.style.borderTop = '1px solid var(--border)';
        sources.slice(0, 5).forEach(ref => {
          const tag = document.createElement('span');
          tag.className = 'px-2 py-0.5 rounded text-xs font-mono';
          tag.style.cssText = 'background:var(--accent-15); color:var(--accent);';
          tag.textContent = ref;
          srcDiv.appendChild(tag);
        });
        if (sources.length > 5) {
          const more = document.createElement('span');
          more.className = 'text-xs';
          more.style.color = 'var(--text-muted-2)';
          more.textContent = '+' + (sources.length - 5) + ' more';
          srcDiv.appendChild(more);
        }
        bubble.appendChild(srcDiv);
      }

      div.appendChild(bubble);
      return div;
    }

    function buildOntologySummaryElement(report, prevTotals) {
      if (!report) return null;
      const div = document.createElement('div');
      div.dataset.chatMessage = '1';
      div.className = 'flex justify-start msg-enter-assistant';
      const bubble = document.createElement('div');
      bubble.className = 'msg-bubble w-full max-w-2xl rounded-xl px-5 py-5 bubble-assistant';
      bubble.style.cssText = 'background:var(--bg-card); color:var(--text-primary); border:1px solid var(--border);';

      const totals = report.totals || {};
      const extractionTotals = report.extraction_totals || {};
      const reasoning = report.reasoning || {};
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
      header.innerHTML = '<div class="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style="background:var(--success-15);">'
        + '<svg class="w-4.5 h-4.5" style="color:var(--success);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>'
        + '</div>'
        + '<div><p class="font-semibold" style="color:var(--text-primary);">Ontology build complete</p>'
        + '<p class="text-xs font-mono mt-0.5" style="color:var(--text-muted);">' + ontologyName + ' · ' + totalChunks + ' chunks · ' + elapsed.toFixed(1) + 's</p>'
        + '</div>'
        + '<span class="ml-auto px-2.5 py-1 rounded-full text-xs font-medium" style="background:var(--success-15);color:var(--success);border:1px solid var(--success-2);">Done</span>';
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
      const keyMap = { 'Classes': 'classes', 'Instances': 'instances', 'Relations': 'relations', 'Axioms': 'axioms', 'Data Props': 'data_properties' };
      statItems.forEach(([label, val]) => {
        const key = keyMap[label] || label.toLowerCase();
        const prev = prevTotals ? (prevTotals[key] ?? 0) : null;
        const delta = prev !== null && val !== prev ? (val - prev) : null;
        const deltaHtml = delta !== null
          ? (delta > 0
            ? '<span style="color:var(--accent);font-size:9px;margin-left:2px;">+' + delta + '</span>'
            : '<span style="color:#555;font-size:9px;margin-left:2px;">' + delta + '</span>')
          : '';
        const card = document.createElement('div');
        card.className = 'rounded-lg px-2 py-2 text-center';
        card.style.cssText = 'background:var(--bg-input); border:1px solid var(--border);';
        card.innerHTML = '<p class="stat-value text-sm font-semibold">' + fmtNum(val) + deltaHtml + '</p>'
          + '<p class="text-xs mt-0.5 stat-label">' + label + '</p>';
        statsGrid.appendChild(card);
      });
      wrap.appendChild(statsGrid);

      const pipelineDiv = document.createElement('details');
      pipelineDiv.className = 'rounded-lg overflow-hidden';
      pipelineDiv.style.cssText = 'border:1px solid var(--border); background:var(--bg-input);';
      const pipelineSummary = document.createElement('summary');
      pipelineSummary.className = 'cursor-pointer px-4 py-2.5 text-xs font-medium flex items-center gap-2';
      pipelineSummary.style.color = 'var(--text-muted)';
      pipelineSummary.innerHTML = '<svg class="w-3 h-3 shrink-0" style="color:var(--accent);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg> Pipeline trace';
      pipelineDiv.appendChild(pipelineSummary);
      const pipelineContent = document.createElement('div');
      pipelineContent.className = 'px-4 pb-3 pt-1 space-y-1 text-xs font-mono';
      pipelineContent.style.color = 'var(--text-muted)';
      const steps = [
        '1. Chunking: ' + totalChunks + ' chunks created',
        '2. Extraction: ' + enhancedChunks + ' of ' + totalChunks + ' chunks enhanced (' + mode + ' mode)',
        '3. Merge: ' + extCls + ' classes, ' + extInst + ' instances, ' + extRel + ' relations, ' + extAx + ' axioms',
        '4. LLM inference: ' + (llmInferred > 0 ? llmInferred + ' relations inferred' : 'Skipped'),
        '5. OWL 2 RL reasoning: ' + (infEdges > 0 ? infEdges + ' relations in ' + iter + ' iterations' : 'Skipped'),
        '6. Final totals: ' + (totals.classes ?? 0) + ' cls, ' + (totals.instances ?? 0) + ' inst, ' + (totals.relations ?? 0) + ' rel, ' + (totals.axioms ?? 0) + ' ax',
      ];
      steps.forEach(s => {
        const p = document.createElement('p');
        p.className = 'process-step';
        p.textContent = s;
        pipelineContent.appendChild(p);
      });
      pipelineDiv.appendChild(pipelineContent);
      wrap.appendChild(pipelineDiv);

      if (chunkStats.length > 0) {
        const toggle = document.createElement('button');
        toggle.className = 'text-xs link-teal cursor-pointer font-mono';
        toggle.textContent = '[+] Per-chunk details';
        toggle.type = 'button';
        const detailsDiv = document.createElement('div');
        detailsDiv.className = 'hidden mt-2 text-xs font-mono overflow-x-auto rounded-lg p-3';
        detailsDiv.style.cssText = 'background:var(--bg-body); border:1px solid var(--border); max-height:120px; overflow-y:auto;';
        const rows = chunkStats.map((c, i) => 'Chunk ' + (i + 1) + ': ' + (c.classes ?? 0) + ' cls, ' + (c.instances ?? 0) + ' inst, ' + (c.relations ?? 0) + ' rel' + (c.axioms ? ', ' + c.axioms + ' ax' : '')).join('\\n');
        detailsDiv.textContent = rows;
        toggle.addEventListener('click', () => {
          detailsDiv.classList.toggle('hidden');
          toggle.textContent = detailsDiv.classList.contains('hidden') ? '[+] Per-chunk details' : '[-] Per-chunk details';
        });
        wrap.appendChild(toggle);
        wrap.appendChild(detailsDiv);
      }

      bubble.appendChild(wrap);
      div.appendChild(bubble);
      return div;
    }

    function renderChatMessages(chat) {
      messagesEl.querySelectorAll('[data-chat-message]').forEach(el => el.remove());
      if (!chat || !chat.messages) return;
      const insertBefore = messagesEl.querySelector('#empty-state-no-kb') || messagesEl.querySelector('#empty-state-ready');
      let lastOntologyTotals = null;
      chat.messages.forEach(m => {
        let el;
        if (m.type === 'ontology_summary') {
          el = buildOntologySummaryElement(m.report, lastOntologyTotals);
          const totals = m.report?.totals || {};
          lastOntologyTotals = { classes: totals.classes ?? 0, instances: totals.instances ?? 0, relations: totals.relations ?? totals.edges ?? 0, axioms: totals.axioms ?? 0, data_properties: totals.data_properties ?? 0 };
        } else {
          el = buildMessageElement(m.role, m.content, m.sources, m.numFactsUsed, m.rawFacts, m.reasoning);
        }
        if (el) messagesEl.insertBefore(el, insertBefore);
      });
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function appendMessage(role, content, sources, numFactsUsed, chatId, rawFacts, reasoning) {
      let chat = chatId ? getChatById(chatId) : getActiveChat();
      if (!chat) {
        if (chatId) return;
        if (!getActiveKbId()) return;
        chat = createNewChat();
      }
      chat.messages.push({ role, content, sources, numFactsUsed, rawFacts, reasoning });
      if (chat.id === _activeChatId) {
        hideEmptyStates();
        const el = buildMessageElement(role, content, sources, numFactsUsed, rawFacts, reasoning);
        const before = messagesEl.querySelector('#empty-state-no-kb') || messagesEl.querySelector('#empty-state-ready');
        messagesEl.insertBefore(el, before);
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
      renderChatTabs();
    }

    function appendOntologySummary(report, kbId) {
      if (!report || !kbId) return;
      let chat = _chats.find(c => c.kbId === kbId);
      if (!chat) chat = createNewChat(kbId);
      chat.messages.push({ type: 'ontology_summary', report });
      if (chat.id === _activeChatId) {
        hideEmptyStates();
        const el = buildOntologySummaryElement(report, lastReportTotals);
        if (el) {
          const before = messagesEl.querySelector('#empty-state-no-kb') || messagesEl.querySelector('#empty-state-ready');
          messagesEl.insertBefore(el, before);
        }
        const totals = report.totals || {};
        const totalRel = totals.relations ?? totals.edges ?? 0;
        lastReportTotals = { classes: totals.classes ?? 0, instances: totals.instances ?? 0, relations: totalRel, axioms: totals.axioms ?? 0, data_properties: totals.data_properties ?? 0 };
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
      renderChatTabs();
    }

    const QA_STEPS = ['Retrieving facts...', 'Synthesizing answer...'];
    let qaStepInterval = null;

    function showLoading(show) {
      loadingIndicator.classList.toggle('hidden', !show);
      const qaLabel = document.getElementById('qa-step-label');
      const qaDots = loadingIndicator.querySelectorAll('.qa-step-dots span');
      if (show) {
        qaLabel.textContent = QA_STEPS[0];
        qaDots.forEach((d, i) => { d.style.background = i === 0 ? 'var(--accent)' : 'var(--bg-card)'; });
        qaStepInterval = setInterval(() => {
          const idx = QA_STEPS.indexOf(qaLabel.textContent);
          const next = (idx + 1) % QA_STEPS.length;
          qaLabel.textContent = QA_STEPS[next];
          qaDots.forEach((d, i) => { d.style.background = i === next ? 'var(--accent)' : 'var(--bg-card)'; });
        }, 1800);
      } else {
        if (qaStepInterval) { clearInterval(qaStepInterval); qaStepInterval = null; }
      }
    }

    chatForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const q = questionInput.value.trim();
      logClick('chat-send', q ? q.slice(0, 50) : '(empty)');
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
      try {
        const chat = getChatById(submitChatId);
        const kbId = (chat && chat.kbId) ? chat.kbId : getActiveKbId();
        if (!kbId) { setInputsEnabled(true); return; }
        const body = { question: q, kb_id: kbId };
        const res = await fetch(API + '/qa/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: controller.signal,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(parseError(data) || res.statusText);
        const sourceTags = (data.source_labels && data.source_labels.length) ? data.source_labels : (data.source_refs || []);
        const rawFacts = data.sources || [];
        const reasoning = data.reasoning || '';
        appendMessage('assistant', data.answer, sourceTags, data.num_facts_used, submitChatId, rawFacts, reasoning);
      } catch (e) {
        const msg = e && e.name === 'AbortError'
          ? 'Request timed out. The model may be overloaded; try again.'
          : e.message;
        appendMessage('assistant', 'Error: ' + msg, null, null, submitChatId, null, null);
      } finally {
        clearTimeout(timeoutId);
        showLoading(false);
        setInputsEnabled(true);
      }
    });

    // Upload (label handles click; drop handlers for drag-and-drop)
    dropZone?.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone?.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    let pendingFiles = [];
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

    function setModalMode(mode) {
      _modalMode = mode;
      const tabNew = document.getElementById('modal-mode-new');
      const tabExtend = document.getElementById('modal-mode-extend');
      if (mode === 'new') {
        tabNew.className = 'w-1/2 px-4 py-2 text-xs font-medium transition-all mode-tab-active';
        tabExtend.className = 'w-1/2 px-4 py-2 text-xs font-medium transition-all mode-tab-inactive';
        modalNewFields.classList.remove('hidden');
        modalExtendFields.classList.add('hidden');
        modalHeading.textContent = 'New Ontology';
        modalConfirm.textContent = 'Create & Build';
      } else {
        tabNew.className = 'w-1/2 px-4 py-2 text-xs font-medium transition-all mode-tab-inactive';
        tabExtend.className = 'w-1/2 px-4 py-2 text-xs font-medium transition-all mode-tab-active';
        modalNewFields.classList.add('hidden');
        modalExtendFields.classList.remove('hidden');
        modalHeading.textContent = 'Add Documents';
        modalConfirm.textContent = 'Add & Merge';
      }
    }

    function showCreateModal(fileOrFiles, source) {
      pendingFiles = Array.isArray(fileOrFiles) ? fileOrFiles : (fileOrFiles ? Array.from(fileOrFiles) : []);
      if (!pendingFiles.length) return;
      const first = pendingFiles[0];
      const stem = first.name.replace(/\\.[^.]+$/, '') || first.name;
      modalTitle.value = stem;
      modalDescription.value = '';
      modalFilename.textContent = pendingFiles.length > 1
        ? pendingFiles.length + ' files: ' + pendingFiles.map(f => f.name).join(', ')
        : 'File: ' + first.name;

      const activeId = getActiveKbId();
      if (activeId) {
        const activeKb = _kbData.find(k => k.id === activeId);
        const kbName = activeKb ? activeKb.name : activeId;
        document.getElementById('modal-mode-kb-name').textContent = kbName;
        modalModeSection.classList.remove('hidden');
        setModalMode(source === 'document' ? 'extend' : 'new');
      } else {
        modalModeSection.classList.add('hidden');
        setModalMode('new');
      }

      createModal.classList.remove('hidden');
      if (_modalMode === 'new') modalTitle.focus();
    }

    function hideCreateModal() {
      createModal.classList.add('hidden');
      pendingFiles = [];
    }

    modalCancel?.addEventListener('click', () => { logClick('upload-modal', 'cancel'); hideCreateModal(); });
    createModal?.querySelector('.modal-backdrop')?.addEventListener('click', () => { logClick('upload-modal', 'backdrop'); hideCreateModal(); });

    // Delete KB modal
    const deleteModal = document.getElementById('delete-modal');
    let _pendingDeleteId = null;
    let _pendingDeleteName = null;

    function deleteActiveKB() {
      const activeId = getActiveKbId();
      if (!activeId) return;
      const activeKb = _kbData.find(k => k.id === activeId);
      _pendingDeleteId = activeId;
      _pendingDeleteName = activeKb ? activeKb.name : activeId;
      document.getElementById('delete-modal-name').textContent = _pendingDeleteName;
      deleteModal.classList.remove('hidden');
    }

    document.getElementById('delete-modal-cancel')?.addEventListener('click', () => {
      deleteModal?.classList.add('hidden');
      _pendingDeleteId = null;
    });
    deleteModal?.querySelector('.modal-backdrop')?.addEventListener('click', () => {
      deleteModal?.classList.add('hidden');
      _pendingDeleteId = null;
    });
    document.getElementById('delete-modal-confirm')?.addEventListener('click', async () => {
      if (!_pendingDeleteId) return;
      logClick('kb-delete-confirm', _pendingDeleteId);
      const idToDelete = _pendingDeleteId;
      deleteModal?.classList.add('hidden');
      _pendingDeleteId = null;
      try {
        const res = await fetch(API + '/knowledge-bases/' + idToDelete, { method: 'DELETE' });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(parseError(data) || res.statusText);
        }
        _chats = _chats.filter(c => c.kbId !== idToDelete);
        if (_activeChatId && _chats.every(c => c.id !== _activeChatId)) {
          _activeChatId = _chats[0]?.id || null;
        }
        try {
          let recent = JSON.parse(localStorage.getItem(RECENT_KB_KEY) || '[]');
          recent = recent.filter(id => id !== idToDelete);
          localStorage.setItem(RECENT_KB_KEY, JSON.stringify(recent));
        } catch (_) {}
        await loadKBs();
        renderChatTabs();
        if (_chats.length && _activeChatId) switchToChat(_activeChatId);
        else if (!_chats.length) {
          renderChatMessages(null);
          updateEmptyStatesForChat({ kbId: null, messages: [] });
          setInputsEnabled(false);
        }
        kbStatus.textContent = 'Knowledge base deleted successfully';
        kbStatus.style.color = 'var(--success)';
        kbStatus.style.display = '';
        setTimeout(() => { kbStatus.style.display = 'none'; }, 3000);
      } catch (e) {
        kbStatus.textContent = 'Delete failed: ' + e.message;
        kbStatus.style.color = 'var(--error)';
        kbStatus.style.display = '';
      }
    });

    // KB summary/edit modal
    const kbSummaryModal = document.getElementById('kb-summary-modal');
    const kbSummaryName = document.getElementById('kb-summary-name');
    const kbSummaryDesc = document.getElementById('kb-summary-desc');
    const kbSummaryStats = document.getElementById('kb-summary-stats');

    function showKbSummaryModal() {
      const activeId = getActiveKbId();
      if (!activeId) return;
      const kb = _kbData.find(k => k.id === activeId);
      if (!kb) return;
      kbSummaryName.value = kb.name || kb.id;
      kbSummaryDesc.value = kb.description || '';
      const stats = kb.stats || {};
      const relCount = stats.relations ?? stats.edges ?? 0;
      kbSummaryStats.innerHTML = '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Stats</p>'
        + '<div class="grid grid-cols-2 gap-2 text-xs font-mono" style="color:var(--text-primary);">'
        + '<div><span style="color:var(--text-muted);">Classes:</span> ' + fmtNum(stats.classes ?? 0) + '</div>'
        + '<div><span style="color:var(--text-muted);">Instances:</span> ' + fmtNum(stats.instances ?? 0) + '</div>'
        + '<div><span style="color:var(--text-muted);">Relations:</span> ' + fmtNum(relCount) + '</div>'
        + '<div><span style="color:var(--text-muted);">Axioms:</span> ' + fmtNum(stats.axioms ?? 0) + '</div>'
        + '<div><span style="color:var(--text-muted);">Data props:</span> ' + fmtNum(stats.data_properties ?? 0) + '</div>'
        + '</div>';
      kbSummaryModal.dataset.kbId = activeId;
      kbSummaryModal.classList.remove('hidden');
    }

    function hideKbSummaryModal() {
      kbSummaryModal.classList.add('hidden');
      delete kbSummaryModal.dataset.kbId;
    }

    document.getElementById('kb-summary-close')?.addEventListener('click', hideKbSummaryModal);
    kbSummaryModal?.querySelector('.modal-backdrop')?.addEventListener('click', hideKbSummaryModal);
    document.getElementById('kb-summary-cancel')?.addEventListener('click', hideKbSummaryModal);
    document.getElementById('kb-summary-save')?.addEventListener('click', async () => {
      logClick('kb-summary-save', kbSummaryModal.dataset.kbId);
      const kbId = kbSummaryModal.dataset.kbId;
      if (!kbId) return;
      const name = kbSummaryName.value.trim();
      const description = kbSummaryDesc.value.trim();
      const body = {};
      if (name) body.name = name;
      body.description = description;
      try {
        const res = await fetch(API + '/knowledge-bases/' + kbId, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(parseError(data) || res.statusText);
        }
        hideKbSummaryModal();
        await loadKBs();
      } catch (e) {
        kbStatus.textContent = 'Update failed: ' + e.message;
        kbStatus.style.display = '';
      }
    });

    // Ontology card: expand/collapse + click to open summary modal
    const ontoCard = document.getElementById('onto-card');
    const ontoCardExpandBtn = document.getElementById('onto-card-expand-btn');
    let _ontoCardExpanded = false;
    if (ontoCard) {
      ontoCardExpandBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        logClick('onto-card', 'expand-toggle');
        _ontoCardExpanded = !_ontoCardExpanded;
        ontoCard.classList.toggle('collapsed', !_ontoCardExpanded);
      });
      ontoCard.addEventListener('click', (e) => {
        if (e.target.closest('#onto-card-expand-btn') || e.target.closest('a') || e.target.closest('button')) return;
        logClick('onto-card', 'summary-modal');
        showKbSummaryModal();
      });
    }

    // Job details modal
    const jobDetailModal = document.getElementById('job-detail-modal');
    const jobDetailContent = document.getElementById('job-detail-content');
    const jobDetailTitle = document.getElementById('job-detail-title');

    modalConfirm?.addEventListener('click', () => {
      logClick('upload-confirm', _modalMode + ' (files: ' + pendingFiles.length + ')');
      if (!pendingFiles.length) return;
      const parallel = _modalMode === 'extend'
        ? document.getElementById('modal-parallel-extend').checked
        : document.getElementById('modal-parallel').checked;
      const files = pendingFiles.slice();
      hideCreateModal();
      if (_modalMode === 'extend') {
        const activeId = getActiveKbId();
        if (activeId) {
          doExtend(files, activeId, parallel);
          return;
        }
      }
      const first = files[0];
      const title = modalTitle.value.trim() || first.name.replace(/\\.[^.]+$/, '');
      const description = modalDescription.value.trim();
      doUpload(files, title, description, parallel);
    });

    dropZone?.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      const files = e.dataTransfer?.files;
      if (files?.length) { logClick('documents-drop', files.length + ' files'); showCreateModal(files, 'document'); }
    });
    fileInput?.addEventListener('change', () => {
      if (fileInput.files?.length) {
        logClick('documents-files', fileInput.files.length + ' files');
        showCreateModal(fileInput.files, 'document');
        fileInput.value = '';
      }
    });
    if (fileInputCreate) fileInputCreate.addEventListener('change', () => {
      if (fileInputCreate.files?.length) {
        logClick('create-kb-files', fileInputCreate.files.length + ' files');
        showCreateModal(fileInputCreate.files, 'create');
      }
      fileInputCreate.value = '';
    });

    const jobs = [];

    function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

    function createJobCard(job) {
      job.progress = job.progress || {};
      const isCreate = job.jobType === 'create';
      const typeClass = isCreate ? 'job-create' : 'job-extend';
      const typeLabel = isCreate ? 'New KB' : 'Expanding';
      const card = document.createElement('div');
      card.className = 'job-card job-clickable ' + typeClass;
      card.dataset.jobId = job.localId;
      card.innerHTML = '<div class="flex items-center justify-between gap-2">'
        + '<div class="flex items-center gap-2 min-w-0 flex-1">'
        + '<span class="job-type-badge text-xs font-medium px-1.5 py-0.5 rounded shrink-0">' + typeLabel + '</span>'
        + '<p class="text-sm font-medium truncate min-w-0" style="color:var(--text-primary);">' + esc(job.title) + '</p>'
        + '</div>'
        + '<button type="button" class="job-cancel shrink-0 w-5 h-5 rounded flex items-center justify-center" style="color:var(--text-muted);">'
        + '<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>'
        + '</button></div>'
        + (job.description ? '<p class="text-xs mt-0.5 truncate" style="color:var(--text-muted-2);">' + esc(job.description) + '</p>' : '')
        + '<div class="flex items-center gap-2 mt-1.5">'
        + '<span class="stage-dot"></span>'
        + '<span class="stage-label text-xs font-mono" style="color:var(--text-muted);">Starting...</span>'
        + '</div>'
        + '<div class="job-metrics text-xs font-mono mt-1" style="color:#6b6b76; min-height:1em;"></div>';
      card.querySelector('.job-cancel').addEventListener('click', (e) => { e.stopPropagation(); logClick('job-cancel', job.localId); cancelJob(job); });
      card.addEventListener('click', (e) => { if (!e.target.closest('.job-cancel')) { logClick('job-detail', job.localId); showJobDetailModal(job); } });
      return card;
    }

    let _modalJob = null;

    function updateJobStage(job, ev) {
      const step = ev.step;
      const d = ev.data || ev;
      if (!job.progress) job.progress = {};
      job.progress[step] = d;
      if (!job.liveMetrics) job.liveMetrics = { classes: 0, instances: 0, relations: 0, axioms: 0, data_properties: 0 };
      if (step === 'file_start') {
        job.fileIndex = d.file_index;
        job.totalFiles = d.total_files;
        job.currentFilename = d.filename || '';
        job.chunksCompleted = 0;
        job.chunksTotal = 0;
      } else if (step === 'extract') {
        job.chunksCompleted = (job.chunksCompleted || 0) + 1;
        job.liveMetrics.classes += d.classes ?? 0;
        job.liveMetrics.instances += d.instances ?? 0;
        job.liveMetrics.relations += d.relations ?? 0;
        job.liveMetrics.axioms += d.axioms ?? 0;
      } else if (step === 'chunk_done') {
        job.chunksTotal = d.total_chunks ?? 0;
      } else if (step === 'merge_done') {
        job.liveMetrics.classes = d.classes ?? 0;
        job.liveMetrics.instances = d.instances ?? 0;
        job.liveMetrics.relations = d.relations ?? 0;
        job.liveMetrics.axioms = d.axioms ?? 0;
      } else if (step === 'inference_done' && d.inferred) {
        job.liveMetrics.relations = (job.liveMetrics.relations || 0) + (d.inferred || 0);
      } else if (step === 'reasoning_done' && d.inferred_edges) {
        job.liveMetrics.relations = (job.liveMetrics.relations || 0) + (d.inferred_edges || 0);
      } else if (step === 'quality_done') {
        job.qualityGrade = d.grade;
        job.qualityScore = d.score;
      }
      const label = job.card?.querySelector('.stage-label');
      if (label) {
        const chunksDone = step === 'extract' ? (job.chunksCompleted || 0) : (job.chunksCompleted || 0);
        const chunksTotal = job.chunksTotal ?? d.total ?? 0;
        const stageMap = {
          'file_start': (d.total_files > 1) ? 'File ' + (d.file_index || '?') + ' of ' + (d.total_files || '?') + ': ' + (d.filename || '') : 'Loading...',
          'load': 'Loading...', 'load_done': 'Loaded',
          'chunk': 'Chunking...', 'chunk_done': (d.total_chunks || 0) + ' chunks',
          'extract': chunksTotal > 0 ? chunksDone + ' of ' + chunksTotal + ' chunks' : 'Extracting...',
          'merge_done': 'Merged',
          'cross_component': 'Cross-component relations...', 'cross_component_done': 'Cross-component done',
          'taxonomy': 'Building taxonomy...', 'taxonomy_done': 'Taxonomy built', 'taxonomy_skip': 'Skipped taxonomy',
          'inference': 'Inferring...', 'inference_done': 'Inferred',
          'inference_skip': 'Skipped inference',
          'reasoning': 'Reasoning...', 'reasoning_done': 'Reasoned',
          'reasoning_skip': 'Skipped reasoning',
          'repair': (d.phase ? d.phase + '...' : 'Repairing...'), 'repair_done': 'Repaired', 'repair_skip': 'Skipped repair',
          'enrichment': (d.message || 'Enrichment...'), 'population': (d.message || 'Population...'),
          'quality': (d.message || 'Quality...'), 'quality_done': (d.grade ? 'Grade ' + d.grade : 'Quality done'),
        };
        label.textContent = stageMap[step] || step;
      }
      const metricsEl = job.card?.querySelector('.job-metrics');
      if (metricsEl) {
        if (step === 'load_done' && d.chars) {
          metricsEl.textContent = (d.chars || 0).toLocaleString() + ' chars';
        } else if (step === 'chunk_done' && d.total_chunks) {
          metricsEl.textContent = (d.total_chunks || 0) + ' chunks';
        } else if (step === 'extract' && (job.chunksCompleted || 0) > 0 && (job.chunksTotal || 0) > 0) {
          metricsEl.textContent = (job.chunksCompleted || 0) + ' of ' + (job.chunksTotal || 0) + ' chunks';
        } else if (step === 'merge_done') {
          const cls = d.classes ?? 0, inst = d.instances ?? 0, rel = d.relations ?? 0;
          metricsEl.textContent = cls + ' cls, ' + inst + ' inst, ' + rel + ' rel';
        } else if (step === 'inference_done' && d.inferred) {
          metricsEl.textContent = '+ ' + (d.inferred || 0) + ' inferred relations';
        } else if (step === 'reasoning_done') {
          const inf = d.inferred_edges ?? 0, iter = d.iterations ?? 0;
          if (inf > 0) metricsEl.textContent = inf + ' relations in ' + iter + ' reasoning iterations';
        } else if (step === 'quality_done' && d.grade) {
          metricsEl.textContent = 'Grade ' + d.grade + (d.score != null ? ' · ' + Number(d.score).toFixed(2) : '');
        }
      }
      if (_modalJob && _modalJob.localId === job.localId) {
        showJobDetailModal(job);
      }
    }

    function showJobDetailModal(job) {
      _modalJob = job;
      jobDetailTitle.textContent = job.title || 'Job Details';
      const report = job.pipeline_report || {};
      const progress = job.progress || {};
      const live = job.liveMetrics || {};
      const totals = report.totals || {};
      const ext = report.extraction_totals || {};
      const reasoning = report.reasoning || {};
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
      const hasRepair = !!progress.repair_done || !!progress.repair_skip;
      const hasQuality = !!progress.quality_done || !!(report.quality && report.quality.reliability_score);
      const isLoad = !!progress.load && !hasLoad;
      const isChunk = !!progress.chunk && !hasChunk;
      const isExtract = (!!progress.extract || !!progress.taxonomy) && !hasMerge;
      const extractCur = chunksDone;
      const extractTot = chunksTotal;
      const isInference = !!progress.inference && !hasInference;
      const isReasoning = !!progress.reasoning && !hasReasoning;
      const isRepair = !!progress.repair && !hasRepair;
      const isQuality = !!progress.quality && !hasQuality;
      const repairPhase = progress.repair?.phase || '';
      const hasEnrichment = !!progress.enrichment;
      const hasPopulation = !!progress.population;
      const enrichmentDone = hasQuality && hasEnrichment;
      const populationDone = hasQuality && hasPopulation;
      const isEnrichment = !!progress.enrichment && !enrichmentDone;
      const isPopulation = !!progress.population && !populationDone;
      const fileIndex = job.fileIndex ?? progress.file_start?.file_index;
      const totalFiles = job.totalFiles ?? progress.file_start?.total_files;

      let html = '<div class="space-y-4">';
      const qualityForBanner = report.quality || {};
      const consistencyForBanner = qualityForBanner.consistency_report || {};
      const criticalCountBanner = consistencyForBanner.critical_count ?? 0;
      if (criticalCountBanner > 0) {
        html += '<div class="rounded-lg p-3 cursor-pointer" style="background:var(--error-15); border:1px solid var(--error);" onclick="document.getElementById(\'job-detail-content\').querySelector(\'.quality-conflict-section\')?.scrollIntoView({behavior:\'smooth\'})">';
        html += '<p class="text-xs font-semibold" style="color:var(--error);">⚠ ' + criticalCountBanner + ' critical relation conflict' + (criticalCountBanner !== 1 ? 's' : '') + ' detected — review before use</p><p class="text-xs mt-0.5" style="color:var(--text-muted);">Click to scroll to details</p></div>';
      }

      html += '<div class="rounded-lg p-3" style="background:var(--bg-input); border:1px solid var(--border);">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Status</p>';
      html += '<p class="font-mono text-sm"><span class="stat-value">' + (job.status || 'running') + '</span></p>';
      if (ontologyName !== '—') html += '<p class="text-xs mt-1" style="color:var(--text-muted);">Ontology: ' + esc(ontologyName) + '</p>';
      html += '</div>';

      const docPath = report.document_path || job.description || '';
      html += '<div class="rounded-lg p-3" style="background:var(--bg-input); border:1px solid var(--border);">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Document &amp; Chunking</p>';
      html += '<ul class="space-y-1 text-xs font-mono" style="color:var(--text-primary);">';
      if (docPath) html += '<li>Document(s): <span class="stat-value">' + esc(docPath) + '</span></li>';
      if (totalFiles > 1 && fileIndex) html += '<li>Current file: <span class="stat-value">' + fileIndex + ' of ' + totalFiles + (job.currentFilename ? ' · ' + esc(job.currentFilename) : '') + '</span></li>';
      html += '<li>Document size: <span class="stat-value">' + (docChars ? docChars.toLocaleString() + ' chars' : '—') + '</span></li>';
      html += '<li>Total chunks: <span class="stat-value">' + totalChunks + '</span></li>';
      html += '<li>Extraction mode: <span class="stat-value">' + mode + '</span></li>';
      if (elapsed > 0) html += '<li>Elapsed: <span class="stat-value">' + elapsed.toFixed(1) + 's</span></li>';
      html += '</ul></div>';

      html += '<div class="rounded-lg p-3" style="background:var(--bg-input); border:1px solid var(--border);">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Entities &amp; Relations</p>';
      html += '<div class="grid grid-cols-2 gap-2 text-xs font-mono">';
      html += '<div><span style="color:var(--text-muted);">Classes:</span> <span class="stat-value">' + cls + '</span></div>';
      html += '<div><span style="color:var(--text-muted);">Instances:</span> <span class="stat-value">' + inst + '</span></div>';
      html += '<div><span style="color:var(--text-muted);">Relations:</span> <span class="stat-value">' + rel + '</span></div>';
      html += '<div><span style="color:var(--text-muted);">Axioms:</span> <span class="stat-value">' + ax + '</span></div>';
      html += '<div><span style="color:var(--text-muted);">Data properties:</span> <span class="stat-value">' + dp + '</span></div>';
      html += '</div></div>';

      html += '<div class="rounded-lg p-3" style="background:var(--bg-input); border:1px solid var(--border);">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Pipeline Breakdown</p>';
      html += '<ol class="space-y-2 text-xs" style="list-style:none; padding-left:0;">';
      const stepStatus = (done, running, warn, err) => {
        if (done) return '<span style="color:var(--success);">✓</span>';
        if (running) return '<span style="color:var(--accent-secondary);">●</span>';
        if (warn) return '<span style="color:var(--warning);">⚠</span>';
        if (err) return '<span style="color:var(--error-bright);">✗</span>';
        return '<span style="color:var(--text-muted-2);">○</span>';
      };
      const stepStatusSimple = (done, running) => stepStatus(done, running, false, false);
      html += '<li class="flex items-start gap-2">' + stepStatusSimple(hasLoad, isLoad) + '<span><strong>1. Load</strong>: ' + (hasLoad ? docChars.toLocaleString() + ' chars loaded' : (isLoad ? 'Loading document...' : 'Pending')) + '</span></li>';
      html += '<li class="flex items-start gap-2">' + stepStatusSimple(hasChunk, isChunk) + '<span><strong>2. Chunk</strong>: ' + (hasChunk ? totalChunks + ' chunks created' : (isChunk ? 'Chunking text...' : 'Pending')) + '</span></li>';
      const extractCountBadge = hasMerge ? (ext.classes ?? cls) + ' classes · ' + (ext.instances ?? inst) + ' instances · ' + (ext.relations ?? rel) + ' relations' : '';
      const extractDetail = hasMerge ? ('✓ ' + extractCountBadge) : (extractCur ? 'Chunk ' + extractCur + '/' + extractTot : (progress.taxonomy ? 'Building taxonomy...' : (progress.extract ? 'Extracting...' : 'Pending')));
      html += '<li class="flex items-start gap-2">' + stepStatusSimple(hasExtract, isExtract) + '<span><strong>3. Extract</strong>: ' + extractDetail + '</span></li>';
      const hasTaxonomy = !!progress.taxonomy_done || !!progress.taxonomy_skip;
      const isTaxonomy = !!progress.taxonomy && !hasTaxonomy;
      html += '<li class="flex items-start gap-2">' + stepStatusSimple(hasTaxonomy, isTaxonomy) + '<span><strong>4. Taxonomy</strong>: ' + (hasTaxonomy ? (progress.taxonomy_skip ? 'Skipped' : 'Built') : (isTaxonomy ? 'Building...' : 'Pending')) + '</span></li>';
      const mergeDetail = hasMerge ? (ext.classes ?? cls) + ' cls, ' + (ext.instances ?? inst) + ' inst, ' + (ext.relations ?? rel) + ' rel merged' : 'Pending';
      html += '<li class="flex items-start gap-2">' + stepStatusSimple(hasMerge, false) + '<span><strong>5. Merge</strong>: ' + mergeDetail + '</span></li>';
      const infDetail = hasInference ? (progress.inference_skip ? 'Skipped' : (llmInferred > 0 ? llmInferred + ' relations inferred' : 'No new relations')) : (progress.inference ? 'Inferring relations...' : 'Pending');
      html += '<li class="flex items-start gap-2">' + stepStatusSimple(hasInference, isInference) + '<span><strong>6. Infer</strong>: ' + infDetail + '</span></li>';
      const reasonDetail = hasReasoning ? (progress.reasoning_skip ? 'Skipped' : (infEdges > 0 ? infEdges + ' relations in ' + iter + ' iterations' : 'Complete')) : (progress.reasoning ? 'Running OWL 2 RL...' : 'Pending');
      html += '<li class="flex items-start gap-2">' + stepStatusSimple(hasReasoning, isReasoning) + '<span><strong>7. Reason</strong>: ' + reasonDetail + '</span></li>';
      const rd = progress.repair_done || {};
      const repairLabel = isRepair && repairPhase ? '[' + repairPhase + ']' : '';
      const repairDetail = hasRepair ? (progress.repair_skip ? 'Skipped' : ((rd.edges_added || rd.orphans_linked || rd.components_bridged) ? (rd.edges_added || 0) + ' edges, ' + (rd.orphans_linked || 0) + ' orphans, ' + (rd.components_bridged || 0) + ' bridged' : 'Done')) : (progress.repair ? (repairLabel || 'Repairing graph...') : 'Pending');
      html += '<li class="flex items-start gap-2">' + stepStatusSimple(hasRepair, isRepair) + '<span><strong>8. Repair</strong>: ' + repairDetail + '</span></li>';
      const qualityGrade = (report.quality && report.quality.reliability_score) ? report.quality.reliability_score.grade : (job.qualityGrade || '');
      const qualityScore = (report.quality && report.quality.reliability_score) ? report.quality.reliability_score.score : (job.qualityScore ?? null);
      if (hasEnrichment || isEnrichment) {
        html += '<li class="flex items-start gap-2">' + stepStatusSimple(enrichmentDone, isEnrichment) + '<span><strong>Enrichment</strong>: ' + (enrichmentDone ? 'Done' : (isEnrichment ? 'Hierarchy enrichment...' : 'Pending')) + '</span></li>';
      }
      if (hasPopulation || isPopulation) {
        html += '<li class="flex items-start gap-2">' + stepStatusSimple(populationDone, isPopulation) + '<span><strong>Population</strong>: ' + (populationDone ? 'Done' : (isPopulation ? 'Population booster...' : 'Pending')) + '</span></li>';
      }
      const qualityDetail = hasQuality ? ('Grade ' + qualityGrade + (qualityScore != null ? ' · ' + Number(qualityScore).toFixed(2) : '')) : (isQuality ? 'Computing quality...' : 'Pending');
      html += '<li class="flex items-start gap-2">' + stepStatusSimple(hasQuality, isQuality) + '<span><strong>9. Quality</strong>: ' + qualityDetail + '</span></li>';
      html += '</ol></div>';

      if (chunkStats.length > 0) {
        html += '<div class="rounded-lg p-3" style="background:var(--bg-input); border:1px solid var(--border);">';
        html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Per-chunk Stats</p>';
        html += '<div class="font-mono text-xs overflow-x-auto" style="max-height:120px; overflow-y:auto;">';
        chunkStats.forEach((c, i) => {
          const docLabel = c.doc_index ? 'Doc ' + c.doc_index + ', ' : '';
          const line = docLabel + 'Chunk ' + ((c.chunk_index ?? i) + 1) + ': ' + (c.chunk_length ?? 0) + ' chars → ' + (c.classes ?? 0) + ' cls, ' + (c.instances ?? 0) + ' inst, ' + (c.relations ?? 0) + ' rel' + (c.axioms ? ', ' + c.axioms + ' ax' : '');
          html += '<div class="py-0.5" style="color:var(--text-muted);">' + esc(line) + '</div>';
        });
        html += '</div></div>';
      }

      const q = report.quality;
      if (q) {
        const sm = q.structural_metrics || {};
        const rs = q.reliability_score || {};
        const cr = q.consistency_report || {};
        const grade = rs.grade || '';
        const score = rs.score ?? 0;
        const criticalCount = cr.critical_count ?? 0;
        const warningCount = cr.warning_count ?? 0;
        const gradeColor = { A: 'var(--success)', B: 'var(--accent-tertiary)', C: 'var(--accent-secondary)', D: 'var(--warning)', F: 'var(--error-bright)' }[grade] || 'var(--text-muted)';
        html += '<div class="rounded-lg p-3 mt-3" style="background:var(--bg-input); border:1px solid var(--border);">';
        html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Graph Health</p>';
        html += '<div class="grid grid-cols-2 gap-2 mb-3 text-xs">';
        const totalNodes = sm.num_classes + sm.num_instances || (totals.classes || 0) + (totals.instances || 0);
        const totalEdges = totals.relations ?? rel;
        html += '<div class="rounded px-2 py-1.5" style="background:var(--bg-card); border:1px solid var(--border);"><span style="color:var(--text-muted);">Nodes</span> <span class="stat-value">' + totalNodes + '</span></div>';
        html += '<div class="rounded px-2 py-1.5" style="background:var(--bg-card); border:1px solid var(--border);"><span style="color:var(--text-muted);">Edges</span> <span class="stat-value">' + totalEdges + '</span></div>';
        html += '</div>';
        html += '<div class="flex items-center gap-2 mb-2"><span class="text-xs font-semibold" style="color:var(--text-muted);">Reliability</span> <span class="px-1.5 py-0.5 rounded text-xs font-medium" style="background:var(--success-15); color:' + gradeColor + ';">' + grade + (score ? ' · ' + Number(score).toFixed(2) : '') + '</span></div>';
        const metricBar = (label, val, greenMin, amberMin, maxVal) => {
          const v = Number(val);
          const max = maxVal != null ? maxVal : (greenMin != null ? Math.max(greenMin, 1) : 1);
          let color = 'var(--error-bright)';
          if (greenMin !== undefined && v >= greenMin) color = 'var(--success)';
          else if (amberMin !== undefined && v >= amberMin) color = 'var(--warning)';
          const pct = Math.min(100, (v / max) * 100);
          return '<div class="flex justify-between text-xs mb-1"><span style="color:var(--text-muted);">' + label + '</span><span class="font-mono">' + (typeof val === 'number' ? val.toFixed(2) : val) + '</span></div><div class="h-1.5 rounded-full overflow-hidden mb-2" style="background:var(--border-subtle);"><div class="h-full rounded-full transition-all" style="width:' + pct + '%; background:' + color + ';"></div></div>';
        };
        html += metricBar('Depth variance', sm.depth_variance ?? 0, 0.9, 0.5, 1);
        html += metricBar('Breadth variance', sm.breadth_variance ?? 0, 20, 5, 30);
        html += metricBar('Max depth', sm.max_depth ?? 0, 5, 3, 10);
        html += metricBar('Max breadth', sm.max_breadth ?? 0, 100, 30, 150);
        html += metricBar('Instance/class ratio', sm.instance_to_class_ratio ?? 0, 1.0, 0.3, 2);
        html += metricBar('Named relation ratio', sm.named_relation_ratio ?? 0, 0.3, 0.15, 1);
        if (rs.reasons && rs.reasons.length) {
          html += '<details class="mt-2"><summary class="text-xs cursor-pointer" style="color:var(--text-muted);">Score breakdown</summary><ul class="text-xs mt-1 space-y-0.5 font-mono" style="color:var(--text-muted);">';
          rs.reasons.forEach(r => { html += '<li>' + (r && r.indexOf('penalty') === -1 && r.indexOf('Low') === -1 ? '✓ ' : '✗ ') + esc(String(r)) + '</li>'; });
          html += '</ul></details>';
        }
        html += '</div>';

        const top20 = q.relation_scores_top20 || [];
        if (top20.length > 0) {
          html += '<div class="rounded-lg p-3 mt-3" style="background:var(--bg-input); border:1px solid var(--border);">';
          html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Relation Quality (top 20)</p>';
          html += '<div class="overflow-x-auto max-h-48 overflow-y-auto"><table class="w-full text-xs font-mono"><thead><tr style="color:var(--text-muted);"><th class="text-left py-1">Source</th><th class="text-left py-1">Relation</th><th class="text-left py-1">Target</th><th class="text-left py-1">Score</th><th class="text-left py-1">Votes</th><th class="text-left py-1">Path</th></tr></thead><tbody>';
          const relationTagColor = (rel) => ({ subClassOf: 'var(--accent)', instanceOf: '#a78bfa', part_of: 'var(--accent-tertiary)', depends_on: 'var(--accent-tertiary)', related_to: 'var(--text-muted-2)', produces: '#6366f1', uses: '#6366f1', has_property: '#6366f1', precedes: '#6366f1' }[rel] || 'var(--text-muted)');
          top20.slice(0, 20).forEach(row => {
            const sc = row.correctness_score ?? 0;
            const barColor = sc >= 0.6 ? 'var(--success)' : (sc >= 0.3 ? 'var(--warning)' : 'var(--error-bright)');
            const pathLen = row.derivation_path_length ?? 1;
            const pathText = pathLen === 1 ? 'direct' : 'inferred ×' + pathLen;
            html += '<tr><td class="py-0.5 pr-2">' + esc(row.source || '') + '</td><td class="py-0.5 pr-2"><span class="px-1 rounded" style="background:var(--border-subtle); color:' + relationTagColor(row.relation) + ';">' + esc(row.relation || '') + '</span></td><td class="py-0.5 pr-2">' + esc(row.target || '') + '</td><td class="py-0.5"><div class="inline-block w-12 h-1 rounded" style="background:var(--border-subtle);"><div class="h-full rounded" style="width:' + (sc * 100) + '%; background:' + barColor + ';"></div></div> ' + (sc.toFixed(2)) + '</td><td class="py-0.5">' + (row.cross_chunk_votes ?? 1) + '×</td><td class="py-0.5">' + pathText + '</td></tr>';
          });
          html += '</tbody></table></div></div>';
        }

        if (criticalCount > 0 || warningCount > 0) {
          html += '<div class="quality-conflict-section rounded-lg p-3 mt-3" style="background:var(--error-15); border:1px solid var(--error);">';
          html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--error);">⚠ ' + criticalCount + ' critical relation conflict' + (criticalCount !== 1 ? 's' : '') + ' detected</p>';
          const critList = cr.critical_conflicts || [];
          critList.slice(0, 5).forEach(c => {
            html += '<div class="text-xs mb-2 p-2 rounded" style="background:var(--bg-card); border:1px solid var(--border);"><strong>' + esc(c.entity_a || '') + '</strong> ↔ <strong>' + esc(c.entity_b || '') + '</strong> — ' + esc(c.conflict_type || '') + '<div class="mt-1 text-muted" style="color:var(--text-muted);">' + esc(c.suggested_resolution || '') + '</div></div>';
          });
          if (warningCount > 0) {
            html += '<details class="mt-2"><summary class="text-xs cursor-pointer" style="color:var(--warning);">' + warningCount + ' warning(s)</summary>';
            (cr.warning_conflicts || []).slice(0, 3).forEach(c => {
              html += '<div class="text-xs mt-1 p-2 rounded" style="background:var(--bg-card); border:1px solid var(--warning);">' + esc(c.entity_a || '') + ' ↔ ' + esc(c.entity_b || '') + ' — ' + esc(c.suggested_resolution || '') + '</div>';
            });
            html += '</details>';
          }
          html += '</div>';
        } else if (cr.is_consistent !== false) {
          html += '<div class="rounded-lg p-3 mt-3" style="background:var(--success-15); border:1px solid var(--success);"><p class="text-xs font-medium" style="color:var(--success);">✓ No conflicts</p></div>';
        }

        const actions = q.recommended_actions || [];
        html += '<div class="rounded-lg p-3 mt-3" style="background:var(--bg-input); border:1px solid var(--border);">';
        html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Recommended Actions</p>';
        if (actions.length === 0) {
          html += '<p class="text-xs" style="color:var(--success);">0 actions needed</p>';
        } else {
          actions.forEach((action, i) => {
            const isCritical = /critical|conflict/i.test(action);
            const isRec = /Enable|Re-run|consider/i.test(action) && !isCritical;
            const borderColor = isCritical ? 'var(--error)' : (isRec ? 'var(--warning)' : 'var(--border)');
            html += '<div class="flex items-start gap-2 mb-2 p-2 rounded" style="border:1px solid ' + borderColor + ';"><span class="shrink-0">' + (isCritical ? '⚠' : '🔧') + '</span><span class="text-xs" style="color:var(--text-primary);">' + esc(action) + '</span></div>';
          });
        }
        html += '</div>';
      }

      const violations = reasoning.consistency_violations || [];
      if (violations.length > 0) {
        html += '<div class="rounded-lg p-3" style="background:var(--error-15); border:1px solid var(--error);">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--error);">Consistency Violations</p>';
        html += '<ul class="text-xs font-mono space-y-1" style="color:var(--text-primary);">';
        violations.forEach(v => { html += '<li>' + esc(String(v)) + '</li>'; });
        html += '</ul></div>';
      }

      html += '</div>';
      jobDetailContent.innerHTML = html;
      jobDetailModal.classList.remove('hidden');
    }

    function hideJobDetailModal() {
      _modalJob = null;
      jobDetailModal.classList.add('hidden');
    }

    document.getElementById('job-detail-close')?.addEventListener('click', hideJobDetailModal);
    jobDetailModal?.querySelector('.modal-backdrop')?.addEventListener('click', hideJobDetailModal);

    function setJobStatus(job, status, label) {
      job.status = status;
      if (!job.card) return;
      const typeClass = job.jobType === 'create' ? 'job-create' : 'job-extend';
      job.card.className = 'job-card job-clickable ' + typeClass + ' ' + status;
      const sl = job.card.querySelector('.stage-label');
      if (sl) sl.textContent = label;
      const cancelBtn = job.card.querySelector('.job-cancel');
      if (cancelBtn && (status === 'done' || status === 'error' || status === 'cancelled')) {
        cancelBtn.style.display = 'none';
      }
      if (_kbData && _kbData.length) renderKbList(_kbData, _activeKbId);
      if (status === 'done' && job.pipeline_report) {
        const report = job.pipeline_report;
        const totals = report.totals || report.extraction_totals || {};
        const cls = totals.classes ?? 0, inst = totals.instances ?? 0, rel = totals.relations ?? 0;
        const elapsed = report.elapsed_seconds ?? 0;
        const metricsEl = job.card.querySelector('.job-metrics');
        if (metricsEl) {
          let txt = cls + ' cls, ' + inst + ' inst, ' + rel + ' rel';
          if (elapsed > 0) txt += ' · ' + elapsed.toFixed(1) + 's';
          metricsEl.textContent = txt;
        }
      }
    }

    async function cancelJob(job) {
      if (job.serverJobId) {
        try { await fetch(API + '/cancel_job/' + job.serverJobId, { method: 'POST' }); } catch(e) {}
      }
      if (job.abortController) job.abortController.abort();
    }

    function removeJobCard(job, delay) {
      setTimeout(() => {
        if (!job.card) return;
        job.card.classList.add('removing');
        setTimeout(() => {
          job.card.remove();
          const idx = jobs.indexOf(job);
          if (idx > -1) jobs.splice(idx, 1);
          if (_kbData && _kbData.length) renderKbList(_kbData, _activeKbId);
        }, 300);
      }, delay || 0);
    }

    async function doUpload(files, title, description, parallel = true) {
      const fileList = Array.isArray(files) ? files : [files];
      const first = fileList[0];
      const job = {
        localId: Date.now(),
        title: title || (first?.name ?? 'Documents'),
        description: description || (fileList.length > 1 ? fileList.length + ' files' : first?.name ?? ''),
        status: 'running',
        serverJobId: null,
        abortController: new AbortController(),
        card: null,
        jobType: 'create',
      };
      jobs.push(job);
      job.card = createJobCard(job);
      if (jobQueue) jobQueue.appendChild(job.card);
      if (jobQueueSection) jobQueueSection.classList.remove('collapsed');
      setStatusBadge('processing');
      tabDocuments?.click();

      const fd = new FormData();
      if (fileList.length === 1) {
        fd.append('file', fileList[0]);
      } else {
        fileList.forEach(f => fd.append('files', f));
      }
      if (title) fd.append('title', title);
      if (description) fd.append('description', description);
      try {
        const parallelParam = parallel ? 'true' : 'false';
        const res = await fetch(API + '/build_ontology_stream?run_inference=true&sequential=true&run_reasoning=true&parallel=' + parallelParam, {
          method: 'POST',
          body: fd,
          signal: job.abortController.signal,
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(parseError(data) || res.statusText);
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let result = null;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split('\n\n');
          buffer = parts.pop() || '';
          for (const part of parts) {
            const line = part.split('\n').find(l => l.startsWith('data: '));
            if (!line) continue;
            try {
              const ev = JSON.parse(line.slice(6));
              if (ev.type === 'job_started') { job.serverJobId = ev.job_id; job.extraction_mode = ev.extraction_mode; continue; }
              if (ev.type === 'error') throw new Error(ev.message || 'Pipeline failed');
              if (ev.type === 'complete') { result = ev; job.pipeline_report = ev.pipeline_report; break; }
              if (ev.step) updateJobStage(job, ev);
            } catch (e) {
              if (e instanceof SyntaxError) continue;
              throw e;
            }
          }
          if (result) break;
        }
        if (result) {
          job.kbId = result.kb_id;
          setJobStatus(job, 'done', 'Complete');
          await loadKBs();
          if (result.kb_id) setActiveKbId(result.kb_id);
          if (result.pipeline_report && result.kb_id) appendOntologySummary(result.pipeline_report, result.kb_id);
          removeJobCard(job, 3000);
          if (kbStatus) { kbStatus.style.display = 'none'; }
        }
      } catch (e) {
        if (e.name === 'AbortError') {
          setJobStatus(job, 'cancelled', 'Cancelled');
        } else {
          setJobStatus(job, 'error', e.message);
          if (kbStatus) { kbStatus.textContent = 'Job failed: ' + e.message; kbStatus.style.display = ''; kbStatus.style.color = 'var(--error)'; }
        }
        removeJobCard(job, 4000);
      } finally {
        const hasRunning = jobs.some(j => j.status === 'running');
        if (!hasRunning) setStatusBadge(getActiveKbId() ? 'ready' : 'empty');
      }
    }

    async function doExtend(files, kbId, parallel = true) {
      const fileList = Array.isArray(files) ? files : [files];
      const activeKb = _kbData.find(k => k.id === kbId);
      const kbName = activeKb ? activeKb.name : kbId;
      const first = fileList[0];
      const job = {
        localId: Date.now(),
        title: 'Adding to ' + kbName,
        description: fileList.length > 1 ? fileList.length + ' files' : (first?.name ?? ''),
        status: 'running',
        serverJobId: null,
        abortController: new AbortController(),
        card: null,
        kbId: kbId,
        jobType: 'extend',
      };
      jobs.push(job);
      job.card = createJobCard(job);
      if (jobQueue) jobQueue.appendChild(job.card);
      if (jobQueueSection) jobQueueSection.classList.remove('collapsed');
      setStatusBadge('processing');
      tabDocuments?.click();
      if (_kbData && _kbData.length) renderKbList(_kbData, _activeKbId);
      if (activeKb) renderOntologyCard(activeKb);

      const fd = new FormData();
      if (fileList.length === 1) {
        fd.append('file', fileList[0]);
      } else {
        fileList.forEach(f => fd.append('files', f));
      }
      try {
        const parallelParam = parallel ? 'true' : 'false';
        const res = await fetch(API + '/knowledge-bases/' + kbId + '/extend_stream?run_inference=true&sequential=true&run_reasoning=true&parallel=' + parallelParam, {
          method: 'POST',
          body: fd,
          signal: job.abortController.signal,
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(parseError(data) || res.statusText);
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let result = null;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split('\n\n');
          buffer = parts.pop() || '';
          for (const part of parts) {
            const line = part.split('\n').find(l => l.startsWith('data: '));
            if (!line) continue;
            try {
              const ev = JSON.parse(line.slice(6));
              if (ev.type === 'job_started') { job.serverJobId = ev.job_id; job.extraction_mode = ev.extraction_mode; continue; }
              if (ev.type === 'error') throw new Error(ev.message || 'Pipeline failed');
              if (ev.type === 'complete') { result = ev; job.pipeline_report = ev.pipeline_report; break; }
              if (ev.step) updateJobStage(job, ev);
            } catch (e) {
              if (e instanceof SyntaxError) continue;
              throw e;
            }
          }
          if (result) break;
        }
        if (result) {
          setJobStatus(job, 'done', 'Merged');
          await loadKBs();
          if (result.kb_id) setActiveKbId(result.kb_id);
          if (result.pipeline_report && result.kb_id) appendOntologySummary(result.pipeline_report, result.kb_id);
          removeJobCard(job, 3000);
        }
      } catch (e) {
        if (e.name === 'AbortError') {
          setJobStatus(job, 'cancelled', 'Cancelled');
        } else {
          setJobStatus(job, 'error', e.message);
        }
        removeJobCard(job, 4000);
      } finally {
        const hasRunning = jobs.some(j => j.status === 'running');
        if (!hasRunning) setStatusBadge(getActiveKbId() ? 'ready' : 'empty');
      }
    }

    // Suggestion button hover effect
    document.querySelectorAll('.suggestion-btn').forEach(btn => {
      btn.addEventListener('mouseenter', () => {
        btn.style.borderColor = 'var(--accent-3)';
        btn.style.background = 'var(--accent-05)';
      });
      btn.addEventListener('mouseleave', () => {
        btn.style.borderColor = 'var(--border)';
        btn.style.background = 'var(--bg-card)';
      });
    });

    function showNewChatModal() {
      const modal = document.getElementById('new-chat-modal');
      const listEl = document.getElementById('new-chat-kb-list');
      if (!listEl) return;
      listEl.innerHTML = '';
      if (_kbData.length === 0) {
        listEl.innerHTML = '<p class="text-sm py-4 text-center" style="color:var(--text-muted);">No knowledge bases. Create one first.</p>';
      } else {
        for (const kb of _kbData) {
          const stats = kb.stats || {};
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
          btn.style.cssText = 'background:var(--bg-input); border:1px solid var(--border); color:var(--text-primary);';
          btn.innerHTML = '<div class="min-w-0"><p class="font-medium truncate text-sm">' + esc(kb.name || kb.id) + '</p><p class="text-xs mt-0.5 truncate" style="color:var(--text-muted);">' + esc(summary) + '</p></div>'
            + (isActive ? '<span class="text-xs shrink-0 px-1.5 py-0.5 rounded" style="background:var(--accent-25);color:var(--accent);">Active</span>' : '');
          btn.addEventListener('click', () => {
            logClick('new-chat-select', kb.id);
            createNewChat(kb.id);
            modal.classList.add('hidden');
          });
          listEl.appendChild(btn);
        }
      }
      modal.classList.remove('hidden');
    }

    document.getElementById('new-chat-btn')?.addEventListener('click', () => {
      logClick('new-chat', 'open');
      showNewChatModal();
    });
    document.getElementById('new-chat-modal-cancel')?.addEventListener('click', () => {
      document.getElementById('new-chat-modal').classList.add('hidden');
    });
    document.getElementById('new-chat-modal')?.querySelector('.modal-backdrop')?.addEventListener('click', () => {
      document.getElementById('new-chat-modal').classList.add('hidden');
    });
    sidebarToggle?.addEventListener('click', () => { logClick('sidebar', 'toggle'); sidebar?.classList.toggle('open'); });
    document.getElementById('sidebar-overlay')?.addEventListener('click', () => sidebar?.classList.remove('open'));

    if (window.matchMedia('(min-width: 769px)').matches) {
      sidebar?.classList.add('open');
    }

    // Ensure graph viewer links use current origin (fixes about:blank when opened in new tab)
    const viewerUrl = window.location.origin + API + '/graph/viewer';
    document.querySelectorAll('a.graph-viewer-link').forEach(function(a) { a.href = viewerUrl; });

    (async function init() {
      logClick('init', 'start');
      try {
        await loadKBs();
        logClick('init', 'loadKBs done, count=' + (_kbData?.length ?? 0));
        const params = new URLSearchParams(window.location.search);
        const urlKbId = params.get('kb_id');
        if (urlKbId && _kbData.some(k => k.id === urlKbId) && urlKbId !== getActiveKbId()) {
          try { await activateKB(urlKbId); } catch (_) {}
          history.replaceState(null, '', window.location.pathname);
        }
      } catch (e) {
        console.error('[init]', e);
        if (statusBadge) { statusBadge.textContent = 'Error loading'; statusBadge.className = 'status-badge px-2 py-0.5 rounded-full text-xs font-medium empty'; }
      }
    })();
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') loadKBs(); });
