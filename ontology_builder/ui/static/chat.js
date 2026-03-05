let _kbData = [];

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
    const tabKnowledgeContent = document.getElementById('tab-knowledge-content');
    const tabDocumentsContent = document.getElementById('tab-documents-content');
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
            chip.style.color = '#8a8a94';
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
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'chat-tab shrink-0' + (c.id === _activeChatId ? ' active' : '');
        btn.textContent = (c.kbName || 'Chat').substring(0, 20) + (c.messages.length ? ' (' + c.messages.length + ')' : '');
        btn.title = c.kbName + (c.messages.length ? ' · ' + c.messages.length + ' messages' : '');
        btn.addEventListener('click', () => switchToChat(c.id));
        container.appendChild(btn);
      });
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
      if (readyEl) { readyEl.classList.remove('hidden'); readyEl.classList.add('flex'); }
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
        chip.style.cssText = 'background:#14141a; border:1px solid #1a1a24;';
        chip.innerHTML = '<p class="stat-value text-base font-semibold">' + fmtNum(val) + '</p>'
          + '<p class="text-xs mt-0.5 stat-label">' + label + '</p>';
        chatStatsGrid.appendChild(chip);
      });

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
        chip.style.cssText = 'background:#14141a; border:1px solid #1a1a24; color:#8a8a94;';
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
      if (!res.ok) return { items: [], active_id: null };
      return res.json();
    }

    function renderKbList(items, activeId) {
      kbList.innerHTML = '';
      kbList.classList.toggle('kb-list-scrollable', items.length > 10);
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
        const card = document.createElement('div');
        card.className = 'kb-list-card rounded-lg px-3 py-2.5 border flex flex-col gap-2' + (isActive ? ' active' : '');
        card.style.background = isActive ? 'rgba(236,72,153,0.08)' : 'rgba(20, 20, 26, 0.9)';
        card.style.borderColor = isActive ? 'rgba(236,72,153,0.5)' : '#2a2a3a';
        card.dataset.kbId = kb.id;
        const viewerUrl = window.location.origin + API + '/graph/viewer?kb_id=' + encodeURIComponent(kb.id);
        const statusBadge = status === 'building'
          ? '<span class="flex items-center gap-1 text-xs font-medium shrink-0" style="color:#f59e0b;"><span class="kb-building-dot"></span>Building</span>'
          : '<span class="kb-ready-badge flex items-center gap-1 text-xs font-medium shrink-0" style="color:#22c55e;"><span class="kb-ready-dot"></span>Ready</span>';
        card.innerHTML = '<div class="flex items-center gap-2.5 min-w-0">'
          + '<div class="flex-1 min-w-0">'
          + '<p class="text-sm font-medium truncate" style="color:#e8e6e3;">' + esc(kb.name || kb.id) + '</p>'
          + '<p class="text-xs truncate mt-0.5" style="color:#8a8a94;">' + esc(summary) + '</p></div>'
          + statusBadge
          + '<a href="' + viewerUrl + '" target="_blank" rel="noopener noreferrer" class="text-xs font-medium shrink-0 link-teal opacity-70 hover:opacity-100" onclick="event.stopPropagation()">Open</a>'
          + '</div>'
          + '<div class="flex items-center gap-2" onclick="event.stopPropagation()">'
          + '<button type="button" class="kb-new-chat-btn text-xs font-medium px-2 py-1 rounded transition-colors shrink-0" style="color:#8a8a94; background:#1a1a24;">+ New chat</button>'
          + '</div>';
        card.querySelector('.kb-new-chat-btn').addEventListener('click', (e) => {
          e.stopPropagation();
          createNewChat(kb.id);
        });
        card.addEventListener('click', async (e) => {
          if (e.target.closest('a') || e.target.closest('button')) return;
          const existing = _chats.find(c => c.kbId === kb.id);
          if (existing) {
            await switchToChat(existing.id);
          } else {
            createNewChat(kb.id);
            await switchToChat(_activeChatId);
          }
        });
        kbList.appendChild(card);
      }
    }

    async function loadKBs() {
      const data = await fetchKBs();
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

    if (kbCreateBtn && fileInputCreate) kbCreateBtn.addEventListener('click', () => fileInputCreate.click());

    tabKnowledge?.addEventListener('click', () => {
      tabKnowledge.classList.add('sidebar-tab-active');
      tabKnowledge.classList.remove('sidebar-tab-inactive');
      tabDocuments?.classList.remove('sidebar-tab-active');
      tabDocuments?.classList.add('sidebar-tab-inactive');
      tabKnowledgeContent?.classList.remove('hidden');
      tabDocumentsContent?.classList.add('hidden');
    });
    tabDocuments?.addEventListener('click', () => {
      tabDocuments?.classList.add('sidebar-tab-active');
      tabDocuments?.classList.remove('sidebar-tab-inactive');
      tabKnowledge?.classList.remove('sidebar-tab-active');
      tabKnowledge?.classList.add('sidebar-tab-inactive');
      tabDocumentsContent?.classList.remove('hidden');
      tabKnowledgeContent?.classList.add('hidden');
    });

    if (jobQueueToggle && jobQueueSection) {
      jobQueueToggle.addEventListener('click', () => jobQueueSection.classList.toggle('collapsed'));
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
        .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded text-xs font-mono" style="background:#14141a;border:1px solid #1a1a24;color:#e8e6e3;">$1</code>')
        .replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>')
        .replace(/\\*([^*]+)\\*/g, '<em>$1</em>')
        .replace(/\\[([a-zA-Z_][a-zA-Z0-9_\\-]*:[^\\]\\n]+)\\]/g, '<span class="px-1.5 py-0.5 rounded text-xs font-mono align-middle" style="background:rgba(236,72,153,0.1); color:#ec4899;">[$1]</span>');
    }

    function renderAssistantGuide(content) {
      const wrapper = document.createElement('div');
      wrapper.className = 'space-y-2.5';
      const lines = String(content || '').split('\\n');
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
          h4.style.color = '#e8e6e3';
          h4.innerHTML = renderInlineMarkdown(trimmed.slice(4));
          wrapper.appendChild(h4);
          return;
        }

        if (trimmed.startsWith('## ')) {
          flushParagraph();
          flushList();
          const h3 = document.createElement('h3');
          h3.className = 'text-base font-semibold mt-1';
          h3.style.color = '#ec4899';
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

    function buildMessageElement(role, content, sources, numFactsUsed) {
      const div = document.createElement('div');
      div.dataset.chatMessage = '1';
      div.className = 'flex ' + (role === 'user' ? 'justify-end msg-enter-user' : 'justify-start msg-enter-assistant');
      const bubble = document.createElement('div');
      bubble.className = 'msg-bubble max-w-[85%] rounded-xl px-4 py-3.5 ' +
        (role === 'user' ? 'msg-user-bubble' : 'bubble-assistant');
      bubble.style.background = role === 'user' ? '#ec4899' : '#1e1e28';
      bubble.style.color = role === 'user' ? '#fff' : '#e8e6e3';
      bubble.style.border = '1px solid ' + (role === 'user' ? 'rgba(236,72,153,0.6)' : '#1a1a24');

      if (role === 'assistant') {
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
        if (numFactsUsed > 0) {
          const factsBadge = document.createElement('span');
          factsBadge.className = 'text-xs px-1.5 py-0.5 rounded font-mono';
          factsBadge.style.cssText = 'background:rgba(236,72,153,0.1); color:#ec4899;';
          factsBadge.textContent = numFactsUsed + ' facts';
          metaRow.appendChild(factsBadge);
        }
        bubble.appendChild(metaRow);

        // Reasoning block
        const hasReasoning = (numFactsUsed !== undefined && numFactsUsed > 0) || (sources && sources.length > 0);
        if (hasReasoning) {
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
          steps.forEach(s => {
            const p = document.createElement('p');
            p.textContent = s;
            reasonContent.appendChild(p);
          });
          reasonDiv.appendChild(reasonContent);
          bubble.appendChild(reasonDiv);
        }
      }

      const text = document.createElement('div');
      text.className = 'whitespace-pre-wrap text-sm leading-relaxed';
      if (typeof content === 'string') {
        if (role === 'assistant') {
          text.className = 'text-sm leading-relaxed';
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
        srcDiv.style.borderTop = '1px solid #1a1a24';
        sources.slice(0, 5).forEach(ref => {
          const tag = document.createElement('span');
          tag.className = 'px-2 py-0.5 rounded text-xs font-mono';
          tag.style.cssText = 'background:rgba(236,72,153,0.1); color:#ec4899;';
          tag.textContent = ref;
          srcDiv.appendChild(tag);
        });
        if (sources.length > 5) {
          const more = document.createElement('span');
          more.className = 'text-xs';
          more.style.color = '#555';
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
      bubble.style.cssText = 'background:#1e1e28; color:#e8e6e3; border:1px solid #1a1a24;';

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
      const keyMap = { 'Classes': 'classes', 'Instances': 'instances', 'Relations': 'relations', 'Axioms': 'axioms', 'Data Props': 'data_properties' };
      statItems.forEach(([label, val]) => {
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
      });
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
        detailsDiv.style.cssText = 'background:#0a0a0f; border:1px solid #1a1a24; max-height:120px; overflow-y:auto;';
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
          el = buildMessageElement(m.role, m.content, m.sources, m.numFactsUsed);
        }
        if (el) messagesEl.insertBefore(el, insertBefore);
      });
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function appendMessage(role, content, sources, numFactsUsed, chatId) {
      let chat = chatId ? getChatById(chatId) : getActiveChat();
      if (!chat) {
        if (chatId) return;
        if (!getActiveKbId()) return;
        chat = createNewChat();
      }
      chat.messages.push({ role, content, sources, numFactsUsed });
      if (chat.id === _activeChatId) {
        hideEmptyStates();
        const el = buildMessageElement(role, content, sources, numFactsUsed);
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
        qaDots.forEach((d, i) => { d.style.background = i === 0 ? '#ec4899' : '#1a1a24'; });
        qaStepInterval = setInterval(() => {
          const idx = QA_STEPS.indexOf(qaLabel.textContent);
          const next = (idx + 1) % QA_STEPS.length;
          qaLabel.textContent = QA_STEPS[next];
          qaDots.forEach((d, i) => { d.style.background = i === next ? '#ec4899' : '#1a1a24'; });
        }, 1800);
      } else {
        if (qaStepInterval) { clearInterval(qaStepInterval); qaStepInterval = null; }
      }
    }

    chatForm.addEventListener('submit', async (e) => {
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
        appendMessage('assistant', data.answer, sourceTags, data.num_facts_used, submitChatId);
      } catch (e) {
        const msg = e && e.name === 'AbortError'
          ? 'Request timed out. The model may be overloaded; try again.'
          : e.message;
        appendMessage('assistant', 'Error: ' + msg, null, null, submitChatId);
      } finally {
        clearTimeout(timeoutId);
        showLoading(false);
        setInputsEnabled(true);
      }
    });

    // Upload
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
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

    function showCreateModal(file) {
      pendingFile = file;
      const stem = file.name.replace(/\\.[^.]+$/, '') || file.name;
      modalTitle.value = stem;
      modalDescription.value = '';
      modalFilename.textContent = 'File: ' + file.name;

      const activeId = getActiveKbId();
      if (activeId) {
        const activeKb = _kbData.find(k => k.id === activeId);
        const kbName = activeKb ? activeKb.name : activeId;
        document.getElementById('modal-mode-kb-name').textContent = kbName;
        modalModeSection.classList.remove('hidden');
        setModalMode('extend');
      } else {
        modalModeSection.classList.add('hidden');
        setModalMode('new');
      }

      createModal.classList.remove('hidden');
      if (_modalMode === 'new') modalTitle.focus();
    }

    function hideCreateModal() {
      createModal.classList.add('hidden');
      pendingFile = null;
    }

    modalCancel.addEventListener('click', hideCreateModal);
    createModal.querySelector('.modal-backdrop').addEventListener('click', hideCreateModal);

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

    document.getElementById('delete-modal-cancel').addEventListener('click', () => {
      deleteModal.classList.add('hidden');
      _pendingDeleteId = null;
    });
    deleteModal.querySelector('.modal-backdrop').addEventListener('click', () => {
      deleteModal.classList.add('hidden');
      _pendingDeleteId = null;
    });
    document.getElementById('delete-modal-confirm').addEventListener('click', async () => {
      if (!_pendingDeleteId) return;
      const idToDelete = _pendingDeleteId;
      deleteModal.classList.add('hidden');
      _pendingDeleteId = null;
      try {
        const res = await fetch(API + '/knowledge-bases/' + idToDelete, { method: 'DELETE' });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(parseError(data) || res.statusText);
        }
        await loadKBs();
        kbStatus.style.display = 'none';
      } catch (e) {
        kbStatus.textContent = 'Delete failed: ' + e.message;
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
    }

    function hideKbSummaryModal() {
      kbSummaryModal.classList.add('hidden');
      delete kbSummaryModal.dataset.kbId;
    }

    document.getElementById('kb-summary-close').addEventListener('click', hideKbSummaryModal);
    kbSummaryModal.querySelector('.modal-backdrop').addEventListener('click', hideKbSummaryModal);
    document.getElementById('kb-summary-cancel').addEventListener('click', hideKbSummaryModal);
    document.getElementById('kb-summary-save').addEventListener('click', async () => {
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
    let _ontoCardExpanded = true;
    if (ontoCard) {
      ontoCardExpandBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        _ontoCardExpanded = !_ontoCardExpanded;
        ontoCard.classList.toggle('collapsed', !_ontoCardExpanded);
      });
      ontoCard.addEventListener('click', (e) => {
        if (e.target.closest('#onto-card-expand-btn') || e.target.closest('a') || e.target.closest('button')) return;
        showKbSummaryModal();
      });
    }

    // Job details modal
    const jobDetailModal = document.getElementById('job-detail-modal');
    const jobDetailContent = document.getElementById('job-detail-content');
    const jobDetailTitle = document.getElementById('job-detail-title');

    modalConfirm.addEventListener('click', () => {
      if (pendingFile) {
        const parallel = _modalMode === 'extend'
          ? document.getElementById('modal-parallel-extend').checked
          : document.getElementById('modal-parallel').checked;
        if (_modalMode === 'extend') {
          const activeId = getActiveKbId();
          if (activeId) {
            doExtend(pendingFile, activeId, parallel);
            hideCreateModal();
            return;
          }
        }
        const title = modalTitle.value.trim() || pendingFile.name.replace(/\\.[^.]+$/, '');
        const description = modalDescription.value.trim();
        doUpload(pendingFile, title, description, parallel);
        hideCreateModal();
      }
    });

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      const files = e.dataTransfer?.files;
      if (files?.length) {
        const activeId = getActiveKbId();
        if (activeId) {
          doExtend(files[0], activeId, true);
        } else {
          kbStatus.textContent = 'Select a KB in the Knowledge tab first.';
          kbStatus.style.display = '';
        }
      }
    });
    fileInput.addEventListener('change', () => {
      if (fileInput.files?.length) {
        const activeId = getActiveKbId();
        if (activeId) {
          doExtend(fileInput.files[0], activeId, true);
        } else {
          kbStatus.textContent = 'Select a KB in the Knowledge tab first.';
          kbStatus.style.display = '';
        }
        fileInput.value = '';
      }
    });
    if (fileInputCreate) fileInputCreate.addEventListener('change', () => {
      if (fileInputCreate.files?.length) {
        const file = fileInputCreate.files[0];
        const title = file.name.replace(/\\.[^.]+$/, '') || file.name;
        doUpload(file, title, '', true);
        fileInputCreate.value = '';
      }
    });

    const jobs = [];

    function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

    function createJobCard(job) {
      job.progress = job.progress || {};
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
        + '</div>'
        + '<div class="job-metrics text-xs font-mono mt-1" style="color:#6b6b76; min-height:1em;"></div>';
      card.querySelector('.job-cancel').addEventListener('click', (e) => { e.stopPropagation(); cancelJob(job); });
      card.addEventListener('click', (e) => { if (!e.target.closest('.job-cancel')) showJobDetailModal(job); });
      return card;
    }

    let _modalJob = null;

    function updateJobStage(job, ev) {
      const step = ev.step;
      const d = ev.data || ev;
      if (!job.progress) job.progress = {};
      job.progress[step] = d;
      if (!job.liveMetrics) job.liveMetrics = { classes: 0, instances: 0, relations: 0, axioms: 0, data_properties: 0 };
      if (step === 'extract') {
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
      }
      const label = job.card?.querySelector('.stage-label');
      if (label) {
        const chunksDone = step === 'extract' ? (job.chunksCompleted || 0) : (job.chunksCompleted || 0);
        const chunksTotal = job.chunksTotal ?? d.total ?? 0;
        const stageMap = {
          'load': 'Loading...', 'load_done': 'Loaded',
          'chunk': 'Chunking...', 'chunk_done': (d.total_chunks || 0) + ' chunks',
          'extract': chunksTotal > 0 ? chunksDone + ' of ' + chunksTotal + ' chunks' : 'Extracting...',
          'merge_done': 'Merged',
          'taxonomy': 'Building taxonomy...', 'taxonomy_done': 'Taxonomy built', 'taxonomy_skip': 'Skipped taxonomy',
          'inference': 'Inferring...', 'inference_done': 'Inferred',
          'inference_skip': 'Skipped inference',
          'reasoning': 'Reasoning...', 'reasoning_done': 'Reasoned',
          'reasoning_skip': 'Skipped reasoning',
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

      if (chunkStats.length > 0) {
        html += '<div class="rounded-lg p-3" style="background:#14141a; border:1px solid #1a1a24;">';
        html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:#8a8a94;">Per-chunk Stats</p>';
        html += '<div class="font-mono text-xs overflow-x-auto" style="max-height:120px; overflow-y:auto;">';
        chunkStats.forEach((c, i) => {
          const line = 'Chunk ' + (i + 1) + ': ' + (c.chunk_length ?? 0) + ' chars → ' + (c.classes ?? 0) + ' cls, ' + (c.instances ?? 0) + ' inst, ' + (c.relations ?? 0) + ' rel' + (c.axioms ? ', ' + c.axioms + ' ax' : '');
          html += '<div class="py-0.5" style="color:#8a8a94;">' + esc(line) + '</div>';
        });
        html += '</div></div>';
      }

      const violations = reasoning.consistency_violations || [];
      if (violations.length > 0) {
        html += '<div class="rounded-lg p-3" style="background:#1a1414; border:1px solid #3a2424;">';
        html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:#ef4444;">Consistency Violations</p>';
        html += '<ul class="text-xs font-mono space-y-1" style="color:#e8e6e3;">';
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
      job.card.className = 'job-card ' + status;
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

    async function doUpload(file, title, description, parallel = true) {
      const job = {
        localId: Date.now(),
        title: title || file.name,
        description: description || '',
        status: 'running',
        serverJobId: null,
        abortController: new AbortController(),
        card: null,
      };
      jobs.push(job);
      job.card = createJobCard(job);
      jobQueue.appendChild(job.card);
      setStatusBadge('processing');
      tabDocuments?.click();

      const fd = new FormData();
      fd.append('file', file);
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
          const parts = buffer.split('\\n\\n');
          buffer = parts.pop() || '';
          for (const part of parts) {
            const line = part.split('\\n').find(l => l.startsWith('data: '));
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

    async function doExtend(file, kbId, parallel = true) {
      const activeKb = _kbData.find(k => k.id === kbId);
      const kbName = activeKb ? activeKb.name : kbId;
      const job = {
        localId: Date.now(),
        title: 'Adding to ' + kbName,
        description: file.name,
        status: 'running',
        serverJobId: null,
        abortController: new AbortController(),
        card: null,
        kbId: kbId,
      };
      jobs.push(job);
      job.card = createJobCard(job);
      jobQueue.appendChild(job.card);
      setStatusBadge('processing');
      tabDocuments?.click();
      if (_kbData && _kbData.length) renderKbList(_kbData, _activeKbId);

      const fd = new FormData();
      fd.append('file', file);
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
          const parts = buffer.split('\\n\\n');
          buffer = parts.pop() || '';
          for (const part of parts) {
            const line = part.split('\\n').find(l => l.startsWith('data: '));
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
        btn.style.borderColor = 'rgba(236,72,153,0.3)';
        btn.style.background = 'rgba(236,72,153,0.04)';
      });
      btn.addEventListener('mouseleave', () => {
        btn.style.borderColor = '#2a2a3a';
        btn.style.background = '#1e1e28';
      });
    });

    document.getElementById('new-chat-btn')?.addEventListener('click', () => {
      if (!getActiveKbId()) {
        kbStatus.textContent = 'Select a KB first.';
        kbStatus.style.display = '';
        return;
      }
      createNewChat();
    });
    sidebarToggle?.addEventListener('click', () => sidebar.classList.toggle('open'));
    document.getElementById('sidebar-overlay')?.addEventListener('click', () => sidebar.classList.remove('open'));

    if (window.matchMedia('(min-width: 769px)').matches) {
      sidebar.classList.add('open');
    }

    // Ensure graph viewer links use current origin (fixes about:blank when opened in new tab)
    const viewerUrl = window.location.origin + API + '/graph/viewer';
    document.querySelectorAll('a.graph-viewer-link').forEach(function(a) { a.href = viewerUrl; });

    (async function init() {
      await loadKBs();
      const params = new URLSearchParams(window.location.search);
      const urlKbId = params.get('kb_id');
      if (urlKbId && _kbData.some(k => k.id === urlKbId) && urlKbId !== getActiveKbId()) {
        try { await activateKB(urlKbId); } catch (_) {}
        history.replaceState(null, '', window.location.pathname);
      }
    })();
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') loadKBs(); });