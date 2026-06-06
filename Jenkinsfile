pipeline {
  agent any

  parameters {
    booleanParam(
      name: 'LOCAL_ONLY',
      defaultValue: true,
      description: 'Run local CI only. When true, skip Docker image push, Kubernetes deploy, and smoke tests.'
    )
    string(
      name: 'REGISTRY',
      defaultValue: 'docker.io',
      description: 'Container registry host used for built images.'
    )
    string(
      name: 'IMAGE_NAMESPACE',
      defaultValue: 'flowdesk',
      description: 'Registry namespace or Docker Hub username/organization that Jenkins can push to.'
    )
    string(
      name: 'DOCKER_CREDENTIALS_ID',
      defaultValue: 'DOCKER_CREDENTIALS',
      description: 'Jenkins Username/Password credential id for registry pushes.'
    )
    booleanParam(
      name: 'PUSH_TO_REGISTRY',
      defaultValue: false,
      description: 'Push built images to REGISTRY. Leave false when Jenkins and Kubernetes use the same local image runtime.'
    )
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
    REGISTRY = "${params.REGISTRY}"
    IMAGE_NAMESPACE = "${params.IMAGE_NAMESPACE}"
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
      when {
        expression { return !params.LOCAL_ONLY }
      }
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
      when {
        expression { return !params.LOCAL_ONLY && params.PUSH_TO_REGISTRY }
      }
      steps {
        withCredentials([usernamePassword(credentialsId: params.DOCKER_CREDENTIALS_ID, usernameVariable: 'DOCKER_USERNAME', passwordVariable: 'DOCKER_PASSWORD')]) {
          sh '''
            set -e
            echo "${DOCKER_PASSWORD}" | docker login "${REGISTRY}" -u "${DOCKER_USERNAME}" --password-stdin
            for svc in $SERVICES; do
              docker push ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:${IMAGE_TAG}
              docker push ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:latest
            done
          '''
        }
      }
    }

    stage('Load Images Into Kubernetes') {
      when {
        expression { return !params.LOCAL_ONLY && !params.PUSH_TO_REGISTRY }
      }
      steps {
        sh '''
          set -e
          mkdir -p .k8s-images
          id
          ls -l /run/k3s/containerd/containerd.sock || true

          import_image_archive() {
            archive="$1"
            if command -v k3s >/dev/null 2>&1; then
              k3s ctr -n k8s.io images import "$archive"
            elif command -v ctr >/dev/null 2>&1; then
              ctr -n k8s.io images import "$archive"
            elif command -v nerdctl >/dev/null 2>&1; then
              nerdctl -n k8s.io load -i "$archive"
            else
              echo "No supported Kubernetes image import tool found. Install k3s, ctr, or nerdctl on the Jenkins agent, or run with PUSH_TO_REGISTRY=true."
              exit 1
            fi
          }

          for svc in $SERVICES; do
            archive=".k8s-images/${svc}.tar"
            docker save -o "$archive" ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:${IMAGE_TAG} ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:latest
            import_image_archive "$archive"
            rm -f "$archive"
          done
        '''
      }
    }

    stage('Deploy to Kubernetes') {
      when {
        expression { return !params.LOCAL_ONLY }
      }
      steps {
        sh '''
          set -e
          echo "---- Kubernetes preflight ----"
          default_kubeconfig="/etc/rancher/k3s/k3s.yaml"
          if [ -z "${KUBECONFIG:-}" ] && [ -r "$default_kubeconfig" ]; then
            export KUBECONFIG="$default_kubeconfig"
          fi

          if [ -n "${KUBECONFIG:-}" ]; then
            echo "KUBECONFIG=${KUBECONFIG}"
            if [ ! -r "${KUBECONFIG}" ]; then
              echo "KUBECONFIG points to a file Jenkins cannot read. For bundled k3s deploys, mount /etc/rancher/k3s into the Jenkins container."
              exit 1
            fi
          else
            echo "KUBECONFIG is not set and $default_kubeconfig is not readable."
            echo "Recreate Jenkins with the host k3s kubeconfig mounted: /etc/rancher/k3s:/etc/rancher/k3s:ro."
            exit 1
          fi
          kubectl version --client=true
          if ! kubectl get nodes -o wide; then
            echo "Jenkins cannot reach the Kubernetes API. For bundled same-server k3s deploys, recreate Jenkins with the /etc/rancher/k3s mount and KUBECONFIG=/etc/rancher/k3s/k3s.yaml."
            exit 1
          fi
          echo "---- End Kubernetes preflight ----"

          dump_k8s_diagnostics() {
            echo "---- Kubernetes diagnostics ----"
            kubectl -n flowdesk get pods -o wide || true
            kubectl -n flowdesk get pvc || true
            kubectl -n flowdesk get events --sort-by=.lastTimestamp || true
            kubectl -n flowdesk describe statefulset/postgres || true
            kubectl -n flowdesk describe pod -l app=postgres || true
            kubectl -n flowdesk logs statefulset/postgres --tail=120 || true
            echo "---- End Kubernetes diagnostics ----"
          }
          diagnostics_on_exit() {
            status=$?
            if [ "$status" -ne 0 ]; then
              dump_k8s_diagnostics
            fi
            exit "$status"
          }
          trap diagnostics_on_exit 0

          kubectl apply -f k8s/namespace.yaml
          kubectl apply -f k8s/configmap.yaml
          kubectl apply -f k8s/secret.yaml
          kubectl apply -f k8s/postgres.yaml
          desired_postgres_image="pgvector/pgvector:pg16"
          current_postgres_image="$(kubectl -n flowdesk get pod postgres-0 -o jsonpath='{.spec.containers[?(@.name=="postgres")].image}' 2>/dev/null || true)"
          if [ -n "$current_postgres_image" ] && [ "$current_postgres_image" != "$desired_postgres_image" ]; then
            echo "Deleting stale postgres-0 pod using image ${current_postgres_image}; StatefulSet will recreate it with ${desired_postgres_image}."
            kubectl -n flowdesk delete pod postgres-0 --wait=false
          fi
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
      when {
        expression { return !params.LOCAL_ONLY }
      }
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
