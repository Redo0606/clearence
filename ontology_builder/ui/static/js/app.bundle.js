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
    const loadingIndicator = document.getElementById('loading-indicator');
    const chatForm = document.getElementById('chat-form');
    const questionInput = document.getElementById('question-input');
    const sendBtn = document.getElementById('send-btn');
    const kbList = document.getElementById('kb-list');
    const kbCreateBtn = document.getElementById('kb-create-btn');
    const fileInputCreate = document.getElementById('file-input-create');
    const tabDocuments = document.getElementById('tab-documents');
    const tabEvaluate = document.getElementById('tab-evaluate');
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
    const currentOntologyStatusBadge = document.getElementById('current-ontology-status-badge');
    const currentOntologyDocsCount = document.getElementById('current-ontology-docs-count');
    const currentOntologyReadyBadge = document.getElementById('current-ontology-ready-badge');
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
        const kb = _kbData.find(k => k.id === chat.kbId);
        if (kb) {
          currentOntologyPill.classList.remove('hidden');
          currentOntologyPill.classList.add('flex');
          currentOntologyName.textContent = kb.name || kb.id;
          const stats = kb.stats || {};
          const relCount = stats.relations ?? stats.edges ?? 0;
          const docs = kb.documents || [];
          const docCount = docs.length;
          const status = getKbStatus(chat.kbId);
          const statParts = [
            fmtNum(stats.classes ?? 0) + ' Classes',
            fmtNum(stats.instances ?? 0) + ' Instances',
            fmtNum(relCount) + ' Relations'
          ];
          const statParts2 = [
            fmtNum(stats.axioms ?? 0) + ' Axioms',
            fmtNum(stats.data_properties ?? 0) + ' Data Props'
          ];
          currentOntologyStats.textContent = statParts.join(' · ') + '  |  ' + statParts2.join(' · ');
          if (currentOntologyDocsCount) currentOntologyDocsCount.textContent = fmtNum(docCount) + ' Documents';
          if (currentOntologyStatusBadge) {
            currentOntologyStatusBadge.textContent = status === 'building' ? '● Building' : '';
            currentOntologyStatusBadge.classList.toggle('hidden', status !== 'building');
            if (status === 'building') currentOntologyStatusBadge.style.cssText = 'color:var(--warning); background:var(--warning-15);';
          }
          if (currentOntologyReadyBadge) {
            currentOntologyReadyBadge.classList.toggle('hidden', status !== 'ready');
          }
        }
      } else {
        currentOntologyPill.classList.add('hidden');
        currentOntologyPill.classList.remove('flex');
      }
    }

    const graphIconSvg = '<svg class="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><circle cx="12" cy="6" r="2"/><circle cx="7" cy="16" r="2"/><circle cx="17" cy="16" r="2"/><path stroke-linecap="round" d="M12 8v4M8.5 14.5l-2 2M15.5 14.5l2 2"/></svg>';
    function renderChatTabs() {
      const container = document.getElementById('chat-tabs');
      if (!container) return;
      container.innerHTML = '';
      _chats.forEach(c => {
        const wrap = document.createElement('div');
        wrap.className = 'chat-tab-wrap flex items-center shrink-0';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'chat-tab shrink-0 flex items-center gap-1' + (c.id === _activeChatId ? ' active' : '');
        const viewerUrl = c.kbId ? window.location.origin + API + '/graph/viewer?kb_id=' + encodeURIComponent(c.kbId) : '';
        const graphLink = c.kbId
          ? '<a href="' + viewerUrl + '" class="chat-tab-graph-link shrink-0 opacity-70 hover:opacity-100 transition-opacity" title="Open graph viewer" onclick="event.stopPropagation()">' + graphIconSvg + '</a>'
          : '';
        btn.innerHTML = graphLink + '<span class="truncate max-w-[100px]">' + esc((c.kbName || 'Chat').substring(0, 20)) + (c.messages.length ? ' (' + c.messages.length + ')' : '') + '</span>';
        btn.title = c.kbName + (c.messages.length ? ' · ' + c.messages.length + ' messages' : '');
        btn.addEventListener('click', (e) => { if (e.target.closest('.chat-tab-graph-link')) return; logClick('chat-tab', c.id); switchToChat(c.id); });
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
          if (hasKb) {
            currentOntologyPill?.classList.remove('hidden');
            currentOntologyPill?.classList.add('flex');
            const kb = _kbData.find(k => k.id === getActiveKbId());
            if (kb) {
              currentOntologyName.textContent = kb.name || kb.id;
              const stats = kb.stats || {};
              const relCount = stats.relations ?? stats.edges ?? 0;
              const statParts = [
                fmtNum(stats.classes ?? 0) + ' Classes',
                fmtNum(stats.instances ?? 0) + ' Instances',
                fmtNum(relCount) + ' Relations'
              ];
              const statParts2 = [fmtNum(stats.axioms ?? 0) + ' Axioms', fmtNum(stats.data_properties ?? 0) + ' Data Props'];
              currentOntologyStats.textContent = statParts.join(' · ') + '  |  ' + statParts2.join(' · ');
              if (currentOntologyDocsCount) currentOntologyDocsCount.textContent = fmtNum((kb.documents || []).length) + ' Documents';
              const status = getKbStatus(kb.id);
              if (currentOntologyStatusBadge) {
                currentOntologyStatusBadge.textContent = status === 'building' ? '● Building' : '';
                currentOntologyStatusBadge.classList.toggle('hidden', status !== 'building');
              }
              if (currentOntologyReadyBadge) currentOntologyReadyBadge.classList.toggle('hidden', status !== 'ready');
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
      if (hasKb && chat) {
        const kb = _kbData.find(k => k.id === chat.kbId);
        if (kb) {
          /* Top bar and sticky are updated in switchToChat / renderOntologyCard; chat-onto-card removed */
        }
      }
    }

    function setStatusBadge(status) {
      if (!statusBadge) return;
      const labels = { ready: 'Active', empty: 'Empty', processing: 'Building' };
      statusBadge.className = 'status-badge px-2 py-0.5 rounded-full text-xs font-medium ' + status;
      statusBadge.textContent = labels[status] || status;
    }

    function setInputsEnabled(enabled) {
      questionInput.disabled = !enabled;
      sendBtn.disabled = !enabled;
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
        ontoInfoPanel?.classList.add('hidden');
        currentOntologyPill.classList.add('hidden');
        currentOntologyPill.classList.remove('flex');
        const downloadLink = document.getElementById('download-ontology-link');
        if (downloadLink) downloadLink.style.display = 'none';
        return;
      }
      const stats = kb.stats || {};
      const name = kb.name || kb.id;
      const relCount = stats.relations ?? stats.edges ?? 0;
      const docs = kb.documents || [];
      const status = getKbStatus(kb.id);

      currentOntologyPill.classList.remove('hidden');
      currentOntologyPill.classList.add('flex');
      currentOntologyName.textContent = name;
      const statParts = [
        fmtNum(stats.classes ?? 0) + ' Classes',
        fmtNum(stats.instances ?? 0) + ' Instances',
        fmtNum(relCount) + ' Relations'
      ];
      const statParts2 = [
        fmtNum(stats.axioms ?? 0) + ' Axioms',
        fmtNum(stats.data_properties ?? 0) + ' Data Props'
      ];
      currentOntologyStats.textContent = statParts.join(' · ') + '  |  ' + statParts2.join(' · ');
      if (currentOntologyDocsCount) currentOntologyDocsCount.textContent = fmtNum(docs.length) + ' Documents';
      if (currentOntologyStatusBadge) {
        currentOntologyStatusBadge.textContent = status === 'building' ? '● Building' : '';
        currentOntologyStatusBadge.classList.toggle('hidden', status !== 'building');
        if (status === 'building') currentOntologyStatusBadge.style.cssText = 'color:var(--warning); background:var(--warning-15);';
      }
      if (currentOntologyReadyBadge) currentOntologyReadyBadge.classList.toggle('hidden', status !== 'ready');
    }

    function showEmptyState(hasKb) {
      if (_hasMessages) {
        emptyStateNoKb.classList.add('hidden');
        emptyStateReady.classList.add('hidden');
        return;
      }
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
      if (document.getElementById('graph-health-card')) return;
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
      if (document.getElementById('graph-health-card')) return;
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
          const more = perQ.length > 50 ? '<p class="text-xs mt-2" style="color:var(--text-muted);">… and ' + (perQ.length - 50) + ' more</p>' : '';
          const metricsBlock = '<div class="space-y-3"><div class="rounded-lg p-3" style="background:var(--bg-input); border:1px solid var(--border);"><p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Metrics</p><div class="text-xs font-mono" style="color:var(--text-primary);">context_recall: ' + (scores.context_recall != null ? (scores.context_recall * 100).toFixed(1) : '—') + '% · entity_recall: ' + (scores.entity_recall != null ? (scores.entity_recall * 100).toFixed(1) : '—') + '% · answer_correctness: ' + (scores.answer_correctness != null ? (scores.answer_correctness * 100).toFixed(1) : '—') + '% · faithfulness: ' + (scores.faithfulness != null ? (scores.faithfulness * 100).toFixed(1) : '—') + '% · answer_relevancy: ' + (scores.answer_relevancy != null ? (scores.answer_relevancy * 100).toFixed(1) : '—') + '%</div></div><div class="rounded-lg p-3 overflow-hidden" style="background:var(--bg-input); border:1px solid var(--border);"><p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Per-question scores</p><div class="overflow-x-auto max-h-[200px] overflow-y-auto"><table class="w-full text-xs font-mono" style="color:var(--text-primary);"><thead><tr style="color:var(--text-muted);"><th class="text-left py-1 pr-2">Question</th><th class="text-right py-1 px-1">CR</th><th class="text-right py-1 px-1">ER</th><th class="text-right py-1 px-1">AC</th></tr></thead><tbody>' + detailRows + '</tbody></table></div>' + more + '</div></div>';
          return '<div class="rounded-lg border overflow-hidden" style="border-color:var(--border); background:var(--bg-card);"><button type="button" class="eval-record-header w-full px-3 py-2.5 flex items-center justify-between text-left hover:opacity-90 transition-opacity" data-id="' + id + '" data-detail="' + detailId + '" style="background:var(--bg-input);"><div class="flex flex-col items-start"><span class="text-xs font-medium" style="color:var(--text-primary);">' + esc(ts) + '</span><span class="text-xs mt-0.5" style="color:var(--text-muted);">' + n + ' questions · avg ' + avg + '% · AC ' + ac + '%</span></div><svg class="eval-record-chevron w-4 h-4 shrink-0 transition-transform" style="color:var(--text-muted);" data-id="' + id + '" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg></button><div id="' + detailId + '" class="eval-record-detail hidden p-3 border-t space-y-3" style="border-color:var(--border); background:var(--bg-body);">' + metricsBlock + '</div></div>';
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

    async function fetchRepairRecords(kbId) {
      if (document.getElementById('graph-health-card')) return;
      const listEl = document.getElementById('repair-records-list');
      if (!listEl) return;
      if (!kbId) {
        listEl.innerHTML = '<p class="text-xs">Select a KB to view repair history</p>';
        return;
      }
      listEl.innerHTML = '<p class="text-xs" style="color:var(--text-muted);">Loading records…</p>';
      try {
        const res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/repair-records');
        if (!res.ok) {
          listEl.innerHTML = '<p class="text-xs" style="color:var(--error);">Failed to load records</p>';
          return;
        }
        const records = await res.json();
        if (!records || !records.length) {
          listEl.innerHTML = '<p class="text-xs">No repair records yet</p>';
          return;
        }
        listEl.innerHTML = records.map((r, idx) => {
          const ts = r.timestamp ? new Date(r.timestamp).toLocaleString() : '—';
          const edges = r.edges_added ?? 0;
          const gaps = r.gaps_repaired ?? 0;
          const iters = r.iterations_completed ?? 1;
          const conf = r.min_fidelity != null ? (r.min_fidelity * 100).toFixed(0) + '%' : '—';
          const id = 'repair-record-' + idx;
          const detailId = 'repair-record-detail-' + idx;
          const summaries = (r.iteration_summaries || []).map((s, i) => {
            const h = s.health?.structural || {};
            const g = s.gaps_remaining ?? '—';
            return '<div class="text-xs font-mono py-0.5" style="color:var(--text-primary);">Iter ' + (i + 1) + ': ' + (h.node_count ?? '—') + ' nodes · ' + g + ' gaps</div>';
          }).join('');
          const hb = r.health_before?.structural || {};
          const ha = r.health_after?.structural || {};
          const configBlock = '<div class="rounded-lg p-3" style="background:var(--bg-input); border:1px solid var(--border);"><p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Config</p><div class="text-xs font-mono" style="color:var(--text-primary);">Internet defs ' + (r.repair_internet_definitions ? 'on' : 'off') + ' · iterations ' + (r.repair_iterations ?? 1) + ' · confidence ≥' + conf + '</div></div>';
          const beforeBlock = '<div class="rounded-lg p-3" style="background:var(--bg-input); border:1px solid var(--border);"><p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Before</p><div class="text-xs font-mono" style="color:var(--text-primary);">' + (hb.node_count ?? '—') + ' nodes · ' + (hb.edge_count ?? '—') + ' edges · ' + (hb.orphan_nodes ?? '—') + ' orphans</div></div>';
          const afterBlock = '<div class="rounded-lg p-3" style="background:var(--bg-input); border:1px solid var(--border);"><p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">After</p><div class="text-xs font-mono" style="color:var(--text-primary);">' + (ha.node_count ?? '—') + ' nodes · ' + (ha.edge_count ?? '—') + ' edges · ' + (ha.orphan_nodes ?? '—') + ' orphans</div></div>';
          const iterBlock = summaries ? '<div class="rounded-lg p-3" style="background:var(--bg-input); border:1px solid var(--border);"><p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Iterations</p>' + summaries + '</div>' : '';
          const detail = '<div class="space-y-3">' + configBlock + beforeBlock + afterBlock + iterBlock + '</div>';
          return '<div class="rounded-lg border overflow-hidden" style="border-color:var(--border); background:var(--bg-card);"><button type="button" class="repair-record-header w-full px-3 py-2.5 flex items-center justify-between text-left hover:opacity-90 transition-opacity" data-id="' + id + '" data-detail="' + detailId + '" style="background:var(--bg-input);"><div class="flex flex-col items-start"><span class="text-xs font-medium" style="color:var(--text-primary);">' + esc(ts) + '</span><span class="text-xs mt-0.5" style="color:var(--text-muted);">+' + edges + ' edges · ' + gaps + ' definitions · ' + iters + ' iter(s) · conf ≥' + conf + '</span></div><svg class="repair-record-chevron w-4 h-4 shrink-0 transition-transform" style="color:var(--text-muted);" data-id="' + id + '" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg></button><div id="' + detailId + '" class="repair-record-detail hidden p-3 border-t space-y-3" style="border-color:var(--border); background:var(--bg-body);">' + detail + '</div></div>';
        }).join('');
        listEl.querySelectorAll('.repair-record-header').forEach(btn => {
          btn.addEventListener('click', () => {
            const detailId = btn.getAttribute('data-detail');
            const chevron = btn.querySelector('.repair-record-chevron');
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
        console.error('[fetchRepairRecords]', e);
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
      ontoInfoPanel?.classList.remove('hidden');
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

    tabDocuments?.addEventListener('click', () => {
      logClick('tab', 'documents');
      tabDocuments?.classList.add('sidebar-tab-active');
      tabDocuments?.classList.remove('sidebar-tab-inactive');
      tabEvaluate?.classList.remove('sidebar-tab-active');
      tabEvaluate?.classList.add('sidebar-tab-inactive');
      tabDocumentsContent?.classList.remove('hidden');
      tabEvaluateContent?.classList.add('hidden');
    });
    tabEvaluate?.addEventListener('click', () => {
      logClick('tab', 'evaluate');
      tabEvaluate?.classList.add('sidebar-tab-active');
      tabEvaluate?.classList.remove('sidebar-tab-inactive');
      tabDocuments?.classList.remove('sidebar-tab-active');
      tabDocuments?.classList.add('sidebar-tab-inactive');
      tabEvaluateContent?.classList.remove('hidden');
      tabDocumentsContent?.classList.add('hidden');
      populateEvalKbSelector();
      const sel = document.getElementById('eval-kb-select');
      if (document.getElementById('graph-health-card') && typeof window.evalTabOnShow === 'function') {
        window.evalTabOnShow(sel?.value);
      } else if (sel?.value) {
        fetchEvalHealth(sel.value); fetchEvalRecords(sel.value); fetchRepairRecords(sel.value);
      }
    });

    jobQueueToggle?.addEventListener('click', () => { logClick('job-queue', 'toggle'); jobQueueSection?.classList.toggle('collapsed'); });
    document.getElementById('job-queue-clear')?.addEventListener('click', () => { logClick('job-queue', 'clear'); clearJobsStorage(); });

    document.getElementById('eval-kb-select')?.addEventListener('change', (e) => {
      const kbId = e.target?.value;
      logClick('eval-kb-select', kbId || 'none');
      if (document.getElementById('graph-health-card')) {
        if (typeof window.evalTabOnKbChange === 'function') window.evalTabOnKbChange(kbId);
        return;
      }
      if (kbId) { fetchEvalHealth(kbId); fetchEvalRecords(kbId); fetchRepairRecords(kbId); }
      else {
        const sh = document.getElementById('eval-health-stats');
        const bh = document.getElementById('eval-health-badge');
        const wh = document.getElementById('eval-health-warnings');
        if (sh) sh.innerHTML = 'Select a KB to view health';
        if (bh) bh.textContent = '—';
        if (wh) wh.innerHTML = '';
        fetchEvalRecords(''); fetchRepairRecords('');
      }
    });
    document.getElementById('eval-repair-btn')?.addEventListener('click', () => { logClick('eval-repair'); showRepairModal(); });
    document.getElementById('eval-run-btn')?.addEventListener('click', () => {
      logClick('eval-run');
      if (document.getElementById('graph-health-card') && typeof window.evalTabRunEvaluation === 'function') {
        window.evalTabRunEvaluation();
        return;
      }
      runEvaluation();
    });

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

    async function fetchRepairDiagnosis(kbId) {
      const body = document.getElementById('repair-details-body');
      if (!body) return;
      body.innerHTML = '<span style="color:var(--text-muted);">Loading…</span>';
      try {
        const res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/repair-diagnosis');
        if (!res.ok) {
          body.innerHTML = '<span style="color:var(--error);">Failed to load diagnosis</span>';
          return;
        }
        const d = await res.json();
        const h = d.health || {};
        const s = h.structural || {};
        const sem = h.semantic || {};
        const badge = h.badge || '—';
        const score = h.overall_score ?? '—';
        const gaps = d.gaps || [];
        const recs = d.recommendations || [];
        let html = '';
        html += '<div class="space-y-2"><p class="font-medium" style="color:var(--text-primary);">Health</p>';
        html += '<p>Score: <span class="font-mono">' + score + '</span> · Badge: <span class="font-mono">' + esc(badge) + '</span></p>';
        html += '<p>Nodes: ' + (s.node_count ?? '—') + ' · Edges: ' + (s.edge_count ?? '—') + ' · Orphans: ' + (s.orphan_nodes ?? '—') + ' · Components: ' + (s.connected_components ?? '—') + '</p>';
        html += '<p>Relation types: ' + (sem.unique_relation_types ?? '—') + ' · Facts/node: ' + (h.retrieval?.facts_per_node ?? '—') + '</p></div>';
        if (gaps.length) {
          html += '<div class="space-y-1"><p class="font-medium" style="color:var(--warning);">Missing definitions (' + gaps.length + ')</p>';
          html += '<p class="font-mono text-[11px] break-words" style="color:var(--text-muted);">' + gaps.slice(0, 12).map(g => esc(g)).join(', ') + (gaps.length > 12 ? ' …' : '') + '</p>';
          html += '<p class="text-[11px]" style="color:var(--text-muted);">Enable Internet definition repair to search the web for these concepts.</p></div>';
        }
        if (recs.length) {
          html += '<div class="space-y-2"><p class="font-medium" style="color:var(--text-primary);">Recommendations</p>';
          recs.forEach(r => {
            html += '<div class="rounded p-2" style="background:var(--bg-input); border:1px solid var(--border);"><p class="font-medium text-[11px]" style="color:var(--accent);">' + esc(r.title || '') + '</p><p class="text-[11px] mt-0.5" style="color:var(--text-muted);">' + esc(r.desc || '') + '</p></div>';
          });
          html += '</div>';
        }
        html += '<div class="pt-1"><p class="font-medium text-[11px]" style="color:var(--text-muted);">What repair does</p><ul class="list-disc list-inside text-[11px] mt-0.5 space-y-0.5" style="color:var(--text-muted);"><li>Add root concept (Thing)</li><li>Link orphan nodes to similar nodes via embeddings</li><li>Bridge disconnected components</li><li>Run OWL 2 RL inference</li><li>Optionally: search web for missing definitions</li><li>With 2+ iterations: rescan graph after each pass, then repair again</li></ul></div>';
        body.innerHTML = html;
        const content = document.getElementById('repair-details-content');
        const chevron = document.getElementById('repair-details-chevron');
        if (content) { content.classList.remove('hidden'); }
        if (chevron) chevron.style.transform = 'rotate(180deg)';
      } catch (e) {
        console.error('[fetchRepairDiagnosis]', e);
        body.innerHTML = '<span style="color:var(--error);">Error loading diagnosis</span>';
      }
    }

    function showRepairModal() {
      const sel = document.getElementById('repair-kb-select');
      if (!sel) return;
      const items = _kbData || [];
      const activeId = getActiveKbId();
      sel.innerHTML = '<option value="">Select a KB</option>' + items.map(k => {
        const docs = k.documents || [];
        const label = k.name + (docs.length ? ' (' + docs.length + ')' : '');
        return '<option value="' + esc(k.id) + '"' + (k.id === activeId ? ' selected' : '') + '>' + esc(label) + '</option>';
      }).join('');
      document.getElementById('repair-form')?.classList.remove('hidden');
      document.getElementById('repair-progress')?.classList.add('hidden');
      const detailsContent = document.getElementById('repair-details-content');
      const detailsBody = document.getElementById('repair-details-body');
      if (detailsContent) detailsContent.classList.add('hidden');
      if (detailsBody) detailsBody.innerHTML = 'Select a KB to load graph health, gaps, and repair recommendations.';
      const chevron = document.getElementById('repair-details-chevron');
      if (chevron) chevron.style.transform = '';
      const kbId = sel?.value;
      if (kbId) fetchRepairDiagnosis(kbId);
      const confWrap = document.getElementById('repair-confidence-wrap');
      const confCb = document.getElementById('repair-internet-definitions');
      if (confWrap && confCb) confWrap.classList.toggle('hidden', !confCb.checked);
      document.getElementById('repair-modal')?.classList.remove('hidden');
    }
    function hideRepairModal() {
      document.getElementById('repair-modal')?.classList.add('hidden');
    }
    document.getElementById('repair-internet-definitions')?.addEventListener('change', (e) => {
      const wrap = document.getElementById('repair-confidence-wrap');
      if (wrap) wrap.classList.toggle('hidden', !e.target?.checked);
    });
    document.getElementById('repair-kb-select')?.addEventListener('change', (e) => {
      const kbId = e.target?.value;
      if (kbId) fetchRepairDiagnosis(kbId);
      else {
        const body = document.getElementById('repair-details-body');
        if (body) body.innerHTML = 'Select a KB to load graph health, gaps, and repair recommendations.';
      }
    });
    document.getElementById('repair-details-toggle')?.addEventListener('click', () => {
      const content = document.getElementById('repair-details-content');
      const chevron = document.getElementById('repair-details-chevron');
      if (content?.classList.contains('hidden')) {
        content.classList.remove('hidden');
        if (chevron) chevron.style.transform = 'rotate(180deg)';
      } else {
        content?.classList.add('hidden');
        if (chevron) chevron.style.transform = '';
      }
    });
    document.getElementById('repair-modal-cancel')?.addEventListener('click', hideRepairModal);
    document.getElementById('repair-modal')?.querySelector('.modal-backdrop')?.addEventListener('click', hideRepairModal);
    document.getElementById('repair-modal-start')?.addEventListener('click', () => {
      const kbId = document.getElementById('repair-kb-select')?.value;
      if (!kbId) { alert('Please select a knowledge base'); return; }
      const repairInternetDefinitions = document.getElementById('repair-internet-definitions')?.checked ?? false;
      const repairIterations = parseInt(document.getElementById('repair-iterations')?.value || '1', 10) || 1;
      const minFidelity = parseFloat(document.getElementById('repair-min-fidelity')?.value || '0.3') || 0.3;
      logClick('repair-modal', 'start');
      hideRepairModal();
      tabEvaluate?.click();
      const evalSel = document.getElementById('eval-kb-select');
      if (evalSel && evalSel.value !== kbId) evalSel.value = kbId;
      runRepair(kbId, repairInternetDefinitions, repairIterations, minFidelity);
    });

    async function runRepair(kbIdOrUndefined, repairInternetDefinitions, repairIterations, minFidelity) {
      const kbId = kbIdOrUndefined ?? document.getElementById('eval-kb-select')?.value;
      if (!kbId) return;
      repairIterations = repairIterations ?? 1;
      minFidelity = minFidelity ?? 0.3;
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
      let stepIdx = 0;
      const totalSteps = 20;
      function addLog(icon, msg, rescan) {
        const div = document.createElement('div');
        div.innerHTML = (icon || '▸') + ' ' + (msg || '');
        logFeed.appendChild(div);
        if (rescan) {
          const r = rescan;
          const sum = document.createElement('div');
          sum.className = 'ml-4 text-[11px] font-mono';
          sum.style.cssText = 'color:var(--text-muted);';
          sum.textContent = (r.health?.structural?.node_count ?? '—') + ' nodes · ' + (r.gaps_remaining ?? '—') + ' gaps remaining';
          logFeed.appendChild(sum);
        }
        logFeed.scrollTop = logFeed.scrollHeight;
      }
      try {
        const params = new URLSearchParams();
        if (repairInternetDefinitions) params.set('repair_internet_definitions', 'true');
        if (repairIterations > 1) params.set('repair_iterations', String(repairIterations));
        params.set('min_fidelity', String(minFidelity));
        const qs = params.toString() ? '?' + params.toString() : '';
        const res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/repair' + qs, { method: 'POST' });
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
                    stepIdx = Math.min(stepIdx + 1, totalSteps - 1);
                    stageLabel.textContent = data.message || 'Repairing...';
                    progressBar.style.width = (100 * stepIdx / totalSteps) + '%';
                    addLog('✓', data.message || '', data.rescan);
                  } else if (data.type === 'done') {
                    const parts = [];
                    if (data.edges_added) parts.push(data.edges_added + ' edges');
                    if (data.gaps_repaired) parts.push(data.gaps_repaired + ' definitions');
                    if (data.iterations_completed > 1) parts.push(data.iterations_completed + ' iterations');
                    stageLabel.textContent = 'Done' + (parts.length ? ' (' + parts.join(', ') + ')' : '');
                    progressBar.style.width = '100%';
                    addLog('✓', 'Repair complete');
                    const defs = data.definitions_added || {};
                    const edges = data.inferred_edges || [];
                    const defKeys = Object.keys(defs);
                    if (defKeys.length > 0 || edges.length > 0) {
                      const summaryParts = [];
                      if (defKeys.length > 0) {
                        const defPreview = defKeys.length <= 5 ? defKeys.join(', ') : defKeys.slice(0, 3).join(', ') + '… (+' + (defKeys.length - 3) + ' more)';
                        summaryParts.push(defKeys.length + ' definitions: ' + defPreview);
                      }
                      if (edges.length > 0) {
                        const fmt = (e) => (e[0] || '') + '→' + (e[2] || '');
                        const edgePreview = edges.length <= 5 ? edges.map(fmt).join(', ') : edges.slice(0, 3).map(fmt).join(', ') + '… (+' + (edges.length - 3) + ' more)';
                        summaryParts.push(edges.length + ' edges: ' + edgePreview);
                      }
                      addLog('·', summaryParts.join(' · '));
                    }
                    if (document.getElementById('graph-health-card') && typeof window.evalTabOnRepairComplete === 'function') {
                      window.evalTabOnRepairComplete(kbId);
                    } else {
                      await fetchEvalHealth(kbId);
                      populateEvalKbSelector();
                      fetchRepairRecords(kbId);
                    }
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
          if (document.getElementById('graph-health-card') && typeof window.evalTabOnRepairComplete === 'function') {
            window.evalTabOnRepairComplete(kbId);
          } else {
            await fetchEvalHealth(kbId);
            populateEvalKbSelector();
          }
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
    }

    function getMessagesInsertBefore() {
      return messagesEl.querySelector('#loading-indicator') || messagesEl.querySelector('#empty-state-no-kb') || messagesEl.querySelector('#empty-state-ready');
    }

    function scrollMessagesToBottom() {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          messagesEl.scrollTop = messagesEl.scrollHeight;
        });
      });
    }

    function renderInlineMarkdown(value) {
      const text = esc(String(value || ''));
      return text
        .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded text-xs font-mono" style="background:var(--bg-input);border:1px solid var(--border);color:var(--text-primary);">$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        .replace(/\[([a-zA-Z_][a-zA-Z0-9_\-]*:[^\]\n]+)\]/g, '<span class="px-1.5 py-0.5 rounded text-xs font-mono align-middle" style="background:var(--accent-15); color:var(--accent);">[$1]</span>')
        .replace(/\b(classes|object properties|datatype properties|relationships|taxonomy|ontology)\b/gi, '<span class="ai-keyword">$1</span>');
    }

    function parseFollowUpQuestions(body) {
      const s = String(body || '').trim();
      const questions = [];
      s.split(/\n+/).forEach(line => {
        const trimmed = line.replace(/^[-*•]\s*/, '').replace(/^\d+\.\s*/, '').trim();
        if (trimmed.length > 10 && trimmed.length < 200) questions.push(trimmed);
      });
      return questions.slice(0, 6);
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
        p.className = 'leading-relaxed';
        p.style.cssText = 'font-size:14px; line-height:1.7;';
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
          h4.className = 'font-semibold mt-2 mb-1';
          h4.style.cssText = 'color:var(--text-primary); font-size:16px; line-height:1.4;';
          h4.innerHTML = renderInlineMarkdown(trimmed.slice(4));
          wrapper.appendChild(h4);
          return;
        }

        if (trimmed.startsWith('## ')) {
          flushParagraph();
          flushList();
          const h3 = document.createElement('h3');
          h3.className = 'font-semibold mt-2 mb-1';
          h3.style.cssText = 'color:var(--accent); font-size:18px; line-height:1.4;';
          h3.innerHTML = renderInlineMarkdown(trimmed.slice(3));
          wrapper.appendChild(h3);
          return;
        }

        if (trimmed.startsWith('- ')) {
          flushParagraph();
          if (!list) {
            list = document.createElement('ul');
            list.className = 'leading-relaxed space-y-1.5 pl-5 list-disc';
            list.style.fontSize = '14px';
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

    function splitAnswerIntoParts(content) {
      const s = String(content || '').trim();
      const splitPattern = /##\s*You might also ask\s*:?\s*/i;
      const parts = s.split(splitPattern);
      if (parts.length >= 2) {
        const result = [];
        const p1 = parts[0].trim();
        const p2 = parts.slice(1).join('').trim();
        if (p1) result.push({ label: 'Answer', body: p1 });
        if (p2) result.push({ label: 'You might also ask', body: p2 });
        return result.length ? result : [{ label: 'Answer', body: s }];
      }
      return [{ label: 'Answer', body: s }];
    }

    function buildMessageElement(role, content, sources, numFactsUsed, rawFacts, reasoning, sessionId) {
      const hasRawFacts = role === 'assistant' && rawFacts && Array.isArray(rawFacts) && rawFacts.length > 0;
      const hasReasoning = role === 'assistant' && reasoning && typeof reasoning === 'string' && reasoning.trim().length > 0;
      const hasSessionId = role === 'assistant' && sessionId && typeof sessionId === 'string' && sessionId.trim().length > 0;
      const div = document.createElement('div');
      div.dataset.chatMessage = '1';
      div.className = 'flex ' + (role === 'user' ? 'justify-end msg-enter-user' : 'justify-start msg-enter-assistant');
      const bubble = document.createElement('div');
      bubble.className = 'msg-bubble max-w-[85%] ' +
        (role === 'user' ? 'msg-user-bubble rounded-xl px-4 py-3.5' : 'ai-answer-card bubble-assistant');
      bubble.style.color = role === 'user' ? '#fff' : 'var(--text-primary)';
      if (role === 'user') {
        bubble.style.background = 'var(--accent)';
        bubble.style.border = '1px solid var(--accent-7)';
      }

      if (role === 'assistant') {
        const metaRow = document.createElement('div');
        metaRow.className = 'ai-meta-bar';
        const lightbulbSvg = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21h6M12 3a6 6 0 0 1 4.5 10H7.5A6 6 0 0 1 12 3z"/></svg>';
        const robotSvg = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="8.5" cy="16.5" r="1.5"/><circle cx="15.5" cy="16.5" r="1.5"/><path d="M9 7h6M12 3v4"/></svg>';
        const chartSvg = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M7 16v-5M12 16V10M17 16v-3"/></svg>';
        const brainSvg = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1 .34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0-.34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/></svg>';
        const pill = (html, label, accent) => {
          const el = document.createElement('span');
          el.className = 'ai-meta-pill' + (accent ? ' ai-meta-pill-accent' : '');
          el.innerHTML = html + ' <span>' + esc(label) + '</span>';
          return el;
        };
        metaRow.appendChild(pill(lightbulbSvg, 'Clearence', true));
        if (hasSessionId) metaRow.appendChild(pill(robotSvg, 'Agent', true));
        if (numFactsUsed > 0) metaRow.appendChild(pill(chartSvg, numFactsUsed + ' facts', true));
        if (hasSessionId) {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'ai-meta-pill ai-meta-pill-accent';
          btn.innerHTML = brainSvg + ' <span>Show reasoning</span>';
          btn.title = 'View exploration steps, reasoning graph, and ontology gaps';
          btn.addEventListener('click', () => showReasoningModal(sessionId));
          metaRow.appendChild(btn);
        }
        if (hasSessionId && !hasRawFacts && !hasReasoning) {
          const hint = document.createElement('p');
          hint.className = 'msg-hint text-xs mt-2';
          hint.style.cssText = 'color:var(--text-muted); padding:0 16px 12px;';
          hint.textContent = 'Click "Show reasoning" to view exploration steps and reasoning graph.';
          bubble.appendChild(metaRow);
          bubble.appendChild(hint);
        } else {
          bubble.appendChild(metaRow);
        }
      }

      const text = document.createElement('div');
      text.className = 'msg-content';
      if (typeof content === 'string') {
        if (role === 'assistant') {
          const parts = splitAnswerIntoParts(content);
          parts.forEach((part, i) => {
            if (part.label === 'Answer') {
              const section = document.createElement('div');
              section.className = 'ai-section';
              const title = document.createElement('div');
              title.className = 'ai-section-title';
              title.textContent = 'Answer';
              section.appendChild(title);
              const bodyWrap = document.createElement('div');
              bodyWrap.className = 'ai-section-body-wrap';
              const body = document.createElement('div');
              body.className = 'ai-section-body';
              body.appendChild(renderAssistantGuide(part.body));
              bodyWrap.appendChild(body);
              section.appendChild(bodyWrap);
              const actionsRow = document.createElement('div');
              actionsRow.className = 'ai-actions-row';
              const copyBtn = document.createElement('button');
              copyBtn.type = 'button';
              copyBtn.className = 'ai-btn-icon';
              copyBtn.title = 'Copy answer';
              copyBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
              copyBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(part.body).then(() => {
                  copyBtn.title = 'Copied!';
                  setTimeout(() => { copyBtn.title = 'Copy answer'; }, 1500);
                });
              });
              actionsRow.appendChild(copyBtn);
              section.appendChild(actionsRow);
              text.appendChild(section);
            } else if (part.label === 'You might also ask') {
              const questions = parseFollowUpQuestions(part.body);
              if (questions.length > 0) {
                const divider = document.createElement('div');
                divider.className = 'ai-section-divider';
                text.appendChild(divider);
                const section = document.createElement('div');
                const title = document.createElement('div');
                title.className = 'ai-section-title';
                title.style.padding = '0 20px';
                title.textContent = 'You might also ask';
                section.appendChild(title);
                const grid = document.createElement('div');
                grid.className = 'ai-followup-grid';
                questions.forEach(q => {
                  const card = document.createElement('button');
                  card.type = 'button';
                  card.className = 'ai-followup-card';
                  card.innerHTML = '<span class="ai-followup-arrow">→</span><span>' + esc(q) + '</span>';
                  card.addEventListener('click', () => fillPrompt(q));
                  grid.appendChild(card);
                });
                section.appendChild(grid);
                text.appendChild(section);
              } else {
                const section = document.createElement('div');
                section.className = 'ai-section';
                const title = document.createElement('div');
                title.className = 'ai-section-title';
                title.textContent = 'You might also ask';
                section.appendChild(title);
                const body = document.createElement('div');
                body.className = 'ai-section-body';
                body.appendChild(renderAssistantGuide(part.body));
                section.appendChild(body);
                text.appendChild(section);
              }
            }
          });
        } else {
          text.className = 'msg-content msg-content-user';
          text.textContent = content;
        }
      } else {
        text.appendChild(content);
      }
      bubble.appendChild(text);

      if (sources && sources.length > 0 && role === 'assistant') {
        const srcDiv = document.createElement('div');
        srcDiv.className = 'mt-0 pt-2.5 pb-3 px-5 flex flex-wrap gap-1.5';
        srcDiv.style.borderTop = '1px solid var(--border)';
        sources.slice(0, 5).forEach(ref => {
          const tag = document.createElement('span');
          tag.className = 'px-2 py-0.5 rounded-full text-xs font-mono';
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
      const insertBefore = getMessagesInsertBefore();
      let lastOntologyTotals = null;
      chat.messages.forEach(m => {
        let el;
        if (m.type === 'ontology_summary') {
          el = buildOntologySummaryElement(m.report, lastOntologyTotals);
          const totals = m.report?.totals || {};
          lastOntologyTotals = { classes: totals.classes ?? 0, instances: totals.instances ?? 0, relations: totals.relations ?? totals.edges ?? 0, axioms: totals.axioms ?? 0, data_properties: totals.data_properties ?? 0 };
        } else {
          el = buildMessageElement(m.role, m.content, m.sources, m.numFactsUsed, m.rawFacts, m.reasoning, m.sessionId);
        }
        if (el) messagesEl.insertBefore(el, insertBefore);
      });
      scrollMessagesToBottom();
    }

    function appendMessage(role, content, sources, numFactsUsed, chatId, rawFacts, reasoning, sessionId) {
      let chat = chatId ? getChatById(chatId) : getActiveChat();
      if (!chat) {
        if (chatId) return;
        if (!getActiveKbId()) return;
        chat = createNewChat();
      }
      chat.messages.push({ role, content, sources, numFactsUsed, rawFacts, reasoning, sessionId });
      if (chat.id === _activeChatId) {
        hideEmptyStates();
        const el = buildMessageElement(role, content, sources, numFactsUsed, rawFacts, reasoning, sessionId);
        messagesEl.insertBefore(el, getMessagesInsertBefore());
        scrollMessagesToBottom();
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
          messagesEl.insertBefore(el, getMessagesInsertBefore());
        }
        const totals = report.totals || {};
        const totalRel = totals.relations ?? totals.edges ?? 0;
        lastReportTotals = { classes: totals.classes ?? 0, instances: totals.instances ?? 0, relations: totalRel, axioms: totals.axioms ?? 0, data_properties: totals.data_properties ?? 0 };
        scrollMessagesToBottom();
      }
      renderChatTabs();
    }

    const reasoningStepsLog = document.getElementById('reasoning-steps-log');

    function showLoading(show, agentMode) {
      loadingIndicator.classList.toggle('hidden', !show);
      if (reasoningStepsLog) {
        if (show && agentMode) {
          reasoningStepsLog.classList.remove('hidden');
          reasoningStepsLog.innerHTML = '';
        } else {
          reasoningStepsLog.classList.add('hidden');
        }
      }
      if (show) scrollMessagesToBottom();
    }

    function appendReasoningStep(stepNum, question) {
      if (!reasoningStepsLog) return;
      const line = document.createElement('div');
      line.className = 'agent-step agent-step-single';
      const num = document.createElement('span');
      num.className = 'agent-step-num';
      num.textContent = 'Step ' + stepNum + ': ';
      const text = document.createElement('span');
      text.className = 'agent-step-text';
      text.textContent = (question || '').slice(0, 200) + (question && question.length > 200 ? '…' : '');
      line.appendChild(num);
      line.appendChild(text);
      reasoningStepsLog.innerHTML = '';
      reasoningStepsLog.appendChild(line);
    }

    async function showReasoningModal(sessionId) {
      const modal = document.getElementById('reasoning-modal');
      const content = document.getElementById('reasoning-modal-content');
      if (!modal || !content) return;
      content.innerHTML = '<div class="loading">Loading...</div>';
      modal.classList.remove('hidden');
      try {
        const res = await fetch(API + '/qa/agent/reasoning/' + encodeURIComponent(sessionId));
        if (!res.ok) throw new Error('Failed to load reasoning');
        const log = await res.json();
        let html = '<div class="space-y-4">';
        html += '<div><p class="text-xs font-medium mb-1" style="color:var(--text-muted);">Query</p><p class="font-medium">' + esc(log.query || '') + '</p></div>';
        if (log.steps && log.steps.length) {
          html += '<div><p class="text-xs font-medium mb-2" style="color:var(--text-muted);">Exploration steps</p>';
          log.steps.forEach((s, i) => {
            html += '<div class="mb-3 p-3 rounded-lg" style="background:var(--bg-input); border:1px solid var(--border);">';
            html += '<p class="text-xs font-semibold mb-1" style="color:var(--accent);">Step ' + (i + 1) + ': ' + esc(s.question || '') + '</p>';
            html += '<p class="text-xs" style="color:var(--text-muted); white-space:pre-wrap;">' + esc((s.answer || '').substring(0, 400)) + '...</p></div>';
          });
          html += '</div>';
        }
        if (log.gaps && log.gaps.length) {
          html += '<div><p class="text-xs font-medium mb-1" style="color:var(--text-muted);">Ontology gaps</p><ul class="list-disc pl-4 text-xs">';
          log.gaps.forEach(g => { html += '<li>' + esc(g.description || JSON.stringify(g)) + '</li>'; });
          html += '</ul></div>';
        }
        html += '<div><p class="text-xs font-medium mb-1" style="color:var(--text-muted);">Final answer</p><p class="whitespace-pre-wrap">' + esc(log.answer || '') + '</p></div>';
        html += '</div>';
        content.innerHTML = html;
      } catch (e) {
        content.innerHTML = '<p class="text-error">Error: ' + esc(e.message) + '</p>';
      }
    }

    document.getElementById('reasoning-modal-close')?.addEventListener('click', () => document.getElementById('reasoning-modal')?.classList.add('hidden'));
    document.getElementById('reasoning-modal')?.querySelector('.modal-backdrop')?.addEventListener('click', () => document.getElementById('reasoning-modal')?.classList.add('hidden'));

    const modeSelector = document.getElementById('mode-selector');
    const modeTag = document.getElementById('mode-tag');
    const modeTagLabel = document.getElementById('mode-tag-label');
    const modeToggleBar = document.getElementById('mode-toggle-bar');
    const modeOptionOntology = document.getElementById('mode-option-ontology');
    const modeOptionAgent = document.getElementById('mode-option-agent');
    const modeAgentOptions = document.getElementById('mode-agent-options');
    const assistantModeToggle = document.getElementById('assistant-mode-toggle');

    let _agentMode = false;

    function setAgentMode(on) {
      _agentMode = on;
      modeOptionOntology?.classList.toggle('mode-selected', !on);
      modeOptionAgent?.classList.toggle('mode-selected', on);
      modeTag?.classList.toggle('mode-active-agent', on);
      if (modeAgentOptions) modeAgentOptions.classList.toggle('hidden', !on);
      updateModeTagLabel();
    }

    function updateModeTagLabel() {
      if (!modeTagLabel) return;
      modeTagLabel.textContent = _agentMode ? 'Agent' : 'Ontology';
    }

    function collapseModeBar() {
      modeToggleBar?.classList.add('hidden');
      modeTag?.classList.remove('mode-expanded');
    }

    modeTag?.addEventListener('click', (e) => {
      e.stopPropagation();
      const isExpanded = modeToggleBar?.classList.contains('hidden');
      if (isExpanded) {
        modeToggleBar?.classList.remove('hidden');
        modeTag?.classList.add('mode-expanded');
      } else {
        collapseModeBar();
      }
    });

    modeOptionOntology?.addEventListener('click', () => { setAgentMode(false); collapseModeBar(); });
    modeOptionAgent?.addEventListener('click', () => { setAgentMode(true); collapseModeBar(); });

    document.addEventListener('click', (e) => {
      if (modeSelector && !modeSelector.contains(e.target)) collapseModeBar();
    });

    setAgentMode(false);

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
      const agentMode = _agentMode;
      showLoading(true, agentMode);
      setInputsEnabled(false);
      const controller = new AbortController();
      const qaTimeoutMs = 90000;
      const timeoutId = setTimeout(() => controller.abort(), qaTimeoutMs);
      try {
        const chat = getChatById(submitChatId);
        const kbId = (chat && chat.kbId) ? chat.kbId : getActiveKbId();
        if (!kbId) { setInputsEnabled(true); showLoading(false); return; }
        const assistantMode = document.getElementById('assistant-mode-toggle')?.checked === true;
        if (agentMode) {
          const endpoint = '/qa/agent/ask/stream';
          const body = { question: q, kb_id: kbId, assistant_mode: assistantMode };
          const res = await fetch(API + endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: controller.signal,
          });
          if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(parseError(data) || res.statusText);
          }
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';
          let stepCount = 0;
          let data = null;
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
                if (ev.type === 'step' && ev.step) {
                  stepCount++;
                  appendReasoningStep(stepCount, ev.step.question);
                } else if (ev.type === 'done' && ev.result) {
                  data = ev.result;
                } else if (ev.type === 'error') {
                  throw new Error(ev.message || 'Agent error');
                }
              } catch (err) {
                if (err instanceof SyntaxError) continue;
                throw err;
              }
            }
          }
          if (!data) throw new Error('No result from agent stream');
          const sessionId = data.session_id || null;
          const hideReasoning = assistantMode && agentMode;
          const rawFacts = hideReasoning ? [] : (data.sources || []);
          const reasoning = hideReasoning ? '' : (data.reasoning || '');
          const sourceTags = (sessionId && agentMode)
            ? []
            : ((data.source_labels && data.source_labels.length) ? data.source_labels : (data.source_refs || []));
          appendMessage('assistant', data.answer, sourceTags, data.num_facts_used, submitChatId, rawFacts, reasoning, sessionId);
        } else {
          const endpoint = '/qa/ask';
          const body = { question: q, kb_id: kbId };
          const res = await fetch(API + endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: controller.signal,
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(parseError(data) || res.statusText);
          const sessionId = data.session_id || null;
          const rawFacts = data.sources || [];
          const reasoning = data.reasoning || '';
          const sourceTags = (data.source_labels && data.source_labels.length) ? data.source_labels : (data.source_refs || []);
          appendMessage('assistant', data.answer, sourceTags, data.num_facts_used, submitChatId, rawFacts, reasoning, sessionId);
        }
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
    const jobDetailCancelBtn = document.getElementById('job-detail-cancel-job');

    modalConfirm?.addEventListener('click', () => {
      logClick('upload-confirm', _modalMode + ' (files: ' + pendingFiles.length + ')');
      if (!pendingFiles.length) return;
      const parallel = _modalMode === 'extend'
        ? document.getElementById('modal-parallel-extend').checked
        : document.getElementById('modal-parallel').checked;
      const minQualityGradeEl = document.getElementById('modal-min-quality-grade');
      const minQualityGrade = (minQualityGradeEl && minQualityGradeEl.value) ? minQualityGradeEl.value : '';
      const files = pendingFiles.slice();
      hideCreateModal();
      if (_modalMode === 'extend') {
        const activeId = getActiveKbId();
        if (activeId) {
          doExtend(files, activeId, parallel, minQualityGrade);
          return;
        }
      }
      const first = files[0];
      const title = modalTitle.value.trim() || first.name.replace(/\\.[^.]+$/, '');
      const description = modalDescription.value.trim();
      const ontologyLanguageEl = document.getElementById('modal-ontology-language');
      const ontologyLanguage = (ontologyLanguageEl && ontologyLanguageEl.value) ? ontologyLanguageEl.value : 'en';
      doUpload(files, title, description, parallel, ontologyLanguage, minQualityGrade);
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
      const isEnrich = job.jobType === 'enrich';
      const typeClass = isCreate ? 'job-create' : (isEnrich ? 'job-enrich' : 'job-extend');
      const typeLabel = isCreate ? 'New KB' : (isEnrich ? 'Web Enrich' : 'Expanding');
      const card = document.createElement('div');
      card.className = 'job-card job-clickable ' + typeClass;
      card.dataset.jobId = job.localId;
      card.innerHTML = '<div class="flex items-center justify-between gap-2 min-w-0">'
        + '<div class="flex items-center gap-2 min-w-0 flex-1">'
        + '<span class="job-type-badge text-xs font-medium px-1.5 py-0.5 rounded shrink-0">' + typeLabel + '</span>'
        + '<p class="job-card-title text-sm font-medium min-w-0" style="color:var(--text-primary);">' + esc(job.title) + '</p>'
        + '</div>'
        + '<button type="button" class="job-cancel shrink-0 w-5 h-5 rounded flex items-center justify-center" style="color:var(--text-muted);">'
        + '<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>'
        + '</button></div>'
        + (job.description ? '<p class="job-card-desc job-card-desc-filename text-xs mt-0.5 min-w-0" style="color:var(--text-muted-2);">' + esc(job.description) + '</p>' : '')
        + '<div class="flex items-center gap-2 mt-1.5 min-w-0">'
        + '<span class="stage-dot shrink-0"></span>'
        + '<span class="stage-label text-xs font-mono min-w-0" style="color:var(--text-muted);">Starting...</span>'
        + '</div>'
        + '<div class="job-metrics text-xs font-mono mt-1 min-w-0" style="color:#6b6b76; min-height:1em;"></div>';
      card.querySelector('.job-cancel').addEventListener('click', (e) => { e.stopPropagation(); logClick('job-cancel', job.localId); cancelJob(job); });
      card.addEventListener('click', (e) => { if (!e.target.closest('.job-cancel')) { logClick('job-detail', job.localId); showJobDetailModal(job); } });
      return card;
    }

    const JOB_STORAGE_KEY = 'clearence_job_records';

    function jobToRecord(job) {
      return {
        localId: job.localId,
        title: job.title,
        description: job.description,
        status: job.status,
        serverJobId: job.serverJobId,
        jobType: job.jobType,
        kbId: job.kbId,
        pipeline_report: job.pipeline_report,
        enrichment_report: job.enrichment_report,
        progress: job.progress || {},
        liveMetrics: job.liveMetrics || {},
        qualityGrade: job.qualityGrade,
        qualityScore: job.qualityScore,
        fileIndex: job.fileIndex,
        totalFiles: job.totalFiles,
        currentFilename: job.currentFilename,
        chunksCompleted: job.chunksCompleted,
        chunksTotal: job.chunksTotal,
        extraction_mode: job.extraction_mode,
      };
    }

    function persistJobs() {
      try {
        const records = jobs.map(jobToRecord);
        localStorage.setItem(JOB_STORAGE_KEY, JSON.stringify(records));
      } catch (e) { /* ignore */ }
    }

    function updateRunningJobIndicator() {
      const el = document.getElementById('job-queue-running-indicator');
      if (!el) return;
      const hasRunning = jobs.some(j => j.status === 'running');
      if (hasRunning) el.classList.remove('hidden'); else el.classList.add('hidden');
    }

    function loadJobsFromStorage() {
      if (!jobQueue) return;
      try {
        const raw = localStorage.getItem(JOB_STORAGE_KEY);
        if (!raw) return;
        const records = JSON.parse(raw);
        if (!Array.isArray(records) || records.length === 0) return;
        const sorted = records.slice().sort((a, b) => (b.localId || 0) - (a.localId || 0));
        for (const rec of sorted) {
          const job = { ...rec, card: null, abortController: null, progress: rec.progress || {} };
          jobs.push(job);
          job.card = createJobCard(job);
          const typeClass = job.jobType === 'create' ? 'job-create' : (job.jobType === 'enrich' ? 'job-enrich' : 'job-extend');
          job.card.className = 'job-card job-clickable ' + typeClass + ' ' + (job.status || 'done');
          jobQueue.appendChild(job.card);
          if (job.status === 'done' && (job.pipeline_report || job.enrichment_report)) {
            const sl = job.card.querySelector('.stage-label');
            if (sl) sl.textContent = 'Complete';
            const metricsEl = job.card.querySelector('.job-metrics');
            if (metricsEl) {
              if (job.enrichment_report) {
                const er = job.enrichment_report;
                const mp = [(er.pages_fetched ?? 0) + ' pages'];
                if (er.nodes_added) mp.push('+' + er.nodes_added + ' nodes');
                if (er.nodes_updated) mp.push(er.nodes_updated + ' updated');
                if (er.edges_added) mp.push('+' + er.edges_added + ' edges');
                if (er.axioms_added) mp.push('+' + er.axioms_added + ' axioms');
                if (er.dp_added) mp.push('+' + er.dp_added + ' data props');
                metricsEl.textContent = mp.join(' · ');
              } else {
                const report = job.pipeline_report;
                const totals = report.totals || report.extraction_totals || {};
                const cls = totals.classes ?? 0, inst = totals.instances ?? 0, rel = totals.relations ?? 0;
                const elapsed = report.elapsed_seconds ?? 0;
                metricsEl.textContent = (cls + ' cls, ' + inst + ' inst, ' + rel + ' rel' + (elapsed > 0 ? ' · ' + elapsed.toFixed(1) + 's' : ''));
              }
            }
          } else if (job.status === 'error' || job.status === 'cancelled') {
            const sl = job.card.querySelector('.stage-label');
            if (sl) sl.textContent = job.status === 'cancelled' ? 'Cancelled' : 'Failed';
            const cancelBtn = job.card.querySelector('.job-cancel');
            if (cancelBtn) cancelBtn.style.display = 'none';
          }
        }
        updateRunningJobIndicator();
      } catch (e) { /* ignore */ }
    }

    function clearJobsStorage() {
      try {
        localStorage.removeItem(JOB_STORAGE_KEY);
        jobs.length = 0;
        if (jobQueue) {
          while (jobQueue.firstChild) jobQueue.removeChild(jobQueue.firstChild);
        }
        updateRunningJobIndicator();
      } catch (e) { /* ignore */ }
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
      } else if (step === 'web_fetch_query') {
        job.liveProgress = { phase: 'fetch', query: d.query, queryIndex: d.query_index, totalQueries: d.total_queries, remaining: d.remaining_queries, pagesSoFar: d.pages_so_far };
      } else if (step === 'web_fetch_page') {
        job.liveProgress = { phase: 'fetch_page', title: d.title, url: d.url, query: d.query, pagesSoFar: d.pages_so_far };
      } else if (step === 'web_build_section') {
        job.liveProgress = { phase: 'build', title: d.title, pageIndex: d.page_index, totalPages: d.total_pages, remaining: d.remaining_pages };
      } else if (step === 'extract' && d.remaining_chunks != null) {
        job.liveProgress = { phase: 'extract', current: d.current, total: d.total, remaining: d.remaining_chunks, preview: d.chunk_preview };
      } else if (step === 'merge_done') {
        job.liveMetrics.classes = d.classes ?? 0;
        job.liveMetrics.instances = d.instances ?? 0;
        job.liveMetrics.relations = d.relations ?? 0;
        job.liveMetrics.axioms = d.axioms ?? 0;
        job.liveMetrics.data_properties = d.data_properties ?? 0;
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
          'extract': chunksTotal > 0 ? chunksDone + '/' + chunksTotal + ' chunks' : 'Extracting...',
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
          'web_queries_start': 'Inferring queries...',
          'web_queries_planned': (d.count ? d.count + ' queries' : 'Queries planned'),
          'web_fetch_query': (d.query ? 'Query ' + (d.query_index || '?') + '/' + (d.total_queries || '?') + ': ' + (d.query || '').slice(0, 30) : 'Fetching...'),
          'web_fetch_page': (d.title ? 'Fetching: ' + (d.title || '').slice(0, 40) : 'Fetching page...'),
          'web_build_section': (d.title ? 'Section ' + (d.page_index || '?') + '/' + (d.total_pages || '?') : 'Building doc...'),
          'web_pages_fetched': (d.count ? d.count + ' pages fetched' : 'Pages fetched'),
          'web_document_built': 'Document built',
          'web_pipeline_run': 'Running extraction...',
          'web_analysis_start': 'Analyzing graph...',
          'web_analysis_done': (d.grade ? 'Grade ' + d.grade : (d.nodes ? d.nodes + ' nodes' : 'Analysis done')),
          'web_threshold_check': (d.passed ? 'Threshold met' : (d.reason || 'Checking threshold')),
          'web_merge_done': (d.merge_skipped ? (d.skip_reason || 'Skipped') : ((d.nodes_added ? '+' + d.nodes_added + ' nodes ' : '') + (d.nodes_updated ? d.nodes_updated + ' updated ' : '') + (d.edges_added ? '+' + d.edges_added + ' edges ' : '') + (d.axioms_added ? '+' + d.axioms_added + ' axioms ' : '') + (d.dp_added ? '+' + d.dp_added + ' data props' : '') || 'Merged')),
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
          const cls = d.classes ?? 0, inst = d.instances ?? 0, rel = d.relations ?? 0, ax = d.axioms ?? 0, dp = d.data_properties ?? 0;
          metricsEl.textContent = cls + ' cls, ' + inst + ' inst, ' + rel + ' rel' + (ax > 0 ? ', ' + ax + ' ax' : '') + (dp > 0 ? ', ' + dp + ' data props' : '');
        } else if (step === 'inference_done' && d.inferred) {
          metricsEl.textContent = '+ ' + (d.inferred || 0) + ' inferred relations';
        } else if (step === 'reasoning_done') {
          const inf = d.inferred_edges ?? 0, iter = d.iterations ?? 0;
          if (inf > 0) metricsEl.textContent = inf + ' relations in ' + iter + ' reasoning iterations';
        } else if (step === 'quality_done' && d.grade) {
          metricsEl.textContent = 'Grade ' + d.grade + (d.score != null ? ' · ' + Number(d.score).toFixed(2) : '');
        } else if (step === 'web_queries_planned' && d.count) {
          metricsEl.textContent = d.count + ' search queries';
        } else if (step === 'web_pages_fetched' && d.count) {
          metricsEl.textContent = d.count + ' pages fetched';
        } else if (step === 'web_merge_done') {
          if (d.merge_skipped) metricsEl.textContent = d.skip_reason || 'Skipped';
          else {
            const p = [];
            if (d.nodes_added) p.push('+' + d.nodes_added + ' nodes');
            if (d.nodes_updated) p.push(d.nodes_updated + ' updated');
            if (d.edges_added) p.push('+' + d.edges_added + ' edges');
            if (d.axioms_added) p.push('+' + d.axioms_added + ' axioms');
            if (d.dp_added) p.push('+' + d.dp_added + ' data props');
            metricsEl.textContent = p.length ? p.join(', ') : 'Merged';
          }
        } else if (step === 'web_analysis_done' && d.grade) {
          metricsEl.textContent = 'Grade ' + d.grade + (d.score != null ? ' · ' + Number(d.score).toFixed(2) : '');
        } else if (step === 'web_threshold_check') {
          metricsEl.textContent = d.passed ? 'Passed' : (d.reason || '');
        } else if (step === 'web_fetch_query' && d.remaining_queries != null) {
          metricsEl.textContent = (d.query_index || '?') + '/' + (d.total_queries || '?') + ' queries · ' + (d.remaining_queries || 0) + ' left · ' + (d.pages_so_far || 0) + ' pages';
        } else if (step === 'web_fetch_page') {
          metricsEl.textContent = (d.pages_so_far || 0) + ' pages';
        } else if (step === 'web_build_section' && d.remaining_pages != null) {
          metricsEl.textContent = (d.page_index || '?') + '/' + (d.total_pages || '?') + ' · ' + (d.remaining_pages || 0) + ' left';
        } else if (step === 'extract' && d.remaining_chunks != null) {
          metricsEl.textContent = (d.current || '?') + '/' + (d.total || '?') + ' chunks · ' + (d.remaining_chunks || 0) + ' left';
        }
      }
      if (_modalJob && _modalJob.localId === job.localId) {
        showJobDetailModal(job);
      }
    }

    function showJobDetailModal(job) {
      _modalJob = job;
      jobDetailTitle.textContent = job.title || 'Job Details';
      const subtitleEl = document.getElementById('job-detail-subtitle');
      const iconEl = document.getElementById('job-detail-icon');
      const typeLabels = { create: 'New ontology from documents', enrich: 'Web content fetch and merge', extend: 'Add documents to existing ontology' };
      if (subtitleEl) subtitleEl.textContent = typeLabels[job.jobType] || 'Document processing and extraction';
      if (iconEl) {
        const icons = {
          create: { bg: 'var(--teal-2)', color: 'var(--teal)', path: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' },
          enrich: { bg: 'var(--accent-12)', color: 'var(--accent)', path: 'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9' },
          extend: { bg: 'var(--accent-secondary-15)', color: 'var(--accent-secondary)', path: 'M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12' }
        };
        const cfg = icons[job.jobType] || icons.create;
        iconEl.style.background = cfg.bg;
        iconEl.innerHTML = '<svg class="w-5 h-5" style="color:' + cfg.color + ';" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="' + cfg.path + '"/></svg>';
      }
      if (job.jobType === 'enrich') {
        const er = job.enrichment_report || {};
        const progress = job.progress || {};
        const hasQueries = !!progress.web_queries_planned;
        const hasPages = !!progress.web_pages_fetched;
        const hasDoc = !!progress.web_document_built;
        const docSkipped = progress.web_document_built && progress.web_document_built.skipped;
        const hasPipeline = !!progress.web_pipeline_run;
        const hasAnalysis = !!progress.web_analysis_done;
        const hasThreshold = !!progress.web_threshold_check;
        const hasMerge = !!progress.web_merge_done;
        const mergeSkipped = er.merge_skipped || progress.web_merge_done?.merge_skipped;
        const skipReason = er.skip_reason || progress.web_merge_done?.skip_reason || '';
        const analysis = er.analysis || {};
        const queries = er.queries || progress.web_queries_planned?.queries || [];
        const queryCount = er.queries_count ?? progress.web_queries_planned?.count ?? queries.length;
        const pagesCount = er.pages_fetched ?? progress.web_pages_fetched?.count ?? 0;
        const stepStatus = (done, running) => done ? '<span style="color:var(--success);">✓</span>' : (running ? '<span style="color:var(--accent-secondary);">●</span>' : '<span style="color:var(--text-muted-2);">○</span>');
        let html = '<div class="space-y-4">';
        html += '<div class="rounded-lg p-3" style="background:var(--bg-input); border:1px solid var(--border);">';
        html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Status</p>';
        html += '<p class="font-mono text-sm"><span class="stat-value">' + (job.status || 'running') + '</span></p>';
        if (mergeSkipped && skipReason) html += '<p class="text-xs mt-1" style="color:var(--warning);">' + esc(skipReason) + '</p>';
        html += '</div>';
        var lp = job.liveProgress;
        if (lp && job.status === 'running') {
          html += '<div class="rounded-lg p-3" style="background:var(--accent-5); border:1px solid var(--accent-4);">';
          html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Processing progress</p>';
          if (lp.phase === 'fetch') {
            html += '<p class="text-sm" style="color:var(--text-primary);">Query ' + (lp.queryIndex || '?') + '/' + (lp.totalQueries || '?') + ': <span class="font-mono">' + esc((lp.query || '').slice(0, 50)) + '</span></p>';
            html += '<p class="text-xs mt-1" style="color:var(--text-muted);">' + (lp.remaining ?? '?') + ' queries remaining · ' + (lp.pagesSoFar ?? 0) + ' pages fetched so far</p>';
          } else if (lp.phase === 'fetch_page') {
            html += '<p class="text-sm" style="color:var(--text-primary);">Fetching: ' + esc((lp.title || '').slice(0, 60)) + '</p>';
            html += '<p class="text-xs mt-1 font-mono break-all" style="color:var(--text-muted);">' + esc((lp.url || '').slice(0, 80)) + '</p>';
            html += '<p class="text-xs mt-1" style="color:var(--text-muted);">' + (lp.pagesSoFar ?? 0) + ' pages so far</p>';
          } else if (lp.phase === 'build') {
            html += '<p class="text-sm" style="color:var(--text-primary);">Section ' + (lp.pageIndex || '?') + '/' + (lp.totalPages || '?') + ': ' + esc((lp.title || '').slice(0, 50)) + '</p>';
            html += '<p class="text-xs mt-1" style="color:var(--text-muted);">' + (lp.remaining ?? '?') + ' sections remaining</p>';
          } else if (lp.phase === 'extract') {
            html += '<p class="text-sm" style="color:var(--text-primary);">Chunk ' + (lp.current || '?') + '/' + (lp.total || '?') + ' · ' + (lp.remaining ?? '?') + ' remaining</p>';
            if (lp.preview) html += '<p class="text-xs mt-1 font-mono italic" style="color:var(--text-muted);">' + esc(lp.preview) + '</p>';
          }
          html += '</div>';
        }
        html += '<div class="rounded-lg overflow-hidden" style="border:1px solid var(--border);">';
        html += '<div class="px-3 py-2" style="background:var(--accent-08); border-bottom:1px solid var(--border);"><p class="text-xs font-semibold uppercase tracking-wider" style="color:var(--accent);">1. Search &amp; build document</p></div>';
        html += '<div class="p-3" style="background:var(--bg-input);"><ol class="space-y-2 text-xs" style="list-style:none; padding-left:0;">';
        html += '<li class="flex items-start gap-2">' + stepStatus(hasQueries, !!progress.web_queries_start && !hasQueries) + '<div><strong>Infer queries</strong><br><span style="color:var(--text-muted);">Batch-infer search queries from graph context</span><br>';
        if (hasQueries && queries.length > 0) {
          html += '<span class="font-mono mt-1 block" style="color:var(--text-primary);">' + queryCount + ' queries: ' + esc(queries.slice(0, 3).join(', ')) + (queries.length > 3 ? ' …' : '') + '</span>';
        } else {
          html += '<span class="font-mono mt-1" style="color:var(--text-primary);">' + (hasQueries ? queryCount + ' queries' : 'Inferring...') + '</span>';
        }
        html += '</div></li>';
        html += '<li class="flex items-start gap-2">' + stepStatus(hasPages, !!progress.web_pages_fetched && !hasDoc) + '<div><strong>Fetch &amp; score</strong><br><span style="color:var(--text-muted);">Search DuckDuckGo, fetch pages, filter by fidelity</span><br>';
        html += '<span class="font-mono mt-1" style="color:var(--text-primary);">' + (hasPages ? pagesCount + ' pages passed min fidelity' : 'Fetching...') + '</span>';
        if (hasPages && pagesCount === 0) html += '<br><span style="color:var(--warning);">No pages passed. Try lowering min fidelity.</span>';
        html += '</div></li>';
        html += '<li class="flex items-start gap-2">' + stepStatus(hasDoc, !!progress.web_document_built && !hasPipeline) + '<div><strong>Build document</strong><br><span style="color:var(--text-muted);">Assemble Markdown from fetched content</span><br>';
        html += '<span class="font-mono mt-1" style="color:var(--text-primary);">' + (hasDoc ? (docSkipped ? 'Skipped (no pages)' : (er.doc_path ? esc(er.doc_path) : 'Built')) : 'Building...') + '</span></div></li>';
        html += '</ol></div></div>';
        html += '<div class="rounded-lg overflow-hidden" style="border:1px solid var(--border);">';
        html += '<div class="px-3 py-2" style="background:var(--accent-08); border-bottom:1px solid var(--border);"><p class="text-xs font-semibold uppercase tracking-wider" style="color:var(--accent);">2. Document processing</p></div>';
        html += '<div class="p-3" style="background:var(--bg-input);"><ol class="space-y-2 text-xs" style="list-style:none; padding-left:0;">';
        var pipelineSkipped = progress.web_pipeline_run && progress.web_pipeline_run.skipped;
        html += '<li class="flex items-start gap-2">' + stepStatus(hasPipeline, !!progress.web_pipeline_run && !hasAnalysis && !pipelineSkipped) + '<span><strong>Load &amp; chunk</strong>: ' + (hasPipeline ? (pipelineSkipped ? 'Skipped' : 'Extract ontology from doc') : 'Pending') + '</span></li>';
        var analysisSkipped = progress.web_analysis_done && progress.web_analysis_done.skipped;
        const rel = analysis.reliability || {};
        html += '<li class="flex items-start gap-2">' + stepStatus(hasAnalysis, !!progress.web_analysis_start && !hasThreshold && !analysisSkipped) + '<span><strong>Analyze</strong>: ' + (hasAnalysis ? (analysisSkipped ? 'Skipped' : ('Grade ' + (rel.grade || '—') + (rel.score != null ? ' · ' + Number(rel.score).toFixed(2) : ''))) : 'Pending') + '</span></li>';
        html += '<li class="flex items-start gap-2">' + stepStatus(hasThreshold, !!progress.web_threshold_check && !hasMerge) + '<span><strong>Threshold</strong>: ' + (hasThreshold ? (mergeSkipped ? 'Skipped: ' + esc(skipReason) : 'Passed') : 'Pending') + '</span></li>';
        var mergeDisplay = 'Merging...';
        if (hasMerge) {
          if (mergeSkipped) mergeDisplay = 'Skipped';
          else {
            const mergeData = { ...(progress.web_merge_done || {}), ...er };
            const parts = [];
            if (mergeData.nodes_added) parts.push('+' + mergeData.nodes_added + ' nodes');
            if (mergeData.nodes_updated) parts.push(mergeData.nodes_updated + ' updated');
            if (mergeData.edges_added) parts.push('+' + mergeData.edges_added + ' edges');
            if (mergeData.axioms_added) parts.push('+' + mergeData.axioms_added + ' axioms');
            if (mergeData.dp_added) parts.push('+' + mergeData.dp_added + ' data props');
            mergeDisplay = parts.length ? parts.join(', ') : 'No new entities (all already in graph)';
          }
        }
        html += '<li class="flex items-start gap-2">' + stepStatus(hasMerge, false) + '<span><strong>Merge into graph</strong>: ' + mergeDisplay + '</span></li>';
        html += '</ol></div></div>';
        if (er.doc_path) {
          html += '<div class="rounded-lg p-3" style="background:var(--bg-input); border:1px solid var(--border);">';
          html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Output document</p>';
          html += '<p class="text-xs font-mono break-all" style="color:var(--text-primary);">' + esc(er.doc_path) + '</p></div>';
        }
        html += '<div class="flex justify-end"><button type="button" class="enrich-modal-close-btn px-4 py-2 rounded-lg text-sm font-medium transition-all" style="background:var(--accent-15); color:var(--accent); border:1px solid var(--accent-4);">Close</button></div>';
        if (jobDetailCancelBtn) {
          if (job.status === 'running') {
            jobDetailCancelBtn.classList.remove('hidden');
            jobDetailCancelBtn.onclick = () => { logClick('job-cancel', 'modal', job.localId); cancelJob(job); hideJobDetailModal(); };
          } else {
            jobDetailCancelBtn.classList.add('hidden');
            jobDetailCancelBtn.onclick = null;
          }
        }
        jobDetailContent.innerHTML = html;
        jobDetailModal.classList.remove('hidden');
        return;
      }
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

      const entitiesSectionTitle = (job.status === 'done' || job.status === 'error') ? 'What was added' : 'Entities &amp; Relations';
      html += '<div class="rounded-lg p-3" style="background:var(--bg-input); border:1px solid var(--border);">';
      html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">' + entitiesSectionTitle + '</p>';
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

      const healthData = report.health;
      if (healthData && (job.status === 'done' || job.status === 'error')) {
        const badge = healthData.badge || '—';
        const overallScore = healthData.overall_score ?? 0;
        const badgeColor = badge === 'Healthy' ? 'var(--success)' : (badge === 'Needs Attention' ? 'var(--warning)' : 'var(--error-bright)');
        const str = healthData.structural || {};
        const sem = healthData.semantic || {};
        const ret = healthData.retrieval || {};
        html += '<div class="rounded-lg p-3 mt-3" style="background:var(--bg-input); border:1px solid var(--border);">';
        html += '<p class="text-xs font-medium uppercase tracking-wider mb-2" style="color:var(--text-muted);">Health</p>';
        html += '<div class="flex items-center gap-2 mb-3"><span class="px-2 py-1 rounded text-xs font-medium" style="background:var(--border-subtle); color:' + badgeColor + ';">' + esc(badge) + '</span><span class="text-xs font-mono" style="color:var(--text-muted);">Score: ' + Number(overallScore).toFixed(0) + '/100</span></div>';
        html += '<div class="grid grid-cols-2 gap-2 text-xs font-mono">';
        html += '<div><span style="color:var(--text-muted);">Nodes</span> <span class="stat-value">' + (str.node_count ?? '—') + '</span></div>';
        html += '<div><span style="color:var(--text-muted);">Edges</span> <span class="stat-value">' + (str.edge_count ?? '—') + '</span></div>';
        html += '<div><span style="color:var(--text-muted);">Orphans</span> <span class="stat-value">' + (str.orphan_nodes ?? '—') + '</span></div>';
        html += '<div><span style="color:var(--text-muted);">Components</span> <span class="stat-value">' + (str.connected_components ?? '—') + '</span></div>';
        html += '<div><span style="color:var(--text-muted);">Largest component</span> <span class="stat-value">' + (str.largest_component_coverage != null ? (Number(str.largest_component_coverage * 100).toFixed(0) + '%') : '—') + '</span></div>';
        html += '<div><span style="color:var(--text-muted);">Relation types</span> <span class="stat-value">' + (sem.unique_relation_types ?? '—') + '</span></div>';
        html += '</div></div>';
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
      if (jobDetailCancelBtn) {
        if (job.status === 'running') {
          jobDetailCancelBtn.classList.remove('hidden');
          jobDetailCancelBtn.onclick = () => { logClick('job-cancel', 'modal', job.localId); cancelJob(job); hideJobDetailModal(); };
        } else {
          jobDetailCancelBtn.classList.add('hidden');
          jobDetailCancelBtn.onclick = null;
        }
      }
      jobDetailModal.classList.remove('hidden');
    }

    function hideJobDetailModal() {
      _modalJob = null;
      jobDetailModal.classList.add('hidden');
    }

    document.getElementById('job-detail-close')?.addEventListener('click', hideJobDetailModal);
    jobDetailModal?.querySelector('.modal-backdrop')?.addEventListener('click', hideJobDetailModal);
    jobDetailContent?.addEventListener('click', (e) => {
      if (e.target.closest('.enrich-modal-close-btn')) hideJobDetailModal();
    });

    function setJobStatus(job, status, label) {
      job.status = status;
      persistJobs();
      updateRunningJobIndicator();
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

    async function doUpload(files, title, description, parallel = true, ontologyLanguage = 'en', minQualityGrade = '') {
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
      if (jobQueue) jobQueue.insertBefore(job.card, jobQueue.firstChild);
      if (jobQueueSection) jobQueueSection.classList.remove('collapsed');
      persistJobs();
      updateRunningJobIndicator();
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
      fd.append('ontology_language', ontologyLanguage || 'en');
      if (minQualityGrade) fd.append('min_quality_grade', minQualityGrade);
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
          // Keep completed job in the list so user can open the modal for details
          if (kbStatus) { kbStatus.style.display = 'none'; }
        }
      } catch (e) {
        if (e.name === 'AbortError') {
          setJobStatus(job, 'cancelled', 'Cancelled');
        } else {
          setJobStatus(job, 'error', e.message);
          if (kbStatus) { kbStatus.textContent = 'Job failed: ' + e.message; kbStatus.style.display = ''; kbStatus.style.color = 'var(--error)'; }
        }
        // Keep failed/cancelled jobs in the list so user can open the modal for details
      } finally {
        const hasRunning = jobs.some(j => j.status === 'running');
        if (!hasRunning) setStatusBadge(getActiveKbId() ? 'ready' : 'empty');
      }
    }

    async function doExtend(files, kbId, parallel = true, minQualityGrade = '') {
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
      if (jobQueue) jobQueue.insertBefore(job.card, jobQueue.firstChild);
      if (jobQueueSection) jobQueueSection.classList.remove('collapsed');
      persistJobs();
      updateRunningJobIndicator();
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
      if (minQualityGrade) fd.append('min_quality_grade', minQualityGrade);
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
          // Keep completed job in the list so user can open the modal for details
        }
      } catch (e) {
        if (e.name === 'AbortError') {
          setJobStatus(job, 'cancelled', 'Cancelled');
        } else {
          setJobStatus(job, 'error', e.message);
        }
        // Keep failed/cancelled jobs in the list so user can open the modal for details
      } finally {
        const hasRunning = jobs.some(j => j.status === 'running');
        if (!hasRunning) setStatusBadge(getActiveKbId() ? 'ready' : 'empty');
      }
    }

    async function doEnrich(kbId, minFidelity, maxQueries) {
      const activeKb = _kbData.find(k => k.id === kbId);
      const kbName = activeKb ? activeKb.name : kbId;
      const job = {
        localId: Date.now(),
        title: 'Web Enrichment: ' + kbName,
        description: 'Fetching web content',
        status: 'running',
        serverJobId: null,
        abortController: new AbortController(),
        card: null,
        kbId: kbId,
        jobType: 'enrich',
      };
      jobs.push(job);
      job.card = createJobCard(job);
      if (jobQueue) jobQueue.insertBefore(job.card, jobQueue.firstChild);
      if (jobQueueSection) jobQueueSection.classList.remove('collapsed');
      persistJobs();
      updateRunningJobIndicator();
      setStatusBadge('processing');
      tabDocuments?.click();
      if (_kbData && _kbData.length) renderKbList(_kbData, _activeKbId);

      const params = new URLSearchParams({ min_fidelity: String(minFidelity || 0.3) });
      if (maxQueries) params.set('max_queries', String(maxQueries));
      try {
        const res = await fetch(API + '/knowledge-bases/' + kbId + '/enrich_stream?' + params.toString(), {
          method: 'POST',
          signal: job.abortController.signal,
        });
        if (!res.ok) {
          const text = await res.text().catch(() => '');
          const data = (() => { try { return JSON.parse(text); } catch { return text ? { detail: text } : {}; } })();
          const msg = parseError(data) || res.statusText;
          console.error('[Enrich]', res.status, msg, text ? text.slice(0, 500) : '(no body)');
          throw new Error(msg);
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
              if (ev.type === 'job_started') { job.serverJobId = ev.job_id; continue; }
              if (ev.type === 'error') throw new Error(ev.message || 'Enrichment failed');
              if (ev.type === 'complete') { result = ev; job.pipeline_report = ev.pipeline_report; job.enrichment_report = ev.enrichment_report; break; }
              if (ev.step) updateJobStage(job, ev);
            } catch (e) {
              if (e instanceof SyntaxError) continue;
              throw e;
            }
          }
          if (result) break;
        }
        if (result) {
          setJobStatus(job, 'done', 'Complete');
          const sl = job.card?.querySelector('.stage-label');
          if (sl) sl.textContent = 'Complete';
          const metricsEl = job.card?.querySelector('.job-metrics');
          if (metricsEl && job.enrichment_report) {
            const er = job.enrichment_report;
            const mp = [(er.pages_fetched ?? 0) + ' pages'];
            if (er.nodes_added) mp.push('+' + er.nodes_added + ' nodes');
            if (er.nodes_updated) mp.push(er.nodes_updated + ' updated');
            if (er.edges_added) mp.push('+' + er.edges_added + ' edges');
            if (er.axioms_added) mp.push('+' + er.axioms_added + ' axioms');
            if (er.dp_added) mp.push('+' + er.dp_added + ' data props');
            metricsEl.textContent = mp.join(' · ');
          }
          await loadKBs();
          if (result.kb_id) setActiveKbId(result.kb_id);
        }
      } catch (e) {
        if (e.name === 'AbortError') {
          setJobStatus(job, 'cancelled', 'Cancelled');
        } else {
          setJobStatus(job, 'error', e.message);
        }
      } finally {
        const hasRunning = jobs.some(j => j.status === 'running');
        if (!hasRunning) setStatusBadge(getActiveKbId() ? 'ready' : 'empty');
        hideWebEnrichmentModal();
      }
    }

    // Web Enrichment modal
    const webEnrichmentModal = document.getElementById('web-enrichment-modal');
    const webEnrichmentKbSelect = document.getElementById('web-enrichment-kb-select');
    const webEnrichmentFidelity = document.getElementById('web-enrichment-fidelity');
    const webEnrichmentFidelityValue = document.getElementById('web-enrichment-fidelity-value');
    const webEnrichmentMaxQueries = document.getElementById('web-enrichment-max-queries');
    const webEnrichmentForm = document.getElementById('web-enrichment-form');
    const webEnrichmentProgress = document.getElementById('web-enrichment-progress');
    const webEnrichmentStage = document.getElementById('web-enrichment-stage');
    const webEnrichmentMetrics = document.getElementById('web-enrichment-metrics');

    function showWebEnrichmentModal() {
      if (!webEnrichmentKbSelect) return;
      webEnrichmentKbSelect.innerHTML = '<option value="">Select a KB</option>';
      _kbData.forEach(kb => {
        const opt = document.createElement('option');
        opt.value = kb.id;
        opt.textContent = kb.name || kb.id;
        if (kb.id === getActiveKbId()) opt.selected = true;
        webEnrichmentKbSelect.appendChild(opt);
      });
      webEnrichmentForm?.classList.remove('hidden');
      webEnrichmentProgress?.classList.add('hidden');
      webEnrichmentModal?.classList.remove('hidden');
    }

    function hideWebEnrichmentModal() {
      webEnrichmentModal?.classList.add('hidden');
    }

    document.getElementById('web-enrichment-btn')?.addEventListener('click', () => {
      logClick('web-enrichment', 'open');
      showWebEnrichmentModal();
    });

    webEnrichmentFidelity?.addEventListener('input', () => {
      if (webEnrichmentFidelityValue) webEnrichmentFidelityValue.textContent = Number(webEnrichmentFidelity.value).toFixed(2);
    });

    document.getElementById('web-enrichment-cancel')?.addEventListener('click', hideWebEnrichmentModal);
    webEnrichmentModal?.querySelector('.modal-backdrop')?.addEventListener('click', hideWebEnrichmentModal);

    document.getElementById('web-enrichment-start')?.addEventListener('click', async () => {
      const kbId = webEnrichmentKbSelect?.value;
      if (!kbId) { alert('Please select a knowledge base'); return; }
      const minFidelity = parseFloat(webEnrichmentFidelity?.value || '0.3');
      const maxQueries = webEnrichmentMaxQueries?.value ? parseInt(webEnrichmentMaxQueries.value, 10) : null;
      logClick('web-enrichment', 'start');
      hideWebEnrichmentModal();
      doEnrich(kbId, minFidelity, maxQueries);
    });

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
    currentOntologyName?.addEventListener('click', () => {
      const kbId = getActiveKbId();
      if (kbId) {
        window.open(window.location.origin + API + '/graph/viewer?kb_id=' + encodeURIComponent(kbId), '_blank', 'noopener,noreferrer');
      }
    });

    if (window.matchMedia('(min-width: 769px)').matches) {
      sidebar?.classList.add('open');
    }

    (async function init() {
      logClick('init', 'start');
      try {
        loadJobsFromStorage();
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
