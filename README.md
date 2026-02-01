# PE Org-AI-R Platform

## Overview

The PE Org-AI-R (Private Equity Organizational AI-Readiness) Platform is a production-grade API system designed to assess and score the AI-readiness of portfolio companies and acquisition targets. The platform evaluates organizations across seven critical dimensions of AI capability and provides quantitative readiness scores to support investment decisions.

This repository contains Case Study 1: the foundational API layer, data models, and persistence infrastructure that serves as the basis for all subsequent platform capabilities.

## Architecture

The platform implements a microservices-ready architecture with the following components:

- **API Layer**: FastAPI application with RESTful endpoints
- **Data Persistence**: Snowflake data warehouse for analytical workloads
- **Caching Layer**: Redis for high-performance data access
- **Document Storage**: AWS S3 for future document management
- **Containerization**: Docker and Docker Compose for consistent deployment

```
┌─────────────────────────────────────────────────┐
│              FastAPI Application                 │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │   Routers    │  │   Pydantic Models        │ │
│  │  (Endpoints) │  │  (Validation)            │ │
│  └──────────────┘  └──────────────────────────┘ │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │   Services   │  │   Config Management      │ │
│  │  (Business)  │  │  (Environment)           │ │
│  └──────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────┘
           │                │              │
           ▼                ▼              ▼
    ┌───────────┐    ┌─────────┐    ┌─────────┐
    │ Snowflake │    │  Redis  │    │   S3    │
    │ (Primary) │    │ (Cache) │    │  (Docs) │
    └───────────┘    └─────────┘    └─────────┘
```

## Prerequisites

### Required Software
- Python 3.11 or higher
- Docker 20.10 or higher
- Docker Compose 2.0 or higher
- Git

### Required Accounts
- Snowflake account with:
  - Active warehouse
  - Database and schema access
  - Appropriate role permissions
- AWS account with:
  - S3 bucket created
  - IAM user with S3 access
  - Access key and secret key
- Redis (provided via Docker Compose)

## Project Structure

```
dummy/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application entry point
│   ├── config.py                    # Configuration management (Pydantic Settings)
│   ├── errors.py                    # Global error handlers
│   ├── models/                      # Pydantic data models
│   │   ├── assessment.py            # Assessment models and validation
│   │   ├── company.py               # Company models and validation
│   │   ├── dimension.py             # Dimension score models and weights
│   │   ├── industry.py              # Industry models
│   │   ├── enums.py                 # Shared enumerations
│   │   ├── pagination.py            # Generic pagination model
│   │   └── assessment_state_machine.py  # Status transition logic
│   ├── routers/                     # API endpoint definitions
│   │   ├── assessments.py           # Assessment CRUD endpoints
│   │   ├── companies.py             # Company CRUD endpoints
│   │   ├── dimension_scores.py      # Dimension score endpoints
│   │   ├── industries.py            # Industry endpoints
│   │   └── health.py                # Health check endpoint
│   ├── services/                    # Business logic and integrations
│   │   ├── assessments_service.py   # Assessment business logic
│   │   ├── company_service.py       # Company business logic
│   │   ├── dimension_scores_service.py  # Dimension score operations
│   │   ├── industry_service.py      # Industry operations
│   │   ├── snowflake.py             # Snowflake connection management
│   │   ├── redis_cache.py           # Redis caching layer
│   │   └── s3_storage.py            # S3 storage operations
│   └── database/
│       └── schema.sql               # Snowflake DDL and seed data
├── docker/
│   ├── Dockerfile                   # Container image definition
│   └── docker-compose.yml           # Multi-container orchestration
├── tests/
│   ├── api/                         # API endpoint tests
│   ├── integration/                 # Snowflake integration tests
│   ├── unit/                        # Model validation tests
│   └── conftest.py                  # Pytest fixtures and configuration
├── .env.example                     # Environment variable template
├── .gitignore                       # Git ignore patterns
├── pyproject.toml                   # Poetry dependency management
├── requirements.txt                 # Pip requirements (alternative)
└── README.md                        # This file
```

## Installation and Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd BigDataIA-Sat-Spring26-Team-2/dummy
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Snowflake Configuration
SNOWFLAKE_ACCOUNT=your_account_identifier
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=PE_ORGAIR
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_ROLE=your_role  # Optional

# Redis Configuration (use these values for Docker)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_REGION=us-east-1
S3_BUCKET=your_s3_bucket_name

