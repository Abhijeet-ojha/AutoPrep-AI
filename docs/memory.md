# Development Memory

## Session 2026-06-07

### Files Created
- `apps/api/app/storage/base.py`
- `apps/api/app/storage/local.py`
- `apps/api/app/storage/factory.py`
- `apps/api/app/services/gemini_service.py`
- `apps/api/app/services/insight_engine.py`
- `apps/api/app/middleware/logging.py`
- `apps/api/app/middleware/security.py`

### Files Modified
- `apps/api/requirements.txt`
- `README.md`
- `.env.example`

### Features Added
- **Gemini Service Integration:** Integrated Gemini 2.5 Flash with backoff retries and offline rule-based fallbacks.
- **Pluggable Storage Layer:** Built storage layer with abstraction for local storage.
- **Report & Visualization Engines:** Implemented HTML summary generation and basic EDA visualization helpers.
- **Production Hardening:** Implemented rate-limiting, upload constraints validation, prompt/SQL injection sanitization, and structured request ID tracking.

### Architectural Decisions
- Moved from permanent user dataset storage to temporary local Parquet files in active session directory scopes (privacy-first).

---

## Session 2026-06-22

### Files Created
- `docs/context.md` (Created in docs root with updated layout structure)
- `docs/architecture.md` (Created in docs root)
- `docs/memory.md` (Created in docs root)

### Features Added
- **Persistent AI Project Knowledge:** Established session-persistent documentation files (`context.md`, `architecture.md`, `memory.md`) in the project directory.

---

## Session 2026-06-23

### Files Created
- `apps/api/tests/test_api.py` (New database-free unit test suite)
- `apps/web/app/(routes)/results/page.tsx` (Page 2: Results dashboard with Plotly visual insights, statistics, and Chatbot)

### Files Modified
- `apps/api/app/core/config.py` (Removed DB settings, added Groq API key and settings)
- `apps/api/app/services/dataset_store.py` (Replaced SessionDatasetStore with in-memory store)
- `apps/api/app/services/gemini_service.py` (Implemented multi-provider LLM chain with Gemini & Groq support)
- `apps/api/app/services/copilot_service.py` (Removed database history calls, updated in-memory chat logging)
- `apps/api/app/services/insight_engine.py` (Removed database caching calls from insight generator)
- `apps/api/app/services/analysis_service.py` (Added `auto_clean_dataset` and `generate_visual_insights` functions)
- `apps/api/app/routers/dataset.py` (Restructured to expose exactly 5 endpoints)
- `apps/api/app/main.py` (Cleaned up DB session initialization)
- `apps/api/tests/conftest.py` (Removed database mocks, simplified client mock)
- `apps/web/app/page.tsx` (Page 1: direct, minimalist Landing page with drag-and-drop CSV uploads)
- `apps/web/components/ChatPanel.tsx` (Remapped chatbot endpoints and response binding keys)
- `docs/context.md` (Updated project status and limitations)
- `docs/architecture.md` (Updated system flow descriptions)
- `docs/memory.md` (Appended current session logs)

### Files Deleted
- SQL database models: `apps/api/app/db/models.py`, `apps/api/app/db/session.py`
- Alembic database migration scripts and configuration files (`apps/api/alembic/`, `apps/api/alembic.ini`)
- SQLite database cache files: `autoprep.db`, `test.db`
- Old backend unit test files: `test_copilot.py`, `test_copilot_d2.py`, `test_persistence.py`, `test_privacy.py`, `test_security.py`, `test_storage.py`, `test_analysis_service.py`
- Frontend `/upload` and `/dashboard` folders (consolidated to `/results` and `/`)

### Features Added
- **Automated Cleaning Pipeline:** The system automatically cleans datasets on upload based on distributions (Imputations, outlier capping, string trimming, datetime conversions).
- **Direct Drag-and-Drop Ingestion:** The Landing Page features a direct drag-and-drop container for uploading CSVs with client-side validation.
- **Plotly Visual Insights:** The backend computes and returns 5-6 Plotly-compatible JSON specifications in the upload payload (bar charts, box plots, correlation heatmaps, class distributions).
- **Groq LLM Support:** Integrated Groq endpoint (`llama-3.3-70b-versatile`) as a primary fallback in the LLM chain.

