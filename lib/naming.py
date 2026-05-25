import os
import re
import uuid


def ephemeral_namespace_name(build_tag: str | None = None) -> str:
    raw = build_tag or os.environ.get("BUILD_TAG") or f"local-{uuid.uuid4().hex[:8]}"
    slug = re.sub(r"[^a-z0-9-]+", "-", raw.lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")[:40].strip("-")
    if not slug:
        slug = uuid.uuid4().hex[:8]
    return f"ci-test-{slug}"
