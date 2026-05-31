import asyncio
import json
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.database import get_conn
from app.services.runner import execute_run
from app.services.url_store import get_active_env, get_base_url
from app.services.chain import load_chain, load_mapping_name, list_mappings, load_chain_from_file, load_mapping_name_from_file

router = APIRouter(prefix="/runs")
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def list_runs(request: Request):
    conn = get_conn()
    runs = conn.execute("""
        SELECT r.*,
               COUNT(rr.id) as total,
               SUM(CASE WHEN rr.status='passed' THEN 1 ELSE 0 END) as passed,
               SUM(CASE WHEN rr.status='failed' THEN 1 ELSE 0 END) as failed
        FROM test_runs r
        LEFT JOIN run_results rr ON rr.run_id = r.id
        GROUP BY r.id
        ORDER BY r.created_at DESC
    """).fetchall()
    conn.close()
    return templates.TemplateResponse(request, "pages/runs.html", {
        "page": "runs", "runs": runs,
    })


@router.get("/new", response_class=HTMLResponse)
async def new_run_form(request: Request, type: str = "functional"):
    conn = get_conn()
    tests = conn.execute("SELECT id, name, method, path FROM test_cases ORDER BY name").fetchall()
    test_count = len(tests)
    conn.close()
    run_type = type if type in ("functional", "performance") else "functional"
    page = "run-functional" if run_type == "functional" else "run-performance"
    mappings = list_mappings() if run_type == "functional" else []
    default_file = mappings[0]["filename"] if mappings else ""
    chain = load_chain_from_file(default_file) if default_file else []
    mapping_name = load_mapping_name_from_file(default_file) if default_file else ""
    all_chains = {
        m["filename"]: load_chain_from_file(m["filename"]) for m in mappings
    }
    return templates.TemplateResponse(request, "pages/run_form.html", {
        "page": page,
        "tests": tests, "test_count": test_count,
        "run_type": run_type,
        "env_name": get_active_env(),
        "mappings": mappings,
        "default_mapping_file": default_file,
        "chain": chain,
        "mapping_name": mapping_name,
        "all_chains_json": json.dumps(all_chains),
    })


@router.post("/new")
async def create_run(
    request: Request,
    run_name: str = Form(...),
    test_type: str = Form("functional"),
    mapping_file: str = Form(""),
    test_case_id: str = Form(""),
    count: int = Form(10),
):
    conn = get_conn()

    if test_type == "functional":
        rows = conn.execute("SELECT id FROM test_cases ORDER BY id").fetchall()
        ids = [r["id"] for r in rows]
        vus_override = None
    else:
        if not test_case_id.strip().isdigit():
            conn.close()
            return RedirectResponse("/runs/new?type=performance", status_code=303)
        ids = [int(test_case_id)]
        vus_override = max(1, count)

    if not ids:
        conn.close()
        return RedirectResponse("/runs/new", status_code=303)

    env_name = get_active_env()
    m_name = load_mapping_name_from_file(mapping_file) if (test_type == "functional" and mapping_file) else ""
    cur = conn.execute(
        "INSERT INTO test_runs (run_name, env_name, mapping_name, mapping_file, test_type, status) VALUES (?,?,?,?,?,?)",
        (run_name, env_name, m_name, mapping_file, test_type, "pending")
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()

    asyncio.create_task(execute_run(run_id, ids, test_type, vus_override, env_name, mapping_file))

    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@router.get("/{run_id:int}", response_class=HTMLResponse)
async def view_run(request: Request, run_id: int):
    conn = get_conn()
    run = conn.execute("SELECT * FROM test_runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        raise HTTPException(404)

    results = conn.execute("""
        SELECT rr.*, tc.name as test_name, tc.method, tc.path, tc.test_type
        FROM run_results rr
        JOIN test_cases tc ON tc.id = rr.test_case_id
        WHERE rr.run_id=?
        ORDER BY rr.id
    """, (run_id,)).fetchall()
    conn.close()

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "passed")
    failed = total - passed
    pass_rate = round((passed / total * 100) if total > 0 else 0)
    avg_duration = round(
        sum(r["duration_ms"] for r in results if r["duration_ms"]) / total
        if total > 0 else 0, 2
    )

    env_name = run["env_name"] or ""

    return templates.TemplateResponse(request, "pages/run_detail.html", {
        "page": "runs",
        "run": run, "results": results,
        "total": total, "passed": passed, "failed": failed,
        "pass_rate": pass_rate, "avg_duration": avg_duration,
        "env_name": env_name,
        "mapping_name": run["mapping_name"] or "",
    })


@router.post("/{run_id:int}/delete")
async def delete_run(run_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM run_results WHERE run_id=?", (run_id,))
    conn.execute("DELETE FROM test_runs WHERE id=?", (run_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/runs/", status_code=303)
