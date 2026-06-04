# Vault-side prerequisites (admin runbook)

Everything the **Vault administrator** must create *once* before the CI suite can run. The suite
itself creates nothing permanent — it logs in, spins up a throwaway child namespace per build, tests
inside it, and tears it down. This document is the complete, copy-pasteable checklist.

> **Audience:** a Vault operator with admin/root on the cluster. Commands use the `vault` CLI; an
> equivalent Terraform sketch is at the end.

---

## 0. What the suite does (so the permissions make sense)

On each build, the `test-runner` identity:

1. Logs in to namespace **`automation`** via **JWT auth** using the CI's OIDC token.
2. Creates an ephemeral child namespace **`automation/ci-test-<build>`**.
3. Inside that child: enables a secrets engine, writes & reads a secret.
4. Tears the child namespace down (disables its mounts/auth, then deletes it).

So the identity needs exactly two things, both granted by a policy **created in `automation`**:

| Need | Vault path (relative to the `automation` namespace) |
|---|---|
| Manage ephemeral child namespaces | `sys/namespaces/ci-test-*` |
| Do anything **inside** those children | `ci-test-*` (the trailing `*` covers the child name *and* every sub-path) |

**The key namespace rule:** policy paths are evaluated *relative to the namespace the token lives in*.
The `test-runner` token lives in `automation`, so to act inside the child `ci-test-x` its policy paths
are prefixed with the child name (`ci-test-x/...`). This is why a bare `sys/mounts/*` would **not**
work — that would grant access to `automation`'s own mounts, not the child's.

---

## 1. Prerequisites

- **Vault Enterprise** (namespaces are an Enterprise feature) with a valid license.
- Admin/root token on the cluster (or on the parent under which `automation` will live).
- The cluster's TLS CA/server certificate, if it uses a self-signed/internal-CA cert — the CI agent
  must trust it (set `VAULT_CACERT`; see [README](../README.md) "Air-gapped dependency setup").
- The **CloudBees OIDC token's claims** in hand. Decode one to read them:

  ```bash
  # paste a token minted by the 'oidc-jwt-provider' credential
  python3 - <<'PY'
  import base64, json, sys
  tok = "PASTE_THE_JWT_HERE"
  payload = tok.split(".")[1]
  payload += "=" * (-len(payload) % 4)              # restore base64 padding
  print(json.dumps(json.loads(base64.urlsafe_b64decode(payload)), indent=2))
  PY
  ```

  Note these fields — you will need them in Step 4:
  - `iss`  → the OIDC **issuer** (used to configure JWT signature verification)
  - `aud`  → the **audience** (must equal your `VAULT_ADDR`, per the credential binding)
  - `sub`  → the **subject** (identifies the CI job; used for `user_claim`/`bound_subject`)

---

## 2. Create the `automation` namespace

Run from the root (or whichever parent should own it):

```bash
vault namespace create automation
```

All remaining steps target `-namespace=automation`.

---

## 3. Enable and configure JWT auth

The suite defaults to mount path `jwt`, but your environment uses **`jwt-jenkins-ci`** — set the
`VAULT_JWT_MOUNT` build parameter to match whatever you choose here.

```bash
# Enable the JWT auth method at the mount the pipeline points to
vault auth enable -namespace=automation -path=jwt-jenkins-ci jwt
```

Configure how Vault verifies the token's signature. Use OIDC discovery if the CloudBees provider
exposes `/.well-known/openid-configuration`:

```bash
vault write -namespace=automation auth/jwt-jenkins-ci/config \
  oidc_discovery_url="<iss from the decoded token>" \
  default_role="test-runner"
```

If discovery isn't available, point Vault at the JWKS endpoint instead:

```bash
vault write -namespace=automation auth/jwt-jenkins-ci/config \
  jwks_url="https://<cloudbees-controller>/oidc/jwks" \
  bound_issuer="<iss from the decoded token>" \
  default_role="test-runner"
```

---

## 4. Write the `test-runner` policy

This is the heart of the setup. Create it **in `automation`**:

```bash
vault policy write -namespace=automation test-runner - <<'EOF'
# --- Lifecycle of the ephemeral child namespaces ---------------------------
# Create/delete automation/ci-test-<build>. These paths are in automation's own
# namespace, so they are NOT prefixed with a child name.
path "sys/namespaces/ci-test-*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}

# --- Everything the tests do INSIDE an ephemeral child namespace -----------
# Evaluated relative to the token's namespace (automation), so child operations
# are addressed as "ci-test-<build>/...". The trailing * matches the child name
# AND every sub-path under it (sys/mounts, sys/auth, <engine>/data/*, etc.),
# which is exactly the scope the suite needs and nothing outside ci-test-*.
path "ci-test-*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
EOF
```

**Why these two stanzas (and nothing more):**
- `sys/namespaces/ci-test-*` — lets the suite create and delete only namespaces whose name starts
  with `ci-test-` (matches [`lib/naming.py`](../lib/naming.py), which always names them `ci-test-<slug>`).
  It cannot touch `automation` itself or sibling namespaces.
- `ci-test-*` — the only grant for in-child work. Because a trailing `*` also matches `/`, this one
  line covers `ci-test-x/sys/mounts/*` (enable/disable engines), `ci-test-x/sys/auth*` (cleanup),
  and `ci-test-x/<mount>/data/*` (KV read/write) — scoped to ephemeral namespaces only.

> This is intentionally least-privilege: the token can manage `ci-test-*` namespaces and operate
> freely *within* them, but has no standing access to `automation` or any other namespace's data.

---

## 5. Create the `test-runner` JWT role

Bind the role to your CI's token claims. Replace the placeholders using the values you decoded in
Step 1.

