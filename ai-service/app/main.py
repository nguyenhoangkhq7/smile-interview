from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import cv_jd, interview, questions

app = FastAPI(
    title=settings.APP_NAME,
    description="Python FastAPI Service for Semantic CV-JD Matching, GNN Skill-gap Detection, and AI Interview Evaluation",
    version="1.0.0",
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(cv_jd.router)
app.include_router(interview.router)
app.include_router(questions.router)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    return {
        "message": "Welcome to Smile Interview AI Service. See /docs for Swagger UI documentation."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
