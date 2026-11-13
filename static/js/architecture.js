/**
 * INTERACTIVE ARCHITECTURE EXPLORER
 * Handles layer filtering, component inspection, and technical drawer interaction.
 */

(function () {
  const data = window.RAG_DATA;
  if (!data) return;

  const nodes = data.architectureNodes;

  function renderArchitecture() {
    const container = document.getElementById("arch-nodes-container");
    if (!container) return;

    // Group nodes by Layer
    const layers = {};
    nodes.forEach(node => {
      if (!layers[node.layer]) layers[node.layer] = [];
      layers[node.layer].push(node);
    });

    let html = `<div class="arch-layers-grid">`;

    for (const [layerName, layerNodes] of Object.entries(layers)) {
      html += `
        <div class="arch-layer" data-layer="${escapeHtml(layerName)}">
          <div class="arch-layer-header">
            <span class="arch-layer-title">
              <span class="status-dot"></span>
              ${escapeHtml(layerName)}
            </span>
            <span class="badge badge-dark">${layerNodes.length} Components</span>
          </div>
          <div class="arch-nodes-row">
      `;

      layerNodes.forEach(node => {
        html += `
          <div class="arch-node" data-id="${node.id}" tabindex="0" role="button" aria-label="Inspect ${escapeHtml(node.title)}">
            <div class="arch-node-top">
              <span class="arch-node-tag">${escapeHtml(node.layer)}</span>
            </div>
            <div class="arch-node-title">${escapeHtml(node.title)}</div>
            <div class="arch-node-file">${escapeHtml(node.file)}</div>
            <div class="arch-node-desc">${escapeHtml(node.description)}</div>
            <div class="arch-node-status">
              <span class="status-dot"></span>
              <span>Click to inspect specification</span>
            </div>
          </div>
        `;
      });

      html += `
          </div>
        </div>
      `;
    }

    html += `</div>`;
    container.innerHTML = html;

    // Attach click and keyboard events
    const nodeEls = container.querySelectorAll(".arch-node");
    nodeEls.forEach(el => {
      el.addEventListener("click", () => {
        selectNode(el.getAttribute("data-id"));
      });
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          selectNode(el.getAttribute("data-id"));
        }
      });
    });
  }

  function selectNode(id) {
    const node = nodes.find(n => n.id === id);
    if (!node) return;

    // Highlight node
    document.querySelectorAll(".arch-node").forEach(el => {
      if (el.getAttribute("data-id") === id) {
        el.classList.add("selected");
      } else {
        el.classList.remove("selected");
      }
    });

    // Populate and show Drawer
    const drawer = document.getElementById("arch-drawer");
    const backdrop = document.getElementById("arch-drawer-backdrop");
    const titleEl = document.getElementById("drawer-node-title");
    const layerEl = document.getElementById("drawer-node-layer");
    const bodyEl = document.getElementById("drawer-node-body");

    if (titleEl) titleEl.textContent = node.title;
    if (layerEl) layerEl.textContent = `${node.layer} // ${node.file}`;
    if (bodyEl) {
      bodyEl.innerHTML = `
        <div style="margin-bottom: var(--space-6);">
          <h4 style="font-size: var(--font-size-sm); color: var(--text-dark-muted); text-transform: uppercase; margin-bottom: var(--space-2);">Core Responsibility</h4>
          <p style="font-size: var(--font-size-sm); line-height: 1.6; color: var(--text-dark-primary);">${escapeHtml(node.description)}</p>
        </div>

        <div style="margin-bottom: var(--space-6);">
          <h4 style="font-size: var(--font-size-sm); color: var(--text-dark-muted); text-transform: uppercase; margin-bottom: var(--space-2);">Specification Contracts</h4>
          <div class="code-block-wrapper" style="margin: 0;">
            <div class="code-content" style="padding: 12px; font-size: 11px;">
<span style="color: #60A5FA;">Input Contract:</span>
${escapeHtml(node.inputs)}

<span style="color: #34D399;">Output Contract:</span>
${escapeHtml(node.outputs)}
            </div>
          </div>
        </div>

        <div style="margin-bottom: var(--space-6);">
          <h4 style="font-size: var(--font-size-sm); color: var(--text-dark-muted); text-transform: uppercase; margin-bottom: var(--space-2);">Failure Boundary & Mitigation</h4>
          <div style="background-color: var(--bg-dark-surface); border: 1px solid var(--bg-dark-border); padding: var(--space-4); border-radius: var(--radius-sm); font-size: var(--font-size-xs); color: var(--text-dark-secondary); line-height: 1.6;">
            ${escapeHtml(node.failureMode)}
          </div>
        </div>

        <div>
          <h4 style="font-size: var(--font-size-sm); color: var(--text-dark-muted); text-transform: uppercase; margin-bottom: var(--space-2);">Verified Source Implementation</h4>
          <code style="display: block; padding: 10px; background-color: var(--bg-dark-surface); border: 1px solid var(--bg-dark-border); color: #E2E8F0; font-size: 12px;">
            ${escapeHtml(node.file)}
          </code>
        </div>
      `;
    }

    if (drawer) drawer.classList.add("active");
    if (backdrop) backdrop.classList.add("active");
  }

  function closeDrawer() {
    const drawer = document.getElementById("arch-drawer");
    const backdrop = document.getElementById("arch-drawer-backdrop");
    if (drawer) drawer.classList.remove("active");
    if (backdrop) backdrop.classList.remove("active");
  }

  function initFilters() {
    const filterBtns = document.querySelectorAll(".arch-filter-btn");
    filterBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        filterBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");

        const target = btn.getAttribute("data-filter");
        const layers = document.querySelectorAll(".arch-layer");

        layers.forEach(layer => {
          const layerName = layer.getAttribute("data-layer").toLowerCase();
          if (target === "all" || layerName.includes(target.toLowerCase())) {
            layer.style.display = "block";
          } else {
            layer.style.display = "none";
          }
        });
      });
    });
  }

  function escapeHtml(text) {
    if (!text) return "";
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  document.addEventListener("DOMContentLoaded", () => {
    renderArchitecture();
    initFilters();

    const closeBtn = document.getElementById("drawer-close-btn");
    const backdrop = document.getElementById("arch-drawer-backdrop");
    if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
    if (backdrop) backdrop.addEventListener("click", closeDrawer);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeDrawer();
    });
  });
})();
