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
    string(name: 'VENV_DIR', defaultValue: '/opt/vault-ent-suite/venv', description: 'Path to the pre-provisioned virtualenv on the agent (see scripts/provision-agent.sh)')
    string(name: 'AREAS', defaultValue: '', description: 'Comma-separated area filter (e.g. "kv,transit,approle"); empty = run all available')
  }

  environment {
    // Falls back to a node/global VAULT_ADDR if no override; coerces an unset value to '' (not the
    // literal "null") so the Setup-stage guard below catches a missing address cleanly.
    VAULT_ADDR             = "${params.VAULT_ADDR_OVERRIDE ?: (env.VAULT_ADDR ?: '')}"
    STRICT_MODE            = "${params.STRICT_MODE}"
    VENV_DIR               = "${params.VENV_DIR}"
    AREAS                  = "${params.AREAS}"
    VAULT_PARENT_NAMESPACE = 'automation'
    VAULT_JWT_MOUNT        = 'jwt'
    VAULT_JWT_ROLE         = 'test-runner'
    // CI_OIDC_TOKEN is injected by the platform's OIDC step/credential (open item in spec section 3)
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Setup (verify pre-provisioned env)') {
      steps {
        sh '''
          set -e
          : "${VAULT_ADDR:?VAULT_ADDR must be set -- pass the VAULT_ADDR_OVERRIDE parameter or set it in the node environment}"
          : "${CI_OIDC_TOKEN:?CI_OIDC_TOKEN must be injected by the platform OIDC credential step}"
          if [ ! -d "$VENV_DIR" ]; then
            echo "Agent not provisioned: virtualenv not found at $VENV_DIR." >&2
            echo "Provision it once with scripts/provision-agent.sh (see README), or bake it into the agent image." >&2
            exit 1
          fi
          . "$VENV_DIR/bin/activate"
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
