pipeline {
  agent any

  parameters {
    booleanParam(
      name: 'LOCAL_ONLY',
      defaultValue: true,
      description: 'Run local CI only. When true, skip Docker image push, Kubernetes deploy, and smoke tests.'
    )
    booleanParam(
      name: 'RUN_LINT',
      defaultValue: true,
      description: 'Run lint checks.'
    )
    booleanParam(
      name: 'RUN_UNIT_TESTS',
      defaultValue: true,
      description: 'Run unit tests.'
    )
    booleanParam(
      name: 'BUILD_DOCKER_IMAGES',
      defaultValue: true,
      description: 'Build Docker images. When false, image push/import is skipped and deploy keeps current images unless DEPLOY_IMAGE_TAG is set.'
    )
    string(
      name: 'DEPLOY_IMAGE_TAG',
      defaultValue: '',
      description: 'Existing image tag to deploy when BUILD_DOCKER_IMAGES=false. Leave blank to keep currently deployed app images.'
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

    stage('Resolve Pipeline Options') {
      steps {
        script {
          def deployTag = params.DEPLOY_IMAGE_TAG?.trim()
          if (params.BUILD_DOCKER_IMAGES) {
            env.IMAGE_TAG = env.BUILD_NUMBER
          } else {
            env.IMAGE_TAG = deployTag ?: ''
          }

          echo "RUN_LINT=${params.RUN_LINT}"
          echo "RUN_UNIT_TESTS=${params.RUN_UNIT_TESTS}"
          echo "BUILD_DOCKER_IMAGES=${params.BUILD_DOCKER_IMAGES}"
          echo "PUSH_TO_REGISTRY=${params.PUSH_TO_REGISTRY}"
          echo "IMAGE_TAG=${env.IMAGE_TAG ?: '(keeping current deployment images)'}"
        }
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

    stage('Build Docker Images') {
      when {
        expression { return !params.LOCAL_ONLY && params.BUILD_DOCKER_IMAGES }
      }
      steps {
        sh '''
          set -e
          for svc in $SERVICES; do
            docker build --network=host -f services/$svc/Dockerfile -t ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:${IMAGE_TAG} .
            docker tag ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:${IMAGE_TAG} ${REGISTRY}/${IMAGE_NAMESPACE}/${svc}:latest
          done
        '''
      }
    }

    stage('Push to Registry') {
      when {
        expression { return !params.LOCAL_ONLY && params.BUILD_DOCKER_IMAGES && params.PUSH_TO_REGISTRY }
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
        expression { return !params.LOCAL_ONLY && params.BUILD_DOCKER_IMAGES && !params.PUSH_TO_REGISTRY }
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
            kubectl -n flowdesk get all -o wide || true
            kubectl -n flowdesk get pods -o wide || true
            kubectl -n flowdesk get svc -o wide || true
            kubectl -n flowdesk get endpoints -o wide || true
            kubectl -n flowdesk get pvc || true
            kubectl -n flowdesk get ingress || true
            kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide || true
            kubectl -n kube-system get svc kube-dns -o wide || true
            kubectl -n flowdesk get events --sort-by=.lastTimestamp || true
            for workload in statefulset/postgres deployment/redis deployment/auth-service deployment/workflow-service deployment/approval-service deployment/notification-service deployment/analytics-service deployment/celery-worker deployment/celery-beat deployment/nginx; do
              echo "---- Describe ${workload} ----"
              kubectl -n flowdesk describe "$workload" || true
            done
            for pod in $(kubectl -n flowdesk get pods --no-headers 2>/dev/null | awk '{ split($2, ready, "/"); if ($3 != "Running" || ready[1] != ready[2]) print $1 }'); do
              echo "---- Describe pod/${pod} ----"
              kubectl -n flowdesk describe pod "$pod" || true
              echo "---- Logs pod/${pod} ----"
              kubectl -n flowdesk logs pod/"$pod" --all-containers --tail=120 || true
            done
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

          current_auth_image=""
          current_workflow_image=""
          current_approval_image=""
          current_notification_image=""
          current_analytics_image=""
          current_celery_workflow_image=""
          current_celery_approval_image=""
          current_celery_notification_image=""
          current_celery_beat_image=""
          if [ -z "${IMAGE_TAG:-}" ]; then
            current_auth_image="$(kubectl -n flowdesk get deployment/auth-service -o jsonpath='{.spec.template.spec.containers[?(@.name=="auth-service")].image}' 2>/dev/null || true)"
            current_workflow_image="$(kubectl -n flowdesk get deployment/workflow-service -o jsonpath='{.spec.template.spec.containers[?(@.name=="workflow-service")].image}' 2>/dev/null || true)"
            current_approval_image="$(kubectl -n flowdesk get deployment/approval-service -o jsonpath='{.spec.template.spec.containers[?(@.name=="approval-service")].image}' 2>/dev/null || true)"
            current_notification_image="$(kubectl -n flowdesk get deployment/notification-service -o jsonpath='{.spec.template.spec.containers[?(@.name=="notification-service")].image}' 2>/dev/null || true)"
            current_analytics_image="$(kubectl -n flowdesk get deployment/analytics-service -o jsonpath='{.spec.template.spec.containers[?(@.name=="analytics-service")].image}' 2>/dev/null || true)"
            current_celery_workflow_image="$(kubectl -n flowdesk get deployment/celery-worker -o jsonpath='{.spec.template.spec.containers[?(@.name=="celery-workflow")].image}' 2>/dev/null || true)"
            current_celery_approval_image="$(kubectl -n flowdesk get deployment/celery-worker -o jsonpath='{.spec.template.spec.containers[?(@.name=="celery-approval")].image}' 2>/dev/null || true)"
            current_celery_notification_image="$(kubectl -n flowdesk get deployment/celery-worker -o jsonpath='{.spec.template.spec.containers[?(@.name=="celery-notification")].image}' 2>/dev/null || true)"
            current_celery_beat_image="$(kubectl -n flowdesk get deployment/celery-beat -o jsonpath='{.spec.template.spec.containers[?(@.name=="celery-beat")].image}' 2>/dev/null || true)"
          fi

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

          if [ -n "${IMAGE_TAG:-}" ]; then
            kubectl -n flowdesk set image deployment/auth-service auth-service=${REGISTRY}/${IMAGE_NAMESPACE}/auth-service:${IMAGE_TAG}
            kubectl -n flowdesk set image deployment/workflow-service workflow-service=${REGISTRY}/${IMAGE_NAMESPACE}/workflow-service:${IMAGE_TAG}
            kubectl -n flowdesk set image deployment/approval-service approval-service=${REGISTRY}/${IMAGE_NAMESPACE}/approval-service:${IMAGE_TAG}
            kubectl -n flowdesk set image deployment/notification-service notification-service=${REGISTRY}/${IMAGE_NAMESPACE}/notification-service:${IMAGE_TAG}
            kubectl -n flowdesk set image deployment/analytics-service analytics-service=${REGISTRY}/${IMAGE_NAMESPACE}/analytics-service:${IMAGE_TAG}
            kubectl -n flowdesk set image deployment/celery-worker celery-workflow=${REGISTRY}/${IMAGE_NAMESPACE}/workflow-service:${IMAGE_TAG} celery-approval=${REGISTRY}/${IMAGE_NAMESPACE}/approval-service:${IMAGE_TAG} celery-notification=${REGISTRY}/${IMAGE_NAMESPACE}/notification-service:${IMAGE_TAG}
            kubectl -n flowdesk set image deployment/celery-beat celery-beat=${REGISTRY}/${IMAGE_NAMESPACE}/approval-service:${IMAGE_TAG}
          else
            echo "Restoring currently deployed application images after manifest apply."
            [ -n "$current_auth_image" ] && kubectl -n flowdesk set image deployment/auth-service auth-service="$current_auth_image"
            [ -n "$current_workflow_image" ] && kubectl -n flowdesk set image deployment/workflow-service workflow-service="$current_workflow_image"
            [ -n "$current_approval_image" ] && kubectl -n flowdesk set image deployment/approval-service approval-service="$current_approval_image"
            [ -n "$current_notification_image" ] && kubectl -n flowdesk set image deployment/notification-service notification-service="$current_notification_image"
            [ -n "$current_analytics_image" ] && kubectl -n flowdesk set image deployment/analytics-service analytics-service="$current_analytics_image"
            [ -n "$current_celery_workflow_image" ] && kubectl -n flowdesk set image deployment/celery-worker celery-workflow="$current_celery_workflow_image"
            [ -n "$current_celery_approval_image" ] && kubectl -n flowdesk set image deployment/celery-worker celery-approval="$current_celery_approval_image"
            [ -n "$current_celery_notification_image" ] && kubectl -n flowdesk set image deployment/celery-worker celery-notification="$current_celery_notification_image"
            [ -n "$current_celery_beat_image" ] && kubectl -n flowdesk set image deployment/celery-beat celery-beat="$current_celery_beat_image"
          fi
          kubectl -n flowdesk rollout restart deployment/nginx

          wait_for_rollout() {
            resource="$1"
            timeout="$2"
            echo "Waiting for rollout: ${resource}"
            kubectl -n flowdesk rollout status "$resource" --timeout="$timeout"
          }

          wait_for_rollout statefulset/postgres 180s
          wait_for_rollout deployment/redis 180s
          wait_for_rollout deployment/auth-service 300s
          wait_for_rollout deployment/workflow-service 300s
          wait_for_rollout deployment/approval-service 300s
          wait_for_rollout deployment/notification-service 300s
          wait_for_rollout deployment/analytics-service 300s
          wait_for_rollout deployment/celery-worker 300s
          wait_for_rollout deployment/celery-beat 300s
          wait_for_rollout deployment/nginx 180s
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
