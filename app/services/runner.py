import httpx
import asyncio
import json
import time
import statistics
from datetime import datetime
from app.services.database import get_conn
from app.services.url_store import get_base_url
from app.services.chain import load_chain, load_chain_from_file, extract_value, build_test_with_context


async def run_functional_test(test: dict, env: dict) -> dict:
    base_url = env["base_url"]
    url = base_url + test["path"]
    method = test["method"].upper()
    headers = {}
    try:
        headers.update(json.loads(env.get("headers") or "{}"))
        headers.update(json.loads(test.get("headers") or "{}"))
    except Exception:
        pass

    body = test.get("body", "")
    body_data = None
    if body:
        try:
            body_data = json.loads(body)
        except Exception:
            body_data = body

    start = time.time()
    error = None
    status_code = None
    response_body = ""
    assertions_passed = 0
    assertions_failed = 0

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            if body_data and isinstance(body_data, dict):
                resp = await getattr(client, method.lower())(url, headers=headers, json=body_data)
            elif body_data:
                resp = await getattr(client, method.lower())(url, headers=headers, content=str(body_data))
            else:
                resp = await getattr(client, method.lower())(url, headers=headers)

            status_code = resp.status_code
            try:
                response_body = resp.text[:4000]
            except Exception:
                response_body = ""

    except Exception as e:
        error = str(e)

    duration_ms = (time.time() - start) * 1000

    expected_status = test.get("expected_status", 200)
    if status_code == expected_status:
        assertions_passed += 1
    else:
        assertions_failed += 1

    expected_body = test.get("expected_body", "")
    if expected_body:
        if expected_body in response_body:
            assertions_passed += 1
        else:
            assertions_failed += 1

    try:
        custom = json.loads(test.get("assertions") or "[]")
        for assertion in custom:
            atype = assertion.get("type")
            value = assertion.get("value", "")
            if atype == "response_contains" and value in response_body:
                assertions_passed += 1
            elif atype == "response_contains":
                assertions_failed += 1
            elif atype == "status_code" and str(status_code) == str(value):
                assertions_passed += 1
            elif atype == "status_code":
                assertions_failed += 1
            elif atype == "duration_lt":
                if duration_ms < float(value):
                    assertions_passed += 1
                else:
                    assertions_failed += 1
    except Exception:
        pass

    status = "passed" if assertions_failed == 0 and error is None else "failed"

    return {
        "status": status,
        "duration_ms": round(duration_ms, 2),
        "status_code": status_code,
        "response_body": response_body,
        "error": error,
        "assertions_passed": assertions_passed,
        "assertions_failed": assertions_failed,
    }


async def run_performance_test(test: dict, env: dict) -> dict:
    base_url = env["base_url"]
    url = base_url + test["path"]
    method = test["method"].upper()
    headers = {}
    try:
        headers.update(json.loads(env.get("headers") or "{}"))
        headers.update(json.loads(test.get("headers") or "{}"))
    except Exception:
        pass

    body = test.get("body", "")
    body_data = None
    if body:
        try:
            body_data = json.loads(body)
        except Exception:
            body_data = body

    vus = int(test.get("_vus_override") or test.get("vus", 10))
    duration_s = int(test.get("duration", 30))
    ramp_up = int(test.get("ramp_up", 5))

    durations = []
    errors = []
    status_codes = []
    stop_event = asyncio.Event()

    async def single_request(client):
        t0 = time.time()
        try:
            if body_data and isinstance(body_data, dict):
                r = await getattr(client, method.lower())(url, headers=headers, json=body_data)
            elif body_data:
                r = await getattr(client, method.lower())(url, headers=headers, content=str(body_data))
            else:
                r = await getattr(client, method.lower())(url, headers=headers)
            status_codes.append(r.status_code)
        except Exception as e:
            errors.append(str(e))
        durations.append((time.time() - t0) * 1000)

    async def vu_loop(vu_id):
        delay = (vu_id / max(vus, 1)) * ramp_up
        await asyncio.sleep(delay)
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            while not stop_event.is_set():
                await single_request(client)
                await asyncio.sleep(0.05)

    tasks = [asyncio.create_task(vu_loop(i)) for i in range(vus)]

    await asyncio.sleep(duration_s)
    stop_event.set()

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    total_requests = len(durations)
    error_count = len(errors)
    elapsed = duration_s

    p50 = round(statistics.median(durations), 2) if durations else 0
    p95 = round(sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 1 else 0, 2)
    p99 = round(sorted(durations)[int(len(durations) * 0.99)] if len(durations) > 1 else 0, 2)
    rps = round(total_requests / elapsed, 2) if elapsed > 0 else 0
    error_rate = round((error_count / total_requests * 100) if total_requests > 0 else 0, 2)

    status = "passed" if error_rate < 5 else "failed"

    return {
        "status": status,
        "duration_ms": round(statistics.mean(durations), 2) if durations else 0,
        "status_code": status_codes[-1] if status_codes else None,
        "response_body": f"Total requests: {total_requests}, Errors: {error_count}",
        "error": "; ".join(set(errors[:3])) if errors else None,
        "assertions_passed": 1 if error_rate < 5 else 0,
        "assertions_failed": 0 if error_rate < 5 else 1,
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
        "rps": rps,
        "error_rate": error_rate,
    }


