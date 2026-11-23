"""Read-only access to the public JSON used by Kaggle competition pages."""

import json
import subprocess

ORIGIN = "https://www.kaggle.com"


class SourceUnavailable(Exception):
    """A public Kaggle item has become unavailable or its network request failed."""


def fetch(url, payload=None):
    args = [
        "curl",
        "--silent",
        "--show-error",
        "--fail",
        "--location",
        "--max-time",
        "30",
        "--retry",
        "2",
        "--retry-delay",
        "1",
        url,
    ]
    if payload is not None:
        args += ["--header", "Content-Type: application/json", "--data-binary", "@-"]
    result = subprocess.run(
        args,
        input=json.dumps(payload) if payload is not None else None,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise SourceUnavailable(result.stderr.strip()[-200:])
    return result.stdout


def api(method, **data):
    return json.loads(fetch(f"{ORIGIN}/api/i/{method}", data))
