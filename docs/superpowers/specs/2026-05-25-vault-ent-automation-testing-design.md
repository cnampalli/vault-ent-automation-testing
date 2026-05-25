# Vault Enterprise Automation Test Suite — Design

**Date:** 2026-05-25
**Status:** Approved (pending spec review)
**Owner:** nampallic@gmail.com

---

## 1. Purpose

A Python/pytest **functional** test suite that runs in **CloudBees CI (Jenkins)** against a
**pre-existing, externally-managed Vault Enterprise cluster**. Each run creates its own
ephemeral, isolated namespace, exercises a defined set of authentication methods and secret
engines **deeply** (happy-path + negative + policy/ACL enforcement + credential lifecycle +
isolation), cleans up after itself, and reports clear **passed / failed / skipped** counts in
three complementary ways.

### Success criteria
- A CI operator can tell at a glance, from the build, how many test cases passed, failed, and were skipped.
- The suite never holds full Vault-admin privilege; it is confined by Vault to a single tenant namespace.
- The suite is resilient to absent external integrations (skips with a clear reason, not red builds).
- Builds run on an **air-gapped** CI agent (no direct internet) using pre-staged dependencies.
- The suite is the validation mechanism itself: because raw output/back-end access cannot be shared,
  correctness is proven by running the suite in CI, so an early end-to-end "walking skeleton" is essential.

---

## 2. Scope

### Auth methods
- **AppRole** — no external dependency.
- **JWT/OIDC** — configured against an **existing OIDC discovery URL**; login performed with a JWT
  from that provider (the CloudBees CI OIDC token, via a test role bound to its claims). In-test
  RSA-keypair + `jwt_validation_pubkeys` path retained as a documented fallback.
- **LDAP** — requires a reachable LDAP/AD server (precondition-gated).
- **Kubernetes** — requires a token-reviewer JWT + cluster CA + host (precondition-gated).

### Secret engines
- **KV v2** — no external dependency.
- **Transit** — no external dependency.
- **PKI** — **two flows**:
  - **Built-in PKI** (Vault is the CA) — always-on, no external dependency.
  - **Venafi PKI plugin** (Vault delegates issuance to Venafi TPP/Cloud) — precondition-gated on
    Venafi reachability + the plugin being registered/enabled on the cluster.
- **Database** — dynamic credential generation; requires a reachable database (precondition-gated).
- **SSH** — **CA mode** (sign a public key, verify the certificate) is no-dep; full end-to-end SSH
  into a host is precondition-gated on an SSH target.

### Out of scope (YAGNI for now)
- Performance/load testing, chaos/HA failover, replication, raft storage internals.
- Managing Vault's lifecycle (the cluster is externally managed).
- UI testing.

---

## 3. Environment & Assumptions (source of truth = user inputs)

- Target is a **pre-existing Vault Enterprise cluster**; the suite never starts/stops it.
- CloudBees CI authenticates to Vault via **OIDC/JWT**; its default identity can configure all of Vault.
- The suite uses a **scoped least-privilege identity** instead (see §4).
- The **CI agent is air-gapped**; a **webhost with internet** stages Python dependencies (see §8).
- Network reachability from the CI agent to `VAULT_ADDR` is confirmed available.

### Open validation items (user to confirm on CloudBCI — inputs taken as truth)
- **(A) Pipeline claim:** the exact JWT claim name + value that uniquely identifies the test pipeline
  (decode a pipeline token: `echo $TOKEN | cut -d. -f2 | base64 -d`). Goes into the role `bound_claims`.
- Agent `python3` version + OS/arch (for wheelhouse platform matching).
- Jenkins plugins present: **JUnit**, **HTML Publisher**.
- How the pipeline receives its CI OIDC token (env var / step / credential).
- Connection params for the gated areas to be run live: LDAP, Database, Venafi, Kubernetes, SSH target.

---

## 4. Authentication & Isolation Model

### Delegated namespace admin (least privilege, enforced by Vault)
A **one-time admin setup** (performed with the existing full-admin OIDC identity) creates a single
parent namespace whose admin is delegated to the test runner. Everything the suite does is physically
confined under it.

```hcl
# 1. Parent namespace = the blast-radius boundary
vault namespace create automation

# 2. Scoped policy, INSIDE automation (paths relative to automation/)
vault policy write -namespace=automation test-runner - <<'EOF'
  # create/delete only ci-test-* child namespaces
  path "sys/namespaces/ci-test-*"     { capabilities = ["create","read","update","delete","list"] }
  # full control INSIDE those children only
  path "ci-test-+/sys/mounts/*"       { capabilities = ["create","read","update","delete","list","sudo"] }
  path "ci-test-+/sys/auth/*"         { capabilities = ["create","read","update","delete","sudo"] }
  path "ci-test-+/sys/policies/acl/*" { capabilities = ["create","read","update","delete","list"] }
  path "ci-test-+/*"                  { capabilities = ["create","read","update","delete","list"] }
EOF

# 3. Dedicated JWT auth mount INSIDE automation, bound to ONLY the test pipeline
vault auth enable -namespace=automation -path=jwt jwt
vault write -namespace=automation auth/jwt/config \
    oidc_discovery_url="<existing-OIDC-discovery-url>" \
    bound_issuer="<issuer>"
vault write -namespace=automation auth/jwt/role/test-runner \
    role_type="jwt" user_claim="sub" \
    bound_audiences="<aud>" bound_claims_type="glob" \
    bound_claims='{"<pipeline-claim>":"<your/test/pipeline/path>"}' \
    token_policies="test-runner" token_ttl="1h"
```

