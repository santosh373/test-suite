"""
Define your REST API test cases here.
Each entry requires: name (unique), method, path.
All other fields are optional and have defaults shown below.
"""

TEST_CASES = [
    {
        "name": "Health Check",
        "description": "Verify the API health endpoint is reachable",
        "method": "GET",
        "path": "/health",
        "expected_status": 200,
        "expected_body": "",
        "assertions": "[]",
        "headers": "{}",
        "body": "",
        "tags": '["smoke"]',
    },
    {
        "name": "List Users",
        "description": "Fetch all users from the API",
        "method": "GET",
        "path": "/api/users",
        "expected_status": 200,
        "expected_body": "",
        "assertions": '[{"type": "response_contains", "value": "id"}]',
        "headers": "{}",
        "body": "",
        "tags": '["users"]',
    },
    {
        "name": "Create User",
        "description": "Create a new user via POST",
        "method": "POST",
        "path": "/api/users",
        "headers": '{"Content-Type": "application/json"}',
        "body": '{"name": "Test User", "email": "test@example.com"}',
        "expected_status": 201,
        "expected_body": "",
        "assertions": '[]',
        "tags": '["users", "write"]',
    },
    # Add more test cases below — each name must be unique.
    # Performance settings (used when running a performance test on this case):
    #   "vus": 10,       <- default virtual users (overridden by count in the run form)
    #   "duration": 30,  <- seconds to sustain load
    #   "ramp_up": 5,    <- seconds to ramp up to full VUs
]
