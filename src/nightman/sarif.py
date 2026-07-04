from __future__ import annotations

import hashlib

from .models import HuntResult
from .severity import fix_hint

_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"


def _level(severity: int) -> str:
    return "error" if severity >= 4 else "warning"


def _security_severity(severity: int) -> str:
    return f"{min(10.0, severity * 2.0):.1f}"


def _rule(category: str) -> dict:
    return {
        "id": f"nightman/{category}",
        "name": category.replace("-", " ").title().replace(" ", ""),
        "shortDescription": {"text": f"{category} fault found by Nightman"},
        "fullDescription": {"text": fix_hint(category)},
        "helpUri": "https://github.com/Falcon305/nightman",
    }


def _location(result: HuntResult) -> dict:
    failure = result.failure
    assert failure is not None
    uri = result.target.rsplit(":", 1)[0]
    region = {}
    if failure.location and failure.location.line:
        region = {"startLine": failure.location.line}
    physical: dict = {"artifactLocation": {"uri": uri}}
    if region:
        physical["region"] = region
    return {"physicalLocation": physical}


def to_sarif(findings: list[HuntResult]) -> dict:
    rules: dict[str, dict] = {}
    results = []
    for result in findings:
        failure = result.failure
        if failure is None:
            continue
        rule_id = f"nightman/{failure.category}"
        rules.setdefault(rule_id, _rule(failure.category))
        verdict = failure.exception_type or f"{result.property} violation"
        fingerprint = hashlib.sha1(f"{rule_id}:{result.target}:{failure.args_repr}".encode()).hexdigest()
        results.append(
            {
                "ruleId": rule_id,
                "level": _level(failure.severity),
                "message": {"text": f"{verdict} on {failure.args_repr} — {failure.message}"},
                "locations": [_location(result)],
                "partialFingerprints": {"primaryLocationLineHash": fingerprint},
                "properties": {"security-severity": _security_severity(failure.severity)},
            }
        )
    return {
        "$schema": _SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "nightman",
                        "informationUri": "https://github.com/Falcon305/nightman",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }
