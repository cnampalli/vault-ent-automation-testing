HEADER = "===== Vault Ent Functional Suite ====="


def _area_line(area: str, r: dict) -> str:
    passed, failed, skipped = r.get("passed", 0), r.get("failed", 0), r.get("skipped", 0)
    if skipped and not passed and not failed:
        # reason is only shown for fully-skipped areas; partial runs show counts
        status = f"SKIPPED ({r.get('reason') or 'precondition not met'})"
    else:
        parts = []
        if passed:
            parts.append(f"{passed} passed")
        if failed:
            parts.append(f"{failed} failed")
        if skipped:
            parts.append(f"{skipped} skipped")
        status = ", ".join(parts) or "0 passed"
    padded = f"{area:<22}"
    dots = "." * max(2, 24 - len(area))
    return f"{padded} {dots} {status}"


def format_summary(area_results: dict) -> str:
    lines = [HEADER]
    totals = {"passed": 0, "failed": 0, "skipped": 0}
    for area, r in area_results.items():
        for k in totals:
            totals[k] += r.get(k, 0)
        lines.append(_area_line(area, r))
    lines.append("-" * len(HEADER))
    lines.append(
        f"TOTAL: {totals['passed']} passed, {totals['failed']} failed, {totals['skipped']} skipped"
    )
    return "\n".join(lines)
