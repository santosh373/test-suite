# API Test Suite

A self-hosted web UI for running, chaining, and monitoring REST API tests — functional and performance — built with FastAPI, SQLite, and Jinja2.

---

## Features

- **Test Case Management** — define tests in `testcases.py` (auto-synced on startup) or create/update through the UI
- **Functional Runs** — execute all test cases in sequence; supports chained execution where one test's response feeds the next
- **Performance Runs** — pick a single test, set virtual user count, and get p50/p95/p99 latency, RPS, and error rate
- **Mapping Chains** — Python scripts in `mappings/` define run order, value extraction (`extract`) from responses, and request injection (`inject`)
- **Multi-environment URLs** — `urls.json` maps named environments (local / lab / staging) to per-service base URLs; each test carries a `url_type` (db / core / auth) resolved at run time
- **API Docs view** — `/api/docs` renders all test cases as endpoint documentation grouped by URL type
- **Session auth** — login required; default credentials `admin` / `admin`

---

## Project Structure

```
api-test-suite/
├── app/
│   ├── main.py                  # FastAPI app, middleware, router wiring
│   ├── routers/
│   │   ├── auth.py              # /login  /logout
│   │   ├── dashboard.py         # /  (stats, recent runs, mapping preview)
│   │   ├── tests.py             # /tests/  CRUD + /tests/file editor
│   │   ├── runs.py              # /runs/  functional & performance runs
│   │   ├── mapping_router.py    # /mapping  list / create / edit / delete
│   │   ├── apidocs.py           # /api/docs  endpoint documentation
│   │   └── urls.py              # /urls/file  editor
│   └── services/
│       ├── database.py          # SQLite schema, init, testcases.py sync
│       ├── runner.py            # HTTP execution engine (functional + perf)
│       ├── chain.py             # Mapping folder loader, extract/inject helpers
│       └── url_store.py         # urls.json loader, active environment resolver
├── mappings/                    # One .py file per mapping chain
│   ├── user_flow.py
│   └── auth_flow.py
├── templates/                   # Jinja2 HTML templates
├── static/                      # CSS + JS assets
├── testcases.py                 # Source of truth for test case definitions
├── urls.json                    # Named URL targets per environment / service
├── requirements.txt
├── Dockerfile
└── k8s/deployment.yaml
```

---

## Quick Start

### Local

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set the active environment (must match a top-level key in urls.json)
export ENV_NAME=local           # Windows: set ENV_NAME=local

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` and log in with **admin / admin**.

### Docker

```bash
docker build -t api-test-suite .

docker run -p 8000:8000 \
  -e ENV_NAME=local \
  -v $(pwd)/data:/data \
  -v $(pwd)/testcases.py:/app/testcases.py \
  -v $(pwd)/urls.json:/app/urls.json \
  -v $(pwd)/mappings:/app/mappings \
  api-test-suite
```

### Kubernetes

```bash
# 1. Replace image and domain in k8s/deployment.yaml
# 2. Apply
kubectl apply -f k8s/deployment.yaml

# Watch rollout
kubectl rollout status deployment/api-test-suite

# Get ingress URL
kubectl get ingress api-test-suite
```

Set `ENV_NAME` under `env:` in the Deployment manifest.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ENV_NAME` | first key in `urls.json` | Active environment — read once at startup |
| `DB_PATH` | `data/testsuitedb.sqlite` | SQLite database file path |

---

## Configuration Files

### `urls.json`

Maps environment names → service names → base URLs.  
Each test case carries a `url_type` (e.g. `db`, `core`, `auth`) that is combined with the selected environment at run time:
`base_url = urls[ENV_NAME][test.url_type]`

```json
{
  "local": {
    "db":   "http://localhost:8080",
    "core": "http://localhost:8081",
    "auth": "http://localhost:8082"
  },
  "staging": {
    "db":   "https://db.staging.example.com",
    "core": "https://core.staging.example.com",
    "auth": "https://auth.staging.example.com"
  }
}
```

Edit live at `/urls/file`.

---

### `testcases.py`

Source of truth for test case definitions. Synced into the database on every server startup. Each entry is identified by its unique `name`.

