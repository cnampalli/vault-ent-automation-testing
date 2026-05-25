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
    string(name: 'WHEELHOUSE_URL', defaultValue: 'http://WEBHOST/wheelhouse.tar.gz', description: 'Air-gapped wheel bundle URL')
  }

  environment {
    // Falls back to a node/global VAULT_ADDR if no override; coerces an unset value to '' (not the
    // literal "null") so the Setup-stage guard below catches a missing address cleanly.
    VAULT_ADDR             = "${params.VAULT_ADDR_OVERRIDE ?: (env.VAULT_ADDR ?: '')}"
    STRICT_MODE            = "${params.STRICT_MODE}"
    VAULT_PARENT_NAMESPACE = 'automation'
    VAULT_JWT_MOUNT        = 'jwt'
    VAULT_JWT_ROLE         = 'test-runner'
    // CI_OIDC_TOKEN is injected by the platform's OIDC step/credential (open item in spec section 3)
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Setup (offline deps)') {
      steps {
        sh '''
          set -e
          : "${VAULT_ADDR:?VAULT_ADDR must be set -- pass the VAULT_ADDR_OVERRIDE parameter or set it in the node environment}"
          : "${CI_OIDC_TOKEN:?CI_OIDC_TOKEN must be injected by the platform OIDC credential step}"
          curl -fSL "$WHEELHOUSE_URL" -o wheelhouse.tar.gz
          tar xzf wheelhouse.tar.gz
          python3 -m venv .venv
          . .venv/bin/activate
          python3 -m pip install --no-index --find-links=./wheelhouse -r requirements.txt
          python3 -c "import hvac, jwt, cryptography, pytest; print('deps OK')"
        '''
      }
    }

    stage('Test') {
      steps {
        sh '''
          set -e
          . .venv/bin/activate
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
      junit allowEmptyResults: true, testResults: 'reports/junit.xml'
      archiveArtifacts artifacts: 'reports/report.html', allowEmptyArchive: true
      // Optional in-UI HTML (requires the HTML Publisher plugin):
      // publishHTML(target: [reportDir: 'reports', reportFiles: 'report.html', reportName: 'Vault Suite'])
    }
  }
}
