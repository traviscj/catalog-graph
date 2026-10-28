"""helpers shared by domain rule modules."""


def f(r, k, d=None):
    v = (r.get("f") or {}).get(k, d)
    return d if v is None else v


def jobs(r, role=None):
    return {j["job"] for j in r.get("jobs", []) if role is None or j.get("role") == role}


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

