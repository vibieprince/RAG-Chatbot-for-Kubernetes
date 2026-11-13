# Enterprise Kubernetes Agentic RAG — Recruiter Showcase Website

A premium, calm, Apple-inspired technical product showcase and recruiter-facing website for the **Enterprise Kubernetes Agentic RAG Platform**.

---

## 🎨 Apple-Inspired Design Philosophy

- **Light Mode Only (Strictly Enforced)**: No dark mode, no theme toggle, no dark section alternatives, and no dark architecture canvas. Remains calm and legible regardless of client OS preferences.
- **Color Palette**:
  - Primary Background: `#F5F7FA` (calm cool off-white)
  - Secondary Background & Cards: `#FFFFFF`
  - Soft Surface: `#F0F3F7`
  - Typography: `#202631` (primary deep slate), `#667085` (secondary neutral), `#8993A4` (muted)
  - Technical Accents: `#4F83CC` (Apple blue), `#E8F0FC` (light accent tint)
  - Borders: Thin, understated `#E3E8EF` (1px)
  - Shadows: Very soft elevation with low-opacity cool grey (`rgba(16, 24, 40, 0.04)`)
- **Restrained Typography**: Native Apple system font stack (`-apple-system`, `SF Pro Display`, `SF Pro Text`), comfortable reading line widths (max `68ch`), moderate heading weights, and responsive `clamp()` scaling.
- **Frosted Glassmorphism**: Translucent surfaces with delicate blur (`backdrop-filter: blur(16px)`), fine light borders, and subtle elevation applied to the sticky navigation and preview cards.

---

## 🛠️ Technology Stack & Architecture

- **HTML5**: Standard, semantic markup.
- **Tailwind CSS**: Light-mode-only Apple design tokens and responsive utility classes.
- **Vanilla JavaScript**: Pure ES modules for navigation, component inspection, and security sandbox.
- **Mermaid.js**: Pinned light-theme architecture and sequence diagrams rendered locally.
- **Zero Frontend Frameworks**: No React, Next.js, Vue, Angular, Svelte, or JSX.
- **Zero Backend Required**: 100% static client-side architecture deployable directly to GitHub Pages.

---

## 📊 Embedded Interactive Mermaid Diagrams

Every major architecture diagram is rendered locally via **Mermaid.js** with light-theme styling and interactive controls:
1. **System Architecture Flowchart** (`ARCHITECTURE.md`)
2. **Request Lifecycle Sequence Diagram** (`docs/architecture/request-lifecycle.md`)
3. **Defense-in-Depth AI Security Pipeline** (`docs/security/security-overview.md`)
4. **Knowledge Retrieval & FlashRank Cross-Encoder Workflow** (`docs/retrieval/retrieval-workflow.md`)
5. **LiteLLM Gateway & Provider Failover Topology** (`docs/gateway/llm-gateway.md`)

### Diagram Controls:
- **Show / Hide**: Collapse or expand the diagram cleanly without leaving large empty spaces.
- **Expand Fullscreen**: Opens an Apple-style modal overlay for large-format diagram inspection (supports keyboard `ESC` to close).

---

## 💻 How to Run Locally

### Option 1: Python Standard Library (Instant, No Dependencies)
From the repository root:
```powershell
python -m http.server 3000 --directory recruiter-site/dist
```
Open your browser to: [http://localhost:3000/](http://localhost:3000/)

### Option 2: Pre-Configured FastAPI Static Mount
FastAPI in `app/main.py` is configured to mount static files. When running:
```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser to: [http://localhost:8000/](http://localhost:8000/)

---

## 🌐 Deploying to GitHub Pages

The website uses **relative paths** (`./assets/...`) and relative anchors, ensuring it renders properly under GitHub Pages subpaths (`https://<username>.github.io/<repo-name>/`).

### Automated GitHub Actions Workflow:
A workflow is configured in [`.github/workflows/deploy-showcase.yml`](../.github/workflows/deploy-showcase.yml).
1. Go to your GitHub repository **Settings** → **Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Push changes to `main` (or run the workflow manually under **Actions** → **Deploy Recruiter Showcase to GitHub Pages**).
4. GitHub Pages will build and deploy the `recruiter-site/dist` directory automatically.

---

## 📁 Directory Structure

```text
recruiter-site/
├── index.html                   # Development HTML source
├── package.json                 # npm scripts & Tailwind devDependencies
├── tailwind.config.js           # Apple design tokens configuration
├── README.md                    # Documentation & deployment guide
├── src/
│   ├── css/
│   │   ├── input.css            # Tailwind directives & glassmorphism tokens
│   │   └── styles.css           # Compiled standalone stylesheet
│   ├── js/
│   │   ├── content.js           # Single source of truth (100% verified documentation data)
│   │   ├── diagrams.js          # Mermaid.js light-theme configuration & diagram definitions
│   │   ├── interactions.js      # Architecture component drawer & interactive security sandbox
│   │   ├── navigation.js        # Apple-style frosted-glass sticky nav & scroll spy
│   │   └── main.js              # Application bootstrapper
│   └── assets/
│       └── favicon.svg          # Minimalist Apple-inspired Kubernetes symbol
└── dist/                        # Ready-to-deploy static build for GitHub Pages
    ├── index.html
    └── assets/
        ├── css/
        │   └── styles.css
        ├── js/
        │   ├── content.js
        │   ├── diagrams.js
        │   ├── interactions.js
        │   ├── navigation.js
        │   └── main.js
        └── favicon.svg
```