# Application Configuration
APP_ENV=local
APP_VERSION=1.0.0
```

### 3. Initialize Snowflake Database

Execute the SQL schema in your Snowflake account:

**Option A: Using Snowflake Web UI**
1. Log in to Snowflake
2. Navigate to Worksheets
3. Open and execute `app/database/schema.sql`

**Option B: Using SnowSQL CLI**
```bash
snowsql -a <account> -u <user> -f app/database/schema.sql
```

Verify tables were created:
```sql
USE DATABASE PE_ORGAIR;
USE SCHEMA PUBLIC;
SHOW TABLES;
```

### 4. Install Dependencies

**Option A: Using Poetry (Recommended)**
```bash
poetry install
```

**Option B: Using pip**
```bash
pip install -r requirements.txt
```

### 5. Run with Docker (Recommended)

```bash
cd docker

# Build containers
docker-compose build

# Start services
docker-compose up -d

# Verify containers are running
docker-compose ps

# View logs
docker-compose logs -f api
```

The API will be available at `http://localhost:8000`

### 6. Run Locally (Development)

If you prefer running outside Docker:

```bash
# Make sure Redis is running (via Docker)
cd docker
docker-compose up -d redis
cd ..

# Update .env for local development
# Set REDIS_HOST=localhost (instead of redis)

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

### Interactive Documentation

Once the application is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-31T22:00:00Z",
  "version": "1.0.0",
  "dependencies": {
    "redis": "healthy",
    "snowflake": "healthy",
    "s3": "healthy"
  }
}
```

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| **Health** |
| GET | `/api/v1/health` | System health check with dependency status |
| **Companies** |
| POST | `/api/v1/companies` | Create a new company |
| GET | `/api/v1/companies` | List companies (paginated, filterable by industry) |
| GET | `/api/v1/companies/{id}` | Get company by ID |
| PUT | `/api/v1/companies/{id}` | Update company information |
| DELETE | `/api/v1/companies/{id}` | Soft delete company |
| **Assessments** |
| POST | `/api/v1/assessments` | Create new AI readiness assessment |
| GET | `/api/v1/assessments` | List assessments (paginated, filterable) |
| GET | `/api/v1/assessments/{id}` | Get assessment with dimension scores |
| PATCH | `/api/v1/assessments/{id}/status` | Update assessment status (state machine) |
| **Dimension Scores** |
| POST | `/api/v1/assessments/{id}/scores` | Add dimension scores to assessment |
| GET | `/api/v1/assessments/{id}/scores` | Get all dimension scores (paginated) |
| PUT | `/api/v1/scores/{id}` | Update individual dimension score |
| GET | `/api/v1/dimension-weights` | Get dimension weight configuration |
| **Industries** |
| POST | `/api/v1/industries` | Create new industry |
| GET | `/api/v1/industries` | List industries (paginated, filterable) |
| GET | `/api/v1/industries/{id}` | Get industry by ID |
| GET | `/api/v1/sectors` | List available sectors |

### Example Usage

**Create a Company:**
```bash
curl -X POST http://localhost:8000/api/v1/companies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TechCorp Inc",
    "ticker": "TECH",
    "industry_id": "550e8400-e29b-41d4-a716-446655440003",
    "position_factor": 0.5
  }'
```

**Create an Assessment:**
```bash
curl -X POST http://localhost:8000/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "<company_uuid>",
    "assessment_type": "screening",
    "primary_assessor": "John Doe"
  }'
```

**List Companies with Pagination:**
```bash
curl "http://localhost:8000/api/v1/companies?page=1&page_size=20"
```

## Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test Suites

```bash
# API tests only
pytest tests/api/ -v

# Integration tests (requires Snowflake connection)
pytest tests/integration/ -v -m integration

# Unit tests only
pytest tests/unit/ -v

# Run with coverage report
pytest tests/ --cov=app --cov-report=html
```

### Test Categories

- **Unit Tests**: Model validation and business logic
- **API Tests**: Endpoint behavior with mocked services
- **Integration Tests**: End-to-end tests with real Snowflake connections

## Data Model

### Core Entities

**Industry**
- Reference data for company categorization
- Includes base AI-readiness score (h_r_base) by sector
- Sectors: Healthcare, Financial, Technology, Energy, Retail, Professional Services, Manufacturing

**Company**
- Portfolio companies or acquisition targets
- Links to industry for context
- Position factor (-1.0 to 1.0) represents market position adjustment
- Soft delete support for data retention

**Assessment**
- AI-readiness evaluation instances
- Types: screening, due_diligence, quarterly, exit_prep
- Status-based workflow with state machine validation
- Stores overall VR (Value-Readiness) score with confidence intervals

**Dimension Score**
- Individual dimension evaluations (7 dimensions)
- Weighted scoring system with configurable weights
- Evidence tracking for audit trail
- Confidence levels for uncertainty quantification

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

```
DRAFT ──────> IN_PROGRESS ──────> SUBMITTED ──────> APPROVED
                                       │                │
                                       │                │
                                       └────> SUPERSEDED <┘
```

