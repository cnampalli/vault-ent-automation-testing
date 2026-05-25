from lib.reporting import format_summary


def test_format_summary_renders_counts_and_total():
    results = {
        "KV v2": {"passed": 3, "failed": 0, "skipped": 0, "reason": None},
        "LDAP": {"passed": 0, "failed": 0, "skipped": 2, "reason": "LDAP_URL not set"},
        "Transit": {"passed": 2, "failed": 1, "skipped": 0, "reason": None},
    }
    out = format_summary(results)

    assert "Vault Ent Functional Suite" in out
    assert "KV v2" in out and "3 passed" in out
    assert "SKIPPED (LDAP_URL not set)" in out
    assert "Transit" in out and "2 passed, 1 failed" in out
    assert "TOTAL: 5 passed, 1 failed, 2 skipped" in out


def test_empty_results():
    out = format_summary({})
    assert "TOTAL: 0 passed, 0 failed, 0 skipped" in out


def test_area_line_mixed_passed_and_skipped_does_not_show_skipped_label():
    from lib.reporting import _area_line
    line = _area_line("Auth", {"passed": 1, "failed": 0, "skipped": 2})
    assert "SKIPPED" not in line
    assert "1 passed" in line
    assert "2 skipped" in line


def test_area_line_failed_and_skipped_surfaces_failure():
    from lib.reporting import _area_line
    line = _area_line("Auth", {"passed": 0, "failed": 1, "skipped": 2})
    assert "SKIPPED" not in line
    assert "1 failed" in line


def test_area_line_all_zero_shows_zero_passed():
    from lib.reporting import _area_line
    line = _area_line("Auth", {"passed": 0, "failed": 0, "skipped": 0})
    assert "0 passed" in line
