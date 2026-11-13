/**
 * COMPONENT INTERACTIONS & EXPLORATION ENGINE
 * Handles architecture component drawer, interactive security sandbox, test matrix, and tabs.
 */

window.RAG_INTERACTIONS = {
  init: function () {
    this.renderArchitectureComponents();
    this.renderSecuritySandbox();
    this.renderTestMatrix();
    this.renderTechStack();
    this.renderDocLibrary();
    this.initEngineeringTabs();
    this.initCopyButtons();
    this.initDrawer();
  },

  // 1. Architecture Component Exploration
  renderArchitectureComponents: function () {
    const container = document.getElementById('arch-components-grid');
    if (!container || !window.RAG_CONTENT) return;

    const components = window.RAG_CONTENT.architectureComponents;
    let html = '';

    components.forEach(comp => {
      html += `
        <div class="glass-card p-5 cursor-pointer hover:border-brand transition-all flex flex-col justify-between"
             data-comp-id="${comp.id}"
             tabindex="0"
             role="button"
             aria-label="Inspect ${escapeHtml(comp.title)}">
          <div>
            <div class="flex items-center justify-between mb-2">
              <span class="badge-quiet badge-neutral text-xs">${escapeHtml(comp.layer)}</span>
              <span class="text-xs text-brand font-mono">Inspect ↗</span>
            </div>
            <h4 class="text-ink-primary font-semibold text-base mb-1">${escapeHtml(comp.title)}</h4>
            <code class="text-xs text-ink-muted block mb-2 font-mono">${escapeHtml(comp.file)}</code>
            <p class="text-xs text-ink-secondary leading-relaxed line-clamp-3">${escapeHtml(comp.role)}</p>
          </div>
          <div class="pt-3 mt-3 border-t border-line-soft flex items-center gap-2 text-xs text-ink-muted">
            <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>View Interface Contract & Failure Mitigation</span>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;

    // Attach click listeners to open detail sheet
    container.querySelectorAll('[data-comp-id]').forEach(el => {
      const id = el.getAttribute('data-comp-id');
      el.addEventListener('click', () => this.openComponentDrawer(id));
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          this.openComponentDrawer(id);
        }
      });
    });
  },

  openComponentDrawer: function (id) {
    const comp = window.RAG_CONTENT.architectureComponents.find(c => c.id === id);
    if (!comp) return;

    const drawer = document.getElementById('component-drawer');
    const backdrop = document.getElementById('component-drawer-backdrop');
    const titleEl = document.getElementById('drawer-title');
    const layerEl = document.getElementById('drawer-layer');
    const bodyEl = document.getElementById('drawer-body');

    if (titleEl) titleEl.textContent = comp.title;
    if (layerEl) layerEl.textContent = `${comp.layer} • ${comp.file}`;

    if (bodyEl) {
      bodyEl.innerHTML = `
        <div class="mb-5">
          <h5 class="text-xs uppercase font-mono tracking-wide text-ink-muted mb-1.5 font-semibold">Subsystem Responsibility</h5>
          <p class="text-sm text-ink-primary leading-relaxed">${escapeHtml(comp.role)}</p>
        </div>

        <div class="mb-5">
          <h5 class="text-xs uppercase font-mono tracking-wide text-ink-muted mb-1.5 font-semibold">Verified Source Code Reference</h5>
          <div class="p-3 bg-canvas-surface border border-line rounded-lg font-mono text-xs text-ink-primary">
            ${escapeHtml(comp.file)}
          </div>
        </div>

        <div class="mb-5">
          <h5 class="text-xs uppercase font-mono tracking-wide text-ink-muted mb-1.5 font-semibold">Interface Specification Contracts</h5>
          <div class="p-3.5 bg-canvas-surface border border-line rounded-lg text-xs font-mono space-y-2">
            <div>
              <span class="text-brand font-semibold">Input Contract:</span>
              <div class="text-ink-secondary mt-0.5">${escapeHtml(comp.inputs)}</div>
            </div>
            <div class="pt-2 border-t border-line-soft">
              <span class="text-emerald-700 font-semibold">Output Contract:</span>
              <div class="text-ink-secondary mt-0.5">${escapeHtml(comp.outputs)}</div>
            </div>
          </div>
        </div>

        <div>
          <h5 class="text-xs uppercase font-mono tracking-wide text-ink-muted mb-1.5 font-semibold">Failure Boundary & Built-in Mitigation</h5>
          <div class="p-3.5 bg-amber-50/50 border border-amber-200/70 rounded-lg text-xs text-ink-secondary leading-relaxed">
            ${escapeHtml(comp.failureMitigation)}
          </div>
        </div>
      `;
    }

    if (drawer) drawer.classList.add('active');
    if (backdrop) backdrop.classList.add('active');
    document.body.style.overflow = 'hidden';
  },

  initDrawer: function () {
    const drawer = document.getElementById('component-drawer');
    const backdrop = document.getElementById('component-drawer-backdrop');
    const closeBtn = document.getElementById('component-drawer-close');

    const close = () => {
      if (drawer) drawer.classList.remove('active');
      if (backdrop) backdrop.classList.remove('active');
      document.body.style.overflow = '';
    };

    if (closeBtn) closeBtn.addEventListener('click', close);
    if (backdrop) backdrop.addEventListener('click', close);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') close();
    });
  },

  // 2. Interactive Security Sandbox
  renderSecuritySandbox: function () {
    const selector = document.getElementById('security-scenarios-selector');
    if (!selector || !window.RAG_CONTENT) return;

    const scenarios = window.RAG_CONTENT.securityScenarios;
    let html = '';

    scenarios.forEach((sc, idx) => {
      const isDefault = idx === 0;
      html += `
        <button class="btn-apple btn-apple-sm ${isDefault ? 'btn-apple-primary' : 'btn-apple-secondary'} scenario-btn"
                data-scenario-idx="${idx}">
          ${escapeHtml(sc.category)}
        </button>
      `;
    });

    selector.innerHTML = html;

    selector.querySelectorAll('.scenario-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        selector.querySelectorAll('.scenario-btn').forEach(b => {
          b.classList.remove('btn-apple-primary');
          b.classList.add('btn-apple-secondary');
        });
        btn.classList.remove('btn-apple-secondary');
        btn.classList.add('btn-apple-primary');

        const idx = parseInt(btn.getAttribute('data-scenario-idx'), 10);
        this.displaySecurityScenario(idx);
      });
    });

    this.displaySecurityScenario(0);
  },

  displaySecurityScenario: function (idx) {
    const sc = window.RAG_CONTENT.securityScenarios[idx];
    if (!sc) return;

    const promptEl = document.getElementById('sandbox-prompt');
    const decisionEl = document.getElementById('sandbox-decision');
    const detectorEl = document.getElementById('sandbox-detector');
    const latencyEl = document.getElementById('sandbox-latency');
    const outcomeEl = document.getElementById('sandbox-outcome');
    const refusalEl = document.getElementById('sandbox-refusal');

    if (promptEl) promptEl.textContent = sc.prompt;
    if (decisionEl) {
      decisionEl.textContent = sc.decision;
      decisionEl.className = `badge-quiet ${sc.badgeClass}`;
    }
    if (detectorEl) detectorEl.textContent = sc.detectedBy;
    if (latencyEl) latencyEl.textContent = sc.latency;
    if (outcomeEl) outcomeEl.textContent = sc.auditOutcome;
    if (refusalEl) refusalEl.textContent = sc.refusalText;
  },

  // 3. Test Suite Matrix
  renderTestMatrix: function () {
    const container = document.getElementById('test-matrix-table');
    if (!container || !window.RAG_CONTENT) return;

    const groups = window.RAG_CONTENT.testSuite.groups;
    let html = `
      <div class="overflow-x-auto border border-line rounded-xl bg-white shadow-card">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="bg-canvas-surface border-b border-line text-ink-muted uppercase font-mono tracking-wider">
              <th class="py-3 px-4 font-semibold">Test Suite File</th>
              <th class="py-3 px-4 font-semibold">Test Method Name</th>
              <th class="py-3 px-4 font-semibold">Target & Verified Assertion</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-line">
    `;

    groups.forEach(group => {
      group.items.forEach((item, idx) => {
        html += `
          <tr class="hover:bg-slate-50/60 transition-colors">
            ${idx === 0 ? `<td rowspan="${group.items.length}" class="py-3.5 px-4 font-mono font-semibold text-ink-primary align-top bg-slate-50/40 border-r border-line">
              <div>${escapeHtml(group.file)}</div>
              <div class="text-xs text-ink-muted font-normal mt-1">${group.count} Automated Tests</div>
            </td>` : ''}
            <td class="py-3 px-4 font-mono text-ink-primary">
              <code>${escapeHtml(item.name)}</code>
            </td>
            <td class="py-3 px-4 text-ink-secondary">
              <span class="badge-quiet badge-green mr-1.5">PASSED</span>
              <span>${escapeHtml(item.expected)}</span>
            </td>
          </tr>
        `;
      });
    });

    html += `
          </tbody>
        </table>
      </div>
    `;

    container.innerHTML = html;
  },

  // 4. Technology Stack
  renderTechStack: function () {
    const container = document.getElementById('tech-stack-grid');
    if (!container || !window.RAG_CONTENT) return;

    let html = '';
    window.RAG_CONTENT.techStack.forEach(cat => {
      html += `
        <div class="glass-card p-5">
          <div class="text-xs uppercase font-mono font-semibold text-brand tracking-wider mb-3">
            ${escapeHtml(cat.category)}
          </div>
          <div class="space-y-3">
      `;
      cat.items.forEach(it => {
        html += `
          <div class="pb-2.5 border-b border-line-soft last:border-0 last:pb-0">
            <div class="flex items-center justify-between mb-1">
              <span class="font-semibold text-ink-primary text-sm">${escapeHtml(it.name)}</span>
              <span class="badge-quiet badge-neutral text-xs font-mono">${escapeHtml(it.version)}</span>
            </div>
            <p class="text-xs text-ink-secondary m-0 leading-relaxed">${escapeHtml(it.role)}</p>
          </div>
        `;
      });
      html += `
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  },

  // 5. Documentation Library
  renderDocLibrary: function () {
    const container = document.getElementById('docs-catalog-grid');
    if (!container || !window.RAG_CONTENT) return;

    let html = '';
    const repoUrl = window.RAG_CONTENT.project.githubRepo;

    window.RAG_CONTENT.documentation.forEach(doc => {
      html += `
        <div class="glass-card p-5 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-2">
              <span class="badge-quiet badge-blue text-xs">${escapeHtml(doc.category)}</span>
              <code class="text-xs text-ink-muted font-mono">${escapeHtml(doc.path)}</code>
            </div>
            <h4 class="text-ink-primary font-semibold text-base mb-1.5">${escapeHtml(doc.title)}</h4>
            <p class="text-xs text-ink-secondary leading-relaxed mb-4">${escapeHtml(doc.desc)}</p>
          </div>
          <div>
            <a href="${repoUrl}/blob/main/${doc.path}" target="_blank" rel="noopener noreferrer"
               class="btn-apple btn-apple-secondary btn-apple-sm w-full text-center">
              <span>View Verified Document ↗</span>
            </a>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  },

  // 6. Engineering Deep Dive Tabs
  initEngineeringTabs: function () {
    const tabBtns = document.querySelectorAll('.eng-tab-btn');
    const panes = document.querySelectorAll('.eng-tab-pane');

    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        tabBtns.forEach(b => {
          b.classList.remove('border-brand', 'text-ink-primary', 'bg-white');
          b.classList.add('border-transparent', 'text-ink-muted');
        });
        btn.classList.add('border-brand', 'text-ink-primary', 'bg-white');
        btn.classList.remove('border-transparent', 'text-ink-muted');

        const tabId = btn.getAttribute('data-tab');
        panes.forEach(pane => {
          if (pane.id === tabId) {
            pane.classList.remove('hidden');
          } else {
            pane.classList.add('hidden');
          }
        });
      });
    });
  },

  // 7. Clipboard Copy
  initCopyButtons: function () {
    document.querySelectorAll('.copy-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const text = btn.getAttribute('data-copy') || '';
        if (text) {
          navigator.clipboard.writeText(text).then(() => {
            const original = btn.textContent;
            btn.textContent = 'Copied ✓';
            setTimeout(() => {
              btn.textContent = original;
            }, 2000);
          });
        }
      });
    });
  }
};

function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
