/**
 * INTERACTIVE SECURITY GATEWAY SANDBOX
 * Demonstrates the 4-layer defense-in-depth pipeline reaction to verified attack vectors.
 */

(function () {
  const data = window.RAG_DATA;
  if (!data) return;

  const scenarios = data.securitySandboxScenarios;

  function renderSecuritySandbox() {
    const selectorContainer = document.getElementById("security-scenario-selector");
    if (!selectorContainer) return;

    let html = "";
    scenarios.forEach((sc, idx) => {
      const isDefault = idx === 0;
      html += `
        <button class="btn btn-sm ${isDefault ? 'btn-primary' : 'btn-secondary'} scenario-btn" data-index="${idx}">
          ${escapeHtml(sc.category)}
        </button>
      `;
    });

    selectorContainer.innerHTML = html;

    selectorContainer.querySelectorAll(".scenario-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        selectorContainer.querySelectorAll(".scenario-btn").forEach(b => {
          b.classList.remove("btn-primary");
          b.classList.add("btn-secondary");
        });
        btn.classList.remove("btn-secondary");
        btn.classList.add("btn-primary");

        const idx = parseInt(btn.getAttribute("data-index"), 10);
        showScenario(idx);
      });
    });

    showScenario(0);
  }

  function showScenario(index) {
    const sc = scenarios[index];
    if (!sc) return;

    const promptEl = document.getElementById("sandbox-input-prompt");
    const decisionEl = document.getElementById("sandbox-decision-badge");
    const categoryEl = document.getElementById("sandbox-category-badge");
    const latencyEl = document.getElementById("sandbox-latency");
    const detectorEl = document.getElementById("sandbox-detector");
    const reactionEl = document.getElementById("sandbox-reaction-narrative");
    const outputEl = document.getElementById("sandbox-output-response");

    if (promptEl) promptEl.textContent = sc.prompt;

    if (decisionEl) {
      decisionEl.textContent = sc.expectedDecision;
      decisionEl.className = "badge " + (sc.expectedDecision === "ALLOW" ? "badge-green" : "badge-red");
    }

    if (categoryEl) {
      categoryEl.textContent = sc.expectedCategory;
      categoryEl.className = "badge " + (sc.expectedDecision === "ALLOW" ? "badge-default" : "badge-violet");
    }

    if (latencyEl) latencyEl.textContent = sc.latency;
    if (detectorEl) detectorEl.textContent = sc.expectedDetector;
    if (reactionEl) reactionEl.textContent = sc.reaction;
    if (outputEl) outputEl.innerHTML = escapeHtml(sc.sampleResponse);
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
    renderSecuritySandbox();
  });
})();
