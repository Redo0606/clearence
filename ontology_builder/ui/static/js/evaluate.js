/**
 * Evaluate tab: Graph Health, QA Evaluation, Records, Modals.
 * Works with app.bundle.js via window.evalTab* callbacks.
 */
(function () {
  'use strict';

  const API = window.APP_CONFIG?.apiBase ?? '/api/v1';

  function esc(s) {
    if (s == null) return '';
    const t = String(s);
    const d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
  }

  function toggleCard(bodyId, chevronId) {
    const body = document.getElementById(bodyId);
    const chevron = document.getElementById(chevronId);
    if (body) body.classList.toggle('expanded');
    if (chevron) chevron.classList.toggle('open');
  }

  function toggleSection(contentId, headerId) {
    const content = document.getElementById(contentId);
    const header = document.getElementById(headerId);
    if (content) content.classList.toggle('collapsed');
    if (header) header.classList.toggle('collapsed');
  }

  function dismissCard(cardId) {
    const card = document.getElementById(cardId);
    if (!card) return;
    card.classList.add('dismissing');
    setTimeout(function () { card.remove(); }, 280);
  }

  function openModal(overlayId) {
    var el = document.getElementById(overlayId);
    if (el) {
      el.classList.add('open');
      document.body.style.overflow = 'hidden';
    }
  }

  function closeModal(overlayId) {
    var el = document.getElementById(overlayId);
    if (el) {
      el.classList.remove('open');
      document.body.style.overflow = '';
    }
  }

  function metricColorClass(value) {
    if (value >= 0.85) return 'high';
    if (value >= 0.70) return 'mid';
    return 'low';
  }

  function evalBadgeClass(avgScore) {
    if (avgScore >= 0.85) return 'badge-complete';
    if (avgScore >= 0.70) return 'badge-expanding';
    return 'badge-attention';
  }

  function buildMetaLine(items) {
    return items.map(function (item, i) {
      const sep = i < items.length - 1 ? '<span class="sep">·</span>' : '';
      return '<span class="val">' + esc(item.value) + '</span> ' + (item.label || '') + sep;
    }).join(' ');
  }

  function flattenHealth(h) {
    var s = h.structural || {};
    var sem = h.semantic || {};
    var r = h.retrieval || {};
    var comps = s.connected_components ?? 0;
    return {
      nodes: s.node_count ?? 0,
      edges: s.edge_count ?? 0,
      density: s.density ?? 0,
      components: comps,
      orphans: s.orphan_nodes ?? 0,
      relation_types: sem.unique_relation_types ?? 0,
      facts_per_node: r.facts_per_node ?? 0,
      hyperedge_coverage: r.hyperedge_coverage ?? 0,
      overall_score: h.overall_score ?? 0,
      badge: h.badge || '—',
      disconnected_subgraphs: Math.max(0, comps - 1),
      recommended_actions: h.recommended_actions || [],
      kb_name: h.kb_name || h.kb_id || '—',
      kb_id: h.kb_id,
    };
  }

  async function loadGraphHealth(kbId) {
    if (!kbId) return null;
    try {
      var res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/health');
      if (!res.ok) return null;
      var data = await res.json();
      return flattenHealth(data);
    } catch (e) {
      console.error('[loadGraphHealth]', e);
      return null;
    }
  }

  function renderGraphHealthCard(data, kbName) {
    var badge = document.getElementById('graph-health-badge');
    var meta = document.getElementById('graph-health-meta');
    var card = document.getElementById('graph-health-card');
    var discon = document.getElementById('health-disconnect-row');

    if (!card) return;

    var score = data.overall_score ?? 0;
    var badgeClass = score >= 85 ? 'badge-healthy' : score >= 60 ? 'badge-attention' : 'badge-failed';
    var badgeText = score >= 85 ? 'Healthy (' + score + ')' : score >= 60 ? 'Needs Attention (' + score + ')' : 'Critical (' + score + ')';

    if (badge) {
      badge.className = 'badge ' + badgeClass;
      badge.textContent = badgeText;
    }

    card.className = 'job-card-eval ' + (score >= 85 ? 'accent-complete' : 'accent-attention');

    if (meta) {
      meta.innerHTML = buildMetaLine([
        { value: data.nodes, label: 'nodes' },
        { value: data.edges, label: 'edges' },
        { value: data.density, label: 'density' },
        { value: data.components, label: 'components' },
        { value: data.orphans, label: 'orphans' },
        { value: data.relation_types, label: 'rel. types' },
        { value: data.facts_per_node, label: 'facts/node' },
      ]);
    }

    if (discon) {
      if (data.disconnected_subgraphs > 0) {
        discon.innerHTML = '<span class="status-dot failed">' + data.disconnected_subgraphs + ' disconnected subgraph(s) detected</span>';
      } else {
        discon.innerHTML = '<span class="status-dot complete">Graph fully connected</span>';
      }
    }

    window._graphHealthData = data;
  }

  function rerunHealth() {
    var kbId = document.getElementById('eval-kb-select')?.value;
    if (!kbId) return;
    loadGraphHealth(kbId).then(function (data) {
      if (data) {
        var sel = document.getElementById('eval-kb-select');
        var opt = sel?.options[sel.selectedIndex];
        renderGraphHealthCard(data, opt ? opt.text : '');
      }
    });
  }

  async function runEvaluation() {
    var kbId = document.getElementById('eval-kb-select')?.value;
    if (!kbId) return;
    var countEl = document.getElementById('eval-num-questions') || document.getElementById('eval-question-count');
    var count = Math.min(500, Math.max(1, parseInt(countEl?.value || '5', 10) || 5));
    var btn = document.getElementById('eval-run-btn') || document.getElementById('btn-run-eval');
    var prog = document.getElementById('eval-progress') || document.getElementById('eval-eval-progress');
    var dot = document.getElementById('eval-status-dot');
    var txt = document.getElementById('eval-status-text');

    if (btn) btn.disabled = true;
    if (prog) prog.style.display = 'block';
    if (dot) dot.className = 'status-dot running';
    if (txt) txt.textContent = 'Starting evaluation…';

    try {
      var res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/evaluate?num_questions=' + count, { method: 'POST' });
      if (!res.ok) throw new Error('Evaluation failed');
      var reader = res.body?.getReader();
      var dec = new TextDecoder();
      var buf = '';
      if (reader) {
        while (true) {
          var r = await reader.read();
          if (r.done) break;
          buf += dec.decode(r.value, { stream: true });
          var lines = buf.split('\n');
          buf = lines.pop() || '';
          for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            if (line.startsWith('data: ')) {
              try {
                var msg = JSON.parse(line.slice(6));
                if (msg.type === 'step' && txt) txt.textContent = msg.message || 'Evaluating…';
                if (msg.type === 'progress' && txt) {
                  var p = msg;
                  txt.textContent = (p.current || 0) + '/' + (p.total || 0) + ' questions';
                }
                if (msg.type === 'complete') {
                  var record = msg.record || {};
                  var scores = msg.scores || record.scores || {};
                  record.scores = scores;
                  record.timestamp = record.timestamp || new Date().toISOString();
                  record.num_questions = record.num_questions ?? count;
                  prependEvaluationRecord(record);
                  if (txt) txt.textContent = 'Evaluation complete';
                  if (dot) dot.className = 'status-dot complete';
                }
                if (msg.type === 'error') {
                  if (txt) txt.textContent = 'Error: ' + (msg.message || 'Unknown');
                  if (dot) dot.className = 'status-dot failed';
                }
              } catch (_) {}
            }
          }
        }
      }
    } catch (e) {
      if (txt) txt.textContent = 'Error: ' + (e.message || 'Connection error');
      if (dot) dot.className = 'status-dot failed';
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function buildMetricRows(metrics) {
    if (!metrics || typeof metrics !== 'object') return '';
    return Object.keys(metrics).filter(function (k) {
      return k !== 'per_question' && typeof metrics[k] === 'number';
    }).map(function (key) {
      var val = metrics[key];
      var pct = (val * 100).toFixed(1);
      var cls = metricColorClass(val);
      return '<div class="metric-row"><span class="m-label">' + esc(key.replace(/_/g, ' ')) + '</span><span class="m-value">' + pct + '%</span><div class="m-bar-track"><div class="m-bar-fill ' + cls + '" style="width:' + pct + '%"></div></div></div>';
    }).join('');
  }

  function buildEvalRecordCard(record) {
    var scores = record.scores || {};
    var perQ = scores.per_question || [];
    var avg = 0;
    var vals = ['answer_correctness', 'faithfulness', 'context_recall', 'entity_recall'].map(function (m) { return scores[m]; }).filter(function (v) { return v != null; });
    if (vals.length) avg = vals.reduce(function (a, b) { return a + b; }, 0) / vals.length;
    else if (perQ.length) avg = perQ.reduce(function (a, p) { return a + (p.answer_correctness ?? 0); }, 0) / perQ.length;

    var ac = scores.answer_correctness != null ? scores.answer_correctness : avg;
    var ts = record.timestamp ? new Date(record.timestamp).toLocaleString() : '—';
    var n = record.num_questions ?? perQ.length ?? 0;
    var avgPct = (avg * 100).toFixed(0);
    var acPct = (ac * 100).toFixed(0);
    var badgeCls = evalBadgeClass(avg);
    var id = 'eval-rec-' + (record.timestamp || record.id || '').replace(/\W/g, '');

    var recordB64 = btoa(unescape(encodeURIComponent(JSON.stringify(record))));
    return '<div class="job-card-eval accent-complete" id="' + id + '" data-record="' + esc(recordB64) + '" onclick="var r=window._evalDecode(this.getAttribute(\'data-record\')); if(r&&window.openEvaluationModal) window.openEvaluationModal(r)">' +
      '<button class="btn-dismiss" onclick="event.stopPropagation(); window.dismissEvalCard && window.dismissEvalCard(\'' + id + '\')" title="Dismiss">×</button>' +
      '<div class="job-card-header"><span class="badge ' + badgeCls + '">Score ' + avgPct + '%</span><div><div class="job-card-title">' + esc(ts) + '</div><div class="job-card-subtitle">' + n + ' questions</div></div>' +
      '<button class="btn-chevron" id="chev-' + id + '" onclick="event.stopPropagation(); window.toggleEvalCard && window.toggleEvalCard(\'body-' + id + '\', \'chev-' + id + '\')">∨</button></div>' +
      '<div class="job-card-meta"><div class="meta-line">' + buildMetaLine([
        { value: avgPct + '%', label: 'avg' },
        { value: acPct + '%', label: 'AC' },
        { value: n, label: 'questions' },
      ]) + '</div></div>' +
      '<div class="job-card-body" id="body-' + id + '"><div class="inner-card" style="margin-top:12px"><div class="section-label">Metrics</div>' + buildMetricRows(scores) + '</div></div></div>';
  }

  function prependEvaluationRecord(record) {
    var container = document.getElementById('eval-records-list');
    if (!container) return;
    var first = container.querySelector('.job-card-eval');
    var html = buildEvalRecordCard(record);
    if (first) first.insertAdjacentHTML('beforebegin', html);
    else container.innerHTML = html + (container.innerHTML || '');
  }

  async function loadEvaluationRecords(kbId) {
    var container = document.getElementById('eval-records-list');
    if (!container) return;
    if (!kbId) {
      container.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:8px 0">Select a KB to view evaluation history</p>';
      return;
    }
    container.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:8px 0">Loading…</p>';
    try {
      var res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/evaluation-records');
      if (!res.ok) throw new Error('Failed');
      var data = await res.json();
      var records = Array.isArray(data) ? data : (data.records || []);
      if (!records.length) {
        container.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:8px 0">No evaluation records yet.</p>';
      } else {
        container.innerHTML = records.map(buildEvalRecordCard).join('');
      }
    } catch (e) {
      container.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:8px 0">Error loading records.</p>';
    }
  }

  function toRepairRecordSpec(r) {
    var hb = r.health_before?.structural || {};
    var ha = r.health_after?.structural || {};
    var steps = (r.iteration_summaries || []).map(function (s) {
      var h = s.health || {};
      var st = h.structural || {};
      var n = h.total_nodes ?? st.node_count ?? h.node_count;
      var e = h.total_edges ?? st.edge_count ?? h.edge_count;
      var g = s.gaps_remaining;
      return { name: 'Iteration ' + (s.iteration || '?'), detail: (n != null ? n + ' nodes' : '') + (e != null ? ' · ' + e + ' edges' : '') + (g != null ? ' · ' + g + ' gaps remaining' : '') };
    });
    if (!steps.length && r.edges_added != null) {
      steps = [{ name: 'Repair', detail: '+' + r.edges_added + ' edges · ' + (r.gaps_repaired || 0) + ' definitions' }];
    }
    return {
      timestamp: r.timestamp,
      kb_name: r.kb_name || r.kb_id,
      config: {
        internet_defs: r.repair_internet_definitions,
        iterations: r.repair_iterations,
        confidence_pct: r.min_fidelity != null ? (r.min_fidelity * 100) : null,
      },
      before: { nodes: hb.node_count, edges: hb.edge_count, orphans: hb.orphan_nodes, components: hb.connected_components },
      after: ha.node_count != null ? { nodes: ha.node_count, edges: ha.edge_count, orphans: ha.orphan_nodes, components: ha.connected_components } : null,
      pipeline_steps: steps,
      recommended_actions: [],
      definitions_added: r.definitions_added || {},
      inferred_edges: r.inferred_edges || [],
    };
  }

  function buildRepairRecordCard(record) {
    var r = toRepairRecordSpec(record);
    var ts = r.timestamp ? new Date(r.timestamp).toLocaleString() : '—';
    var id = 'rep-rec-' + (r.timestamp || '').replace(/\W/g, '');
    var cfg = r.config || {};
    var conf = cfg.confidence_pct != null ? cfg.confidence_pct + '%' : '—';

    var recordB64 = btoa(unescape(encodeURIComponent(JSON.stringify(r))));
    return '<div class="job-card-eval accent-new" id="' + id + '" data-record="' + esc(recordB64) + '" onclick="var r=window._evalDecode(this.getAttribute(\'data-record\')); if(r&&window.openRepairDetailModal) window.openRepairDetailModal(r)">' +
      '<button class="btn-dismiss" onclick="event.stopPropagation(); window.dismissEvalCard && window.dismissEvalCard(\'' + id + '\')" title="Dismiss">×</button>' +
      '<div class="job-card-header"><span class="badge badge-complete">Complete</span><div><div class="job-card-title">Repair · ' + esc(ts) + '</div></div>' +
      '<button class="btn-chevron" id="chev-' + id + '" onclick="event.stopPropagation(); window.toggleEvalCard && window.toggleEvalCard(\'body-' + id + '\', \'chev-' + id + '\')">∨</button></div>' +
      '<div class="job-card-meta"><div class="meta-line">' + buildMetaLine([
        { value: cfg.iterations ?? '—', label: 'iterations' },
        { value: '≥' + conf, label: 'confidence' },
        { value: cfg.internet_defs ? 'inet on' : 'inet off' },
      ]) + '</div></div>' +
      '<div class="job-card-body" id="body-' + id + '"><div class="inner-card" style="margin-top:12px"><div class="section-label">Before</div><div class="meta-line">' +
      buildMetaLine([
        { value: r.before?.nodes ?? '—', label: 'nodes' },
        { value: r.before?.edges ?? '—', label: 'edges' },
        { value: r.before?.orphans ?? '—', label: 'orphans' },
      ]) + '</div></div>' +
      (r.after ? '<div class="inner-card"><div class="section-label">After</div><div class="meta-line">' +
      buildMetaLine([
        { value: r.after.nodes, label: 'nodes' },
        { value: r.after.edges, label: 'edges' },
        { value: r.after.orphans, label: 'orphans' },
      ]) + '</div></div>' : '') + '</div></div>';
  }

  async function loadRepairRecords(kbId) {
    var container = document.getElementById('repair-records-list');
    if (!container) return;
    if (!kbId) {
      container.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:8px 0">Select a KB to view repair history</p>';
      return;
    }
    container.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:8px 0">Loading…</p>';
    try {
      var res = await fetch(API + '/knowledge-bases/' + encodeURIComponent(kbId) + '/repair-records');
      if (!res.ok) throw new Error('Failed');
      var data = await res.json();
      var records = Array.isArray(data) ? data : (data.records || []);
      if (!records.length) {
        container.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:8px 0">No repair records yet.</p>';
      } else {
        container.innerHTML = records.map(buildRepairRecordCard).join('');
      }
    } catch (e) {
      container.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:8px 0">Error loading records.</p>';
    }
  }

  function openGraphHealthModal() {
    var d = window._graphHealthData;
    if (!d) return;
    var score = d.overall_score ?? 0;
    var badgeCls = score >= 85 ? 'badge-healthy' : score >= 60 ? 'badge-attention' : 'badge-failed';
    var barCls = score >= 85 ? 'green' : score >= 60 ? 'yellow' : 'red';

    var status = document.getElementById('mgh-status');
    if (status) status.innerHTML = '<span class="badge ' + badgeCls + '">' + (score >= 85 ? 'Healthy' : score >= 60 ? 'Needs Attention' : 'Critical') + '</span>';

    var statGrid = document.getElementById('mgh-stat-grid');
    if (statGrid) {
      var rows = [['Nodes', d.nodes], ['Edges', d.edges], ['Density', d.density], ['Components', d.components], ['Orphans', d.orphans], ['Relation types', d.relation_types], ['Facts/node', d.facts_per_node], ['Hyperedge cov.', d.hyperedge_coverage]];
      statGrid.innerHTML = rows.map(function (x) { return '<span class="sg-label">' + esc(x[0]) + '</span><span class="sg-value">' + esc(x[1]) + '</span>'; }).join('');
    }

    var scoreBadge = document.getElementById('mgh-score-badge');
    if (scoreBadge) {
      scoreBadge.className = 'badge ' + badgeCls;
      scoreBadge.textContent = score >= 85 ? 'A' : score >= 70 ? 'B' : score >= 60 ? 'C' : 'D';
    }

    var bar = document.getElementById('mgh-score-bar');
    if (bar) {
      bar.className = 'progress-fill-eval ' + barCls;
      bar.style.width = score + '%';
    }

    var scoreVal = document.getElementById('mgh-score-val');
    if (scoreVal) scoreVal.textContent = score + '/100';

    var conn = document.getElementById('mgh-connectivity');
    if (conn) conn.innerHTML = d.disconnected_subgraphs > 0
      ? '<span class="status-dot failed">' + d.disconnected_subgraphs + ' disconnected subgraph(s)</span>'
      : '<span class="status-dot complete">Fully connected</span>';

    var actions = document.getElementById('mgh-actions');
    if (actions) {
      var acts = d.recommended_actions || [];
      actions.innerHTML = acts.length ? acts.map(function (a) { return '<div class="action-row"><span class="action-icon">↳</span>' + esc(a) + '</div>'; }).join('') : '<p style="color:var(--text-muted);font-size:13px">No actions recommended.</p>';
    }

    openModal('modal-graph-health');
  }

  function openEvaluationModal(record) {
    var scores = record.scores || {};
    var perQ = scores.per_question || [];
    var avg = 0;
    var vals = ['answer_correctness', 'faithfulness', 'context_recall'].map(function (m) { return scores[m]; }).filter(function (v) { return v != null; });
    if (vals.length) avg = vals.reduce(function (a, b) { return a + b; }, 0) / vals.length;
    else if (perQ.length) avg = perQ.reduce(function (a, p) { return a + (p.answer_correctness ?? 0); }, 0) / perQ.length;

    var ac = scores.answer_correctness != null ? scores.answer_correctness : avg;
    var ts = record.timestamp ? new Date(record.timestamp).toLocaleString() : '—';
    var n = record.num_questions ?? perQ.length ?? 0;
    var avgPct = (avg * 100).toFixed(1);
    var acPct = (ac * 100).toFixed(1);
    var bc = evalBadgeClass(avg);

    var sub = document.getElementById('med-subtitle');
    if (sub) sub.textContent = ts + ' · ' + n + ' questions';

    var status = document.getElementById('med-status');
    if (status) status.innerHTML = '<span class="badge ' + bc + '">Avg ' + avgPct + '%</span><span class="status-dot complete" style="margin-left:12px">Complete</span>';

    var config = document.getElementById('med-config');
    if (config) config.innerHTML = [
      ['Questions', n], ['Knowledge Base', record.kb_name || '—'], ['Run at', ts], ['Model', record.model || '—']
    ].map(function (x) { return '<span class="sg-label">' + esc(x[0]) + '</span><span class="sg-value">' + esc(x[1]) + '</span>'; }).join('');

    var metrics = document.getElementById('med-metrics');
    if (metrics) metrics.innerHTML = buildMetricRows(scores);

    var agg = document.getElementById('med-aggregate');
    if (agg) {
      var best = Object.keys(scores).filter(function (k) { return k !== 'per_question' && typeof scores[k] === 'number'; });
      var bestK = best.length ? best.reduce(function (a, b) { return scores[b] > scores[a] ? b : a; }) : '';
      var worstK = best.length ? best.reduce(function (a, b) { return scores[b] < scores[a] ? b : a; }) : '';
      agg.innerHTML = [
        ['Average Score', avgPct + '%'],
        ['Answer Correctness', acPct + '%'],
        ['Top metric', bestK ? bestK.replace(/_/g, ' ') + ' (' + (scores[bestK] * 100).toFixed(1) + '%)' : '—'],
        ['Lowest metric', worstK ? worstK.replace(/_/g, ' ') + ' (' + (scores[worstK] * 100).toFixed(1) + '%)' : '—'],
      ].map(function (x) { return '<span class="sg-label">' + esc(x[0]) + '</span><span class="sg-value">' + esc(x[1]) + '</span>'; }).join('');
    }

    var wrap = document.getElementById('med-warnings-wrap');
    var lowCount = perQ.filter(function (q) { return (q.answer_correctness ?? q.score ?? 0) < 0.60; }).length;
    if (wrap) {
      wrap.style.display = lowCount > 0 ? '' : 'none';
      var warn = document.getElementById('med-warnings');
      if (warn) warn.innerHTML = lowCount > 0 ? '<div class="alert-box"><div class="alert-title">⚠ ' + lowCount + ' question(s) scored below 0.60</div></div>' : '';
    }

    var tbody = document.getElementById('med-qlog-body');
    if (tbody) {
      tbody.innerHTML = perQ.map(function (q, i) {
        var s = (q.answer_correctness ?? q.score ?? 0) * 100;
        var sCls = s >= 85 ? 'q-score-high' : s >= 70 ? 'q-score-mid' : 'q-score-low';
        var pass = s >= 60;
        return '<tr><td style="color:var(--text-label)">' + (i + 1) + '</td><td class="q-text">' + esc(q.question || '') + '</td><td class="' + sCls + '">' + s.toFixed(0) + '%</td><td class="' + (pass ? 'q-pass' : 'q-fail') + '">' + (pass ? '✓ pass' : '✗ fail') + '</td></tr>';
      }).join('');
    }

    openModal('modal-eval-detail');
  }

  function openRepairDetailModal(record) {
    var ts = record.timestamp ? new Date(record.timestamp).toLocaleString() : '—';

    var sub = document.getElementById('mrd-subtitle');
    if (sub) sub.textContent = ts + ' · ' + (record.kb_name || '—');

    var status = document.getElementById('mrd-status');
    if (status) status.innerHTML = '<span class="badge badge-complete">Complete</span><span class="status-dot complete" style="margin-left:12px">Done</span>';

    var cfg = record.config || {};
    var config = document.getElementById('mrd-config');
    if (config) config.innerHTML = [
      ['Internet defs', cfg.internet_defs ? 'On' : 'Off'],
      ['Iterations', cfg.iterations ?? '—'],
      ['Confidence', '≥' + (cfg.confidence_pct ?? '—') + '%'],
      ['Mode', cfg.mode || 'auto'],
    ].map(function (x) { return '<span class="sg-label">' + esc(x[0]) + '</span><span class="sg-value">' + esc(x[1]) + '</span>'; }).join('');

    function renderStatGrid(obj, refObj) {
      var keys = [['Nodes', 'nodes'], ['Edges', 'edges'], ['Orphans', 'orphans'], ['Components', 'components']];
      return keys.map(function (x) {
        var val = obj?.[x[1]] ?? '—';
        var delta = refObj && obj ? obj[x[1]] - refObj[x[1]] : null;
        var dHtml = delta === null ? '' : (delta > 0 ? '<span class="sg-delta-pos">+' + delta + '</span>' : delta < 0 ? '<span class="sg-delta-neg">' + delta + '</span>' : '');
        return '<span class="sg-label">' + esc(x[0]) + '</span><span class="sg-value">' + esc(val) + dHtml + '</span>';
      }).join('');
    }

    var before = document.getElementById('mrd-before');
    if (before) before.innerHTML = renderStatGrid(record.before, null);

    var after = document.getElementById('mrd-after');
    var afterCard = document.getElementById('mrd-after-card');
    if (after) after.innerHTML = renderStatGrid(record.after, record.before);
    if (afterCard) afterCard.style.display = record.after ? '' : 'none';

    var pipeline = document.getElementById('mrd-pipeline');
    if (pipeline) pipeline.innerHTML = (record.pipeline_steps || []).map(function (step) {
      return '<div class="pipeline-step"><span class="ps-check">✓</span><span><span class="ps-label">' + esc(step.name || '') + '</span>' + (step.detail ? '<span class="ps-detail"> · ' + esc(step.detail) + '</span>' : '') + '</span></div>';
    }).join('');

    var elementsCard = document.getElementById('mrd-elements-card');
    var elementsEl = document.getElementById('mrd-elements');
    var defs = record.definitions_added || {};
    var edges = record.inferred_edges || [];
    var defKeys = Object.keys(defs);
    var hasElements = defKeys.length > 0 || edges.length > 0;
    if (elementsCard) elementsCard.style.display = hasElements ? '' : 'none';
    if (elementsEl && hasElements) {
      var parts = [];
      var maxShow = 8;
      var maxEdgesShow = 15;
      if (defKeys.length > 0) {
        var defList = defKeys.length <= maxShow
          ? defKeys.map(function (k) { return '<span class="element-tag">' + esc(k) + '</span>'; }).join('')
          : '<span class="element-summary">' + defKeys.length + ' definitions: ' + defKeys.slice(0, 5).map(esc).join(', ') + '…</span>';
        parts.push('<div class="elements-block"><div class="section-sublabel">Definitions</div><div class="elements-list">' + defList + '</div></div>');
      }
      if (edges.length > 0) {
        var fmt = function (e) {
          var s = Array.isArray(e) ? e : [e.source, e.relation || e[1], e.target || e[2]];
          var src = s[0] || '', rel = s[1] || '', tgt = s[2] || '';
          return src + ' → ' + tgt + (rel ? ' (' + rel + ')' : '');
        };
        var edgeList = edges.length <= maxEdgesShow
          ? edges.map(function (e) { return '<div class="element-edge">' + esc(fmt(e)) + '</div>'; }).join('')
          : '<div class="element-summary">' + edges.length + ' edges: ' + edges.slice(0, 5).map(function (e) { return esc(fmt(e)); }).join(', ') + '…</div>';
        parts.push('<div class="elements-block"><div class="section-sublabel">Edges</div><div class="elements-list">' + edgeList + '</div></div>');
      }
      elementsEl.innerHTML = parts.join('');
    }

    var acCard = document.getElementById('mrd-actions-card');
    var acts = record.recommended_actions || [];
    if (acCard) acCard.style.display = acts.length ? '' : 'none';
    var acEl = document.getElementById('mrd-actions');
    if (acEl) acEl.innerHTML = acts.map(function (a) { return '<div class="action-row"><span class="action-icon">↳</span>' + esc(a) + '</div>'; }).join('');

    openModal('modal-repair-detail');
  }

  function onKbChange(kbId) {
    if (kbId) {
      loadGraphHealth(kbId).then(function (data) {
        if (data) {
          var sel = document.getElementById('eval-kb-select');
          var opt = sel?.options[sel.selectedIndex];
          renderGraphHealthCard(data, opt ? opt.text : '');
        }
      });
      loadEvaluationRecords(kbId);
      loadRepairRecords(kbId);
    } else {
      var card = document.getElementById('graph-health-card');
      if (card) card.classList.add('accent-attention');
      var badge = document.getElementById('graph-health-badge');
      if (badge) { badge.className = 'badge badge-attention'; badge.textContent = '—'; }
      var meta = document.getElementById('graph-health-meta');
      if (meta) meta.innerHTML = 'Select a KB to view health';
      var discon = document.getElementById('health-disconnect-row');
      if (discon) discon.innerHTML = '';
      loadEvaluationRecords('');
      loadRepairRecords('');
    }
  }

  function onTabShow(kbId) {
    onKbChange(kbId);
  }

  function evalDecode(b64) {
    if (!b64) return null;
    try {
      return JSON.parse(decodeURIComponent(escape(atob(b64))));
    } catch (e) { return null; }
  }

  function init() {
    if (!document.getElementById('graph-health-card')) return;

    window._evalDecode = evalDecode;
    window.evalCloseModal = closeModal;
    window.toggleEvalCard = toggleCard;
    window.toggleEvalSection = toggleSection;
    window.dismissEvalCard = dismissCard;
    window.openEvaluationModal = openEvaluationModal;
    window.openRepairDetailModal = openRepairDetailModal;
    window.openGraphHealthModal = openGraphHealthModal;
    window.rerunHealth = rerunHealth;

    window.evalTabOnKbChange = onKbChange;
    window.evalTabOnShow = onTabShow;
    window.evalTabOnRepairComplete = function (kbId) {
      loadGraphHealth(kbId).then(function (data) {
        if (data) {
          var sel = document.getElementById('eval-kb-select');
          var opt = sel && sel.options[sel.selectedIndex];
          renderGraphHealthCard(data, opt ? opt.text : '');
        }
      });
      loadRepairRecords(kbId);
    };
    window.evalTabRerunHealth = rerunHealth;
    window.evalTabRunEvaluation = runEvaluation;
    window.evalOpenRepairModal = function () {
      document.getElementById('eval-repair-btn')?.click();
      setTimeout(function () {
        var es = document.getElementById('eval-kb-select');
        var rs = document.getElementById('repair-kb-select');
        if (es && es.value && rs) rs.value = es.value;
      }, 50);
    };

    document.querySelectorAll('.modal-overlay').forEach(function (overlay) {
      overlay.addEventListener('click', function (e) {
        if (e.target === overlay) closeModal(overlay.id);
      });
    });

    var kbId = document.getElementById('eval-kb-select')?.value;
    if (kbId) onKbChange(kbId);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