### Architectural Decisions
- Removed all SQL databases (PostgreSQL/SQLite) and persistent ORM layers to implement a purely ephemeral, zero-persistence architecture.
- Session states (statistical summaries, cleaning logs, chat logs) exist only in memory inside an active `InMemoryDatasetStore` mapping.
- Cleaned datasets reside temporarily as files under `storage/temp/{session_id}/` and are strictly deleted from disk and memory immediately upon download completion.
- Configured a multi-provider LLM chain sequence (Gemini 2.5 Flash -> Groq Llama 3.3 -> Offline Fallback) to maximize chat reliability.

---

## Session 2026-06-23 (Milestone Phase D3 Frontend Integration Complete)

### Files Created
- `apps/web/components/ThemeToggle.tsx` (Manual dark/light explicit toggle)
- `apps/web/react-plotly.d.ts` (TS type declaration module override)

### Files Modified
- `apps/api/app/routers/dataset.py` (Added `session_token` key generator and validated `X-Session-Token` headers for secure download, report, and copilot requests)
- `apps/web/lib/api.ts` (Updated `getJSON` and `postJSON` to inject header, added fetch-based `downloadCleanedCSV` and `viewCleaningReport` methods)
- `apps/web/tailwind.config.ts` (Enabled `darkMode: 'class'` toggle support)
- `apps/web/app/globals.css` (Added dark gradient rules and styling classes)
- `apps/web/app/page.tsx` (Completed premium Hero design, drag-drop zone, client size/format check, direct loading screen spinner, and sessionStorage cache flow)
- `apps/web/app/(routes)/results/page.tsx` (Assembled results sections in exact request layout sequence, wrapped page in `<Suspense>`, implemented radial score indicator, timeline, downloads, and expired redirects)
- `apps/web/components/ChatPanel.tsx` (Assembled user/bot bubble lists, typing statuses, suggested query chips, and scroll controls)

### Features Added & Verified
- **Auth Token validation:** Generated token is transferred securely in headers to authorize download streams, report prints, and copilot messaging sessions.
- **Immediate Eviction Flow:** Verification checks that download triggers filesystem cleanup and local cookie/session clear, displaying the "Session Expired" UI correctly on page refresh.
- **Plotly Lazy Loading:** Dynamics imports with loaders ensure fast page paints without rendering lag.

---

## Session 2026-06-23 (Final Adjustments & PDF Reports)

### Files Modified
- `apps/api/requirements.txt` (Added `matplotlib` and `reportlab`)
- `apps/api/app/services/analysis_service.py` (Implemented dataset health score formula with deductions, severity standardizations, flattened audit payload, `generate_pdf_report` with ReportLab, and `generate_and_save_charts` with Matplotlib)
- `apps/api/app/routers/dataset.py` (Updated to cache PNGs, JSON logs, and PDF files. Changed `/report` endpoint to stream PDF, and added `/download_log` endpoint)
- `apps/web/lib/api.ts` (Added `downloadCleaningLog` and replaced `viewCleaningReport` with `downloadReport` for PDF handling)
- `apps/web/app/page.tsx` (Updated Landing page to be dark-mode only, removed duplicate branding, and enforced no-scroll layout)
- `apps/web/app/(routes)/results/page.tsx` (Updated Session Expired screen with "Privacy Protected", added Audit Details modal, and added JSON log download button)
- `docs/*` (Architecture and memory updates)

### Features Added
- **Matplotlib & ReportLab PDFs:** Switched from HTML reports to professional, embedded PDF reports containing dataset overview, cleaning logs, and static charts.
- **Asset Caching:** Charts and reports are generated once during the `/upload` pipeline and cached to the temporary session directory to speed up `/report` downloads and reduce computational overhead.
- **Audit Details Modal:** Replaced text lists with a detailed, tabular Audit Modal showing exact column issues, severity badges, and affected rows.
- **JSON Log Exports:** Added capability for users to download the raw cleaning logs in JSON format.
- **Dark Mode Enforcement:** Landing page is now locked to a premium dark-mode aesthetic with no-scroll behavior.
