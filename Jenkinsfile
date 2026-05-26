pipeline {
  agent any

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
            flake8 services/$svc/apps --max-line-length=120 --exclude=migrations
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
            . services/$svc/venv/bin/activate
            pytest services/$svc/tests
            deactivate
          done
        '''
      }
    }

    stage('Build Docker Images') {
      steps {
        sh '''
          set -e
          for svc in $SERVICES; do
            docker build -t ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:${IMAGE_TAG} services/$svc
            docker tag ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:${IMAGE_TAG} ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:latest
          done
        '''
      }
    }

    stage('Push to Registry') {
      when {
        expression { return env.DOCKER_CREDENTIALS_USR?.trim() }
      }
      steps {
        sh '''
          set -e
          echo "${DOCKER_CREDENTIALS_PSW}" | docker login -u "${DOCKER_CREDENTIALS_USR}" --password-stdin
          for svc in $SERVICES; do
            docker push ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:${IMAGE_TAG}
            docker push ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:latest
          done
        '''
      }
    }

    stage('Deploy to Kubernetes') {
      when {
        expression { return fileExists('k8s/kustomization.yaml') }
      }
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
        '''
      }
    }

    stage('Smoke Tests') {
      steps {
        sh '''
          curl -f http://localhost/ || true
          curl -f http://localhost:8001/health/
          curl -f http://localhost:8002/health/
          curl -f http://localhost:8003/health/
          curl -f http://localhost:8005/health/
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
