MAPPING_NAME = "Auth Flow"

FUNCTIONAL_CHAIN = [
    {
        "test": "Health Check",
    },
    {
        "test": "Login",
        "extract": {
            "token": "access_token",
        },
    },
    {
        "test": "Get Profile",
        "inject": {
            "headers": '{"Authorization": "Bearer {token}"}',
        },
    },
]
