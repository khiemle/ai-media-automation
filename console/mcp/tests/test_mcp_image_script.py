"""Tests for console/mcp/scripts/mcp-image.sh.

Drive the script with `--token-only --stdin --no-smoke-test --env-file`
so tests never invoke Docker or pbpaste.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "console" / "mcp" / "scripts" / "mcp-image.sh"


def run_script(stdin: str, env_file: Path, *extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--token-only",
            "--stdin",
            "--no-smoke-test",
            "--env-file",
            str(env_file),
            *extra_args,
        ],
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
    )


def read_env_file(p: Path) -> dict[str, str]:
    out = {}
    for line in p.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k] = v
    return out


CANONICAL_PASTED = '''claude mcp add ai-media-console-prod \\
  --transport stdio \\
  --env MCP_API_TOKEN="eyJhbGciOiJIUzI1NiJ9.aaa.bbb" \\
  --env MCP_CONSOLE_API_BASE=http://192.168.68.119:8080 \\
  -- python -m console.mcp.stdio
'''


def test_parses_canonical_admin_ui_output(tmp_path):
    env_file = tmp_path / "out.env"
    result = run_script(CANONICAL_PASTED, env_file)

    assert result.returncode == 0, result.stderr
    contents = read_env_file(env_file)
    assert contents["MCP_API_TOKEN"] == "eyJhbGciOiJIUzI1NiJ9.aaa.bbb"
    assert contents["MCP_CONSOLE_API_BASE"] == "http://192.168.68.119:8080"


def test_env_file_has_mode_0600(tmp_path):
    env_file = tmp_path / "out.env"
    run_script(CANONICAL_PASTED, env_file)
    mode = env_file.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"


def test_localhost_rewritten_to_host_docker_internal(tmp_path):
    pasted = CANONICAL_PASTED.replace(
        "http://192.168.68.119:8080", "http://localhost:8080"
    )
    env_file = tmp_path / "out.env"
    result = run_script(pasted, env_file)

    assert result.returncode == 0, result.stderr
    contents = read_env_file(env_file)
    assert contents["MCP_CONSOLE_API_BASE"] == "http://host.docker.internal:8080"
    # User-visible warning on stderr
    assert "host.docker.internal" in result.stderr
    assert "warning" in result.stderr.lower() or "rewrote" in result.stderr.lower()


def test_127_0_0_1_rewritten(tmp_path):
    pasted = CANONICAL_PASTED.replace(
        "http://192.168.68.119:8080", "http://127.0.0.1:8080"
    )
    env_file = tmp_path / "out.env"
    result = run_script(pasted, env_file)

    assert result.returncode == 0, result.stderr
    contents = read_env_file(env_file)
    assert contents["MCP_CONSOLE_API_BASE"] == "http://host.docker.internal:8080"


def test_lan_ip_passes_through(tmp_path):
    """LAN IPs should NOT be rewritten and should NOT emit a warning."""
    env_file = tmp_path / "out.env"
    result = run_script(CANONICAL_PASTED, env_file)

    contents = read_env_file(env_file)
    assert contents["MCP_CONSOLE_API_BASE"] == "http://192.168.68.119:8080"
    assert "host.docker.internal" not in result.stderr


def test_single_line_command_parsed(tmp_path):
    pasted = (
        'claude mcp add ai-media-console-prod --transport stdio '
        '--env MCP_API_TOKEN="abc.def.ghi" '
        '--env MCP_CONSOLE_API_BASE=http://example.com:8080 '
        '-- python -m console.mcp.stdio'
    )
    env_file = tmp_path / "out.env"
    result = run_script(pasted, env_file)

    assert result.returncode == 0, result.stderr
    contents = read_env_file(env_file)
    assert contents["MCP_API_TOKEN"] == "abc.def.ghi"
    assert contents["MCP_CONSOLE_API_BASE"] == "http://example.com:8080"


def test_crlf_line_endings_handled(tmp_path):
    """Pasted command with CRLF endings should not produce a CR-suffixed env value."""
    pasted = CANONICAL_PASTED.replace("\n", "\r\n")
    env_file = tmp_path / "out.env"
    result = run_script(pasted, env_file)

    assert result.returncode == 0, result.stderr
    contents = read_env_file(env_file)
    assert contents["MCP_CONSOLE_API_BASE"] == "http://192.168.68.119:8080"
    assert "\r" not in contents["MCP_CONSOLE_API_BASE"]
    assert "\r" not in contents["MCP_API_TOKEN"]


def test_missing_token_returns_exit_2(tmp_path):
    pasted = (
        'claude mcp add ai-media-console-prod --transport stdio '
        '--env MCP_CONSOLE_API_BASE=http://example.com:8080 '
        '-- python -m console.mcp.stdio'
    )
    env_file = tmp_path / "out.env"
    result = run_script(pasted, env_file)

    assert result.returncode == 2
    assert "MCP_API_TOKEN" in result.stderr
    assert not env_file.exists()


def test_missing_base_returns_exit_2(tmp_path):
    pasted = (
        'claude mcp add ai-media-console-prod --transport stdio '
        '--env MCP_API_TOKEN="abc.def.ghi" '
        '-- python -m console.mcp.stdio'
    )
    env_file = tmp_path / "out.env"
    result = run_script(pasted, env_file)

    assert result.returncode == 2
    assert "MCP_CONSOLE_API_BASE" in result.stderr
    assert not env_file.exists()


def test_garbage_input_returns_exit_2(tmp_path):
    env_file = tmp_path / "out.env"
    result = run_script("hello world\nthis is not the right command\n", env_file)

    assert result.returncode == 2
    assert "expected" in result.stderr.lower() or "format" in result.stderr.lower()
    assert not env_file.exists()


def test_help_flag(tmp_path):
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        text=True,
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0
    # Usage mentions every documented flag
    for flag in ["--build-only", "--token-only", "--no-smoke-test", "--from-clipboard", "--stdin", "--env-file", "--image-tag"]:
        assert flag in result.stdout
