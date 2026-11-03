from __future__ import annotations

from typing import Any


def handle(
    operation: str,
    values: list[float],
    period: float | None = None,
    **_: Any,
) -> dict[str, Any]:
    if not values:
        return {"ok": False, "error": "empty_values", "message": "values must be non-empty"}

    formula = ""
    result: float

    if operation == "sum":
        result = float(sum(values))
        formula = "sum(values)"
    elif operation == "average":
        result = float(sum(values) / len(values))
        formula = "sum(values)/n"
    elif operation == "delta":
        if len(values) < 2:
            return {"ok": False, "error": "need_two_values", "message": "delta needs ≥2 values"}
        result = float(values[-1] - values[0])
        formula = "last - first"
    elif operation == "ratio":
        if len(values) < 2 or values[1] == 0:
            return {"ok": False, "error": "bad_ratio", "message": "ratio needs a,b with b≠0"}
        result = float(values[0] / values[1])
        formula = "a/b"
    elif operation == "share":
        total = sum(values)
        if total == 0:
            return {"ok": False, "error": "zero_total", "message": "share total is 0"}
        # return first value as share of total
        result = float(values[0] / total)
        formula = "values[0]/sum(values)"
    elif operation == "growth_rate":
        if len(values) < 2 or values[0] == 0:
            return {
                "ok": False,
                "error": "bad_growth",
                "message": "growth_rate needs start≠0 and end",
            }
        result = float((values[-1] - values[0]) / values[0])
        formula = "(end-start)/start"
    elif operation == "cagr":
        n = period if period and period > 0 else max(len(values) - 1, 1)
        if values[0] <= 0:
            return {"ok": False, "error": "bad_cagr", "message": "cagr needs positive start"}
        result = float((values[-1] / values[0]) ** (1 / n) - 1)
        formula = "(end/start)^(1/n) - 1"
    else:
        return {
            "ok": False,
            "error": "unknown_operation",
            "message": f"Unsupported operation {operation}",
        }

    return {
        "ok": True,
        "operation": operation,
        "inputs": values,
        "period": period,
        "result": result,
        "formula": formula,
        "provenance": {"kind": "calculation", "operation": operation},
    }
