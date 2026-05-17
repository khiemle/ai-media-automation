#!/usr/bin/env python3
"""Render a markdown summary of pytest/vitest JUnit + Cobertura coverage.

Writes to $GITHUB_STEP_SUMMARY (so it appears on the workflow run page) and
prints the same content to stdout (so it appears in the step log).

Inputs (via env vars):
  REPORT_NAME    — heading text (e.g. "Backend Tests")
  JUNIT_PATH     — path to JUnit XML (default: junit.xml)
  COVERAGE_PATH  — path to Cobertura XML (default: coverage.xml)

Both files are optional — sections render only if the file exists.
"""
from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_junit(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    root = ET.parse(p).getroot()
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}
    failures: list[dict] = []
    for s in suites:
        totals["tests"] += int(s.get("tests", 0) or 0)
        totals["failures"] += int(s.get("failures", 0) or 0)
        totals["errors"] += int(s.get("errors", 0) or 0)
        totals["skipped"] += int(s.get("skipped", 0) or 0)
        try:
            totals["time"] += float(s.get("time", 0) or 0)
        except ValueError:
            pass
        for tc in s.findall("testcase"):
            fail = tc.find("failure")
            err = tc.find("error")
            if fail is None and err is None:
                continue
            node = fail if fail is not None else err
            message = (node.get("message") or node.text or "").strip().splitlines()
            first = message[0][:240] if message else "(no message)"
            failures.append(
                {
                    "classname": tc.get("classname") or "",
                    "name": tc.get("name") or "",
                    "message": first,
                    "type": "failure" if fail is not None else "error",
                }
            )
    totals["passed"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    totals["failures_list"] = failures
    return totals


def parse_coverage(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    root = ET.parse(p).getroot()
    try:
        percent = float(root.get("line-rate", 0)) * 100
    except (TypeError, ValueError):
        percent = 0.0
    packages: list[tuple[str, float, int, int]] = []
    for pkg in root.iter("package"):
        name = pkg.get("name") or "(root)"
        try:
            pct = float(pkg.get("line-rate", 0)) * 100
        except (TypeError, ValueError):
            pct = 0.0
        covered = 0
        valid = 0
        for line in pkg.iter("line"):
            valid += 1
            if int(line.get("hits", 0) or 0) > 0:
                covered += 1
        packages.append((name, pct, covered, valid))
    packages.sort(key=lambda x: x[1])
    return {"percent": percent, "packages": packages}


def render(name: str, junit: dict | None, coverage: dict | None) -> str:
    lines: list[str] = [f"# {name}\n"]

    lines.append("## Test results\n")
    if junit is None:
        lines.append("_No JUnit XML produced._\n")
    else:
        bad = junit["failures"] + junit["errors"]
        emoji = "✅" if bad == 0 else "❌"
        xfailed = junit.get("skipped", 0)
        lines.append(
            f"{emoji} **{junit['passed']} passed** · "
            f"{junit['failures']} failed · "
            f"{junit['errors']} errors · "
            f"{xfailed} skipped/xfailed · "
            f"{junit['tests']} total · "
            f"{junit['time']:.1f}s\n"
        )
        if junit["failures_list"]:
            lines.append("\n### Failures\n")
            shown = junit["failures_list"][:25]
            for f in shown:
                node = f"`{f['classname']}::{f['name']}`" if f["classname"] else f"`{f['name']}`"
                lines.append(f"- **{f['type']}** — {node}\n  - {f['message']}\n")
            extra = len(junit["failures_list"]) - len(shown)
            if extra > 0:
                lines.append(f"\n_… {extra} more failure(s) — download the junit.xml artifact for full detail._\n")

    lines.append("\n## Coverage\n")
    if coverage is None:
        lines.append("_No coverage XML produced._\n")
    else:
        lines.append(f"**Overall: {coverage['percent']:.1f}%**\n")
        if coverage["packages"]:
            lines.append("\n| Package | Coverage | Lines |\n|---|---:|---:|\n")
            shown = coverage["packages"][:30]
            for pkg_name, pct, covered, valid in shown:
                bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
                lines.append(f"| `{pkg_name}` | `{bar}` {pct:.1f}% | {covered}/{valid} |\n")
            extra = len(coverage["packages"]) - len(shown)
            if extra > 0:
                lines.append(f"\n_… {extra} more package(s) — see htmlcov artifact for full report._\n")

    return "".join(lines)


def main() -> int:
    name = os.environ.get("REPORT_NAME", "Test Report")
    junit_path = os.environ.get("JUNIT_PATH", "junit.xml")
    cov_path = os.environ.get("COVERAGE_PATH", "coverage.xml")

    junit = parse_junit(junit_path)
    coverage = parse_coverage(cov_path)
    md = render(name, junit, coverage)

    sys.stdout.write(md)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
