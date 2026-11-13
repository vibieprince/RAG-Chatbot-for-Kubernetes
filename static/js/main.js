/**
 * MAIN PRESENTATION & UX CONTROLLER
 * Manages Recruiter Fast-Scan mode, scroll spy, dynamic content rendering, and copy actions.
 */

(function () {
  const data = window.RAG_DATA;
  if (!data) return;

  // --------------------------------------------------------------------------
  // 1. RECRUITER 60-SEC SCAN vs TECHNICAL DEEP DIVE MODE TOGGLE
  // --------------------------------------------------------------------------
  function initRecruiterToggle() {
    const toggleBtn = document.getElementById("recruiter-toggle-btn");
    const summaryBox = document.getElementById("recruiter-executive-box");
    if (!toggleBtn || !summaryBox) return;

    let isRecruiterMode = true; // default enabled for instant 60-second clarity

    function updateMode() {
      if (isRecruiterMode) {
        toggleBtn.classList.add("active");
        toggleBtn.innerHTML = `<span class="pulse-dot"></span><span>Recruiter 60s View (Active)</span>`;
        summaryBox.style.display = "block";
      } else {
        toggleBtn.classList.remove("active");
        toggleBtn.innerHTML = `<span>Switch to Recruiter 60s View</span>`;
      }
    }

    toggleBtn.addEventListener("click", () => {
      isRecruiterMode = !isRecruiterMode;
      updateMode();
      if (isRecruiterMode) {
        summaryBox.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });

    updateMode();
  }

  // --------------------------------------------------------------------------
  // 2. DYNAMIC CONTENT RENDERING FROM SINGLE SOURCE OF TRUTH
  // --------------------------------------------------------------------------
  function renderDynamicContent() {
    // A. Render Problem vs Solution
    const probList = document.getElementById("problem-items-list");
    const solList = document.getElementById("solution-items-list");

    if (probList && data.problemVsSolution) {
      probList.innerHTML = data.problemVsSolution.problems
        .map(p => `<li><strong>${escapeHtml(p.title)}:</strong> ${escapeHtml(p.desc)}</li>`)
        .join("");
    }

    if (solList && data.problemVsSolution) {
      solList.innerHTML = data.problemVsSolution.solutions
        .map(s => `<li><strong>${escapeHtml(s.title)}:</strong> ${escapeHtml(s.desc)}</li>`)
        .join("");
    }

    // B. Render Test Matrix Table (24 Tests)
    const testContainer = document.getElementById("test-matrix-container");
    if (testContainer && data.testSuite) {
      let tableHtml = `
        <div class="test-table-wrapper">
          <table class="test-table">
            <thead>
              <tr>
                <th style="width: 25%;">Test Suite / Target</th>
                <th style="width: 35%;">Test Function Name</th>
                <th style="width: 40%;">Verified Assertion & Criterion</th>
              </tr>
            </thead>
            <tbody>
      `;

      data.testSuite.groups.forEach(group => {
        group.classes.forEach(cls => {
          cls.items.forEach((item, idx) => {
            tableHtml += `
              <tr>
                ${idx === 0 ? `<td rowspan="${cls.items.length}" style="font-weight: 700; color: var(--text-primary); vertical-align: top; background-color: var(--bg-secondary);">
                  <div style="font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);">${escapeHtml(group.file)}</div>
                  ${escapeHtml(cls.name)}
                </td>` : ''}
                <td><code style="font-size: 12px;">${escapeHtml(item.name)}</code></td>
                <td>
                  <span class="badge badge-green" style="margin-right: 6px;">PASSED</span>
                  <span style="font-size: 12px; color: var(--text-secondary);">${escapeHtml(item.verified)}</span>
                </td>
              </tr>
            `;
          });
        });
      });

      tableHtml += `
            </tbody>
          </table>
        </div>
      `;
      testContainer.innerHTML = tableHtml;
    }

    // C. Render Tech Stack (10 Categorized Layers)
    const techContainer = document.getElementById("tech-stack-container");
    if (techContainer && data.techStack) {
      let techHtml = "";
      data.techStack.forEach(cat => {
        techHtml += `
          <div class="card" style="padding: var(--space-5);">
            <div style="font-family: var(--font-mono); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--text-muted); margin-bottom: var(--space-3);">
              ${escapeHtml(cat.category)}
            </div>
            <div style="display: flex; flex-direction: column; gap: var(--space-3);">
        `;
        cat.items.forEach(it => {
          techHtml += `
            <div style="border-bottom: 1px solid var(--border-primary); padding-bottom: var(--space-2);">
              <div style="display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 2px;">
                <span style="font-weight: 700; font-size: var(--font-size-sm); color: var(--text-primary);">${escapeHtml(it.name)}</span>
                <span class="badge badge-default" style="font-size: 10px;">${escapeHtml(it.version)}</span>
              </div>
              <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin: 0; line-height: 1.4;">${escapeHtml(it.role)}</p>
            </div>
          `;
        });
        techHtml += `
            </div>
          </div>
        `;
      });
      techContainer.innerHTML = techHtml;
    }

    // D. Render Documentation Library (15 Docs)
    const docContainer = document.getElementById("doc-library-container");
    if (docContainer && data.documentation) {
      let docHtml = "";
      data.documentation.forEach(doc => {
        docHtml += `
          <div class="card" style="display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-2);">
                <span class="badge badge-default" style="font-size: 10px;">${escapeHtml(doc.category)}</span>
                <code style="font-size: 10px; color: var(--text-muted);">${escapeHtml(doc.path)}</code>
              </div>
              <h4 style="font-size: var(--font-size-base); font-weight: 700; margin-bottom: var(--space-2); color: var(--text-primary);">
                ${escapeHtml(doc.title)}
              </h4>
              <p style="font-size: var(--font-size-xs); color: var(--text-secondary); line-height: 1.5; margin-bottom: var(--space-4);">
                ${escapeHtml(doc.description)}
              </p>
            </div>
            <div>
              <a href="${data.project.githubRepo}/blob/main/${doc.path}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="width: 100%;">
                View Verified Doc ↗
              </a>
            </div>
          </div>
        `;
      });
      docContainer.innerHTML = docHtml;
    }

    // E. Render Limitations & Roadmap
    const limitContainer = document.getElementById("limitations-container");
    const roadmapContainer = document.getElementById("roadmap-container");

    if (limitContainer && data.limitationsAndRoadmap) {
      limitContainer.innerHTML = data.limitationsAndRoadmap.knownLimitations.map(item => `
        <div class="card" style="margin-bottom: var(--space-4); border-left: 3px solid var(--accent-amber);">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-2);">
            <h4 style="font-size: var(--font-size-sm); font-weight: 700; margin: 0;">${escapeHtml(item.title)}</h4>
            <span class="badge badge-default">${escapeHtml(item.status)}</span>
          </div>
          <p style="font-size: var(--font-size-xs); color: var(--text-secondary); margin: 0;">${escapeHtml(item.desc)}</p>
        </div>
      `).join("");
    }

    if (roadmapContainer && data.limitationsAndRoadmap) {
      roadmapContainer.innerHTML = data.limitationsAndRoadmap.plannedRoadmap.map(item => `
        <div class="card" style="margin-bottom: var(--space-4); border-left: 3px solid var(--accent-blue);">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-2);">
            <h4 style="font-size: var(--font-size-sm); font-weight: 700; margin: 0;">${escapeHtml(item.title)}</h4>
            <span class="badge badge-blue">${escapeHtml(item.status)}</span>
          </div>
          <p style="font-size: var(--font-size-xs); color: var(--text-secondary); margin: 0;">${escapeHtml(item.desc)}</p>
        </div>
      `).join("");
    }
  }

  // --------------------------------------------------------------------------
  // 3. TABS CONTROLLER
  // --------------------------------------------------------------------------
  function initTabs() {
    const tabGroups = document.querySelectorAll(".tab-group");
    tabGroups.forEach(group => {
      const buttons = group.querySelectorAll(".tab-btn");
      buttons.forEach(btn => {
        btn.addEventListener("click", () => {
          buttons.forEach(b => b.classList.remove("active"));
          btn.classList.add("active");

          const targetId = btn.getAttribute("data-tab");
          const parent = group.closest(".tab-parent") || document;
          const panes = parent.querySelectorAll(".tab-pane");

          panes.forEach(pane => {
            if (pane.id === targetId) {
              pane.classList.add("active");
            } else {
              pane.classList.remove("active");
            }
          });
        });
      });
    });
  }

  // --------------------------------------------------------------------------
  // 4. SCROLL SPY & NAVIGATION HIGHLIGHTING
  // --------------------------------------------------------------------------
  function initScrollSpy() {
    const sections = document.querySelectorAll("section[id]");
    const navLinks = document.querySelectorAll(".nav-link[href^='#']");

    function onScroll() {
      const scrollPos = window.scrollY + 120;
      sections.forEach(sec => {
        const top = sec.offsetTop;
        const height = sec.offsetHeight;
        const id = sec.getAttribute("id");

        if (scrollPos >= top && scrollPos < top + height) {
          navLinks.forEach(link => {
            if (link.getAttribute("href") === `#${id}`) {
              link.classList.add("active");
            } else {
              link.classList.remove("active");
            }
          });
        }
      });
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  // --------------------------------------------------------------------------
  // 5. COPY TO CLIPBOARD
  // --------------------------------------------------------------------------
  function initCopyButtons() {
    document.querySelectorAll(".copy-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const targetSelector = btn.getAttribute("data-copy-target");
        let textToCopy = "";
        if (targetSelector) {
          const targetEl = document.querySelector(targetSelector);
          if (targetEl) textToCopy = targetEl.textContent || targetEl.innerText;
        } else {
          textToCopy = btn.getAttribute("data-copy-text") || "";
        }

        if (textToCopy) {
          navigator.clipboard.writeText(textToCopy.trim()).then(() => {
            const originalText = btn.innerHTML;
            btn.innerHTML = `✔ Copied!`;
            setTimeout(() => {
              btn.innerHTML = originalText;
            }, 2000);
          });
        }
      });
    });
  }

  // --------------------------------------------------------------------------
  // 6. MOBILE MENU
  // --------------------------------------------------------------------------
  function initMobileMenu() {
    const toggle = document.getElementById("mobile-menu-toggle");
    const nav = document.getElementById("navbar-nav");
    if (!toggle || !nav) return;

    toggle.addEventListener("click", () => {
      const isVisible = nav.style.display === "flex";
      nav.style.display = isVisible ? "none" : "flex";
      if (!isVisible) {
        nav.style.flexDirection = "column";
        nav.style.position = "absolute";
        nav.style.top = "72px";
        nav.style.left = "0";
        nav.style.width = "100%";
        nav.style.backgroundColor = "#FFFFFF";
        nav.style.padding = "24px";
        nav.style.borderBottom = "1px solid var(--border-primary)";
        nav.style.boxShadow = "var(--shadow-lg)";
      }
    });

    nav.querySelectorAll(".nav-link").forEach(link => {
      link.addEventListener("click", () => {
        if (window.innerWidth <= 768) {
          nav.style.display = "none";
        }
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
    initRecruiterToggle();
    renderDynamicContent();
    initTabs();
    initScrollSpy();
    initCopyButtons();
    initMobileMenu();
  });
})();
