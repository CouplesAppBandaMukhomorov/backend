import json
import re
from pathlib import Path

import pytest
from openapi_spec_validator import validate

from app.api.openapi import ERROR_CODES
from app.main import app

APP_DIR = Path(__file__).resolve().parent.parent / "app"
EXCEPTION_TAXONOMY = APP_DIR / "core" / "errors.py"
CODE_PATTERNS = (
    re.compile(r'\bcode="([a-z_]+)"'),
    re.compile(r'\bcode\s*=\s*"([a-z_]+)"'),
    re.compile(r'"code"\s*:\s*"([a-z_]+)"'),
)

EXAMPLES_REQUIRED = (
    "TokenPair",
    "UserRead",
    "UserShort",
    "CoupleRead",
    "InvitationRead",
    "InvitationPreview",
    "InvitationAcceptResponse",
    "GoogleAuthorizeUrl",
    "GoogleConnectionRead",
    "GoogleCalendarRead",
    "CalendarLinkRequest",
    "CalendarLink",
    "EventDateTime",
    "EventReminders",
    "EventCreate",
    "EventUpdate",
    "EventRead",
    "NoteCreate",
    "NoteUpdate",
    "NoteRead",
    "ErrorResponse",
    "ValidationErrorResponse",
)


@pytest.fixture(scope="module")
def spec() -> dict:
    return app.openapi()


def operations(spec: dict):
    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if isinstance(operation, dict):
                yield path, method, operation


def test_info_is_described(spec):
    info = spec["info"]
    assert info["title"]
    assert info["version"]
    assert "Google Calendar" in info["description"]
    assert "кодов ошибок" in info["description"]


def test_root_tags_match_operations(spec):
    declared = {tag["name"] for tag in spec.get("tags", [])}
    assert declared == {
        "auth",
        "users",
        "couples",
        "invitations",
        "google",
        "calendar",
        "notes",
        "service",
    }

    used = {tag for _, _, operation in operations(spec) for tag in operation.get("tags", [])}
    assert used <= declared

    for tag in spec["tags"]:
        assert tag["description"]


def test_every_operation_is_described(spec):
    for path, method, operation in operations(spec):
        where = f"{method.upper()} {path}"
        assert operation.get("summary"), f"{where} без summary"
        assert len(operation["summary"]) > 10, f"{where}: summary слишком короткий"
        description = operation.get("description")
        assert description, f"{where} без description"
        assert len(description) > 40, f"{where}: description слишком короткий"


def test_secured_operations_document_unauthorized(spec):
    for path, method, operation in operations(spec):
        if not operation.get("security"):
            continue
        where = f"{method.upper()} {path}"
        assert "401" in operation["responses"], f"{where} не описывает 401"


def test_validation_errors_use_our_schema(spec):
    for path, method, operation in operations(spec):
        response = operation["responses"].get("422")
        if response is None:
            continue
        where = f"{method.upper()} {path}"
        ref = response["content"]["application/json"]["schema"]["$ref"]
        assert ref == "#/components/schemas/ValidationErrorResponse", f"{where} описывает 422 не своей схемой"


def test_domain_errors_use_error_response(spec):
    for path, method, operation in operations(spec):
        for status, response in operation["responses"].items():
            if not status.startswith(("4", "5")) or status == "422":
                continue
            where = f"{method.upper()} {path} {status}"
            ref = response["content"]["application/json"]["schema"]["$ref"]
            assert ref == "#/components/schemas/ErrorResponse", f"{where} описывает ошибку не своей схемой"
            assert response.get("description"), f"{where} без описания"


def test_framework_validation_schemas_removed(spec):
    schemas = spec["components"]["schemas"]
    assert "HTTPValidationError" not in schemas
    assert "ValidationError" not in schemas
    assert "ValidationErrorResponse" in schemas


def test_all_properties_are_described(spec):
    for name, schema in spec["components"]["schemas"].items():
        for field, meta in (schema.get("properties") or {}).items():
            assert meta.get("description"), f"{name}.{field} без описания"


def test_key_schemas_have_examples(spec):
    for name in EXAMPLES_REQUIRED:
        schema = spec["components"]["schemas"][name]
        assert schema.get("examples") or schema.get("example"), f"{name} без примеров"


@pytest.mark.parametrize("name", ["EventCreate", "EventRead", "ErrorResponse"])
def test_examples_are_json_serializable(spec, name):
    json.dumps(spec["components"]["schemas"][name]["examples"], ensure_ascii=False)


def test_error_codes_are_exposed(spec):
    exposed = spec["components"]["schemas"]["ErrorResponse"]["x-error-codes"]
    assert exposed == sorted(ERROR_CODES)


def test_documented_error_codes_match_the_source():
    found: set[str] = set()
    for file in APP_DIR.rglob("*.py"):
        if file == EXCEPTION_TAXONOMY:
            continue
        text = file.read_text(encoding="utf-8")
        for pattern in CODE_PATTERNS:
            found.update(pattern.findall(text))

    assert found, "не найдено ни одного кода ошибки — сломался парсер"

    documented = set(ERROR_CODES)
    assert not found - documented, f"коды в коде без документации: {sorted(found - documented)}"
    assert not documented - found, f"документация обещает несуществующие коды: {sorted(documented - found)}"
    assert len(found) == len(documented)


def test_description_mentions_every_error_code(spec):
    description = spec["info"]["description"]
    for code in ERROR_CODES:
        assert f"`{code}`" in description, f"{code} не упомянут в описании API"


def test_spec_is_valid_openapi(spec):
    validate(spec)


def test_google_callback_is_hidden(spec):
    assert "/api/v1/google/callback" not in spec["paths"]


def test_security_scheme_is_described(spec):
    scheme = spec["components"]["securitySchemes"]["BearerAuth"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert scheme["bearerFormat"] == "JWT"
    assert scheme["description"]


def test_every_parameter_is_described(spec):
    for path, method, operation in operations(spec):
        for parameter in operation.get("parameters", []):
            where = f"{method.upper()} {path} [{parameter['in']}:{parameter['name']}]"
            description = parameter.get("description") or parameter["schema"].get("description")
            assert description, f"{where} без описания"
            examples = parameter.get("example") or parameter["schema"].get("examples")
            assert examples, f"{where} без примера"


def test_every_request_body_is_described(spec):
    for path, method, operation in operations(spec):
        body = operation.get("requestBody")
        if body is None:
            continue
        where = f"{method.upper()} {path}"
        content = body["content"]
        assert "application/json" in content, f"{where} без application/json"
        assert content["application/json"].get("examples"), f"{where} без примеров тела"


async def test_openapi_json_endpoint_serves_patched_schema(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    served = response.json()
    assert served["components"]["schemas"]["ErrorResponse"]["x-error-codes"]
    assert "HTTPValidationError" not in served["components"]["schemas"]


async def test_docs_are_available(client):
    response = await client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text