Valid transitions are enforced at the API level to maintain workflow integrity.

## Design Decisions

### Architecture Choices

**Snowflake for Primary Persistence**
- Chosen for analytical query performance and scalability
- Supports complex aggregations needed for scoring algorithms
- Native support for semi-structured data (future JSON evidence storage)
- Separation of compute and storage for cost optimization

**Redis for Caching Layer**
- Implements read-through cache pattern for frequently accessed entities
- TTL-based invalidation strategy:
  - Companies: 5 minutes (moderate update frequency)
  - Industries: 1 hour (static reference data)
  - Assessments: 2 minutes (active during workflow)
  - Dimension weights: 24 hours (configuration data)
- Cache invalidation on mutations to maintain consistency

**FastAPI Framework**
- Auto-generated OpenAPI documentation
- Built-in request validation via Pydantic
- Async support for I/O-bound operations
- High performance with minimal overhead

**Pydantic for Data Validation**
- Type safety at API boundaries
- Automatic request/response validation
- Clear error messages for invalid data
- Model serialization for caching

### Data Modeling Decisions

**Soft Deletes for Companies**
- Maintains referential integrity with assessments
- Supports historical analysis and audit requirements
- Enables restoration if needed
- Filtered at query level via `is_deleted = FALSE`

**UUID Primary Keys**
- Distributed system compatibility
- No coordination required for ID generation
- Merge-friendly for multi-environment scenarios
- Standard format for external API integration

**Weighted Dimension Scoring**
- Default weights configurable via constants
- Override capability for custom assessment methodologies
- Supports future dynamic weighting based on industry or use case
- Transparent scoring logic for stakeholder review

**Assessment State Machine**
- Enforces workflow integrity
- Prevents invalid status transitions
- Supports compliance requirements (e.g., two-step approval)
- Extensible for future workflow enhancements

### Caching Strategy

**Cache Key Patterns**
- `company:{uuid}` - Individual company records
- `assessment:{uuid}` - Individual assessment records
- `industries:page:X:size:Y:sector:Z` - Paginated industry lists
- `dimension:weights` - Configuration data

**Invalidation Rules**
- Write-through: Update database first, then invalidate cache
- Pattern-based invalidation for list endpoints
- Automatic TTL expiration as fallback
- No stale data risk due to conservative TTLs

## Known Limitations

### Current Scope (Case Study 1)

1. **Authentication and Authorization**: Not implemented. Production deployment would require:
   - JWT-based authentication
   - Role-based access control (RBAC)
   - API key management for external integrations

2. **VR Score Calculation**: The overall Value-Readiness score formula is not yet implemented. Dimension scores are stored, but the weighted calculation with non-compensatory penalties and talent risk adjustment will be added in Case Study 3.

3. **S3 Integration**: Basic health check and client initialization only. Full document upload/download capabilities will be implemented in Case Study 2 for SEC filing ingestion.

4. **Rate Limiting**: No request throttling implemented. Production deployment should add rate limiting to prevent abuse.

5. **Audit Logging**: Changes to assessments and scores are not tracked. A full audit log would be valuable for compliance.

6. **Input Sanitization**: Basic validation only. Additional sanitization for XSS prevention should be added before public deployment.

### Database Constraints

- **Company ticker symbols**: Uppercase enforcement at application level (not database constraint)
- **Concurrent updates**: Last-write-wins semantics. Consider optimistic locking for production.
- **Dimension score uniqueness**: One score per dimension per assessment enforced via unique constraint

### Performance Considerations

- **Pagination limits**: Maximum page_size capped at 100 records to prevent memory issues
- **Cache memory**: Redis operates in-memory; monitor usage with large datasets
- **Snowflake warehouse**: Manual suspend/resume required for cost control

## Configuration

### Environment Variables

All configuration is managed through environment variables loaded from `.env`:

**Snowflake** (Required)
- `SNOWFLAKE_ACCOUNT`: Account identifier (e.g., `abc12345.us-east-1`)
- `SNOWFLAKE_USER`: Username
- `SNOWFLAKE_PASSWORD`: Password
- `SNOWFLAKE_DATABASE`: Database name (default: `PE_ORGAIR`)
- `SNOWFLAKE_SCHEMA`: Schema name (default: `PUBLIC`)
- `SNOWFLAKE_WAREHOUSE`: Warehouse name (e.g., `COMPUTE_WH`)
- `SNOWFLAKE_ROLE`: Role name (optional)

**Redis** (Required for Docker)
- `REDIS_HOST`: Hostname (use `redis` for Docker, `localhost` for local)
- `REDIS_PORT`: Port (default: `6379`)
- `REDIS_DB`: Database number (default: `0`)

