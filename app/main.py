from fastapi import FastAPI
from app.routers import assessments, companies, dimension_scores, industries, health

app = FastAPI(
    title="PE Org-AI-R Platform Team-2",
    description="AI Rediness Platform"
)

app.include_router(health.router,prefix="/api/v1")

app.include_router(dimension_scores.router, prefix="/api/v1")

app.include_router(assessments.router, prefix="/api/v1")
app.include_router(companies.router, prefix="/api/v1")
app.include_router(industries.router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "PE Org-AI-R Platform is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
