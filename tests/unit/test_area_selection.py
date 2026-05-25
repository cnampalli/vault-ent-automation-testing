from conftest import parse_areas, select_areas


def test_parse_areas_splits_and_normalizes():
    assert parse_areas("KV v2, Transit ,, ldap") == ["kv v2", "transit", "ldap"]
    assert parse_areas("") == []
    assert parse_areas(None) == []


def test_select_areas_keeps_matching_substring():
    amap = {"t1": "KV v2", "t2": "Transit", "t3": "Kubernetes"}
    keep, drop, unmatched = select_areas(amap, ["kv", "transit"])
    assert set(keep) == {"t1", "t2"}
    assert drop == ["t3"]
    assert unmatched == []


def test_select_areas_reports_unmatched_filter():
    amap = {"t1": "KV v2"}
    keep, drop, unmatched = select_areas(amap, ["kv", "nope"])
    assert keep == ["t1"]
    assert unmatched == ["nope"]


def test_select_areas_pki_substring_matches_both():
    amap = {"a": "PKI (built-in)", "b": "PKI (Venafi)", "c": "SSH"}
    keep, drop, unmatched = select_areas(amap, ["pki"])
    assert set(keep) == {"a", "b"}
    assert drop == ["c"]


def test_select_areas_no_filters_keeps_all():
    amap = {"a": "KV v2", "b": "SSH"}
    keep, drop, unmatched = select_areas(amap, [])
    assert set(keep) == {"a", "b"}
    assert drop == []