def _save_result(conn, run_id: int, test_id: int, result: dict):
    conn.execute("""
        INSERT INTO run_results
        (run_id, test_case_id, status, duration_ms, status_code, response_body,
         error, assertions_passed, assertions_failed, p50_ms, p95_ms, p99_ms, rps, error_rate)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        run_id, test_id,
        result["status"], result["duration_ms"], result["status_code"],
        result["response_body"], result["error"],
        result["assertions_passed"], result["assertions_failed"],
        result.get("p50_ms"), result.get("p95_ms"), result.get("p99_ms"),
        result.get("rps"), result.get("error_rate"),
    ))


async def execute_run(run_id: int, test_ids: list, test_type: str, vus_override: int = None, env_name: str = "", mapping_file: str = ""):
    conn = get_conn()
    try:
        conn.execute("UPDATE test_runs SET status='running', started_at=? WHERE id=?",
                     (datetime.utcnow().isoformat(), run_id))
        conn.commit()

        if test_type == "performance":
            for test_id in test_ids:
                test_row = conn.execute("SELECT * FROM test_cases WHERE id=?", (test_id,)).fetchone()
                if not test_row:
                    continue
                test = dict(test_row)
                if vus_override is not None:
                    test["_vus_override"] = vus_override
                env = {"base_url": get_base_url(env_name, test.get("url_type", "")), "headers": "{}"}
                result = await run_performance_test(test, env)
                _save_result(conn, run_id, test_id, result)
                conn.commit()
        else:
            # Functional: use mapping chain if defined, otherwise run test_ids in order
            chain = load_chain_from_file(mapping_file) if mapping_file else load_chain()
            if chain:
                # Build name → test lookup from DB
                all_tests = {
                    row["name"]: dict(row)
                    for row in conn.execute("SELECT * FROM test_cases").fetchall()
                }
                context: dict = {}  # shared extracted values
                for step in chain:
                    test_name = step.get("test", "")
                    test = all_tests.get(test_name)
                    if not test:
                        continue
                    test = build_test_with_context(test, step, context)
                    env = {"base_url": get_base_url(env_name, test.get("url_type", "")), "headers": "{}"}
                    result = await run_functional_test(test, env)
                    # Extract values from response into shared context
                    for var_name, path in (step.get("extract") or {}).items():
                        val = extract_value(result.get("response_body", ""), path)
                        if val:
                            context[var_name] = val
                    _save_result(conn, run_id, test["id"], result)
                    conn.commit()
            else:
                for test_id in test_ids:
                    test_row = conn.execute("SELECT * FROM test_cases WHERE id=?", (test_id,)).fetchone()
                    if not test_row:
                        continue
                    test = dict(test_row)
                    env = {"base_url": get_base_url(env_name, test.get("url_type", "")), "headers": "{}"}
                    result = await run_functional_test(test, env)
                    _save_result(conn, run_id, test_id, result)
                    conn.commit()

        conn.execute("UPDATE test_runs SET status='completed', finished_at=? WHERE id=?",
                     (datetime.utcnow().isoformat(), run_id))
        conn.commit()
    except Exception:
        conn.execute("UPDATE test_runs SET status='failed', finished_at=? WHERE id=?",
                     (datetime.utcnow().isoformat(), run_id))
        conn.commit()
    finally:
        conn.close()
