from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.services.database import get_conn
from app.services.chain import load_chain

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    conn = get_conn()
    total_tests = conn.execute("SELECT COUNT(*) FROM test_cases").fetchone()[0]
    total_runs = conn.execute("SELECT COUNT(*) FROM test_runs").fetchone()[0]
    passed = conn.execute("SELECT COUNT(*) FROM run_results WHERE status='passed'").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM run_results WHERE status='failed'").fetchone()[0]

    recent_runs = conn.execute("""
        SELECT r.id, r.run_name, r.status, r.test_type, r.started_at, r.finished_at,
               COUNT(rr.id) as total_results,
               SUM(CASE WHEN rr.status='passed' THEN 1 ELSE 0 END) as passed_count,
               SUM(CASE WHEN rr.status='failed' THEN 1 ELSE 0 END) as failed_count
        FROM test_runs r
        LEFT JOIN run_results rr ON rr.run_id = r.id
        GROUP BY r.id
        ORDER BY r.created_at DESC LIMIT 8
    """).fetchall()

    pass_rate = round((passed / (passed + failed) * 100) if (passed + failed) > 0 else 0)
    conn.close()

    chain = load_chain()

    return templates.TemplateResponse(request, "pages/dashboard.html", {
        "page": "dashboard",
        "total_tests": total_tests,
        "total_runs": total_runs,
        "pass_rate": pass_rate,
        "passed": passed,
        "failed": failed,
        "recent_runs": recent_runs,
        "mapping_count": len(chain),
        "chain": chain,
    })
