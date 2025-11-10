from fastapi import APIRouter

health_router = APIRouter(prefix="/api")

@health_router.get("/health")
def health_check() -> str:
    return "ok"

@health_router.get("/ping")
def ping() -> str:
    return "ok"
