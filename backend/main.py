"""
RehabTwin FastAPI Application Entry Point.
"""
from typing import Dict
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.routes import sessions, patients, analysis

app = FastAPI(
    title="RehabTwin API",
    description="Production-quality integration & API layer for RehabTwin Rehabilitation Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration for local React frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Can be restricted via env vars in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(sessions.router)
app.include_router(patients.router)
app.include_router(analysis.router)


# Global Exception Handlers
@app.exception_handler(KeyError)
async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
    key_str = str(exc).strip("'")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": f"Resource not found: {key_str}"}
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)}
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log internally in production, return clean 500 to client without stack trace leakage
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected internal server error occurred."}
    )


@app.get("/", tags=["Health"])
def root() -> Dict[str, str]:
    """Root endpoint for API service discovery."""
    return {
        "service": "RehabTwin API",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
def health_check() -> Dict[str, str]:
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy"
    }