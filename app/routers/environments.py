from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.database import get_conn

router = APIRouter(prefix="/environments")
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def list_environments(request: Request):
    conn = get_conn()
    envs = conn.execute("SELECT * FROM environments ORDER BY created_at DESC").fetchall()
    conn.close()
    return templates.TemplateResponse(request, "pages/environments.html", {
        "page": "environments", "envs": envs,
    })


@router.post("/new")
async def create_env(
    name: str = Form(...),
    base_url: str = Form(...),
    env_type: str = Form("dev"),
    headers: str = Form("{}"),
):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO environments (name, base_url, env_type, headers) VALUES (?,?,?,?)",
            (name, base_url, env_type, headers)
        )
        conn.commit()
    except Exception:
        pass
    conn.close()
    return RedirectResponse("/environments/", status_code=303)


@router.post("/{env_id}/edit")
async def update_env(
    env_id: int,
    name: str = Form(...),
    base_url: str = Form(...),
    env_type: str = Form("dev"),
    headers: str = Form("{}"),
):
    conn = get_conn()
    conn.execute(
        "UPDATE environments SET name=?, base_url=?, env_type=?, headers=? WHERE id=?",
        (name, base_url, env_type, headers, env_id)
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/environments/", status_code=303)


@router.post("/{env_id}/delete")
async def delete_env(env_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM environments WHERE id=?", (env_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/environments/", status_code=303)
