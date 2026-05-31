MAPPING_NAME = "User Flow"

FUNCTIONAL_CHAIN = [
    {
        "test": "Health Check",
    },
    {
        "test": "Create User",
        "extract": {
            "user_id": "id",
            "token":   "data.token",
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
            "path":    "/api/users/{user_id}",
            "headers": '{"Authorization": "Bearer {token}"}',
        },
    },
]
