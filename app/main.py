from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.routers import tests, runs, dashboard, auth, urls, apidocs, mapping_router
from app.services.database import init_db, sync_test_cases_from_file

_PUBLIC_PATHS = {"/login", "/logout"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    sync_test_cases_from_file()
    yield


app = FastAPI(title="API Test Suite", lifespan=lifespan)

# Auth guard must be declared BEFORE SessionMiddleware is added so that
# in the final stack SessionMiddleware (outer) runs first and populates
# request.session before the guard (inner) reads it.
@app.middleware("http")
async def require_auth(request: Request, call_next):
    if request.url.path in _PUBLIC_PATHS or request.url.path.startswith("/static"):
        return await call_next(request)
    if not request.session.get("user"):
        return RedirectResponse("/login", status_code=302)
    return await call_next(request)


app.add_middleware(SessionMiddleware, secret_key="testsuite-secret-key-change-in-prod")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(tests.router)
app.include_router(runs.router)
app.include_router(urls.router)
app.include_router(apidocs.router)
app.include_router(mapping_router.router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
