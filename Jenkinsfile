pipeline {
  agent any

  options {
    timeout(time: 30, unit: 'MINUTES')
  }

  triggers {
    // PR/merge handled by the multibranch SCM webhook; this cron adds a nightly drift check.
    cron('H 2 * * *')
  }

  parameters {
    string(name: 'VAULT_ADDR_OVERRIDE', defaultValue: '', description: 'Override VAULT_ADDR')
    booleanParam(name: 'STRICT_MODE', defaultValue: false, description: 'Fail (not skip) on missing external deps')
    string(name: 'VENV_DIR', defaultValue: '/var/lib/jenkins/vault-ent-suite/venv', description: 'Stable, agent-writable path for the provisioned virtualenv (auto-created on first build)')
    string(name: 'PY_BASE', defaultValue: '/var/lib/jenkins/vault-ent-suite/python', description: 'Stable, agent-writable path where the vendored CPython runtime is extracted (the venv references it)')
    string(name: 'AREAS', defaultValue: '', description: 'Comma-separated area filter (e.g. "kv,transit,approle"); empty = run all available')
    string(name: 'VAULT_JWT_MOUNT', defaultValue: 'jwt', description: 'JWT auth mount path inside the parent namespace (e.g. "jwt-jenkins-ci")')
    string(name: 'VAULT_JWT_ROLE', defaultValue: 'test-runner', description: 'Vault JWT auth role name')
    booleanParam(name: 'VAULT_SKIP_VERIFY', defaultValue: false, description: 'INSECURE: skip Vault TLS verification. Prefer VAULT_CACERT for self-signed/internal CAs')
    string(name: 'VAULT_CACERT', defaultValue: '', description: 'Path on the agent to a CA/server cert bundle to trust (for self-signed or internal-CA Vault TLS)')
  }

  environment {
    // Falls back to a node/global VAULT_ADDR if no override; coerces an unset value to '' (not the
    // literal "null") so the Setup-stage guard below catches a missing address cleanly.
    VAULT_ADDR             = "${params.VAULT_ADDR_OVERRIDE ?: (env.VAULT_ADDR ?: '')}"
    STRICT_MODE            = "${params.STRICT_MODE}"
    VENV_DIR               = "${params.VENV_DIR}"
    PY_BASE                = "${params.PY_BASE}"
    AREAS                  = "${params.AREAS}"
    VAULT_PARENT_NAMESPACE = 'automation'
    VAULT_JWT_MOUNT        = "${params.VAULT_JWT_MOUNT}"
    VAULT_JWT_ROLE         = "${params.VAULT_JWT_ROLE}"
    // TLS trust for a self-signed / internal-CA Vault. Empty CACERT + skip=false => verify with
    // the system trust store (secure default; will fail closed against an untrusted cert).
    VAULT_SKIP_VERIFY      = "${params.VAULT_SKIP_VERIFY}"
    VAULT_CACERT           = "${params.VAULT_CACERT}"
    // Mints a short-lived JWT via the CloudBees OpenID Connect provider credential
    // (id 'oidc-jwt-provider', global scope). Its audience is set to VAULT_ADDR, so the Vault
    // JWT auth role 'test-runner' must set bound_audiences=$VAULT_ADDR to accept the token.
    CI_OIDC_TOKEN          = credentials('oidc-jwt-provider')
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Setup (provision venv if missing)') {
      steps {
        sh '''
          set -e
          : "${VAULT_ADDR:?VAULT_ADDR must be set -- pass the VAULT_ADDR_OVERRIDE parameter or set it in the node environment}"
          : "${CI_OIDC_TOKEN:?CI_OIDC_TOKEN empty -- check the 'oidc-jwt-provider' credential binding}"
          # Provision once per agent (idempotent): if the venv is missing or its deps don't import,
          # build it offline from the vendored CPython 3.11 + hash-locked wheels in vendor/.
          if [ -x "$VENV_DIR/bin/python3" ] && "$VENV_DIR/bin/python3" -c "import hvac, jwt, cryptography, pytest" >/dev/null 2>&1; then
            echo "venv present at $VENV_DIR -- skipping provisioning"
          else
            echo "venv missing/invalid at $VENV_DIR -- provisioning from vendored artifacts (first build on this agent)"
            VENV_DIR="$VENV_DIR" PY_BASE="$PY_BASE" bash scripts/provision-agent.sh
          fi
          . "$VENV_DIR/bin/activate"
          python3 -c "import sys; assert sys.version_info[:2]==(3,11), sys.version; print('python', sys.version.split()[0])"
          python3 -c "import hvac, jwt, cryptography, pytest; print('deps OK')"
        '''
      }
    }

    stage('Test') {
      steps {
        sh '''
          set -e
          . "$VENV_DIR/bin/activate"
          mkdir -p reports
          pytest \
            --junitxml=reports/junit.xml \
            --html=reports/report.html --self-contained-html
        '''
      }
    }
  }

  post {
    always {
      // lenient on purpose for bring-up: a Setup-stage failure shouldn't add a spurious
      // "no test results" error on top of the real one. Tighten to false once known-green.
      junit allowEmptyResults: true, testResults: 'reports/junit.xml'
      archiveArtifacts artifacts: 'reports/report.html', allowEmptyArchive: true
      // Optional in-UI HTML (requires the HTML Publisher plugin):
      // publishHTML(target: [reportDir: 'reports', reportFiles: 'report.html', reportName: 'Vault Suite'])
    }
  }
}
