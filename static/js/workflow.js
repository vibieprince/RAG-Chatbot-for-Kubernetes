/**
 * INTERACTIVE REQUEST LIFECYCLE & SSE SIMULATOR
 * Visualizes the 6-stage request sequence and simulated Server-Sent Events.
 */

(function () {
  const data = window.RAG_DATA;
  if (!data) return;

  const stages = data.workflowStages;
  let activeStageIndex = 0;
  let simulationTimer = null;

  function renderStepper() {
    const nav = document.getElementById("workflow-stepper-nav");
    if (!nav) return;

    let html = "";
    stages.forEach((st, idx) => {
      const isActive = idx === activeStageIndex;
      html += `
        <button class="step-btn ${isActive ? 'active' : ''}" data-index="${idx}" aria-label="Step ${st.step}: ${escapeHtml(st.title)}">
          <div class="step-number">${st.step}</div>
          <div class="step-meta">
            <span class="step-title">${escapeHtml(st.title)}</span>
            <span class="step-sub">${escapeHtml(st.endpoint)}</span>
          </div>
        </button>
      `;
    });

    nav.innerHTML = html;

    nav.querySelectorAll(".step-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        stopSimulation();
        const idx = parseInt(btn.getAttribute("data-index"), 10);
        showStage(idx);
      });
    });

    showStage(0);
  }

  function showStage(index) {
    activeStageIndex = index;
    const stage = stages[index];
    if (!stage) return;

    // Update nav active states
    document.querySelectorAll(".step-btn").forEach((btn, idx) => {
      if (idx === index) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    // Update Stage Details Card
    const headingEl = document.getElementById("workflow-stage-heading");
    const narrativeEl = document.getElementById("workflow-narrative");
    const streamFeedEl = document.getElementById("sse-stream-feed");

    if (headingEl) {
      headingEl.textContent = `Stage ${stage.step}: ${stage.title}`;
    }

    if (narrativeEl) {
      narrativeEl.innerHTML = `
        <div style="margin-bottom: var(--space-4);">
          <div class="badge badge-default" style="margin-bottom: var(--space-2);">${escapeHtml(stage.file)}</div>
          <p style="font-size: var(--font-size-base); color: var(--text-primary); font-weight: 500;">
            ${escapeHtml(stage.description)}
          </p>
        </div>

        <div style="background-color: var(--bg-tertiary); padding: var(--space-4); border-radius: var(--radius-sm); border-left: 3px solid var(--text-primary);">
          <h4 style="font-size: var(--font-size-xs); font-family: var(--font-mono); text-transform: uppercase; margin-bottom: var(--space-1); color: var(--text-muted);">
            Engineered Execution Details
          </h4>
          <p style="font-size: var(--font-size-sm); margin: 0; color: var(--text-secondary);">
            ${escapeHtml(stage.detail)}
          </p>
        </div>
      `;
    }

    if (streamFeedEl) {
      renderConsoleEvents(index);
    }
  }

  function renderConsoleEvents(upToIndex) {
    const feed = document.getElementById("sse-stream-feed");
    if (!feed) return;

    let html = "";
    for (let i = 0; i <= upToIndex; i++) {
      const st = stages[i];
      if (st.mockEvent) {
        html += `
          <div class="sse-line">
            <span class="sse-line-event">event: ${escapeHtml(st.mockEvent.event)}</span><br>
            <span class="sse-line-data">data: ${escapeHtml(JSON.stringify(st.mockEvent.data, null, 2))}</span>
          </div>
          <div style="height: 8px;"></div>
        `;
      }
    }

    if (upToIndex === 5) {
      html += `
        <div class="sse-line sse-line-token">
          <span style="color: #34D399;">✔ Stream Completed | Single generation guarantee verified</span>
        </div>
      `;
    }

    feed.innerHTML = html;
    feed.scrollTop = feed.scrollHeight;
  }

  function startSimulation() {
    stopSimulation();
    let current = 0;
    const simBtn = document.getElementById("simulate-workflow-btn");
    if (simBtn) simBtn.textContent = "Simulating Lifecycle...";

    showStage(current);

    simulationTimer = setInterval(() => {
      current++;
      if (current >= stages.length) {
        clearInterval(simulationTimer);
        simulationTimer = null;
        if (simBtn) simBtn.textContent = "Replay Lifecycle Simulation ↺";
      } else {
        showStage(current);
      }
    }, 1400);
  }

  function stopSimulation() {
    if (simulationTimer) {
      clearInterval(simulationTimer);
      simulationTimer = null;
      const simBtn = document.getElementById("simulate-workflow-btn");
      if (simBtn) simBtn.textContent = "Simulate Request Lifecycle ▶";
    }
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
    renderStepper();

    const simBtn = document.getElementById("simulate-workflow-btn");
    if (simBtn) {
      simBtn.addEventListener("click", () => {
        if (simulationTimer) {
          stopSimulation();
        } else {
          startSimulation();
        }
      });
    }
  });
})();