```bash
vault write -namespace=automation auth/jwt-jenkins-ci/role/test-runner \
  role_type="jwt" \
  user_claim="sub" \
  bound_audiences="<VAULT_ADDR>" \
  bound_subject="<sub claim from the CI token>" \
  token_policies="test-runner" \
  token_ttl="30m" \
  token_max_ttl="45m"
```

Field-by-field:

| Field | Value / why |
|---|---|
| `role_type` | `jwt` — the CI presents an already-minted token (machine auth), not an interactive OIDC flow. |
| `user_claim` | Claim that names the principal; usually `sub`. Must exist in the token. |
| `bound_audiences` | **Must equal your `VAULT_ADDR`** — the `oidc-jwt-provider` credential sets the token's `aud` to `VAULT_ADDR`. Mismatch → `invalid audience`. |
| `bound_subject` | Optional but recommended: pin to the exact `sub` so only your pipeline can assume the role. Omit to accept any subject from this issuer. |
| `token_policies` | `test-runner` (the policy from Step 4). |
| `token_ttl` / `token_max_ttl` | Must outlast a build. The pipeline times out at 30 min, so `30m`/`45m` is safe. |

**Hardening (optional):** restrict to a specific repo/branch/job with `bound_claims`, e.g.
`bound_claims='{"<claim>":"<value>"}'`, once you've identified a stable claim in the token.

---

## 6. Verify before running CI

```bash
# 1) Confirm JWT login works and yields a token with the right policy
VAULT_TOKEN=$(vault write -namespace=automation -field=token \
  auth/jwt-jenkins-ci/login role=test-runner jwt="<a fresh CI token>")
vault token lookup -namespace=automation "$VAULT_TOKEN"   # should list policy "test-runner"

# 2) Confirm the token can create a child namespace and work inside it
VAULT_TOKEN="$VAULT_TOKEN" vault namespace create -namespace=automation ci-test-smoke
VAULT_TOKEN="$VAULT_TOKEN" vault secrets enable -namespace=automation/ci-test-smoke -path=kv kv-v2
VAULT_TOKEN="$VAULT_TOKEN" vault kv put -namespace=automation/ci-test-smoke kv/hello x=1
VAULT_TOKEN="$VAULT_TOKEN" vault kv get -namespace=automation/ci-test-smoke kv/hello

# 3) Clean up the smoke namespace
VAULT_TOKEN="$VAULT_TOKEN" vault secrets disable -namespace=automation/ci-test-smoke kv
VAULT_TOKEN="$VAULT_TOKEN" vault namespace delete -namespace=automation ci-test-smoke
```

If all three succeed, the suite will pass against this cluster.

---

## 7. CI parameters that must match this setup

Set these on the Jenkins job (or as env) so the suite lines up with what you built above:

| Parameter | Value |
|---|---|
| `VAULT_ADDR` (or `VAULT_ADDR_OVERRIDE`) | your cluster URL — **must equal** the role's `bound_audiences` |
| `VAULT_JWT_MOUNT` | `jwt-jenkins-ci` (the Step 3 mount) |
| `VAULT_JWT_ROLE` | `test-runner` |
| `VAULT_PARENT_NAMESPACE` | `automation` (the suite's default) |
| `VAULT_CACERT` *or* `VAULT_SKIP_VERIFY` | trust the cluster's TLS cert (prefer `VAULT_CACERT`) |

`CI_OIDC_TOKEN` is injected automatically by the `oidc-jwt-provider` credential — no action needed.

---

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `invalid audience (aud) claim` | Role's `bound_audiences` ≠ `VAULT_ADDR`. Make them identical. |
| `permission denied` creating namespace | Policy missing/incorrect, or `VAULT_JWT_MOUNT`/`VAULT_JWT_ROLE` point at the wrong place. Re-check Steps 4–5. |
| `permission denied` enabling engine / writing KV in the child | The `ci-test-*` stanza is missing or was written with a leading namespace prefix. It must be exactly `path "ci-test-*"` in the `automation` policy. |
| `self-signed certificate in certificate chain` | Agent doesn't trust Vault's TLS. Set `VAULT_CACERT` (preferred) or `VAULT_SKIP_VERIFY=true`. |
| `1 error` in the summary on a Vault test | Means a fixture failed (login/TLS/namespace). The suite now surfaces these as failures — read the error above the summary. |
| namespace won't delete | It still has mounts; the suite disables them first. If a prior run crashed, delete leftover `automation/ci-test-*` namespaces manually. |

---

## Appendix: Terraform equivalent (sketch)

```hcl
resource "vault_namespace" "automation" { path = "automation" }

resource "vault_jwt_auth_backend" "ci" {
  namespace          = vault_namespace.automation.path_fq
  path               = "jwt-jenkins-ci"
  oidc_discovery_url = var.oidc_issuer
  default_role       = "test-runner"
}

resource "vault_policy" "test_runner" {
  namespace = vault_namespace.automation.path_fq
  name      = "test-runner"
  policy    = <<EOT
path "sys/namespaces/ci-test-*" { capabilities = ["create","read","update","delete","list","sudo"] }
path "ci-test-*"                { capabilities = ["create","read","update","delete","list"] }
EOT
}

resource "vault_jwt_auth_backend_role" "test_runner" {
  namespace       = vault_namespace.automation.path_fq
  backend         = vault_jwt_auth_backend.ci.path
  role_name       = "test-runner"
  role_type       = "jwt"
  user_claim      = "sub"
  bound_audiences = [var.vault_addr]
  token_policies  = ["test-runner"]
  token_ttl       = 1800
  token_max_ttl   = 2700
}
```
