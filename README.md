# PE Org-AI-R Platform

**AI Readiness Assessment Platform for Private Equity**

A production-grade API system designed to assess and score the AI-readiness of portfolio companies and acquisition targets through comprehensive evidence collection and analysis.

**Authors:** Prachi Pradhan, Samiksh Gupta, Siddharth Shukla  
**Course:** Big Data and Intelligent Analytics  
**Codelab Link** https://codelabs-preview.appspot.com/?file_id=1JvR76bJ4wraYiLsfH8YzLDftXFJsoL5hjIfpnsIzi5s#9
🎥 **Video Presentation:** [Watch here](https://northeastern-my.sharepoint.com/personal/shukla_sid_northeastern_edu/_layouts/15/stream.aspx?id=%2Fpersonal%2Fshukla%5Fsid%5Fnortheastern%5Fedu%2FDocuments%2FRecordings%2FMeeting%20in%20Big%20Data%2D20260206%5F052700%2DMeeting%20Recording%2Emp4)
**Deployed Applicatiom**: https://pe-orgair-ui.onrender.com/ 
(If you get API disconnected error, kindly refresh the webpage)



## Table of Contents

- [Overview](#overview)
- [Business Context](#business-context)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation and Setup](#installation-and-setup)
- [Data Model](#data-model)
- [API Documentation](#api-documentation)
- [Evidence Collection](#evidence-collection)
- [Running Tests](#running-tests)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Deployment](#deployment)
- [Known Limitations](#known-limitations)


## Overview

The PE Org-AI-R (Private Equity Organizational AI-Readiness) Platform evaluates organizations across seven critical dimensions of AI capability and provides quantitative readiness scores to support investment decisions.

### Key Capabilities

- **Say-Do Gap Analysis**: Compare what companies claim in SEC filings versus actual AI investment
- **Multi-dimensional Scoring**: Evaluate AI readiness across 7 weighted dimensions
- **Evidence Collection**: Automated ingestion of SEC filings and external signals
- **Signal Analysis**: Job postings, patents, technology stack, and leadership commitment tracking

### Completed Case Studies

**Case Study 1: Platform Foundation**
- FastAPI application with RESTful endpoints
- Pydantic data models with validation
- Snowflake data warehouse integration
- Redis caching layer
- Docker containerization

**Case Study 2: Evidence Collection**
- SEC EDGAR filing download and parsing
- External signal collection (jobs, patents, tech stack, leadership)
- Document chunking for LLM processing
- S3 document storage
- Signal scoring algorithms


## Business Context

### The Say-Do Gap Problem

73% of companies mention "AI" in 10-K filings, but only 23% have deployed AI in production. This platform quantifies the gap between rhetoric and reality.

### Evidence Types

**What Companies SAY (SEC Filings)**
- 10-K annual reports: Strategy, risk factors, MD&A
- 10-Q quarterly reports: Recent developments
- 8-K material events: AI announcements, executive changes
- DEF-14A proxy statements: Executive compensation tied to technology

**What Companies DO (External Signals)**
- Technology Hiring: AI/ML job postings analysis (Weight: 30%)
- Innovation Activity: Patent filings in AI domains (Weight: 25%)
- Digital Presence: Technology stack analysis (Weight: 25%)
- Leadership Signals: Executive AI backgrounds (Weight: 20%)

### Target Companies

The platform tracks 10 companies across 5 sectors:

| Sector | Companies |
|--------|-----------|
| Manufacturing | CAT (Caterpillar), DE (Deere & Company) |
| Healthcare | UNH (UnitedHealth Group), HCA (HCA Healthcare) |
| Services | ADP (Automatic Data Processing), PAYX (Paychex Inc.) |
| Retail | WMT (Walmart Inc.), TGT (Target Corporation) |
| Financial | JPM (JPMorgan Chase), GS (Goldman Sachs) |

---

## Architecture

### System Overview

  
┌─────────────────────────────────────────────────┐
│           Streamlit UI                          │
│   Home | Dashboard | Signals | Reports          │
└─────────────────────────────────────────────────┘
                       │
┌─────────────────────────────────────────────────┐
│           FastAPI Application                    │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │   Routers    │  │   Pydantic Models        │ │
│  │  (Endpoints) │  │  (Validation)            │ │
│  └──────────────┘  └──────────────────────────┘ │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │   Services   │  │   Pipelines              │ │
│  │  (Business)  │  │  (Evidence Collection)   │ │
│  └──────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────┘
           │                │              │
           ▼                ▼              ▼
    ┌───────────┐    ┌─────────┐    ┌─────────┐
    │ Snowflake │    │  Redis  │    │   S3    │
    │ (Primary) │    │ (Cache) │    │  (Docs) │
    └───────────┘    └─────────┘    └─────────┘
  

### Evidence Collection Flow

  
SEC EDGAR → Document Pipeline → S3 (Raw) → Snowflake (Metadata)
Job Boards → Signal Pipeline → External Signals → Summary Scores
Patents → Patent Pipeline → Innovation Scores
Websites → Tech Pipeline → Digital Presence
  

---

## Project Structure

  
pe-org-air-platform/
├── app/
│   ├── main.py                      # FastAPI application entry point
│   ├── config.py                    # Configuration management
│   ├── errors.py                    # Global error handlers
│   ├── logging_config.py            # Structured logging setup
│   ├── models/                      # Pydantic data models
│   │   ├── assessment.py            # Assessment models
│   │   ├── company.py               # Company models
│   │   ├── dimension.py             # Dimension scores
│   │   ├── document.py              # SEC filing models
│   │   ├── evidence.py              # Evidence chunks
│   │   ├── signal.py                # External signals
│   │   ├── leadership.py            # Leadership evidence
│   │   ├── enums.py                 # Shared enumerations
│   │   └── assessment_state_machine.py  # Status transitions
│   ├── routers/                     # API endpoint definitions
│   │   ├── assessments.py           # Assessment CRUD
│   │   ├── companies.py             # Company CRUD
│   │   ├── dimension_scores.py      # Dimension scoring
│   │   ├── industries.py            # Industry reference
│   │   ├── documents.py             # SEC filing access
│   │   ├── signal.py                # Signal collection
│   │   └── health.py                # Health checks
│   ├── services/                    # Business logic
│   │   ├── assessments_service.py
│   │   ├── company_service.py
│   │   ├── dimension_scores_service.py
│   │   ├── industry_service.py
│   │   ├── signal_service.py
│   │   ├── sec_edgar_service.py
│   │   ├── snowflake.py             # Database connection
│   │   ├── redis_cache.py           # Caching layer
│   │   └── s3_storage.py            # Document storage
│   ├── pipelines/                   # Evidence collection
│   │   ├── sec_edgar.py             # SEC filing downloader
│   │   ├── document_parser.py       # PDF/HTML extraction
│   │   ├── chunker.py               # Semantic chunking
│   │   ├── job_signals.py           # Job posting analysis
│   │   ├── tech_signals.py          # Tech stack detection
│   │   ├── patent_signals.py        # Patent analysis
│   │   ├── leadership_signals.py    # Executive backgrounds
│   │   ├── say_score_analyzer.py    # AI rhetoric measurement
│   │   └── collectors/              # Pluggable collectors
│   │       ├── base_collector.py
│   │       ├── website_collector.py
│   │       ├── news_collector.py
│   │       └── hardcoded_collector.py
│   ├── reports/                     # Report generation
│   │   └── patent_report.py
│   └── database/
│       └── schema.sql               # Snowflake DDL
├── streamlit_ui/                    # User interface
│   ├── home.py                      # Dashboard home
│   ├── pages/
│   │   ├── collection_dashboard.py  # Evidence collection
│   │   ├── company_reports.py       # Company analysis
│   │   └── signal_analysis.py       # Signal comparison
│   └── utils/
│       └── api_client.py            # API wrapper
├── scripts/                         # Automation scripts
│   ├── collect_evidence.py          # Main collection orchestrator
│   ├── calculate_say_scores.py      # Say score calculation
│   └── fetch_evidence_stats.py      # Report generation
├── tests/                           # Test suite
│   ├── api/                         # API endpoint tests
│   ├── integration/                 # Snowflake integration tests
│   ├── unit/                        # Model validation tests
│   └── conftest.py                  # Pytest fixtures
├── docker/
│   ├── Dockerfile                   # Container image
│   └── docker-compose.yml           # Service orchestration
├── reports/                         # Generated reports
│   ├── evidence_stats.md            # Summary statistics
│   └── patent_signals/              # Patent analysis reports
├── .env.example                     # Environment template
├── pyproject.toml                   # Poetry dependencies
├── requirements.txt                 # Pip dependencies
└── README.md                        # This file
  

---

## Prerequisites

### Required Software
- Python 3.11 or higher
- Docker 20.10 or higher
- Docker Compose 2.0 or higher
- Git
- Poetry (recommended) or pip

### Required Accounts
- **Snowflake**: Active warehouse, database and schema access
- **AWS**: S3 bucket with IAM user permissions
- **Redis**: Provided via Docker Compose
- **NewsAPI**: Optional, for leadership signal enrichment

---

## Installation and Setup

### 1. Clone Repository

 
git clone <repository-url>
cd pe-org-air-platform
  

### 2. Configure Environment

cp .env.example .env

Edit `.env` with your credentials:

# Snowflake Configuration
SNOWFLAKE_ACCOUNT=your_account_identifier
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=PE_ORGAIR
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_ROLE=your_role  # Optional

# Redis Configuration
REDIS_HOST=redis  # Use 'localhost' for local development
REDIS_PORT=6379
REDIS_DB=0

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_REGION=us-east-1
S3_BUCKET=your_s3_bucket_name

# Optional: NewsAPI for leadership signals
NEWS_API_KEY=your_news_api_key

# Application
APP_ENV=local
APP_VERSION=1.0.0

### 3. Initialize Snowflake Database

Execute the SQL schema in your Snowflake account:

**Using Snowflake Web UI:**
1. Log in to Snowflake
2. Navigate to Worksheets
3. Open and execute `app/database/schema.sql`

**Using SnowSQL CLI:**
snowsql -a <account> -u <user> -f app/database/schema.sql

Verify tables:
USE DATABASE PE_ORGAIR;
USE SCHEMA PUBLIC;
SHOW TABLES;

### 4. Install Dependencies

**Using Poetry (Recommended):**
poetry install

**Using pip:**
pip install -r requirements.txt

**Install Playwright (for patent signals):**
playwright install chromium

### 5. Run with Docker


cd docker

# Build and start services
docker-compose up -d

# Verify containers
docker-compose ps

# View logs
docker-compose logs -f api
API available at: `http://localhost:8000`

### 6. Run Locally (Development)

# Start Redis via Docker
cd docker
docker-compose up -d redis
cd ..

# Update .env: Set REDIS_HOST=localhost

# Run FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

### 7. Run Streamlit UI
# In a separate terminal
streamlit run streamlit_ui/home.py

UI available at: `http://localhost:8501`


## Data Model

### Core Entities

**Industry**
- Reference data for company categorization
- Base AI-readiness score (h_r_base) by sector
- Sectors: Healthcare, Financial, Manufacturing, Services, Retail

**Company**
- Portfolio companies or acquisition targets
- Links to industry for context
- Position factor (-1.0 to 1.0) for market position adjustment
- Soft delete support

**Assessment**
- AI-readiness evaluation instances
- Types: screening, due_diligence, quarterly, exit_prep
- Status workflow with state machine validation
- VR score with confidence intervals

**Dimension Score**
- Individual dimension evaluations (7 dimensions)
- Weighted scoring system
- Evidence tracking
- Confidence levels

**Document**
- SEC filings (10-K, 10-Q, 8-K, DEF-14A)
- Content hashing for deduplication
- S3 storage integration
- Section extraction tracking

**Document Chunks**
- Semantic chunking with overlap
- Section-aware chunking
- Ready for LLM processing and vector search

**External Signals**
- Job postings, patents, tech stack, leadership
- Normalized scores (0-100)
- Metadata in JSON format
- Signal summaries by company

### AI-Readiness Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Data Infrastructure | 0.25 | Quality, accessibility, and governance of data assets |
| AI Governance | 0.20 | Policies, ethics frameworks, compliance readiness |
| Technology Stack | 0.15 | Cloud infrastructure, ML tooling, API architecture |
| Talent & Skills | 0.15 | AI/ML talent density, retention, training programs |
| Leadership & Vision | 0.10 | Executive commitment, AI strategy, investment appetite |
| Use Case Portfolio | 0.10 | AI projects in production, pipeline, ROI tracking |
| Culture & Change | 0.05 | Innovation culture, change readiness, adoption rates |

### Assessment Status State Machine

  
DRAFT ──────> IN_PROGRESS ──────> SUBMITTED ──────> APPROVED
                                       │                │
                                       └────> SUPERSEDED <┘


## API Documentation

### Interactive Documentation

Once running, access API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Core Endpoints

**Health**
- `GET /api/v1/health` - System health check with dependency status

**Companies**
- `POST /api/v1/companies` - Create company
- `GET /api/v1/companies` - List companies (paginated, filterable)
- `GET /api/v1/companies/{id}` - Get company by ID
- `PUT /api/v1/companies/{id}` - Update company
- `DELETE /api/v1/companies/{id}` - Soft delete company

**Assessments**
- `POST /api/v1/assessments` - Create assessment
- `GET /api/v1/assessments` - List assessments (paginated, filterable)
- `GET /api/v1/assessments/{id}` - Get assessment with scores
- `PATCH /api/v1/assessments/{id}/status` - Update status

**Dimension Scores**
- `POST /api/v1/assessments/{id}/scores` - Add dimension scores
- `GET /api/v1/assessments/{id}/scores` - Get scores (paginated)
- `PUT /api/v1/scores/{id}` - Update score
- `GET /api/v1/dimension-weights` - Get weight configuration

**Documents**
- `POST /api/v1/documents/sec-edgar/download` - Download SEC filings
- `GET /api/v1/documents/sec-edgar/download-zip` - Download as ZIP
- `GET /api/v1/documents/file` - Download local file

**Signals**
- `POST /api/v1/signals/collect-job-signals` - Collect job signals
- `POST /api/v1/signals/collect-tech-signals` - Collect tech signals
- `POST /api/v1/signals/collect-patent-signals` - Collect patent signals
- `POST /api/v1/signals/collect-leadership-signals` - Collect leadership signals
- `GET /api/v1/signals/companies/{id}` - Get company signals
- `GET /api/v1/signals/companies/{id}/summary` - Get signal summary
- `POST /api/v1/signals/companies/{id}/summary/refresh` - Refresh summary

**Industries**
- `POST /api/v1/industries` - Create industry
- `GET /api/v1/industries` - List industries (paginated, filterable)
- `GET /api/v1/industries/{id}` - Get industry by ID
- `GET /api/v1/sectors` - List available sectors

### Example Usage

**Create Company:**
curl -X POST http://localhost:8000/api/v1/companies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TechCorp Inc",
    "ticker": "TECH",
    "industry_id": "550e8400-e29b-41d4-a716-446655440003",
    "position_factor": 0.5
  }'

**Download SEC Filings:**

curl -X POST "http://localhost:8000/api/v1/documents/sec-edgar/download?company_id={uuid}&ticker=AAPL&filing_types=10-K&filing_types=10-Q&after=2023-01-01&limit=5"

**Collect Job Signals:**
curl -X POST "http://localhost:8000/api/v1/signals/collect-job-signals?company_id={uuid}&company_name=Apple%20Inc&max_results=20"

## Evidence Collection

### Automated Collection Script

Run evidence collection for all target companies:

# Collect all signal types for all companies
python scripts/collect_evidence.py --companies all --signals all

# Collect specific signals
python scripts/collect_evidence.py --companies JPM,GS --signals job,leadership

# Single company collection
python scripts/collect_evidence.py --ticker WMT --signals all


### Signal Types

**Technology Hiring Signals**
- Scrapes LinkedIn, Indeed using JobSpy
- AI relevance scoring based on keywords and skills
- Seniority distribution analysis
- Normalized score: 0-100

**Innovation Activity Signals**
- Google Patents search via Playwright
- CPC code filtering (G06N family for AI)
- Recency bonus for recent patents
- Category diversity scoring

**Digital Presence Signals**
- Company website, tech blogs, GitHub scraping
- AI technology detection
- Tech stack categorization
- Multi-source evidence aggregation

**Leadership Signals**
- Executive profile scraping
- AI background detection
- Role weight calculation
- Two-tier scoring (AI leadership present/absent)

### Say Score Calculation

Measures AI rhetoric in SEC filings:

python scripts/calculate_say_scores.py

Output: Say scores (0-100) based on AI keyword density in filing text

### Evidence Statistics

Generate comprehensive evidence report:

python scripts/fetch_evidence_stats.py


Output: `reports/evidence_stats.md` with:
- Document counts by company and filing type
- Chunk statistics
- Say vs. Do score comparison
- Sector analysis
- Latest signals detail


## Running Tests

### Full Test Suite


pytest tests/ -v

### Test Categories


# Unit tests (fast, no external dependencies)
pytest tests/unit/ -v

# API tests (mocked services)
pytest tests/api/ -v

# Integration tests (requires Snowflake)
pytest tests/integration/ -v -m integration

# With coverage report
pytest tests/ --cov=app --cov-report=html

## Configuration

### Environment Variables

**Snowflake (Required)**
- `SNOWFLAKE_ACCOUNT`: Account identifier
- `SNOWFLAKE_USER`: Username
- `SNOWFLAKE_PASSWORD`: Password
- `SNOWFLAKE_DATABASE`: Database name (default: PE_ORGAIR)
- `SNOWFLAKE_SCHEMA`: Schema name (default: PUBLIC)
- `SNOWFLAKE_WAREHOUSE`: Warehouse name
- `SNOWFLAKE_ROLE`: Role name (optional)

**Redis (Required)**
- `REDIS_HOST`: Hostname (redis for Docker, localhost for local)
- `REDIS_PORT`: Port (default: 6379)
- `REDIS_DB`: Database number (default: 0)

**AWS S3 (Required)**
- `AWS_ACCESS_KEY_ID`: IAM access key
- `AWS_SECRET_ACCESS_KEY`: IAM secret key
- `AWS_REGION`: AWS region (default: us-east-1)
- `S3_BUCKET`: S3 bucket name

**Application**
- `APP_ENV`: Environment (local/dev/prod)
- `APP_VERSION`: Version string

### Caching Strategy

| Data | TTL | Invalidation |
|------|-----|--------------|
| Company by ID | 5 minutes | On update/delete |
| Industry list | 1 hour | On create |
| Assessment | 2 minutes | On status change |
| Dimension weights | 24 hours | Configuration change |



## Troubleshooting

### Container Issues

**Container fails to start:**
 
docker-compose logs api
  

Common causes:
- Missing environment variables
- Invalid Snowflake credentials
- Port conflicts

**Port already in use:**
 
# Mac/Linux
lsof -i :8000

# Windows
netstat -ano | findstr :8000
  

### Database Connection

**Snowflake connection fails:**
- Verify warehouse is running (not suspended)
- Check role permissions
- Confirm network connectivity

  sql
ALTER WAREHOUSE COMPUTE_WH RESUME;
  

**Redis unhealthy:**
 
docker exec -it pe_orgair_redis redis-cli ping
# Should return: PING
  

### S3 Connection

**S3 not configured:**
- Verify bucket exists
- Check IAM permissions (s3:HeadBucket, s3:GetObject, s3:PutObject)
- Confirm access key is active


### Common Errors

**"Industry not found"** - Run seed data from schema.sql

**"Invalid status transition"** - Check allowed transitions in assessment_state_machine.py

**"assessment_id mismatch"** - Ensure body assessment_id matches URL parameter

**"No chunks found"** - Verify SEC filings were downloaded and parsed successfully

---


### Scaling Considerations

- FastAPI is stateless (horizontal scaling ready)
- Consider connection pooling for Snowflake
- Redis can be sharded if cache grows
- S3 provides unlimited storage
- Rate limiting on collection endpoints (10/hour for downloads, 100/minute for file access)

---

## Known Limitations

### Current Scope

1. **Authentication**: Not implemented - production requires JWT and RBAC
2. **VR Score Calculation**: Formula defined but not implemented (Case Study 3)
3. **Rate Limiting**: Basic limits on document endpoints only
4. **Audit Logging**: Changes not tracked
5. **NewsAPI**: Disabled due to free tier limitations (HTTP 426)
6. **Patent Collection**: Synchronous (can be slow for large patent portfolios)

### Data Quality

- **Say Scores**: Only 4/10 companies have complete SEC data retrieval
- **Leadership Signals**: Some companies require hardcoded executive data
- **Job Signals**: Subject to scraping availability and rate limits
- **Patent Signals**: Relies on Google Patents UI (no official API)

### Performance

- Pagination capped at 100 records
- SEC downloads rate-limited by SEC (10/second)
- Job scraping can take 2-5 minutes per company
- Patent analysis requires browser automation (Playwright)

---

## Design Decisions

### Architecture

**Snowflake for Primary Persistence**
- Analytical query performance
- Semi-structured data support (VARIANT for JSON)
- Compute/storage separation

**Redis for Caching**
- Read-through cache pattern
- TTL-based invalidation
- Pattern-based bulk invalidation

**FastAPI Framework**
- Auto-generated OpenAPI docs
- Built-in validation via Pydantic
- Async support for I/O operations

**Pydantic for Data Validation**
- Type safety at API boundaries
- Automatic serialization
- Clear error messages

### Data Modeling

**Soft Deletes** - Maintains referential integrity, supports audit trails

**UUID Primary Keys** - Distributed system friendly, no coordination needed

**Weighted Scoring** - Configurable dimension weights, transparent logic

**State Machine** - Enforces workflow integrity, prevents invalid transitions

**Section-Level Deduplication** - Prevents duplicate chunks from TOC matches

**Signal Summaries** - Materialized view pattern for fast composite score access

### Evidence Collection

**Modular Collectors** - Base class pattern for extensible signal sources

**Multi-Source Aggregation** - Combines website, GitHub, news for comprehensive evidence

**Two-Tier Leadership Scoring** - Full credit for AI leadership, 50% penalty without

**AI Relevance Scoring** - Composite score from title keywords and skill count

**CPC-Based Patent Filtering** - Uses G06N family codes for AI classification

---

## Evidence Statistics

### Document Collection (as of February 2026)

- **Companies**: 10
- **Total Documents**: 53 (20 × 10-K, 11 × 10-Q, 11 × 8-K, 11 × DEF-14A)
- **Total Chunks**: 2,602
- **Total Words**: 2,587,824

### Signal Collection

- **Total Signals**: 38
- **Companies with Signals**: 10
- **Average Composite Score**: 42.9/100

### Top Companies by Do Score

1. **WMT** - 68.2 (Quiet builder, Do > Say)
2. **UNH** - 66.3
3. **GS** - 57.0

### Biggest Say-Do Gaps

1. **ADP** - Say: 100.0, Do: 31.8 (Gap: +68.2)
2. **PAYX** - Say: 93.7, Do: 28.4 (Gap: +65.3)
3. **HCA** - Say: 76.1, Do: 40.2 (Gap: +35.8)

---

## Development Workflow

### Adding New Endpoints

1. Define Pydantic models in `app/models/`
2. Implement business logic in `app/services/`
3. Create router in `app/routers/`
4. Register router in `app/main.py`
5. Add tests in `tests/api/`

### Adding New Signal Collectors

1. Create collector class inheriting from `BaseLeadershipCollector` or similar
2. Implement `collect_leadership_data()` method
3. Add to orchestrator in relevant pipeline
4. Add endpoint in `app/routers/signal.py`
5. Update `scripts/collect_evidence.py`

### Database Changes

1. Update `app/database/schema.sql`
2. Run migration in Snowflake
3. Update Pydantic models
4. Update service layer queries
5. Clear relevant Redis caches

---

## Key Findings

### Say-Do Gap Analysis

Companies with positive gaps (more talk than action):
- ADP, PAYX, HCA show high AI rhetoric but limited actual investment
- Common in services sector

Companies with negative gaps (quiet builders):
- WMT, JPM show more AI activity than filing rhetoric
- Indicates operational focus over marketing

### Sector Trends

- **Healthcare**: Highest average composite (53.3) - Strong leadership signals
- **Retail**: Second highest (50.8) - Balanced across all dimensions
- **Services**: Lowest (30.1) - High say scores but weak execution signals

## Team Contributions

| Name | Email | Role |
|------|-------|------|
| Prachi Pradhan | pradhanprac@northeastern.edu | SEC EDGAR pipeline, document parser, chunking logic, S3 storage, Snowflake schema, Say Score analyzer, leadership signals, Redis caching, documentation |
| Samiksha Gupta | gupta.samik@northeastern.edu | Job signal pipeline, evidence collection script, Streamlit signal analysis page, Docker setup, UI changes, Snowflake setup, S3 setup |
| Siddharth Shukla | shukla.sid@northeastern.edu | FastAPI endpoints, Pydantic models, Redis caching, assessment state machine, health check, Streamlit company reports page, tech signal pipeline, patent signal pipeline, signal scoring |

## AI Tools Disclosure

| Tool | Usage |
|------|-------|
| Claude (Anthropic) | Code debugging, architecture discussions, documentation drafting |
| GitHub Copilot | Code autocompletion during development |

All code was reviewed, understood, and tested by team members before inclusion.

## Resources

### Documentation

- FastAPI: https://fastapi.tiangolo.com
- Pydantic v2: https://docs.pydantic.dev
- Snowflake Python: https://docs.snowflake.com/en/developer-guide/python-connector
- Redis-py: https://redis-py.readthedocs.io
- sec-edgar-downloader: https://sec-edgar-downloader.readthedocs.io
- JobSpy: https://github.com/Bunsly/JobSpy

