/**
 * APPLICATION BOOTSTRAPPER & INITIALIZATION
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Initialize Navigation & Mobile Drawer
  if (window.RAG_NAVIGATION) {
    window.RAG_NAVIGATION.init();
  }

  // 2. Initialize Component Interactions, Sandboxes & Tables
  if (window.RAG_INTERACTIONS) {
    window.RAG_INTERACTIONS.init();
  }

  // 3. Populate Problem vs Solution Comparison Lists
  renderComparisonLists();

  // 4. Populate Limitations & Future Roadmap
  renderLimitationsAndRoadmap();

  // 5. Initialize Mermaid Diagrams
  if (window.RAG_DIAGRAMS) {
    window.RAG_DIAGRAMS.init();
  }
});

function renderComparisonLists() {
  const probList = document.getElementById('problem-comparison-list');
  const solList = document.getElementById('solution-comparison-list');
  if (!probList || !solList || !window.RAG_CONTENT) return;

  const data = window.RAG_CONTENT.problemVsSolution;

  probList.innerHTML = data.problems.map(p => `
    <li class="flex items-start gap-3">
      <span class="text-rose-500 font-bold mt-0.5 select-none">✕</span>
      <div>
        <strong class="text-ink-primary font-semibold block text-sm mb-0.5">${escapeHtml(p.title)}</strong>
        <p class="text-xs text-ink-secondary leading-relaxed m-0">${escapeHtml(p.desc)}</p>
      </div>
    </li>
  `).join('');

  solList.innerHTML = data.solutions.map(s => `
    <li class="flex items-start gap-3">
      <span class="text-emerald-600 font-bold mt-0.5 select-none">✓</span>
      <div>
        <strong class="text-ink-primary font-semibold block text-sm mb-0.5">${escapeHtml(s.title)}</strong>
        <p class="text-xs text-ink-secondary leading-relaxed m-0">${escapeHtml(s.desc)}</p>
      </div>
    </li>
  `).join('');
}

function renderLimitationsAndRoadmap() {
  const limList = document.getElementById('limitations-list');
  const roadList = document.getElementById('roadmap-list');
  if (!limList || !roadList || !window.RAG_CONTENT) return;

  const data = window.RAG_CONTENT.limitationsAndRoadmap;

  limList.innerHTML = data.limitations.map(item => `
    <div class="glass-card p-4 border-l-4 border-l-amber-400">
      <div class="flex items-center justify-between mb-1">
        <h5 class="text-sm font-semibold text-ink-primary">${escapeHtml(item.title)}</h5>
        <span class="badge-quiet badge-neutral text-xs">Current Boundary</span>
      </div>
      <p class="text-xs text-ink-secondary m-0 leading-relaxed">${escapeHtml(item.desc)}</p>
    </div>
  `).join('');

  roadList.innerHTML = data.roadmap.map(item => `
    <div class="glass-card p-4 border-l-4 border-l-brand">
      <div class="flex items-center justify-between mb-1">
        <h5 class="text-sm font-semibold text-ink-primary">${escapeHtml(item.title)}</h5>
        <span class="badge-quiet badge-blue text-xs">Planned Scope</span>
      </div>
      <p class="text-xs text-ink-secondary m-0 leading-relaxed">${escapeHtml(item.desc)}</p>
    </div>
  `).join('');
}

function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
