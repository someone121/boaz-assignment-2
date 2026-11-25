"""Checks that keep the static frontend and the FastAPI backend in sync.

The frontend has no build step or JS test runner, so these tests read the
HTML/JS files and compare them against the app's real routes.
"""

import re

import pytest

from app.config import STATIC_DIR
from app.main import app

PAGES = {
    "/": "login.html",
    "/login": "login.html",
    "/lecturer_dashboard": "lecturer_dashboard.html",
    "/dashboard": "lecturer_dashboard.html",
    "/student_dashboard": "student_dashboard.html",
    "/live": "student_dashboard.html",
    "/s/some-token": "student_dashboard.html",
    "/forum": "forum.html",
}


@pytest.mark.parametrize("path,filename", PAGES.items())
def test_page_routes_serve_the_right_html(client, path, filename):
    res = client.get(path)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert res.text == (STATIC_DIR / filename).read_text(encoding="utf-8")


def test_every_local_script_in_html_exists(client):
    for page in STATIC_DIR.glob("*.html"):
        for src in re.findall(r'src="(/static/[^"]+)"', page.read_text(encoding="utf-8")):
            assert client.get(src).status_code == 200, f"{page.name} references missing {src}"


def test_every_js_import_exists():
    for js in (STATIC_DIR / "js").glob("*.js"):
        for target in re.findall(r'from\s+"\./([^"]+)"', js.read_text(encoding="utf-8")):
            assert (STATIC_DIR / "js" / target).exists(), f"{js.name} imports missing ./{target}"


def _api_route_patterns() -> list[re.Pattern]:
    # The OpenAPI schema lists every REST route, including ones from included routers.
    patterns = []
    for path in app.openapi()["paths"]:
        if path.startswith("/api/"):
            regex = re.sub(r"\{[^}]+\}", "[^/]+", path)
            patterns.append(re.compile(f"^{regex}$"))
    return patterns


def test_every_api_call_in_api_js_has_a_backend_route():
    source = (STATIC_DIR / "js" / "api.js").read_text(encoding="utf-8")
    # Paths appear as "/api/..." strings or `/api/...${x}...` template literals.
    raw_paths = re.findall(r'["`](/api/[^"`?]*)', source)
    assert raw_paths, "no API paths found in api.js"

    patterns = _api_route_patterns()
    for raw in raw_paths:
        path = re.sub(r"\$\{[^}]+\}", "x", raw)
        assert any(p.match(path) for p in patterns), f"api.js calls {raw}, which has no backend route"


def test_role_guards_on_dashboards():
    lecturer = (STATIC_DIR / "lecturer_dashboard.html").read_text(encoding="utf-8")
    student = (STATIC_DIR / "student_dashboard.html").read_text(encoding="utf-8")
    assert 'user.role !== "lecturer"' in lecturer
    assert 'user.role !== "student"' in student
    assert "?redirect=" in student  # QR scans return to /s/{token} after login
