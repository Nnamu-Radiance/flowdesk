pipeline {
  agent any

  parameters {
    string(
      name: 'SMOKE_BASE_URL',
      defaultValue: 'http://localhost',
      description: 'Externally reachable host/base URL for deployed smoke tests, for example http://flowdesk.local or http://127.0.0.1.'
    )
    string(
      name: 'SMOKE_HOST_HEADER',
      defaultValue: 'flowdesk.local',
      description: 'Host header used by smoke tests when reaching the ingress by IP or localhost.'
    )
  }

  options {
    timestamps()
    timeout(time: 1, unit: 'HOURS')
    buildDiscarder(logRotator(numToKeepStr: '10'))
  }

  environment {
    SERVICES = 'auth-service workflow-service approval-service notification-service analytics-service'
    REGISTRY = 'docker.io'
    IMAGE_NAMESPACE = 'flowdesk'
    IMAGE_TAG = "${BUILD_NUMBER}"
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Lint') {
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
    steps {
        sh '''
            set -e
            for svc in $SERVICES; do
                cd services/$svc
                . venv/bin/activate
                pytest tests --cov=apps --cov-fail-under=80
                deactivate
                cd ../..
            done
        '''
    }
}

    stage('Build Docker Images') {
      steps {
        sh '''
          set -e
          for svc in $SERVICES; do
            docker build --network=host -t ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:${IMAGE_TAG} services/$svc
            docker tag ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:${IMAGE_TAG} ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:latest
          done
        '''
      }
    }

    stage('Push to Registry') {
      steps {
        sh '''
          set -e
          if [ -n "${DOCKER_CREDENTIALS_USR:-}" ]; then
            echo "${DOCKER_CREDENTIALS_PSW}" | docker login -u "${DOCKER_CREDENTIALS_USR}" --password-stdin
          fi
          for svc in $SERVICES; do
            docker push ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:${IMAGE_TAG}
            docker push ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:latest
          done
        '''
      }
    }

    stage('Deploy to Kubernetes') {
      steps {
        sh '''
          kubectl apply -f k8s/namespace.yaml
          kubectl apply -f k8s/configmap.yaml
          kubectl apply -f k8s/secret.yaml
          kubectl apply -f k8s/postgres.yaml
          kubectl apply -f k8s/redis.yaml
          kubectl apply -f k8s/auth-service/
          kubectl apply -f k8s/workflow-service/
          kubectl apply -f k8s/approval-service/
          kubectl apply -f k8s/notification-service/
          kubectl apply -f k8s/analytics-service/
          kubectl apply -f k8s/celery-worker.yaml
          kubectl apply -f k8s/celery-beat.yaml
          kubectl apply -f k8s/nginx/
          kubectl apply -f k8s/ingress.yaml

          kubectl -n flowdesk set image deployment/auth-service auth-service=${REGISTRY}/${IMAGE_NAMESPACE}/auth-service:${IMAGE_TAG}
          kubectl -n flowdesk set image deployment/workflow-service workflow-service=${REGISTRY}/${IMAGE_NAMESPACE}/workflow-service:${IMAGE_TAG}
          kubectl -n flowdesk set image deployment/approval-service approval-service=${REGISTRY}/${IMAGE_NAMESPACE}/approval-service:${IMAGE_TAG}
          kubectl -n flowdesk set image deployment/notification-service notification-service=${REGISTRY}/${IMAGE_NAMESPACE}/notification-service:${IMAGE_TAG}
          kubectl -n flowdesk set image deployment/analytics-service analytics-service=${REGISTRY}/${IMAGE_NAMESPACE}/analytics-service:${IMAGE_TAG}
          kubectl -n flowdesk set image deployment/celery-worker celery-workflow=${REGISTRY}/${IMAGE_NAMESPACE}/workflow-service:${IMAGE_TAG} celery-approval=${REGISTRY}/${IMAGE_NAMESPACE}/approval-service:${IMAGE_TAG} celery-notification=${REGISTRY}/${IMAGE_NAMESPACE}/notification-service:${IMAGE_TAG}
          kubectl -n flowdesk set image deployment/celery-beat celery-beat=${REGISTRY}/${IMAGE_NAMESPACE}/approval-service:${IMAGE_TAG}
          kubectl -n flowdesk rollout restart deployment/nginx

          kubectl -n flowdesk rollout status statefulset/postgres --timeout=180s
          kubectl -n flowdesk rollout status deployment/redis --timeout=180s
          kubectl -n flowdesk rollout status deployment/auth-service --timeout=300s
          kubectl -n flowdesk rollout status deployment/workflow-service --timeout=300s
          kubectl -n flowdesk rollout status deployment/approval-service --timeout=300s
          kubectl -n flowdesk rollout status deployment/notification-service --timeout=300s
          kubectl -n flowdesk rollout status deployment/analytics-service --timeout=300s
          kubectl -n flowdesk rollout status deployment/celery-worker --timeout=300s
          kubectl -n flowdesk rollout status deployment/celery-beat --timeout=300s
          kubectl -n flowdesk rollout status deployment/nginx --timeout=180s
        '''
      }
    }

    stage('Smoke Tests') {
      steps {
        sh '''
          set -e
          base_url="${SMOKE_BASE_URL%/}"
          host_header="${SMOKE_HOST_HEADER:-flowdesk.local}"

          curl -fsS -H "Host: ${host_header}" "${base_url}/"
          curl -fsS -H "Host: ${host_header}" "${base_url}/health/auth/"
          curl -fsS -H "Host: ${host_header}" "${base_url}/health/workflow/"
          curl -fsS -H "Host: ${host_header}" "${base_url}/health/approval/"
          curl -fsS -H "Host: ${host_header}" "${base_url}/health/notification/"
          curl -fsS -H "Host: ${host_header}" "${base_url}/health/analytics/"
        '''
      }
    }
  }

  post {
    always {
      cleanWs()
    }
  }
}