Vault enforces the boundary: a `test-runner` token **cannot** reach the root namespace or any sibling
tenant — independent of test-code behaviour. The scoped JWT mount lives **inside** `automation/`,
fully separate from the root full-admin JWT mount.

### Per-run flow
1. Session fixture logs in: `automation/auth/jwt/login` with `role=test-runner` + the CI OIDC token → short-lived scoped token.
2. Session fixture creates `automation/ci-test-<build-id>` (`build-id` from `BUILD_TAG`, fallback uuid).
3. Each test enables its engine/auth at a **unique path** inside the ephemeral namespace (per-test isolation).
4. Teardown (`lib/cleanup.py`, runs even on failure): revoke leases → disable secret engines → disable
   auth methods → delete child namespace. (Vault refuses to delete a non-empty namespace, so order matters.)

---

## 5. Repository Layout

```
vault-ent-automation-testing/
├── Jenkinsfile                 # CI pipeline (triggers, stages, publish)
├── requirements.txt            # hvac, pytest, pytest-html, pyjwt[crypto], cryptography
├── pyproject.toml              # pytest config + area markers
├── conftest.py                 # session fixtures: scoped auth, ephemeral namespace, terminal-summary hook
├── config/
│   └── settings.py             # all config from env vars (12-factor); per-dependency optional config
├── lib/
│   ├── vault_client.py         # namespace-aware hvac wrapper
│   ├── preconditions.py        # dependency probes -> pytest skip-with-reason markers
│   └── cleanup.py              # best-effort recursive namespace teardown
├── tests/
│   ├── auth/
│   │   ├── test_approle.py
│   │   ├── test_ldap.py
│   │   ├── test_jwt_oidc.py
│   │   └── test_kubernetes.py
│   ├── secrets/
│   │   ├── test_kv_v2.py
│   │   ├── test_transit.py
│   │   ├── test_database.py
│   │   ├── test_pki_builtin.py
│   │   ├── test_pki_venafi.py
│   │   └── test_ssh.py
│   └── namespace/
│       └── test_namespace_isolation.py
└── reports/                    # junit.xml + report.html (gitignored)
```

---

## 6. Test Design — no-dep vs. precondition-gated

Even with **zero** external integrations wired up, the suite still delivers real functional coverage
of KV v2, Transit, AppRole, JWT auth, built-in PKI, SSH-CA, and namespace isolation. Gated areas light
up as their dependencies become available; when absent they report **SKIPPED with a clear reason**.

| Area | Always-on (no external dep) | Gated on external dep |
|---|---|---|
| KV v2 | write/read/version/delete/undelete/metadata | — |
| Transit | create key / encrypt / decrypt / rotate / rewrap / sign / verify | — |
| AppRole | role -> secret-id -> login -> policy checks | — |
| JWT/OIDC auth | configure vs existing OIDC discovery URL; login w/ CI token (RSA-keypair fallback) | (optional) dedicated test IdP |
| Built-in PKI | root/intermediate CA -> role -> issue -> verify -> revoke -> CRL | — |
| SSH | CA mode: configure CA, sign public key, verify certificate | SSH into a real host (target + vault-ssh-helper) |
| Namespace isolation | child namespace CRUD + cross-namespace deny assertions | — |
| Venafi PKI | — | Venafi TPP/Cloud + plugin registered |
| LDAP | — | LDAP/AD server |
| Kubernetes | — | token reviewer + SA token + cluster CA + host |
| Database | — | reachable database |

### Depth per area (deep coverage)
For each area: happy-path, key **negative** cases (wrong creds rejected, denied path -> 403, revoked
token unusable), **policy/ACL enforcement**, **credential lifecycle** (renew / revoke / expiry),
**rotation/versioning** where applicable, and **cross-namespace isolation** assertions.

### Precondition gating
`lib/preconditions.py` exposes probes (env presence + lightweight connectivity check). Each gated test
module is decorated so an unmet precondition yields `pytest.skip(reason=...)` with an explicit message
(e.g. `"LDAP_URL not set"`), surfaced as SKIPPED in JUnit/HTML/console.

---

## 7. Reporting

A **single** `pytest` invocation produces all three outputs (keeps aggregate counts clean):

- `--junitxml=reports/junit.xml` → Jenkins `junit` step → total/passed/failed/skipped counts,
  per-test drill-down, cross-build failure trends, build marked **UNSTABLE** on failures.
- `--html=reports/report.html --self-contained-html` → archived build **artifact** (and optional
  HTML Publisher for in-UI viewing).
