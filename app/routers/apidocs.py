from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.services.database import get_conn
from app.services.url_store import get_active_env, get_base_url
import json

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/api/docs", response_class=HTMLResponse)
async def api_docs(request: Request):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM test_cases ORDER BY url_type, method, path"
    ).fetchall()
    conn.close()

    env_name = get_active_env()

    # Group by url_type
    groups: dict = {}
    for row in rows:
        tc = dict(row)
        tc["base_url"] = get_base_url(env_name, tc.get("url_type") or "")
        tc["full_url"] = (tc["base_url"] or "") + tc["path"]

        # pretty-print JSON fields
        for field in ("headers", "body", "assertions"):
            val = tc.get(field, "")
            try:
                parsed = json.loads(val) if val else None
                tc[field + "_pretty"] = json.dumps(parsed, indent=2) if parsed else ""
            except Exception:
                tc[field + "_pretty"] = val or ""

        # parse tags into a plain list
        try:
            tc["tags_list"] = json.loads(tc.get("tags") or "[]")
        except Exception:
            tc["tags_list"] = []

        group = tc.get("url_type") or "general"
        groups.setdefault(group, []).append(tc)

    return templates.TemplateResponse(request, "pages/api_docs.html", {
        "page": "",
        "groups": groups,
        "env_name": env_name,
        "total": len(rows),
    })
