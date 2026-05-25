import re
from lib.naming import ephemeral_namespace_name


def test_uses_build_tag_sanitized():
    name = ephemeral_namespace_name("jenkins-MyFolder/Vault Job #123")
    assert name.startswith("ci-test-")
    assert "/" not in name and " " not in name
    assert re.fullmatch(r"ci-test-[a-z0-9-]+", name)


def test_length_capped():
    name = ephemeral_namespace_name("x" * 200)
    assert len(name) <= 48  # "ci-test-" (8) + up to 40


def test_fallback_when_no_tag(monkeypatch):
    monkeypatch.delenv("BUILD_TAG", raising=False)
    name = ephemeral_namespace_name(None)
    assert name.startswith("ci-test-local-")


def test_reads_build_tag_env(monkeypatch):
    monkeypatch.setenv("BUILD_TAG", "build-42")
    assert ephemeral_namespace_name() == "ci-test-build-42"
