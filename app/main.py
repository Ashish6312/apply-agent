"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.logging_config import configure_logging

configure_logging()

app = FastAPI(
    title="ApplyAgent",
    description="AI agent that analyzes a job opportunity against a candidate's resume.",
    version="1.0.0",
)

# Streamlit runs on a different port; CORS is wide open here because this is
# a local prototype, not a deployed multi-tenant service.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
