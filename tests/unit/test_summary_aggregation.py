from conftest import aggregate_outcomes


def test_aggregate_groups_by_area():
    records = [
        ("KV v2", "passed", None),
        ("KV v2", "passed", None),
        ("LDAP", "skipped", "LDAP_URL not set"),
        ("Transit", "failed", None),
    ]
    agg = aggregate_outcomes(records)
    assert agg["KV v2"]["passed"] == 2
    assert agg["LDAP"]["skipped"] == 1
    assert agg["LDAP"]["reason"] == "LDAP_URL not set"
    assert agg["Transit"]["failed"] == 1


def test_aggregate_strips_skipped_prefix():
    records = [("LDAP", "skipped", "Skipped: LDAP_URL not set")]
    agg = aggregate_outcomes(records)
    assert agg["LDAP"]["reason"] == "LDAP_URL not set"


def test_aggregate_first_skip_reason_wins():
    records = [
        ("LDAP", "skipped", "Skipped: first"),
        ("LDAP", "skipped", "Skipped: second"),
    ]
    agg = aggregate_outcomes(records)
    assert agg["LDAP"]["reason"] == "first"
    assert agg["LDAP"]["skipped"] == 2
