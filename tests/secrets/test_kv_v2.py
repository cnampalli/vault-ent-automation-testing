import uuid
import pytest

pytestmark = pytest.mark.area("KV v2")


def test_kv_v2_write_then_read(ns_client):
    mount = f"kv-{uuid.uuid4().hex[:8]}"
    ns_client.hvac.sys.enable_secrets_engine(
        backend_type="kv", path=mount, options={"version": "2"}
    )

    ns_client.hvac.secrets.kv.v2.create_or_update_secret(
        path="smoke", secret={"hello": "world"}, mount_point=mount
    )
    read = ns_client.hvac.secrets.kv.v2.read_secret_version(
        path="smoke", mount_point=mount
    )

    assert read["data"]["data"] == {"hello": "world"}