- `pytest_terminal_summary` hook in `conftest.py` → **console summary block** grouped by area in the
  raw build log:

```
===== Vault Ent Functional Suite =====
AppRole .............. 9 passed
JWT/OIDC ............. 7 passed
KV v2 ................ 11 passed
Transit .............. 8 passed
PKI (built-in) ....... 6 passed
PKI (Venafi) ......... SKIPPED (VENAFI_URL not set)
LDAP ................. SKIPPED (LDAP_URL not set)
Database ............. SKIPPED (DB_URL not set)
Kubernetes ........... SKIPPED (K8S_HOST not set)
SSH .................. 5 passed
Namespace isolation .. 4 passed
--------------------------------------
TOTAL: 60 passed, 0 failed, 4 skipped
```

---

## 8. Air-gapped Dependency Installation (offline wheelhouse)

The CI agent has **no direct internet**; a **webhost with internet** stages wheels.

**Critical:** `cryptography` is a compiled wheel — it must match the agent's **OS + CPU arch + Python
version**. Run the download on a host matching the agent, or force matching wheels with explicit flags.

Capture agent platform (on the CI agent):
```bash
python3 --version        # e.g. 3.11.x -> cp311
uname -s -m              # e.g. Linux x86_64 -> manylinux2014_x86_64
```

On the webhost (has internet):
```bash
# requirements.txt: hvac / pytest / pytest-html / pyjwt[crypto] / cryptography
pip download -r requirements.txt -d wheelhouse/                       # (a) matching host
# (b) non-matching host: force the agent's platform
pip download -r requirements.txt -d wheelhouse/ --only-binary=:all: \
    --implementation cp --python-version 311 --abi cp311 --platform manylinux2014_x86_64
tar czf wheelhouse.tar.gz wheelhouse/                                 # publish on webhost HTTP path
```

On the CI agent (Setup stage):
```bash
curl -fSL http://<webhost>/wheelhouse.tar.gz -o wheelhouse.tar.gz && tar xzf wheelhouse.tar.gz
python3 -m venv .venv && . .venv/bin/activate
pip install --no-index --find-links=./wheelhouse -r requirements.txt
python -c "import hvac, jwt, cryptography, pytest; print('deps OK')" && pytest --version
```

Variant (webhost serves `wheelhouse/` over HTTP, no tarball):
```bash
pip install --no-index --find-links=http://<webhost>/wheelhouse/ --trusted-host <webhost> -r requirements.txt
```

Steps to build the wheelhouse are one-time prep (re-run when deps change); the agent-side steps become
the Jenkinsfile **Setup** stage.

---

## 9. CI Pipeline (Jenkinsfile)

- **Agent:** node/pod with `python3` + `pip` (and optionally the `vault` CLI).
- **Triggers:** SCM webhook on **PR/merge** (validates the suite itself) **+** nightly **cron**
  (catches cluster drift/regressions).
- **Parameters:** `VAULT_ADDR` override, `STRICT_MODE` (default lenient = skip-on-missing; can flip to
  fail-on-missing), `AREAS` (subset selection).
- **Stages:** Checkout → Setup (venv + offline install per §8) → Authenticate (scoped JWT login) →
  Test (single pytest run) → Publish.
- **`post { always { … } }`:** `junit 'reports/junit.xml'` + `archiveArtifacts 'reports/report.html'`
  (+ optional HTML Publisher). Build → **UNSTABLE** on test failures; **FAILED** only on infra/auth errors.

---

## 10. Phased Rollout (basis for the implementation plan)

- **Phase 0 — Walking skeleton:** scaffolding, `config/settings.py`, scoped-auth + ephemeral-namespace
  fixtures, reporting plumbing (JUnit + HTML + console hook), and **one trivial KV test** proving the
  full pipeline end-to-end in CloudBCI. Validate the offline wheelhouse install here.
- **Phase 1 — No-dep deep coverage:** KV v2, Transit, AppRole, JWT (OIDC URL), built-in PKI, SSH-CA,
  namespace isolation.
- **Phase 2 — Gated areas:** LDAP, Kubernetes, Database, Venafi PKI — each precondition-gated.
- **Phase 3 — Depth & hardening:** lifecycle/rotation/policy-enforcement across all areas,
  console-summary polish, parameterization, nightly cron tuning.

---

## 11. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `cryptography` wheel/platform mismatch on agent | Download on matching host or use explicit `--platform/--abi/--python-version`; verify import in Setup. |
| Namespace delete fails because mounts/leases remain | `lib/cleanup.py` revokes leases + disables mounts/auth before namespace delete; teardown always runs. |
| Scoped policy too narrow/broad | Validate against real run in Phase 0; tighten `ci-test-+` paths iteratively. |
| Pipeline claim value unknown | Open item (A): user decodes a real token and supplies claim name/value. |
| Cannot share back-end output | Suite is the validation; Phase 0 walking skeleton proves the loop early. |
| Shared cluster contamination | Ephemeral per-run namespace + unique per-test mount paths + always-on teardown. |
```