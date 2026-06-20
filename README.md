# AutoPrep AI

**Production-Grade AI-Assisted Dataset Cleaning, Profiling, and EDA Platform**

AutoPrep AI is an intelligent platform that combines automated data analysis with Gemini 2.5 Flash AI to help data scientists and ML engineers prepare datasets for machine learning.

## 🚀 What's New in Phase 2

- ✨ **Gemini AI Integration** - AI-powered insights, explanations, and conversational analytics
- 💾 **PostgreSQL Persistence** - Datasets, versions, and history survive application restarts
- 📁 **File Storage Layer** - Abstracted storage supporting local and cloud backends
- 📄 **PDF Reports** - Professional, downloadable analysis reports
- 📊 **Complete EDA Suite** - 10+ interactive chart types
- 🎯 **AI Insights** - Executive summaries and AutoML recommendations
- 🔒 **Production Security** - Input validation, rate limiting, and prompt injection prevention
- 📈 **Observability** - Structured logging, request tracing, and metrics
- ✅ **Testing Ready** - Comprehensive test infrastructure

## Stack

- **Frontend**: Next.js (TypeScript) + Tailwind CSS + Plotly
- **Backend**: FastAPI + Pandas + NumPy + Scikit-Learn
- **AI**: Google Gemini 2.5 Flash
- **Database**: PostgreSQL + Redis
- **Storage**: Local filesystem (extensible to S3/GCS/Azure)
- **Deployment**: Docker Compose

## Features

### Core Capabilities
- 📥 Dataset ingestion (CSV/XLSX/JSON) with smart encoding detection
- 📊 Automated profiling with detailed column statistics
- 🤖 AI-powered column role inference with explanations
- 🔍 Comprehensive quality audit (missing values, duplicates, outliers, formatting, class imbalance)
- 💡 Intelligent cleaning recommendations with confidence scores
- ❤️ Dataset health scoring (0-100) with improvement suggestions
- 🔧 Automated cleaning pipeline with reversible actions
- 📜 Complete cleaning history with version management and rollback
- 📈 Interactive EDA dashboard with 10+ chart types
- 🧪 Feature engineering advisor with ML-optimized suggestions
- 🎯 ML readiness assessment with task suitability analysis
- 💬 AI-powered dataset chatbot (Gemini-backed)
- 📝 Preprocessing code generator (Python/Pandas)
- 📄 Professional report generation (HTML + PDF)
- 📤 Export center (cleaned CSV, reports, code)

### AI-Powered Features (NEW)
- 🤖 **Gemini Explanations** - AI explains every cleaning decision
- 💡 **Executive Insights** - Automatic discovery of key patterns
- 🎯 **AutoML Advisor** - Recommended ML tasks and models
- 💬 **Conversational Analytics** - Ask questions in natural language
- 📊 **Smart Summaries** - AI-generated dataset overviews

### Production Features (NEW)
- 💾 **Persistent Storage** - PostgreSQL + file storage
- 🔐 **Security Hardening** - File validation, input sanitization, rate limiting
- 📊 **Observability** - Request tracing, metrics, structured logging
- 🧪 **Testing Infrastructure** - Unit and integration test support
- 🗄️ **Database Migrations** - Alembic-based schema management

## Quick Start

### Prerequisites
- Docker & Docker Compose
- (Optional) Python 3.11+ for local development
- (Optional) Node.js 20+ for frontend development

### 1. Clone and Configure

```bash
# Clone repository
git clone <repo-url>
cd autoprep-ai

# Copy environment template
cp .env.example .env

# Add your Gemini API key
echo "GEMINI_API_KEY=your_api_key_here" >> .env
```

### 2. Run with Docker (Recommended)

```bash
docker compose up --build
```

**Access:**
- 🌐 Web UI: http://localhost:3000
- 🔌 API: http://localhost:8000
- 📚 API Docs: http://localhost:8000/docs
- ❤️ Health: http://localhost:8000/health
- 📊 Metrics: http://localhost:8000/metrics

### 3. Initialize Database

```bash
# Run migrations
docker compose exec api alembic upgrade head
```

## Local Development

### Backend

```bash
cd apps/api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd apps/web

# Install dependencies
npm install

# Start development server
npm run dev
```

## Project Structure

```
autoprep-ai/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── app/
│   │   │   ├── core/          # Configuration
│   │   │   ├── db/            # Database models & session
│   │   │   ├── middleware/    # Logging, security
│   │   │   ├── repositories/  # Data access layer
│   │   │   ├── routers/       # API endpoints
│   │   │   ├── schemas/       # Pydantic models
│   │   │   ├── services/      # Business logic
│   │   │   │   ├── gemini_service.py    # Gemini AI
│   │   │   │   ├── pdf_service.py       # PDF generation
│   │   │   │   ├── eda_service.py       # Enhanced EDA
│   │   │   │   ├── analysis_service.py  # Core analysis
│   │   │   │   └── ...
│   │   │   ├── storage/       # Storage abstraction
│   │   │   └── utils/         # Utilities
│   │   ├── alembic/           # Database migrations
│   │   └── tests/             # Backend tests
│   └── web/                   # Next.js frontend
│       ├── app/               # Pages & routes
│       ├── components/        # React components
│       └── lib/               # Client utilities
├── docs/                      # Documentation
│   ├── architecture.md
│   └── PHASE2_IMPLEMENTATION.md
├── docker-compose.yml
└── README.md
```

