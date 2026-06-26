# AutoPrep AI - Project Context (v2)

## Project Overview
AutoPrep AI is a production-grade, AI-assisted dataset preparation and analysis platform. Re-designed in v2, it focuses on a strict **privacy-first, zero-persistence architecture**. Raw dataset uploads are processed entirely in ephemeral session memory and temporary local files, and are deleted immediately after use. The platform profiles, audits, cleans, and generates visualization payloads and rule-based insights in a single upload request, allowing users to converse with the dataset via a chatbot and export the cleaned dataset securely.

---

## Current Status
- **Backend:** The FastAPI backend is fully operational with a database-free, in-memory metadata store. It exposes exactly five API endpoints (`/upload`, `/{session_id}/metadata`, `/{session_id}/download`, `/{session_id}/report`, `/{session_id}/copilot`). It integrates a multi-provider LLM chain (Gemini -> Groq -> Offline Fallback) and generates 5-6 Plotly chart specifications on ingestion.
- **Frontend:** The Next.js frontend is fully implemented as a premium two-page experience. It includes drag-and-drop CSV uploads, client-side validation, direct session storage parsing, a system-preference-responsive dark mode toggle, and dynamically imported lazy-loaded Plotly configurations with skeleton loaders. All API queries enforce the `X-Session-Token` validation constraint.
- **Testing:** The backend unit test suite has been updated to cover v2 and executes with 100% passing tests (6 assertions covering upload validation, auto-clean, download eviction, session token validation, and copilot fallbacks).

---

## Implemented Features (v2)
- **Drag-and-Drop Ingestion:** Direct file uploading restricting file formats to CSV and a maximum size of 100MB.
- **Automated Cleaning Strategy:** Ingestion automatically triggers a rule-based clean engine:
  - *Duplicates:* Drops exact duplicates.
  - *Numeric Columns:* Detects skewness and outliers; applies Median Imputation (if skewed or has outliers) or Mean Imputation. Caps outliers using IQR boundary clipping.
  - *Categorical Columns:* Applies Mode Imputation (low cardinality) or labels missing data as "Unknown" (high cardinality).
  - *Data Types:* Automatically converts object columns ending in date/time keywords to datetime. Strips whitespace in text columns.
  - *Logs:* Each action tracks Action, Method, Reason, Confidence, and affected cell counts.
- **Visual Insights Payload:** Computes and returns 5-6 Plotly-compatible JSON specifications (Missing Values, Correlation Heatmap, Histogram, Box Plot, and Class Distribution) in the upload response.
- **Privacy-First Eviction:** Cleaned datasets are written temporarily to `storage/temp/{session_id}/cleaned.csv`. Upon calling `/download`, the CSV stream completes and immediately cleanses both the memory dictionary (`active_sessions`) and deletes the temporary files.
- **Active LLM Provider Chain:**
  - **Gemini 2.5 Flash:** Primary LLM chatbot provider.
  - **Groq llama-3.3-70b-versatile:** Secondary LLM chatbot provider fallback.
  - **Deterministic Fallback Engine:** Rule-based fallback if all cloud LLM endpoints fail.
- **Rate-Limiting:** IP-based rate limiter capping uploads to 20 uploads per hour.

---

## Historical Transition (v1 to v2)
In Phase 2, AutoPrep AI was originally built as a multi-tenant relational platform with PostgreSQL persistence, Alembic migrations, dataset versions rollback, and ReportLab PDF reporting. In v2, the database layer was completely removed. Relational ORM models and version histories were replaced with `InMemoryDatasetStore` and immediate filesystem purge mechanisms to comply with data privacy policies prohibiting permanent storage of user datasets on the server.

---

## Current Limitations
- **Uptime Memory Loss:** Active sessions and chat history are stored in-memory; restarting the backend process evicts all active sessions.
- **Sync Code Execution:** Large CSV file profiling runs on the main FastAPI request thread. Larger files (up to 100MB) can temporarily block execution.
- **Single-File Scope:** The dashboard evaluates and processes one CSV file per session.

---

## Technical Debt
- **In-Memory Rate Limiting:** Rate limit attempt maps are kept in server memory and do not scale horizontally across load-balanced containers.
- **CORS Configuration:** CORS is globally allowed (`*`) and needs specific domain configurations before production hosting.

---

## Next Planned Phase
- **Production Deployment Configuration:** Dockerizing backend and frontend containers, and configuring proxy setups for staging/production deployment.
- **Memory TTL Worker:** Setting up a lightweight daemon script to clear sessions exceeding the 30-minute inactivity timeout.
