import os
import subprocess
from pathlib import Path

import pytest

from app.core.config import Settings

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "render_env.sh"
EXAMPLE = ROOT / ".env.example"
BASE_ENV = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}

MUST_BE_REQUIRED = ("DATABASE_URL", "JWT_SECRET", "FERNET_KEY")


def render(**settings: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env={**BASE_ENV, **settings},
        capture_output=True,
        text=True,
        check=False,
    )


def all_settings(**overrides: str) -> dict[str, str]:
    env = {name.upper(): "test-value" for name in Settings.model_fields}
    env.update(overrides)
    return env


def parse_keys(output: str) -> set[str]:
    return {line.split("=", 1)[0].lower() for line in output.splitlines() if "=" in line}


def test_every_setting_is_rendered():
    result = render(**all_settings())

    assert result.returncode == 0, result.stderr
    assert parse_keys(result.stdout) == set(Settings.model_fields)


def test_output_is_a_well_formed_dotenv():
    result = render(**all_settings())

    assert result.stdout.endswith("\n")
    lines = result.stdout.splitlines()
    assert len(lines) == len(Settings.model_fields)
    for line in lines:
        name, separator, value = line.partition("=")
        assert separator == "="
        assert name == name.upper()
        assert value


@pytest.mark.parametrize("name", MUST_BE_REQUIRED)
def test_critical_setting_cannot_be_missing(name):
    env = all_settings()
    env.pop(name)

    result = render(**env)

    assert result.returncode != 0
    assert name in result.stderr


@pytest.mark.parametrize("mode", ["unset", "empty"])
def test_optional_setting_is_skipped_when_unset_or_empty(mode):
    env = all_settings()
    if mode == "unset":
        env.pop("APP_NAME")
    else:
        env["APP_NAME"] = ""

    result = render(**env)

    assert result.returncode == 0, result.stderr
    assert parse_keys(result.stdout) == set(Settings.model_fields) - {"app_name"}


def test_multiline_value_is_rejected():
    result = render(**all_settings(APP_NAME="first\nsecond"))

    assert result.returncode != 0
    assert "APP_NAME" in result.stderr
    assert "line break" in result.stderr


def test_values_survive_compose_parsing():
    result = render(
        **all_settings(
            DATABASE_URL="postgresql+asyncpg://user:p$ss#word@db:5432/couple",
            APP_NAME="Couple API",
        )
    )

    assert result.returncode == 0, result.stderr
    assert "DATABASE_URL=postgresql+asyncpg://user:p$$ss#word@db:5432/couple\n" in result.stdout
    assert "APP_NAME=Couple API\n" in result.stdout


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("first\nsecond", "line break"),
        ("a # b", "space followed by #"),
        ('"quoted', "starts with a quote"),
        ("'quoted", "starts with a quote"),
        ("#comment", "starts with a quote or a comment character"),
        (" leading", "leading or trailing whitespace"),
        ("trailing ", "leading or trailing whitespace"),
        ("backslash\\", "ends with a backslash"),
    ],
)
def test_values_that_compose_would_mangle_are_rejected(value, reason):
    result = render(**all_settings(APP_NAME=value))

    assert result.returncode != 0
    assert "APP_NAME" in result.stderr
    assert reason in result.stderr


def test_dollar_is_escaped_so_the_value_survives():
    result = render(**all_settings(FERNET_KEY="a$b"))

    assert result.returncode == 0, result.stderr
    assert "FERNET_KEY=a$$b\n" in result.stdout


def test_example_env_documents_every_setting():
    keys = {
        line.split("=", 1)[0].strip().lower()
        for line in EXAMPLE.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.strip().startswith("#")
    }

    assert set(Settings.model_fields) <= keys


@pytest.mark.parametrize("name", ["DATABASE_URL", "DEBUG", "JWT_ALGORITHM"])
def test_empty_environment_variable_falls_back_to_the_default(monkeypatch, name):
    field = next(key for key in Settings.model_fields if key.upper() == name)
    monkeypatch.setenv(name, "")

    settings = Settings(_env_file=None)

    assert getattr(settings, field) == Settings.model_fields[field].default
