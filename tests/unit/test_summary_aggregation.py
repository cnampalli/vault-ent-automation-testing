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
