import importlib.util
import json
import os

MAPPINGS_DIR = os.path.join(os.getcwd(), "mappings")


def _load_module(filename: str):
    path = os.path.join(MAPPINGS_DIR, filename)
    try:
        spec = importlib.util.spec_from_file_location(filename[:-3], path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def list_mappings() -> list:
    """Returns list of dicts: {filename, mapping_name, step_count}"""
    os.makedirs(MAPPINGS_DIR, exist_ok=True)
    result = []
    for fname in sorted(os.listdir(MAPPINGS_DIR)):
        if not fname.endswith(".py"):
            continue
        mod = _load_module(fname)
        if mod is None:
            continue
        result.append({
            "filename":     fname,
            "mapping_name": getattr(mod, "MAPPING_NAME", fname[:-3]),
            "step_count":   len(getattr(mod, "FUNCTIONAL_CHAIN", [])),
        })
    return result


def load_chain_from_file(filename: str) -> list:
    mod = _load_module(filename)
    return getattr(mod, "FUNCTIONAL_CHAIN", []) if mod else []


def load_mapping_name_from_file(filename: str) -> str:
    mod = _load_module(filename)
    return getattr(mod, "MAPPING_NAME", filename[:-3]) if mod else filename[:-3]


def read_file_content(filename: str) -> str:
    path = os.path.join(MAPPINGS_DIR, filename)
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return ""


def write_file_content(filename: str, content: str):
    os.makedirs(MAPPINGS_DIR, exist_ok=True)
    path = os.path.join(MAPPINGS_DIR, filename)
    with open(path, "w") as f:
        f.write(content)


def delete_file(filename: str):
    path = os.path.join(MAPPINGS_DIR, filename)
    if os.path.exists(path):
        os.remove(path)


# ── value extraction / injection ──────────────────────────────────────────────

def extract_value(response_body: str, path: str) -> str:
    try:
        data = json.loads(response_body)
        for part in path.split("."):
            if isinstance(data, dict):
                data = data[part]
            elif isinstance(data, list):
                data = data[int(part)]
            else:
                return ""
        return str(data)
    except Exception:
        return ""


def apply_context(value: str, context: dict) -> str:
    for k, v in context.items():
        value = value.replace("{" + k + "}", v)
    return value


def build_test_with_context(test: dict, step: dict, context: dict) -> dict:
    test = dict(test)
    for field, template in (step.get("inject") or {}).items():
        test[field] = apply_context(template, context)
    return test


def load_chain() -> list:
    mappings = list_mappings()
    return load_chain_from_file(mappings[0]["filename"]) if mappings else []


def load_mapping_name() -> str:
    mappings = list_mappings()
    return mappings[0]["mapping_name"] if mappings else ""
