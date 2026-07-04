from __future__ import annotations

VERIFIED = "verified"
HIGH = "high"
HEURISTIC = "heuristic"

_CRASH_CATEGORY = {
    "IndexError": "boundary",
    "KeyError": "missing-key",
    "ZeroDivisionError": "division-by-zero",
    "RecursionError": "runaway-recursion",
    "OverflowError": "numeric-overflow",
    "UnicodeDecodeError": "unicode-edge",
    "UnicodeEncodeError": "unicode-edge",
    "UnicodeError": "unicode-edge",
    "TypeError": "type-mismatch",
    "AttributeError": "none-or-missing-attr",
    "ValueError": "unhandled-value",
    "TimeoutError": "slow-or-infinite-loop",
    "MemoryError": "runaway-memory",
    "AssertionError": "broken-invariant",
}

_PROPERTY_CATEGORY = {
    "differential": "wrong-result",
    "roundtrip": "roundtrip-broken",
    "idempotent": "not-idempotent",
    "commutative": "not-commutative",
    "metamorphic": "broken-relation",
    "type-contract": "wrong-output-type",
}

_LOW_CONFIDENCE_EXC = {"ValueError", "TimeoutError"}
_LOW_SEVERITY_EXC = {"ValueError"}
_MID_SEVERITY_EXC = {"TimeoutError", "TypeError", "KeyError"}

_FIX_HINTS = {
    "boundary": "Guard the index/range bound before you touch it — the empty and single-element cases.",
    "missing-key": "Use .get() or check membership before indexing the mapping.",
    "division-by-zero": "Reject or special-case a zero denominator before dividing.",
    "runaway-recursion": "Add a base case for the missing branch (negatives?) or make it iterative.",
    "numeric-overflow": "Avoid materializing unbounded ranges; compute the size arithmetically.",
    "unicode-edge": "Encode/decode with utf-8 and errors= handling, not ascii.",
    "type-mismatch": "Coerce or validate the argument's type before combining it.",
    "none-or-missing-attr": "Handle the None / missing-attribute case explicitly.",
    "unhandled-value": "Validate the input up front and raise a clear, documented error.",
    "slow-or-infinite-loop": "Ensure the loop makes progress and terminates for every input.",
    "wrong-result": "The output disagrees with the reference on this input — reconcile the logic.",
    "roundtrip-broken": "decode(encode(x)) must return x — check the escaping/encoding pair.",
    "not-idempotent": "Applying it twice should equal applying it once — normalize fully in one pass.",
}


def classify(kind: str, property_name: str, exception_type: str | None, verified: bool) -> tuple[str, int, str]:
    if kind == "property":
        category = _PROPERTY_CATEGORY.get(property_name, "broken-relation")
        confidence = VERIFIED if verified else HIGH
        return category, 4, confidence
    exc = exception_type or ""
    category = _CRASH_CATEGORY.get(exc, "crash")
    if exc in _LOW_SEVERITY_EXC:
        severity = 2
    elif exc in _MID_SEVERITY_EXC:
        severity = 3
    else:
        severity = 4
    if exc in _LOW_CONFIDENCE_EXC:
        confidence = HEURISTIC
    elif verified:
        confidence = VERIFIED
    else:
        confidence = HIGH
    return category, severity, confidence


def fix_hint(category: str) -> str:
    return _FIX_HINTS.get(category, "Handle this input explicitly, or document it as unsupported.")


def rank(severity: int, confidence: str) -> float:
    weight = {VERIFIED: 1.0, HIGH: 0.8, HEURISTIC: 0.5}.get(confidence, 0.5)
    return severity * weight
