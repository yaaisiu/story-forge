"""Unit tests for the frontend npm-audit gate (`scripts/check_npm_audit.py`).

The gate decides whether a HIGH/CRITICAL advisory in a *shipped* frontend dependency
blocks `main` (spec §6.7 "Frontend dependencies audited"). It is the newest of the three
SCA gates to gain a waiver mechanism, and a waiver gate that silently suppresses
everything is worse than no gate at all — so the decision logic is pinned here rather
than left to a green CI run to vouch for.

The script lives at the repo root (`scripts/`), outside the backend package, because it
gates the *frontend* job. These tests live here because `backend/tests/` is the only
suite a required CI job runs. Pure — no npm, no network.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_npm_audit.py"


def _load_gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_npm_audit", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: @dataclass resolves annotations via sys.modules[cls.__module__],
    # which is None for a module loaded by path alone.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


# --- fixtures: the shape `npm audit --omit=dev --json` actually emits ------------------
# A directly-affected package carries dict entries in `via` (the advisories themselves);
# a package that is only affected *through* another carries plain strings. Both appear in
# the real react-router output, which is why the distinction is pinned here.

RSC_URL = "https://github.com/advisories/GHSA-qwww-vcr4-c8h2"


def _audit_json(severity: str = "high", url: str = RSC_URL) -> dict:
    return {
        "vulnerabilities": {
            "react-router": {
                "name": "react-router",
                "severity": severity,
                "via": [
                    {
                        "source": 1234,
                        "name": "react-router",
                        "title": "React Router: RSC Mode CSRF Bypass",
                        "url": url,
                        "severity": severity,
                        "range": ">=7.12.0 <8.3.0",
                    }
                ],
            },
            "react-router-dom": {
                "name": "react-router-dom",
                "severity": severity,
                "via": ["react-router"],
            },
        }
    }


def _waiver(ignore_until: str = "2026-09-30", advisory_id: str = "GHSA-qwww-vcr4-c8h2"):
    return gate.Waiver(
        id=advisory_id,
        reason="Unreachable: no RSC APIs used.",
        ignore_until=date.fromisoformat(ignore_until),
    )


TODAY = date(2026, 7, 30)


# --- collecting findings ---------------------------------------------------------------


def test_collects_the_advisory_once_despite_two_affected_packages() -> None:
    """The transitive `react-router-dom` entry must not double-count the same advisory."""
    findings = gate.collect_findings(_audit_json())
    assert [f.advisory_id for f in findings] == ["GHSA-qwww-vcr4-c8h2"]


def test_ignores_severities_below_high() -> None:
    assert gate.collect_findings(_audit_json(severity="moderate")) == []


def test_collects_critical() -> None:
    findings = gate.collect_findings(_audit_json(severity="critical"))
    assert len(findings) == 1
    assert findings[0].severity == "critical"


def test_no_vulnerabilities_is_no_findings() -> None:
    assert gate.collect_findings({"vulnerabilities": {}}) == []


# --- the gate decision -----------------------------------------------------------------


def test_unwaived_high_blocks() -> None:
    verdict = gate.evaluate(gate.collect_findings(_audit_json()), [], TODAY)
    assert [f.advisory_id for f in verdict.blocking] == ["GHSA-qwww-vcr4-c8h2"]
    assert verdict.failed


def test_waived_high_passes() -> None:
    verdict = gate.evaluate(gate.collect_findings(_audit_json()), [_waiver()], TODAY)
    assert verdict.blocking == []
    assert [f.advisory_id for f, _ in verdict.waived] == ["GHSA-qwww-vcr4-c8h2"]
    assert not verdict.failed


def test_expired_waiver_stops_suppressing_and_re_reds() -> None:
    """The whole point of the mandatory `ignoreUntil`: an ignore expires loudly."""
    expired = _waiver(ignore_until="2026-07-29")  # yesterday, relative to TODAY
    verdict = gate.evaluate(gate.collect_findings(_audit_json()), [expired], TODAY)
    assert [f.advisory_id for f in verdict.blocking] == ["GHSA-qwww-vcr4-c8h2"]
    assert [w.id for _, w in verdict.expired] == ["GHSA-qwww-vcr4-c8h2"]
    assert verdict.failed


def test_waiver_expiring_today_still_suppresses() -> None:
    """Boundary: the waiver is valid *through* its ignoreUntil date, not up to it."""
    verdict = gate.evaluate(
        gate.collect_findings(_audit_json()), [_waiver(ignore_until="2026-07-30")], TODAY
    )
    assert verdict.blocking == []
    assert not verdict.failed


def test_waiver_matching_nothing_is_reported_stale_but_does_not_fail() -> None:
    """A retired advisory should prompt cleanup, not red `main` on a fixed dependency."""
    verdict = gate.evaluate([], [_waiver()], TODAY)
    assert [w.id for w in verdict.stale] == ["GHSA-qwww-vcr4-c8h2"]
    assert not verdict.failed


def test_a_waiver_does_not_suppress_a_different_advisory() -> None:
    other = _audit_json(url="https://github.com/advisories/GHSA-chx6-hx7r-mcp5")
    verdict = gate.evaluate(gate.collect_findings(other), [_waiver()], TODAY)
    assert [f.advisory_id for f in verdict.blocking] == ["GHSA-chx6-hx7r-mcp5"]
    assert verdict.failed


# --- parsing the waiver file (fail closed) ---------------------------------------------


def test_parses_a_well_formed_waiver_file() -> None:
    waivers = gate.load_waivers(
        """
        [[IgnoredVulns]]
        id = "GHSA-qwww-vcr4-c8h2"
        reason = "Unreachable: no RSC APIs used."
        ignoreUntil = 2026-09-30
        """
    )
    assert len(waivers) == 1
    assert waivers[0].id == "GHSA-qwww-vcr4-c8h2"
    assert waivers[0].ignore_until == date(2026, 9, 30)


def test_waiver_without_ignore_until_is_rejected() -> None:
    """An undated ignore is the exact failure mode the mechanism exists to prevent."""
    with pytest.raises(ValueError, match="ignoreUntil"):
        gate.load_waivers(
            """
            [[IgnoredVulns]]
            id = "GHSA-qwww-vcr4-c8h2"
            reason = "Unreachable."
            """
        )


def test_waiver_without_reason_is_rejected() -> None:
    with pytest.raises(ValueError, match="reason"):
        gate.load_waivers(
            """
            [[IgnoredVulns]]
            id = "GHSA-qwww-vcr4-c8h2"
            ignoreUntil = 2026-09-30
            """
        )


def test_waiver_with_non_date_ignore_until_is_rejected() -> None:
    """A quoted date is a TOML string, not a date — reject rather than guess."""
    with pytest.raises(ValueError, match="ignoreUntil"):
        gate.load_waivers(
            """
            [[IgnoredVulns]]
            id = "GHSA-qwww-vcr4-c8h2"
            reason = "Unreachable."
            ignoreUntil = "2026-09-30"
            """
        )


def test_malformed_toml_is_rejected() -> None:
    with pytest.raises(ValueError):
        gate.load_waivers("[[IgnoredVulns]\nid = ")


def test_empty_waiver_file_is_no_waivers() -> None:
    assert gate.load_waivers("# nothing waived\n") == []


def test_duplicate_waivers_for_one_advisory_are_rejected() -> None:
    """Two entries mean two expiries, and the loser might be the earlier one."""
    with pytest.raises(ValueError, match="duplicate"):
        gate.load_waivers(
            """
            [[IgnoredVulns]]
            id = "GHSA-qwww-vcr4-c8h2"
            reason = "First."
            ignoreUntil = 2026-08-31

            [[IgnoredVulns]]
            id = "GHSA-qwww-vcr4-c8h2"
            reason = "Second, with a later date."
            ignoreUntil = 2027-08-31
            """
        )


# --- npm audit payload validation (the fail-OPEN trap) ---------------------------------


def test_accepts_a_real_audit_payload() -> None:
    payload = gate.parse_audit_payload('{"vulnerabilities": {}}')
    assert payload == {"vulnerabilities": {}}


def test_an_npm_error_payload_is_rejected_rather_than_read_as_clean() -> None:
    """`npm audit` prints this and exits **0** when it cannot audit at all.

    It parses cleanly and carries no `vulnerabilities`, so treating it as "nothing found"
    would pass the gate green having audited nothing. Regression test for a real fail-open
    bug found reviewing this script: a missing lockfile silently disabled the gate.
    """
    payload = (
        '{"error": {"code": "ENOLOCK", "summary": "This command requires an existing lockfile.",'
        ' "detail": "Try creating one first"}}'
    )
    with pytest.raises(ValueError, match="did not audit"):
        gate.parse_audit_payload(payload)


def test_a_payload_without_vulnerabilities_is_rejected() -> None:
    with pytest.raises(ValueError, match="did not audit"):
        gate.parse_audit_payload('{"metadata": {"totals": 0}}')


def test_unparseable_output_is_rejected() -> None:
    with pytest.raises(ValueError, match="no parseable JSON"):
        gate.parse_audit_payload("npm ERR! something went very wrong")


def test_a_non_object_payload_is_rejected() -> None:
    with pytest.raises(ValueError, match="expected an object"):
        gate.parse_audit_payload("[]")
