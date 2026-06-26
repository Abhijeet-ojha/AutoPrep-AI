# AutoPrep AI - System Architecture (v2)

## Design Principles
- **Zero-Persistence Privacy:** No raw user dataset is ever saved permanently in databases or filesystems.
- **In-Memory Sessions:** Dataset metadata (profile stats, health audits, chat history) is stored in ephemeral memory (`InMemoryDatasetStore`) and cleared upon session timeout (30 minutes) or dataset download.
- **Single-Request processing:** Profiling, cleaning, statistical aggregates, and visual specs are computed in a single `/upload` call to maximize efficiency.
- **LLM Metadata Isolation:** The AI copilot never receives raw dataset rows. It only processes statistical summaries, quality audits, and logs.
- **Provider Redundancy:** A multi-provider chain automatically fails over from Gemini to Groq if API errors occur, with a deterministic offline engine as a final fallback.

---

## High-Level Architecture & Data Flow

```
User
  │
  ▼ [Uploads CSV]
Next.js Web Frontend (Page 1: Landing Page '/')
  │
  ▼ [POST /datasets/upload]
FastAPI Backend API
  │
  ├─► Auto-Cleaning Engine (Pandas, Scikit-Learn)
  ├─► Statistical Profiling & Quality Audit
  ├─► Visual Payload Generator (Plotly Chart JSON Specs)
  │
  ▼ [Saves Cleaned CSV to Disk & Metadata to Memory]
InMemoryDatasetStore
  ├─► active_sessions (Dict mapping session_id to metadata)
  └─► temporary storage (storage/temp/{session_id}/)
        ├─► cleaned.csv
        ├─► cleaning_log.json
        ├─► report.pdf
        └─► *.png (Charts)
  │
  ▼ [Redirects with session_id]
Next.js Web Frontend (Page 2: Results Page '/results')
  │
  ├─► Fetches /datasets/{session_id}/metadata (if page refreshed)
  ├─► Renders 5-6 Plotly charts using react-plotly.js
  ├─► Displays Stats Table, Cleaning Logs, & Audit Modal
  ├─► ChatPanel (POST /datasets/{session_id}/copilot)
  │     └─► LLMProvider Chain (Gemini -> Groq -> Offline Fallback)
  │
  ▼ [Downloads Cleaned CSV]
GET /datasets/{session_id}/download
  │
  └─► Streams file content and deletes temporary directory & evicts memory state
```

---

## Backend Component Architecture

### FastAPI API Gateway
Exposes **six JSON endpoints** under `/datasets`:
1. `POST /upload`: Validates file size (< 100MB) and formats, cleans the DataFrame, profiles statistics, generates visual specifications (Plotly), saves static PNGs and PDF reports, stores files/state, and returns the metadata.
2. `GET /{session_id}/metadata`: Returns metadata for page refreshes.
3. `GET /{session_id}/download`: Streams the cleaned CSV. Triggers early deletion of the session's temporary folder and memory dictionary key upon stream completion.
4. `GET /{session_id}/report`: Streams the generated PDF report from cache.
5. `GET /{session_id}/download_log`: Streams the raw JSON cleaning log from cache.
6. `POST /{session_id}/copilot`: Handles chat messages via the LLM provider.

### Automated Cleaning Engine
An automated function (`auto_clean_dataset` in `analysis_service.py`) cleans data sequentially:
- **Exact Duplicates:** Dropped.
- **Numeric Imputation:** Median imputation if skewness > 1.5 or outliers exist; otherwise Mean Imputation.
- **Categorical Imputation:** Mode imputation for card <= 15; otherwise labels nulls as "Unknown".
- **Outlier Scaling:** Clips values to Q1/Q3 IQR boundaries.
- **Formattings:** Trims leading/trailing whitespaces and parses temporal columns.

### LLM Provider Architecture
An abstract provider structure implemented in `gemini_service.py`:
- `LLMProvider` (Abstract base)
- `GeminiProvider`: Calls Google Generative AI `"gemini-2.5-flash"`.
- `GroqProvider`: Calls Groq API `"llama-3.3-70b-versatile"` using HTTP client.
- `FallbackProvider`: Deterministic offline rules.
- `MultiProviderChain`: Orchestrates sequential calls: Gemini -> Groq. Falls back to offline mode if both fail.

---

## Frontend Component Architecture

The Next.js frontend comprises exactly **two pages** and requires strict header token authorization:
1. **Landing Page (`/`):** Drag-and-drop CSV zone. Coordinates file size verification (<100MB) and formats extension validation. Mounts a fullscreen loader while processing. Saves the response payload (`session_token`, `dataset_summary.dataset_id`, etc.) into `sessionStorage` and routes to `/results`.
2. **Results Page (`/results`):** Wrapped in a `<Suspense>` boundary. Grid layout rendering sections in exact order:
   - **Dataset Summary (Section A):** Grid of stat cards displaying rows, columns, missing values, duplicates, numeric, and categorical columns.
   - **Health Score (Section B):** Circular SVG radial progress indicator and audit issues list.
   - **Cleaning Actions (Section C):** Chronological timeline listing actions, reasons, and confidence percentages.
   - **Visual Insights (Section D):** Dynamically imported, responsive, lazy-loaded Plotly charts loaded directly from backend specs with skeleton screens.
   - **Dataset Copilot (Section E):** Refactored bubble chat panel connecting to `POST /copilot` with auto-scroll and quick suggested query chips.
   - **Download Center (Section F):** Triggers fetch downloads/reports passing the `X-Session-Token` header. Automatically purges the local session and evicts the dataset from the server on completion.


---

## Deployment Architecture
- **Frontend Container:** Next.js served on port 3000.
- **Backend Container:** FastAPI served via Uvicorn on port 8000.
- **Storage Volume:** Local volume mount to docker container mapped at `/storage` for temporary CSV files. No SQL database or Redis cache containers are deployed.
