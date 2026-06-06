pipeline {
  agent any

  parameters {
    booleanParam(
      name: 'RUN_LINT',
      defaultValue: true,
      description: 'Run flake8 lint checks on every service.'
    )
    booleanParam(
      name: 'RUN_UNIT_TESTS',
      defaultValue: true,
      description: 'Run per-service unit tests (pytest, 80% coverage gate).'
    )
    booleanParam(
      name: 'DEPLOY',
      defaultValue: true,
      description: 'Build images and start all services with Docker Compose.'
    )
    string(
      name: 'NGINX_PORT',
      defaultValue: '18080',
      description: 'Host port nginx is mapped to (matches FLOWDESK_HTTP_PORT in docker-compose.yml).'
    )
  }

  options {
    timestamps()
    timeout(time: 1, unit: 'HOURS')
    buildDiscarder(logRotator(numToKeepStr: '10'))
  }

  environment {
    SERVICES = 'auth-service workflow-service approval-service notification-service analytics-service'
    COMPOSE_PROJECT_NAME = 'flowdesk'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Lint') {
      when {
        expression { return params.RUN_LINT }
      }
      steps {
        sh '''
          set -e
          for svc in $SERVICES; do
            python3 -m venv services/$svc/venv
            . services/$svc/venv/bin/activate
            pip install --upgrade pip
            pip install -r services/$svc/requirements.txt flake8
            flake8 services/$svc/apps --max-line-length=140 --exclude=migrations
            deactivate
          done
        '''
      }
    }

    stage('Unit Tests') {
      when {
        expression { return params.RUN_UNIT_TESTS }
      }
      steps {
        sh '''
          set -e
          for svc in $SERVICES; do
            cd services/$svc
            if [ ! -x venv/bin/python ]; then
              python3 -m venv venv
              . venv/bin/activate
              pip install --upgrade pip
              pip install -r requirements.txt
            else
              . venv/bin/activate
            fi
            pytest tests --cov=apps --cov-fail-under=80
            deactivate
            cd ../..
          done
        '''
      }
    }

    stage('Deploy') {
      when {
        expression { return params.DEPLOY }
      }
      steps {
        sh '''
          set -e
          if ! command -v docker-compose >/dev/null 2>&1; then
            echo "Downloading docker-compose v2 binary..."
            arch=$(uname -m)
            curl -fsSL \
              "https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-${arch}" \
              -o /usr/local/bin/docker-compose \
            || curl -fsSL \
              "https://get.daocloud.io/docker/compose/releases/download/v2.27.0/docker-compose-linux-${arch}" \
              -o /usr/local/bin/docker-compose
            chmod +x /usr/local/bin/docker-compose
          fi
          docker-compose -f docker-compose.yml -f docker-compose.ci.yml up -d --build --remove-orphans
        '''
      }
    }

    stage('Smoke Tests') {
      when {
        expression { return params.DEPLOY }
      }
      steps {
        sh '''
          set -e
          base_url="http://localhost:${NGINX_PORT}"
          max_wait=180
          elapsed=0

          echo "Waiting for nginx gateway..."
          until curl -fsS "${base_url}/" > /dev/null 2>&1; do
            if [ "$elapsed" -ge "$max_wait" ]; then
              echo "Timeout: nginx did not respond within ${max_wait}s"
              docker logs flowdesk-nginx --tail=40 2>&1 || true
              docker logs flowdesk-auth --tail=20 2>&1 || true
              exit 1
            fi
            sleep 5
            elapsed=$((elapsed + 5))
          done

          echo "Checking service health endpoints..."
          curl -fsS "${base_url}/health/auth/"
          curl -fsS "${base_url}/health/workflows/"
          curl -fsS "${base_url}/health/approvals/"
          curl -fsS "${base_url}/health/analytics/"
          curl -fsS "${base_url}/health/notifications/"
          echo "All smoke tests passed."
        '''
      }
    }
  }

  post {
    failure {
      sh '''
        echo "=== Container status ==="
        docker ps --filter "label=com.docker.compose.project=flowdesk" || true
        echo "=== Recent logs ==="
        for name in flowdesk-auth flowdesk-workflow flowdesk-approval flowdesk-notification flowdesk-analytics flowdesk-nginx flowdesk-postgres flowdesk-redis; do
          echo "--- $name ---"
          docker logs "$name" --tail=30 2>&1 || true
        done
      '''
    }
    always {
      cleanWs()
    }
  }
}
