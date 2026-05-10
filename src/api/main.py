from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .data_loader import load_all_data
from .routers.actions import router as actions_router
from .routers.alerts import router as alerts_router
from .routers.clients import router as clients_router
from .routers.map import router as map_router
from .routers.overview import router as overview_router


app = FastAPI(
    title="Smart Demand Signals API",
    description="Inibsa Commercial Intelligence Backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "PATCH"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.on_event("startup")
async def startup() -> None:
    load_all_data()


app.include_router(overview_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(actions_router, prefix="/api")
app.include_router(map_router, prefix="/api")
app.include_router(clients_router, prefix="/api")

