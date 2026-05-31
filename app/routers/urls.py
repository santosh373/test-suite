import json
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.url_store import URLS_FILE

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/urls/file", response_class=HTMLResponse)
async def view_urls_file(request: Request, saved: str = ""):
    try:
        with open(URLS_FILE) as f:
            content = f.read()
    except FileNotFoundError:
        content = '[\n  {"name": "local", "base_url": "http://localhost:8080"}\n]\n'
    return templates.TemplateResponse(request, "pages/urls_file.html", {
        "page": "",
        "content": content,
        "saved": saved == "1",
    })


@router.post("/urls/file")
async def save_urls_file(request: Request, content: str = Form(...)):
    # validate JSON before saving
    json.loads(content)
    with open(URLS_FILE, "w") as f:
        f.write(content)
    return RedirectResponse("/urls/file?saved=1", status_code=303)