```python
TEST_CASES = [
    {
        "name":            "Health Check",   # unique identifier
        "method":          "GET",
        "path":            "/health",
        "url_type":        "core",           # service key from urls.json
        "expected_status": 200,
        "description":     "Verify the core service is reachable",
        "expected_body":   "",               # substring match (optional)
        "assertions":      "[]",             # JSON array — see below
        "headers":         "{}",             # extra request headers (JSON)
        "body":            "",               # request body (JSON or raw)
        "tags":            '["smoke"]',
    },
    {
        "name":            "Create User",
        "method":          "POST",
        "path":            "/api/users",
        "url_type":        "core",
        "headers":         '{"Content-Type": "application/json"}',
        "body":            '{"name": "Test User", "email": "test@example.com"}',
        "expected_status": 201,
        "assertions":      '[{"type": "response_contains", "value": "id"}]',
    },
]
```

**Custom assertion types:**

| Type | Passes when |
|---|---|
| `response_contains` | Response body contains `value` |
| `status_code` | HTTP status equals `value` |
| `duration_lt` | Response time < `value` ms |

Test cases can also be created / updated at `/tests/new` (upsert by name), or by editing `testcases.py` directly at `/tests/file`.

---

## Mapping Chains

Mapping files live in the `mappings/` folder. Each `.py` file defines one chain. The functional run form lets you select which mapping to use.

### Format

```python
# mappings/user_flow.py

MAPPING_NAME = "User Flow"      # display name shown in the UI

FUNCTIONAL_CHAIN = [
    {
        "test": "Health Check",
        # no extract / inject — just run and validate
    },
    {
        "test": "Create User",
        "extract": {
            "user_id": "id",          # response["id"]        → context["user_id"]
            "token":   "data.token",  # response["data"]["token"] → context["token"]
        },
    },
    {
        "test": "Get User",
        "inject": {
            "path":    "/api/users/{user_id}",
            "headers": '{"Authorization": "Bearer {token}"}',
        },
    },
    {
        "test": "Delete User",
        "inject": {
            "path": "/api/users/{user_id}",
        },
    },
]
```

**`extract`** — dot-notation path into the JSON response. `"data.token"` navigates `response["data"]["token"]`.

**`inject`** — overrides `path`, `body`, or `headers` before the request is sent. `{variable}` placeholders are replaced with values extracted from earlier steps.

If no mapping is selected (or the chain is empty) all test cases run in creation order.

Manage mapping files at `/mapping`.

---

## UI Reference

| Path | Description |
|---|---|
| `/` | Dashboard — stats, recent runs, active mapping chain |
| `/tests/` | Test case list |
| `/tests/new` | Create or update a test case (upserts by name) |
| `/tests/file` | Edit `testcases.py` directly in the browser |
| `/runs/` | Run history |
| `/runs/new?type=functional` | Start a functional run |
| `/runs/new?type=performance` | Start a performance run |
| `/mapping` | List all mapping chain scripts |
| `/mapping/new` | Create a new mapping script |
| `/mapping/edit/<file.py>` | Edit a mapping script (shows chain preview table) |
| `/api/docs` | API documentation — all test cases grouped by URL type |
| `/urls/file` | Edit `urls.json` in the browser |
| `/login` | Login |
| `/logout` | Clear session |

---

## Changing Credentials

Update `CREDENTIALS` in `app/routers/auth.py`:

```python
CREDENTIALS = {"admin": "admin", "youruser": "yourpassword"}
```

---

## Tech Stack

| Package | Role |
|---|---|
| FastAPI | Web framework |
| Starlette | ASGI, session middleware |
| SQLite (WAL) | Embedded database |
| httpx | Async HTTP client for test execution |
| Jinja2 | Server-side HTML templates |
| itsdangerous | Signed session cookies |
| uvicorn | ASGI server |

---

## Notes

- SQLite runs in WAL mode for better concurrent reads during long performance runs
- Performance tests are fully async using `asyncio` — no external load-testing tools required
- The Kubernetes manifest uses `strategy: Recreate` because SQLite requires a single writer on a ReadWriteOnce PVC
- For multi-replica deployments, replace SQLite with PostgreSQL and update `database.py` accordingly
