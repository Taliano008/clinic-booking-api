from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.errors import register_error_handlers
from app.routers import appointments, doctors, patients

app = FastAPI(
    title="Clinic Booking API",
    version="0.2.0",
    description=(
        "Appointment booking for a small multi-doctor clinic.\n\n"
        'All errors share one shape: `{"detail": "...", "code": "MACHINE_CODE"}`. '
        "Times are accepted with any UTC offset and returned in clinic-local time."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(doctors.router)
app.include_router(appointments.router)
app.include_router(patients.router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
