from fastapi import FastAPI

from app.api.market import router
from app.api.contracts import router as contracts_router

app = FastAPI(title="Uranium Market Dashboard", version="0.1.0")
app.include_router(router)
app.include_router(contracts_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Report API liveness; database readiness is added with persistence."""
    return {"status": "ok"}
