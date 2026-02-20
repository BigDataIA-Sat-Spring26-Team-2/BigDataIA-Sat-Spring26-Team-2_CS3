# PE Org-AI-R Platform

> **Private Equity AI Readiness Assessment Platform**
> Quantifying the Say-Do Gap Between AI Claims and AI Investment

**Authors:** Prachi Pradhan · Samiksh Gupta · Siddharth Shukla
**Course:** Big Data and Intelligent Analytics — Northeastern University, Spring 2026
**Instructor:** Sri Krishnamurthy

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Snowflake](https://img.shields.io/badge/Snowflake-Database-29B5E8?logo=snowflake)](https://snowflake.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://python.org)

---

## Table of Contents

- [Overview](#overview)
- [The Org-AI-R Formula](#the-org-ai-r-formula)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Case Studies](#case-studies)
- [Target Companies](#target-companies)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Configuration](#configuration)
- [Running the Platform](#running-the-platform)
- [API Documentation](#api-documentation)
- [Scoring Pipeline](#scoring-pipeline)
- [Evidence Collection](#evidence-collection)
- [Testing](#testing)
- [Deployment](#deployment)
- [Known Limitations](#known-limitations)
- [AI Tools Disclosure](#ai-tools-disclosure)
- [Team Contributions](#team-contributions)
- [Resources](#resources)

---

## Overview

The PE Org-AI-R platform helps private equity firms assess the **AI readiness** of portfolio companies and acquisition targets. It exposes the **Say-Do Gap** — the difference between what companies claim about AI in SEC filings versus their actual AI investment signals.

### Core Capabilities

| Capability | Description |
|---|---|
| Say-Do Gap Analysis | Compares AI rhetoric in SEC filings vs. actual investment signals |
| Multi-Dimensional Scoring | Evaluates 7 weighted AI-readiness dimensions |
| Full Org-AI-R Pipeline | End-to-end: evidence → V^R → H^R → Synergy → Final Score |
| Evidence Collection | Automated ingestion from SEC EDGAR, job boards, patents, websites |
| Investment Memo Generation | PE-style memos via Claude AI (Anthropic) |

### Deployed Links

| Resource | URL |
|---|---|
| Live Application | https://pe-orgair-ui.onrender.com |
| Swagger API | https://pe-orgair-api.onrender.com/docs |
| Codelab | https://codelabs-preview.appspot.com/?file_id=1M1qy9K_uIb4iEWX_q6jUartn6D3v5NVLpBwZ-TPpm9c#10 |
| Video Presentation | [Watch on SharePoint](https://northeastern-my.sharepoint.com/personal/shukla_sid_northeastern_edu/_layouts/15/stream.aspx?id=%2Fpersonal%2Fshukla%5Fsid%5Fnortheastern%5Fedu%2FDocuments%2FRecordings%2FMeeting%20in%20Big%20Data%2D20260206%5F052700%2DMeeting%20Recording%2Emp4) |

---

## The Org-AI-R Formula

```
Org-AI-Rⱼ,ₜ = (1 − β) · [α · V^R_org,j(t) + (1 − α) · H^R_org,k(t)] + β · Synergy(V^R, H^R)
```

| Symbol | Value | Description |
|:---:|:---:|---|
| α | 0.60 | Idiosyncratic weight (company-specific factors) |
| β | 0.12 | Synergy weight (alignment effects) |
| λ | 0.25 | Non-compensatory CV penalty coefficient |
| δ | 0.15 | Position adjustment coefficient |

### V^R Formula (Venture Readiness)

```
V^R = D̄_w × (1 − 0.25 × CV_D) × TalentRiskAdj

TalentRiskAdj = 1 − 0.15 × max(0, TC − 0.25)
```

### H^R Formula (Industry Readiness)

```
H^R = H^R_base × (1 + 0.15 × PositionFactor)
```

---

## Architecture

```
Diagram: https://drive.google.com/file/d/1Lf1HIuNp9F5kZNLsNwiyC-fTdwWLm-es/view?usp=sharing 

---


## Project Structure

```text
pe-org-air-platform/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── errors.py
│   ├── logging_config.py
│   │
│   ├── models/
│   │   ├── assessment.py
│   │   ├── assessment_state_machine.py
│   │   ├── board.py
│   │   ├── company.py
│   │   ├── dimension.py
│   │   ├── document.py
│   │   ├── enums.py
│   │   ├── evidence.py
│   │   ├── health.py
│   │   ├── industry.py
│   │   ├── leadership.py
│   │   ├── pagination.py
│   │   └── signal.py
│   │
│   ├── routers/
│   │   ├── assessments.py
│   │   ├── companies.py
│   │   ├── dimension_scores.py
│   │   ├── documents.py
│   │   ├── health.py
│   │   ├── industries.py
│   │   ├── scoring.py
│   │   └── signal.py
│   │
│   ├── services/
│   │   ├── assessments_service.py
│   │   ├── company_service.py
│   │   ├── dimension_scores_service.py
│   │   ├── evidence_counter.py
│   │   ├── industry_service.py
│   │   ├── integration_service.py
│   │   ├── leadership_signal_service.py
│   │   ├── redis_cache.py
│   │   ├── s3_storage.py
│   │   ├── scoring_service.py
│   │   ├── sec_edgar_service.py
│   │   ├── signal_service.py
│   │   └── snowflake.py
│   │
│   ├── pipelines/
│   │   ├── board_analyzer.py
│   │   ├── chunker.py
│   │   ├── document_parser.py
│   │   ├── glassdoor_collector.py
│   │   ├── job_signals.py
│   │   ├── leadership_signals.py
│   │   ├── patent_signals.py
│   │   ├── say_score_analyzer.py
│   │   ├── sec_edgar.py
│   │   ├── sec_item_analyzer.py
│   │   ├── tech_signals.py
│   │   └── collectors/
│   │       ├── base_collector.py
│   │       ├── hardcoded_collector.py
│   │       ├── news_collector.py
│   │       └── website_collector.py
│   │
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── confidence_calculator.py
│   │   ├── evidence_helpers.py
│   │   ├── evidence_mapper.py
│   │   ├── hr_calculator.py
│   │   ├── investment_memo_generator.py
│   │   ├── position_factor.py
│   │   ├── rubric_scorer.py
│   │   ├── synergy_calculator.py
│   │   ├── talent_concentration.py
│   │   ├── utils.py
│   │   └── vr_calculator.py
│   │
│   ├── reports/
│   │   └── patent_report.py
│   │
│   └── database/
│       └── schema.sql
│
├── streamlit_ui/
│   ├── home.py
│   ├── pages/
│   │   ├── collection_dashboard.py
│   │   ├── data_management.py
│   │   ├── hr_calculator.py
│   │   ├── scoring_memo.py
│   │   ├── signal_analysis.py
│   │   ├── streamlit_app.py
│   │   └── vr_calculator.py
│   └── utils/
│       └── api_client.py
│
├── scripts/
│   ├── calculate_say_scores.py
│   ├── collect_evidence.py
│   ├── fetch_evidence_stats.py
│   ├── integration_service_scripts.py
│   ├── sample_JSON.py
│   └── upload_to_s3.py
│
├── tests/
│   ├── api/
│   │   ├── test_assessments_api.py
│   │   ├── test_companies_api.py
│   │   └── test_dimension_scores_api.py
│   ├── integration/
│   │   ├── test_snowflake_assessments.py
│   │   ├── test_snowflake_companies.py
│   │   └── test_snowflake_dimension_scores.py
│   ├── unit/
│   │   ├── test_models_assessment.py
│   │   ├── test_models_company.py
│   │   ├── test_models_dimension_score.py
│   │   └── test_rubric_scorer.py
│   ├── conftest.py
│   ├── test_board_analyzer.py
│   ├── test_evidence_mapper_integration.py
│   ├── test_leadership.py
│   ├── test_scoring_pipeline.py
│   ├── test_talent_concetration.py
│   └── test_tc_standalone.py
│
├── reports/
│   └── evidence_stats.md
│
├── .env.example
├── pyproject.toml
├── requirements.txt
├── render.yaml
└── README.md
```

---

## Case Studies

### Case Study 1 — Platform Foundation

| Component | Description |
|---|---|
| FastAPI Application | RESTful endpoints with auto-generated OpenAPI docs |
| Pydantic v2 Models | Type-safe validation at API boundaries |
| Snowflake Integration | Companies, industries, assessments, dimension scores |
| Redis Caching | TTL-based read-through cache with pattern invalidation |
| Assessment State Machine | DRAFT → IN_PROGRESS → SUBMITTED → APPROVED → SUPERSEDED |

### Case Study 2 — Evidence Collection

| Component | Description |
|---|---|
| SEC EDGAR Pipeline | Download, parse, and chunk 10-K, 10-Q, 8-K, DEF 14A filings |
| Job Signal Collector | LinkedIn + Indeed AI/ML job posting analysis |
| Patent Signal Collector | Google Patents CPC G06N filtering via Playwright |
| Tech Stack Collector | Company website + GitHub technology detection |
| Leadership Collector | Executive AI background scoring |
| Say Score Analyzer | AI keyword density measurement in SEC filings |

### Case Study 3 — AI Scoring Engine

| Task | Component | Description |
|---|---|---|
| 5.0a | Evidence Mapper | 9 signal sources → 7 dimensions with primary/secondary weights |
| 5.0b | Rubric Scorer | 5-level qualitative rubrics for all 7 dimensions |
| 5.0c | Glassdoor Collector | Employee review culture signal analysis |
| 5.0d | Board Analyzer | DEF 14A proxy statement governance scoring |
| 5.0e | Talent Concentration | Key-person risk from job metadata |
| 5.1 | Decimal Utilities | Weighted mean, std dev, CV with Decimal precision |
| 5.2 | V^R Calculator | Full venture readiness formula with audit logging |
| 5.3 | Property-Based Tests | Hypothesis tests (500 examples each) |
| 6.0a | Position Factor | Company position relative to sector peers |
| 6.0b | Integration Service | End-to-end CS1/CS2 → Org-AI-R pipeline |
| 6.1 | H^R Calculator | Industry AI readiness with position adjustment |
| 6.2 | Confidence Calculator | SEM-based 95% confidence intervals |
| 6.3 | Synergy Calculator | Alignment × timing factor synergy score |
| 6.4 | Org-AI-R Calculator | Final weighted composite score |
| 6.5 | Portfolio Results | 13-company scored portfolio |

---

## Target Companies

| Sector | Ticker | Company |
|---|:---:|---|
| Manufacturing | CAT | Caterpillar Inc. |
| Manufacturing | DE | Deere & Company |
| Manufacturing | GE | General Electric Co. |
| Healthcare | UNH | UnitedHealth Group |
| Healthcare | HCA | HCA Healthcare |
| Services | ADP | Automatic Data Processing |
| Services | PAYX | Paychex Inc. |
| Retail | WMT | Walmart Inc. |
| Retail | TGT | Target Corporation |
| Retail | DG | Dollar General Corp. |
| Financial | JPM | JPMorgan Chase |
| Financial | GS | Goldman Sachs |
| Technology | NVDA | NVIDIA Corporation |

---

## Prerequisites

- Python 3.11+
- Docker & Docker Compose 2.0+
- Snowflake account (warehouse, database, schema)
- AWS account (S3 bucket + IAM credentials)
- Anthropic API key (for investment memo generation)

---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd pe-org-air-platform
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Snowflake
SNOWFLAKE_ACCOUNT=your_account_identifier
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=PE_ORGAIR
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_ROLE=your_role          # optional

# Redis
REDIS_HOST=redis                  # use 'localhost' for local dev
REDIS_PORT=6379
REDIS_DB=0

# AWS S3
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_REGION=us-east-1
S3_BUCKET=your_s3_bucket_name

# Anthropic (for investment memo generation)
ANTHROPIC_API_KEY=your_anthropic_api_key
CLAUDE_MODEL=claude-haiku-4-5-20251001

# Application
APP_ENV=local
APP_VERSION=1.0.0
```

### 3. Initialize Snowflake Schema

Run `app/database/schema.sql` in your Snowflake worksheet or via SnowSQL:

```bash
snowsql -a <account> -u <user> -f app/database/schema.sql
```

### 4. Install Dependencies

```bash
# Using Poetry (recommended)
poetry install

# Using pip
pip install -r requirements.txt

# Install Playwright for patent signals
playwright install chromium
```

### 5. Run with Docker

```bash
cd docker
docker-compose up -d
```

API available at `http://localhost:8000`

### 6. Run Locally (Development)

```bash
# Start Redis only
docker-compose up -d redis

# Update .env: set REDIS_HOST=localhost

# Start FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 7. Start the Streamlit UI

```bash
streamlit run streamlit_ui/home.py
```

UI available at `http://localhost:8501`

---

## Configuration

### Environment Variables Reference

| Variable | Required | Description |
|---|:---:|---|
| SNOWFLAKE_ACCOUNT | Yes | Snowflake account identifier |
| SNOWFLAKE_USER | Yes | Username |
| SNOWFLAKE_PASSWORD | Yes | Password |
| SNOWFLAKE_DATABASE | Yes | Database name (PE_ORGAIR) |
| SNOWFLAKE_SCHEMA | Yes | Schema name (PUBLIC) |
| SNOWFLAKE_WAREHOUSE | Yes | Warehouse name |
| SNOWFLAKE_ROLE | No | Role (optional) |
| REDIS_HOST | Yes | Redis hostname |
| REDIS_PORT | Yes | Redis port (6379) |
| AWS_ACCESS_KEY_ID | Yes | AWS access key |
| AWS_SECRET_ACCESS_KEY | Yes | AWS secret key |
| AWS_REGION | Yes | AWS region |
| S3_BUCKET | Yes | S3 bucket name |
| ANTHROPIC_API_KEY | Yes | Anthropic API key for Claude |
| CLAUDE_MODEL | No | Claude model ID (defaults to haiku) |

### Caching Strategy

| Data | TTL | Invalidation Trigger |
|---|:---:|---|
| Company by ID | 5 min | On update or delete |
| Industry list | 1 hour | On create |
| Assessment | 2 min | On status change |
| Dimension weights | 24 hours | Configuration change |

---

## Running the Platform

### Collect Evidence for All Companies

```bash
# Collect all signal types for all companies
python scripts/collect_evidence.py --companies all --signals all

# Collect specific signals for specific tickers
python scripts/collect_evidence.py --companies JPM,GS --signals job,leadership

# Single company, all signals
python scripts/collect_evidence.py --ticker WMT --signals all
```

Available signal types: `job`, `leadership`, `tech`, `patent`, `board`

### Calculate Say Scores

```bash
python scripts/calculate_say_scores.py
```

### Generate Evidence Report

```bash
python scripts/fetch_evidence_stats.py
# Output: reports/evidence_stats.md
```

---

## API Documentation

Interactive docs available at runtime:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Core Endpoints

#### Health
```
GET /api/v1/health
```

#### Companies
```
POST   /api/v1/companies
GET    /api/v1/companies
GET    /api/v1/companies/{id}
PUT    /api/v1/companies/{id}
DELETE /api/v1/companies/{id}
```

#### Assessments
```
POST   /api/v1/assessments
GET    /api/v1/assessments
GET    /api/v1/assessments/{id}
PATCH  /api/v1/assessments/{id}/status
```

#### Dimension Scores
```
POST  /api/v1/assessments/{id}/scores
GET   /api/v1/assessments/{id}/scores
PUT   /api/v1/scores/{id}
GET   /api/v1/dimension-weights
```

#### Documents
```
POST /api/v1/documents/sec-edgar/download
GET  /api/v1/documents/sec-edgar/download-zip
```

#### Signals
```
POST /api/v1/signals/collect-job-signals
POST /api/v1/signals/collect-tech-signals
POST /api/v1/signals/collect-patent-signals
POST /api/v1/signals/collect-leadership-signals
POST /api/v1/signals/collect-board-signals
POST /api/v1/signals/collect-sec-item1-signals
POST /api/v1/signals/collect-sec-item1a-signals
POST /api/v1/signals/collect-sec-item7-signals
GET  /api/v1/signals/companies/{id}
GET  /api/v1/signals/companies/{id}/summary
POST /api/v1/signals/companies/{id}/summary/refresh
```

#### Scoring (CS3)
```
GET  /api/v1/scoring/companies/{id}/dimensions
GET  /api/v1/scoring/companies/{id}/vr
GET  /api/v1/scoring/companies/{id}/org-air
POST /api/v1/scoring/companies/{id}/memo
POST /api/v1/scoring/companies/vr/batch
POST /api/v1/scoring/companies/compare
```

---

## Scoring Pipeline

### 7 AI-Readiness Dimensions

| Dimension | Default Weight | Description |
|---|:---:|---|
| Data Infrastructure | 0.25 | Data storage, pipelines, quality |
| AI Governance | 0.20 | Policies, ethics, risk controls |
| Technology Stack | 0.15 | ML tooling, MLOps, cloud platforms |
| Talent & Skills | 0.15 | AI/ML hiring depth and skill diversity |
| Leadership & Vision | 0.10 | Executive commitment, AI strategy |
| Use Case Portfolio | 0.10 | Deployed AI use cases and ROI |
| Culture & Change | 0.05 | Innovation culture and agility |

### Signal-to-Dimension Mapping (Table 1)

> `(P)` = Primary contribution. All weights per source sum to 1.0.

| CS2 Source | Data Infra | AI Gov | Tech Stack | Talent | Leadership | Use Case | Culture |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| technology_hiring | 0.10 | — | 0.20 | 0.70 (P) | — | — | — |
| innovation_activity | 0.20 | — | 0.50 (P) | — | — | 0.30 | — |
| digital_presence | 0.60 (P) | — | 0.40 | — | — | — | — |
| leadership_signals | — | 0.25 | — | — | 0.60 (P) | — | 0.15 |
| sec_item_1_business | — | — | 0.30 | — | — | 0.70 (P) | — |
| sec_item_1a_risk | 0.20 | 0.80 (P) | — | — | — | — | — |
| sec_item_7_mda | 0.20 | — | — | — | 0.50 (P) | 0.30 | — |
| glassdoor_reviews | — | — | — | 0.10 | 0.10 | — | 0.80 (P) |
| board_composition | — | 0.70 (P) | — | — | 0.30 | — | — |

### Path A + Path B Score Combination

```
Combined Score = 0.60 × Path A (quantitative) + 0.40 × Path B (qualitative)
```

| Path | Method | Description |
|---|---|---|
| Path A | Evidence Mapper | Weighted contributions from CS2 signal scores |
| Path B | Rubric Scorer | 5-level qualitative rubrics evaluated against extracted evidence text |

### 5-Level Rubric (Example: Talent Dimension)

| Level | Score Range | Criteria |
|:---:|:---:|---|
| 5 | 80 - 100 | ML platform team, 20+ specialists, AI research capability |
| 4 | 60 - 79 | Established team (10-20), active hiring, retention programs |
| 3 | 40 - 59 | Small team (3-10 data scientists), growing capability |
| 2 | 20 - 39 | 1-2 data scientists, high turnover, limited depth |
| 1 | 0 - 19 | No AI talent, vendor-dependent |

### Sector-Specific V^R Weights

| Sector | Data Infra | AI Gov | Tech Stack | Talent | Leadership | Use Case | Culture |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Technology | 0.25 | 0.15 | 0.20 | 0.20 | 0.10 | 0.05 | 0.05 |
| Financial | 0.25 | 0.25 | 0.15 | 0.15 | 0.10 | 0.05 | 0.05 |
| Healthcare | 0.25 | 0.25 | 0.15 | 0.15 | 0.10 | 0.05 | 0.05 |
| Retail | 0.25 | 0.15 | 0.15 | 0.15 | 0.10 | 0.15 | 0.05 |
| Manufacturing | 0.25 | 0.20 | 0.15 | 0.15 | 0.10 | 0.10 | 0.05 |
| Business Services | 0.25 | 0.20 | 0.15 | 0.15 | 0.10 | 0.10 | 0.05 |

### Confidence Interval (Spearman-Brown Reliability)

```
ρ = (n × r) / (1 + (n − 1) × r)
SEM = σ × √(1 − ρ)
95% CI = score ± 1.96 × SEM
```

---

## Evidence Collection

### What Companies SAY (SEC Filings)

| Filing | Sections Extracted | Purpose |
|---|---|---|
| 10-K | Item 1 (Business), Item 1A (Risk), Item 7 (MD&A) | Strategy, risks, investment |
| 10-Q | Item 1A, Item 2 (MD&A) | Quarterly updates |
| 8-K | Item 8.01 | Material AI announcements |
| DEF 14A | Executive Compensation, Board Bios | Governance, leadership |

### What Companies DO (External Signals)

| Signal | Source | Composite Weight | Description |
|---|---|:---:|---|
| Technology Hiring | LinkedIn + Indeed | 30% | AI/ML job posting analysis |
| Innovation Activity | Google Patents | 25% | CPC G06N AI patent filings |
| Digital Presence | Tech blogs + GitHub | 25% | AI technology stack detection |
| Leadership Signals | Company websites | 20% | Executive AI backgrounds |
| Board Governance | DEF 14A Proxy Statements | — | Board AI expertise, tech committee presence, data officer roles |
| SEC Item 1 | 10-K Business Section | — | AI use case mentions, production deployments, product diversity |
| SEC Item 1A | 10-K Risk Factors | — | AI risk disclosure, cybersecurity, regulatory compliance |
| SEC Item 7 | 10-K / 10-Q MD&A | — | AI strategy discussion, technology investment, executive priorities |
| Culture Signals | Glassdoor Reviews (S3) | — | Innovation culture, data-driven mindset, change readiness |


### Say Score Calculation

Measures AI rhetoric density across ~90 weighted keywords in SEC filings:

```
mention_density = weighted_mentions / total_words × 1000
say_score       = min(√(mention_density) × 95, 100)
```

---

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Test Categories

```bash
# Unit tests (no external dependencies)
pytest tests/unit/ -v

# API tests (monkeypatched services)
pytest tests/api/ -v

# Integration tests (requires Snowflake)
pytest tests/integration/ -v -m integration

# Scoring pipeline tests
pytest tests/test_scoring_pipeline.py -v -s

# Talent concentration standalone (no DB required)
pytest tests/test_tc_standalone.py -v

# Property-based tests (Hypothesis, 500 examples)
pytest tests/test_talent_concetration.py -v

# With coverage report
pytest tests/ --cov=app --cov-report=html
```

### Property-Based Tests (Hypothesis)

| Property | Description |
|---|---|
| test_all_dimensions_returned | EvidenceMapper always returns exactly 7 dimensions |
| test_missing_evidence_defaults_to_50 | No evidence returns default score of 50.0 |
| test_more_evidence_higher_confidence | More sources gives equal or higher confidence |
| test_tc_always_bounded | Talent Concentration always in [0, 1] |
| test_larger_teams_lower_concentration | Larger team produces lower TC score |
| test_vr_always_bounded | V^R always in [0, 100] |
| test_score_within_level_bounds | Rubric score always within its level's min/max range |
| test_deterministic | Same inputs always produce identical output |

---

## Deployment

The platform is deployed on [Render](https://render.com) using `render.yaml`.

### Services

| Service | Type | Description |
|---|---|---|
| pe-orgair-api | Web (Python) | FastAPI backend |
| pe-orgair-ui | Web (Python) | Streamlit frontend |
| pe-orgair-redis | Redis | Cache layer |

### Health Check

```bash
curl https://pe-orgair-api.onrender.com/health
```

### Rate Limits

| Endpoint | Limit |
|---|---|
| SEC EDGAR download | 10 requests / hour |
| ZIP file download | 10 requests / hour |
| Local file access | 100 requests / minute |

---

## Data Model

### Assessment Status State Machine

```
DRAFT ──→ IN_PROGRESS ──→ SUBMITTED ──→ APPROVED
                               │              │
                               └──→ SUPERSEDED ←┘
```

### Database Tables

| Table | Description |
|---|---|
| industries | Reference data with H^R base by sector |
| companies | Portfolio companies with position factor |
| assessments | AI readiness assessments per company |
| dimension_scores | 7-dimension scores per assessment |
| documents | SEC filing metadata |
| document_chunks | Section-aware text chunks |
| external_signals | CS2 + CS3 evidence signals |
| company_signal_summaries | Materialized composite scores |

---

## Known Limitations

| Limitation | Description |
|---|---|
| Authentication | Not implemented — production requires JWT + RBAC |
| NewsAPI | Disabled (HTTP 426 on free tier) |
| Patent Collection | Synchronous Playwright browser — slow for large portfolios |
| Rate Limits | SEC downloads: 10/hour; ZIP downloads: 10/hour |
| SEC Data Coverage | Some companies have partial multi-year filing history |

---

## AI Tools Disclosure

| Tool | Usage |
|---|---|
| Claude (Anthropic) | Code debugging, architecture design, documentation, investment memo generation |
| GitHub Copilot | Code autocompletion during development |

All code was reviewed, understood, and tested by team members before inclusion.

---

## Team Contributions

| Name | Email | Contributions |
|---|---|---|
| Prachi Pradhan | pradhanprac@northeastern.edu | SEC EDGAR pipeline, document parser, chunking, S3 storage, Snowflake schema, Say Score analyzer, leadership signals, Redis caching, CS3 scoring engine (evidence mapper, rubric scorer, VR calculator),Board analyer composition, investment memo generator using claude anthropic, documentation |
| Samiksh Gupta | gupta.samik@northeastern.edu | Job signal pipeline, evidence collection script, Streamlit signal analysis page, Docker setup, UI improvements, Snowflake setup, S3 setup,HR/synergy calculators, confidence CI,glassdoor reviews collection, ruberics scorer, integration service|
| Siddharth Shukla | shukla.sid@northeastern.edu | FastAPI endpoints, Pydantic models, Redis caching, assessment state machine, health check, Streamlit company reports, tech signal pipeline, patent signal pipeline, signal scoring,HR/synergy calculators, confidence CI , talent concentration, ruberic scorer,integration service, Airflow implementation for sec edgar pipeline|

---

## Resources

| Resource | Link |
|---|---|
| FastAPI | https://fastapi.tiangolo.com |
| Pydantic v2 | https://docs.pydantic.dev |
| Snowflake Python Connector | https://docs.snowflake.com/en/developer-guide/python-connector |
| Redis-py | https://redis-py.readthedocs.io |
| sec-edgar-downloader | https://sec-edgar-downloader.readthedocs.io |
| JobSpy | https://github.com/Bumsly/JobSpy |
| Hypothesis | https://hypothesis.readthedocs.io |
| Anthropic API | https://docs.anthropic.com |

---

