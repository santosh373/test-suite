import re
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.chain import (
    list_mappings, read_file_content, write_file_content,
    delete_file, load_chain_from_file, MAPPINGS_DIR,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

_SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_\-]+\.py$')

NEW_TEMPLATE = '''\
MAPPING_NAME = "{name}"

FUNCTIONAL_CHAIN = [
    {{
        "test": "Test Case Name",
        # "extract": {{"var": "response.field"}},
        # "inject":  {{"path": "/api/{{var}}"}},
    }},
]
'''


@router.get("/mapping", response_class=HTMLResponse)
async def list_mapping_files(request: Request, saved: str = ""):
    mappings = list_mappings()
    return templates.TemplateResponse(request, "pages/mapping_list.html", {
        "page": "",
        "mappings": mappings,
        "saved": saved == "1",
    })


@router.get("/mapping/new", response_class=HTMLResponse)
async def new_mapping_form(request: Request):
    return templates.TemplateResponse(request, "pages/mapping_editor.html", {
        "page": "",
        "filename": "",
        "content": NEW_TEMPLATE.format(name="My Flow"),
        "is_new": True,
        "saved": False,
    })


@router.post("/mapping/new")
async def create_mapping(
    request: Request,
    filename: str = Form(...),
    content: str = Form(...),
):
    fname = filename.strip()
    if not fname.endswith(".py"):
        fname += ".py"
    if not _SAFE_FILENAME.match(fname):
        raise HTTPException(400, "Invalid filename")
    write_file_content(fname, content)
    return RedirectResponse(f"/mapping/edit/{fname}?saved=1", status_code=303)


@router.get("/mapping/edit/{filename:path}", response_class=HTMLResponse)
async def edit_mapping_form(request: Request, filename: str, saved: str = ""):
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(400, "Invalid filename")
    content = read_file_content(filename)
    if not content:
        raise HTTPException(404)
    chain = load_chain_from_file(filename)
    return templates.TemplateResponse(request, "pages/mapping_editor.html", {
        "page": "",
        "filename": filename,
        "content": content,
        "chain": chain,
        "is_new": False,
        "saved": saved == "1",
    })


@router.post("/mapping/edit/{filename:path}")
async def save_mapping(
    request: Request,
    filename: str,
    content: str = Form(...),
):
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(400, "Invalid filename")
    write_file_content(filename, content)
    return RedirectResponse(f"/mapping/edit/{filename}?saved=1", status_code=303)


@router.post("/mapping/delete/{filename:path}")
async def delete_mapping(filename: str):
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(400, "Invalid filename")
    delete_file(filename)
    return RedirectResponse("/mapping", status_code=303)