**AWS S3** (Required)
- `AWS_ACCESS_KEY_ID`: IAM access key
- `AWS_SECRET_ACCESS_KEY`: IAM secret key
- `AWS_REGION`: AWS region (default: `us-east-1`)
- `S3_BUCKET`: S3 bucket name

**Application**
- `APP_ENV`: Environment name (local/dev/prod)
- `APP_VERSION`: Application version string

## Troubleshooting

### Container Issues

**Container fails to start**
```bash
# Check logs for errors
docker-compose logs api

# Common causes:
# - Missing required environment variables
# - Invalid Snowflake credentials
# - Poetry lock file mismatch
```

**Port already in use**
```bash
# Find process using port 8000
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Stop conflicting process or change port in docker-compose.yml
```

### Database Connection Issues

**Snowflake connection fails**
- Verify warehouse is running (not suspended)
- Confirm user has USAGE privilege on warehouse
- Check role permissions for database/schema access
- Verify network connectivity (firewall, VPN)

**Example: Resume suspended warehouse**
```sql
ALTER WAREHOUSE COMPUTE_WH RESUME;
```

### Redis Connection Issues

**Redis unhealthy in health check**
```bash
# Verify Redis container is running
docker ps | grep redis

# Test Redis directly
docker exec -it pe_orgair_redis redis-cli ping
# Should return: PONG

# Check Redis logs
docker-compose logs redis
```

### S3 Connection Issues

**S3 unhealthy or not_configured**
- Verify bucket exists in AWS Console
- Confirm IAM user has s3:HeadBucket, s3:GetObject, s3:PutObject permissions
- Check access key is active (not rotated/deleted)
- Verify bucket is in the specified AWS region

**Test S3 access directly**
```bash
# Using AWS CLI
aws s3 ls s3://your-bucket-name

# If this fails, check IAM permissions
```

### Common Error Messages

**"Industry not found"**
- Run the seed data from `schema.sql`
- Verify industry_id exists before creating company

**"Invalid status transition"**
- Check assessment_state_machine.py for allowed transitions
- Current status must have a valid path to target status

**"assessment_id in body must match path parameter"**
- When adding dimension scores, ensure assessment_id in JSON matches URL parameter

## Development Workflow

### Adding a New Endpoint

1. Define Pydantic models in `app/models/`
2. Implement business logic in `app/services/`
3. Create router in `app/routers/`
4. Register router in `app/main.py`
5. Add tests in `tests/api/`

### Making Database Changes

1. Update `app/database/schema.sql` with new DDL
2. Run migration in Snowflake
3. Update Pydantic models to match
4. Update service layer queries
5. Clear relevant Redis caches

### Testing Strategy

- **Unit tests**: Fast, isolated, test business logic
- **API tests**: Test endpoints with mocked services
- **Integration tests**: End-to-end with real Snowflake (marked with `@pytest.mark.integration`)

Run integration tests only when needed to avoid Snowflake costs:
```bash
pytest tests/integration/ -v -m integration
```

## Deployment Considerations

### Production Readiness Checklist

- [ ] Replace default SECRET_KEY with secure random value
- [ ] Enable HTTPS (TLS/SSL certificates)
- [ ] Implement authentication and authorization
- [ ] Add rate limiting middleware
- [ ] Configure CORS for frontend integration
- [ ] Set up centralized logging (e.g., CloudWatch, Datadog)
- [ ] Implement health check monitoring and alerting
- [ ] Use managed Redis (AWS ElastiCache, etc.)
- [ ] Rotate Snowflake and AWS credentials regularly
- [ ] Enable Snowflake query result caching
- [ ] Configure auto-suspend for Snowflake warehouse
- [ ] Set up CI/CD pipeline for automated testing

### Scaling Considerations

- **Horizontal scaling**: FastAPI is stateless and can run multiple instances behind a load balancer
- **Database pooling**: Consider implementing connection pooling for Snowflake
- **Cache sharding**: Redis can be sharded if cache size grows significantly
- **Async operations**: Health checks already use async; extend to other I/O operations if needed

## Team

- Prachi Pradhan (pradhanprac@northeastern.edu)
- Samiksh Gupta (gupta.samik@northeastern.edu)
- Siddharth Shukla (shukla.sid@northeastern.edu)  


## Course Information

**Course**: Big Data and Intelligent Analytics  
**Institution**: Northeastern University  
**Term**: Spring 2026  
**Instructor**: Sri Krishnamurthy

## License

This project is developed for educational purposes as part of the Big Data and Intelligent Analytics course.

## Acknowledgments

Case Study 1 provides the foundation for a multi-phase platform development project. Future case studies will extend this foundation with:


---

**Version**: 1.0.0  
**Last Updated**: February 2026