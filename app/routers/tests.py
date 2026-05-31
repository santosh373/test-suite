from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.database import get_conn, sync_test_cases_from_file
from app.services.url_store import get_services
import os

router = APIRouter(prefix="/tests")
templates = Jinja2Templates(directory="templates")

TESTCASES_FILE = os.path.join(os.getcwd(), "testcases.py")


@router.get("/", response_class=HTMLResponse)
async def list_tests(request: Request):
    conn = get_conn()
    tests = conn.execute("SELECT * FROM test_cases ORDER BY created_at DESC").fetchall()
    conn.close()
    return templates.TemplateResponse(request, "pages/tests.html", {
        "page": "tests-new", "tests": tests,
    })


@router.get("/new", response_class=HTMLResponse)
async def new_test_form(request: Request):
    return templates.TemplateResponse(request, "pages/test_form.html", {
        "page": "tests-new", "test": None, "services": get_services(),
    })


@router.get("/{test_id:int}/edit", response_class=HTMLResponse)
async def edit_test_form(request: Request, test_id: int):
    conn = get_conn()
    test = conn.execute("SELECT * FROM test_cases WHERE id=?", (test_id,)).fetchone()
    conn.close()
    if not test:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "pages/test_form.html", {
        "page": "tests-new", "test": test, "services": get_services(),
    })


@router.post("/save")
async def save_test(
    request: Request,
    test_id: str = Form(""),
    name: str = Form(...),
    description: str = Form(""),
    test_type: str = Form("functional"),
    method: str = Form("GET"),
    path: str = Form(...),
    headers: str = Form("{}"),
    body: str = Form(""),
    expected_status: int = Form(200),
    expected_body: str = Form(""),
    assertions: str = Form("[]"),
    vus: int = Form(10),
    duration: int = Form(30),
    ramp_up: int = Form(5),
    tags: str = Form("[]"),
    url_type: str = Form(""),
):
    fields = (description, test_type, method, path, headers, body,
              expected_status, expected_body, assertions, vus, duration, ramp_up, tags, url_type)

    conn = get_conn()

    # If test_id is provided, update that record directly.
    if test_id.strip().isdigit():
        conn.execute("""
            UPDATE test_cases
            SET name=?, description=?, test_type=?, method=?, path=?,
                headers=?, body=?, expected_status=?, expected_body=?, assertions=?,
                vus=?, duration=?, ramp_up=?, tags=?, url_type=?, updated_at=datetime('now')
            WHERE id=?
        """, (name, *fields, int(test_id)))
        conn.commit()
        conn.close()
        return RedirectResponse("/tests/", status_code=303)

    # No test_id: upsert by name.
    existing = conn.execute("SELECT id FROM test_cases WHERE name=?", (name,)).fetchone()
    if existing:
        conn.execute("""
            UPDATE test_cases
            SET description=?, test_type=?, method=?, path=?,
                headers=?, body=?, expected_status=?, expected_body=?, assertions=?,
                vus=?, duration=?, ramp_up=?, tags=?, url_type=?, updated_at=datetime('now')
            WHERE name=?
        """, (*fields, name))
    else:
        conn.execute("""
            INSERT INTO test_cases
            (name, description, test_type, method, path, headers, body,
             expected_status, expected_body, assertions, vus, duration, ramp_up, tags, url_type)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (name, *fields))

    conn.commit()
    conn.close()
    return RedirectResponse("/tests/", status_code=303)


@router.get("/file", response_class=HTMLResponse)
async def view_testcases_file(request: Request, saved: str = ""):
    try:
        with open(TESTCASES_FILE, "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    return templates.TemplateResponse(request, "pages/testcases_file.html", {
        "page": "testcases-file",
        "content": content,
        "saved": saved == "1",
    })


@router.post("/file")
async def save_testcases_file(request: Request, content: str = Form(...)):
    with open(TESTCASES_FILE, "w") as f:
        f.write(content)
    sync_test_cases_from_file()
    return RedirectResponse("/tests/file?saved=1", status_code=303)


@router.post("/{test_id:int}/delete")
async def delete_test(test_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM test_cases WHERE id=?", (test_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/tests/", status_code=303)


@router.get("/{test_id:int}", response_class=HTMLResponse)
async def view_test(request: Request, test_id: int):
    conn = get_conn()
    test = conn.execute("SELECT * FROM test_cases WHERE id=?", (test_id,)).fetchone()
    results = conn.execute("""
        SELECT rr.*, r.run_name, r.started_at as run_started
        FROM run_results rr
        JOIN test_runs r ON r.id = rr.run_id
        WHERE rr.test_case_id=?
        ORDER BY rr.created_at DESC LIMIT 20
    """, (test_id,)).fetchall()
    conn.close()
    if not test:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "pages/test_detail.html", {
        "page": "tests-new", "test": test, "results": results,
    })
