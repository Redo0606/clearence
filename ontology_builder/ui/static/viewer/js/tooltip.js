/**
 * Ontology Graph Viewer - Tooltip system
 */

import { escHtml } from "./utils.js";

export function showTooltip(tooltipEl, node, stats, domPoint, container) {
  if (!tooltipEl) return;
  const meta = node || {};
  const desc = meta.description
    ? '<div class="desc">' + escHtml(meta.description).slice(0, 220) + "</div>"
    : "";
  const relPills = stats.relItems && stats.relItems.length
    ? '<div class="rels">' +
      stats.relItems.map((item) => '<span class="rel-pill">' + escHtml(item[0]) + " ×" + item[1] + "</span>").join("") +
      "</div>"
    : "";
  const total = stats.total || 0;
  const incoming = stats.incoming || 0;
  const outgoing = stats.outgoing || 0;
  tooltipEl.innerHTML =
    '<div class="kind">' + escHtml(meta.kind || "node") + '</div>' +
    '<div class="name">' + escHtml(node?.id || "") + '</div>' +
    '<div class="stats">' +
    '<div class="stat"><span class="v">' + total + '</span><span class="stat-label">links</span></div>' +
    '<div class="stat"><span class="v">' + incoming + '</span><span class="stat-label">in</span></div>' +
    '<div class="stat"><span class="v">' + outgoing + '</span><span class="stat-label">out</span></div>' +
    '</div>' +
    relPills +
    desc;

  requestAnimationFrame(() => {
    const cw = container ? container.clientWidth || 400 : 400;
    const ch = container ? container.clientHeight || 300 : 300;
    const left = Math.min(domPoint.x + 16, cw - 320);
    const top = Math.min(domPoint.y + 16, ch - 200);
    tooltipEl.style.left = Math.round(Math.max(8, left)) + "px";
    tooltipEl.style.top = Math.round(Math.max(8, top)) + "px";
    if (cw === 0 || ch === 0) {
      tooltipEl.style.left = "50%";
      tooltipEl.style.top = "50%";
      tooltipEl.style.transform = "translate(-50%, -50%)";
    }
    tooltipEl.classList.add("visible");
  });
}

export function hideTooltip(tooltipEl) {
  if (tooltipEl) tooltipEl.classList.remove("visible");
}