## API Reference

### Core Endpoints

```
POST   /datasets/upload              # Upload dataset
GET    /datasets/{id}/profile        # Get profile with AI insights
GET    /datasets/{id}/quality        # Quality audit
GET    /datasets/{id}/recommendations # AI-powered recommendations
GET    /datasets/{id}/health         # Health score & breakdown
POST   /datasets/{id}/clean          # Apply cleaning actions
GET    /datasets/{id}/versions       # Version history
POST   /datasets/{id}/rollback       # Rollback to version
GET    /datasets/{id}/eda            # Enhanced EDA charts
GET    /datasets/{id}/feature-engineering # Feature suggestions
GET    /datasets/{id}/ml-readiness   # ML readiness score
POST   /datasets/{id}/chat           # AI chatbot
GET    /datasets/{id}/code           # Generated preprocessing code
GET    /datasets/{id}/report/html    # HTML report
GET    /datasets/{id}/report/pdf     # PDF report (NEW)
GET    /datasets/{id}/export/csv     # Export cleaned data
GET    /datasets/{id}/insights       # AI executive insights (NEW)
GET    /datasets/{id}/ml-strategy    # AutoML recommendations (NEW)
```

### Observability Endpoints

```
GET    /health                        # Health check
GET    /metrics                       # Usage metrics
```

## Configuration

### Environment Variables

```bash
# API
DATABASE_URL=postgresql+psycopg2://autoprep:autoprep@postgres:5432/autoprep
REDIS_URL=redis://redis:6379/0
GEMINI_API_KEY=your_gemini_api_key_here

# Storage
STORAGE_BACKEND=local          # local | s3 | gcs | azure
STORAGE_PATH=./storage

# Security
SECRET_KEY=your-secret-key-change-in-production
MAX_UPLOAD_SIZE_MB=100

# Observability
LOG_LEVEL=INFO
ENABLE_TRACING=false

# Frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Documentation

- 📘 [Architecture Overview](docs/architecture.md)
- 📗 [Phase 2 Implementation Guide](docs/PHASE2_IMPLEMENTATION.md)
- 📕 API Documentation: http://localhost:8000/docs (when running)

## Testing

```bash
# Run backend tests
cd apps/api
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

## Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Check current version
alembic current
```

## Security Considerations

- ✅ File upload validation (type, size, filename)
- ✅ Input sanitization (SQL injection prevention)
- ✅ Prompt injection prevention for AI
- ✅ Rate limiting (configurable)
- ✅ Security headers (CSP, XSS protection)
- ✅ Environment-based secrets management

## Performance & Scalability

- Database connection pooling (10 connections, 20 overflow)
- Indexed foreign keys for fast lookups
- File storage abstraction for cloud scale
- Retry logic for AI API calls
- Efficient DataFrame operations

## Production Deployment Checklist

- [ ] Set strong `SECRET_KEY`
- [ ] Configure production `DATABASE_URL`
- [ ] Set valid `GEMINI_API_KEY`
- [ ] Configure specific CORS origins (not `*`)
- [ ] Enable tracing (`ENABLE_TRACING=true`)
- [ ] Set up log aggregation
- [ ] Configure cloud storage backend (S3/GCS/Azure)
- [ ] Set up database backups
- [ ] Configure SSL/TLS
- [ ] Set up monitoring and alerting
- [ ] Review rate limiting settings
- [ ] Adjust file upload limits

## Roadmap

### Phase 3 (Future)
- [ ] User authentication & authorization (JWT)
- [ ] Multi-tenancy support
- [ ] Async job queue (Celery/RQ)
- [ ] Advanced RAG for chatbot
- [ ] Real-time collaboration
- [ ] Custom ML model integration
- [ ] Data lineage tracking
- [ ] Automated monitoring & alerts

## Troubleshooting

### Database Issues
```bash
# Check PostgreSQL
docker compose ps postgres

# Reset database (DEV ONLY)
docker compose down -v
docker compose up -d postgres
docker compose exec api alembic upgrade head
```

### Gemini API Issues
```bash
# Verify API key
echo $GEMINI_API_KEY

# Check logs
docker compose logs api | grep -i gemini
```

### Storage Issues
```bash
# Check storage directory
ls -la ./storage

# Fix permissions
chmod -R 755 ./storage
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

[Your License Here]

## Support

For questions, issues, or contributions:
- Open an issue on GitHub
- Check logs: `docker compose logs api`
- Review docs in `docs/` folder
- Check metrics: `GET /metrics`

---

Built with ❤️ for data scientists and ML engineers who want to focus on models, not data cleaning.
