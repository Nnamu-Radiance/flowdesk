# FlowDesk Jenkins Production Server Guide

This guide covers the production-side setup that remains after local CI is working.

## Goal

Run the full pipeline with `LOCAL_ONLY=false` so Jenkins performs:

1. Lint
2. Unit tests
3. Docker image build
4. Image push to registry
5. Kubernetes deployment
6. Smoke checks

## 1. Production infrastructure prerequisites

1. A VPS or server where Jenkins agent can run shell commands
2. Docker daemon available to Jenkins runner
3. Kubernetes cluster reachable from Jenkins runner
4. Container registry account (Docker Hub or private registry)
5. DNS/TLS configured for production ingress domain

## 2. Jenkins runtime requirements

Your Jenkins execution environment must include:

1. `python3`, `pip`, `venv`
2. `docker` CLI plus permission to use Docker daemon
3. `kubectl`
4. `git`

Note: current `Dockerfile.jenkins` installs Docker CLI but not `kubectl`. Add it before production rollout.

## 3. Jenkins credentials required

Create these in Jenkins Credentials:

1. Registry credential (Username/Password), example id: `DOCKER_CREDENTIALS`
2. Kubernetes access credential (preferred: Secret File with kubeconfig)
3. Git credential (only if repository is private)

## 4. Pipeline parameter for production

In `Build with Parameters`, set:

1. `LOCAL_ONLY=false`

This enables build/push/deploy/smoke stages.

## 5. Registry configuration checklist

Confirm these `Jenkinsfile` environment values are correct for production:

1. `REGISTRY` (currently `docker.io`)
2. `IMAGE_NAMESPACE` (currently `flowdesk`)
3. `IMAGE_TAG` (`${BUILD_NUMBER}`)

Current image naming format:

1. `${REGISTRY}/${IMAGE_NAMESPACE}/${service}:${IMAGE_TAG}`
2. `${REGISTRY}/${IMAGE_NAMESPACE}/${service}:latest`

## 6. Kubernetes configuration checklist

Before first deploy, update Kubernetes manifests:

1. [k8s/secret.yaml](c:/Users/bkbad/OneDrive/Desktop/Flowdesk/k8s/secret.yaml)
2. [k8s/configmap.yaml](c:/Users/bkbad/OneDrive/Desktop/Flowdesk/k8s/configmap.yaml)
3. [k8s/ingress.yaml](c:/Users/bkbad/OneDrive/Desktop/Flowdesk/k8s/ingress.yaml)

Required updates:

1. Replace placeholder secrets (`DJANGO_SECRET_KEY`, `JWT_SECRET_KEY`, DB URLs)
2. Set real `ALLOWED_HOSTS`
3. Set ingress host/TLS settings for your domain

## 7. Image/deployment behavior to understand

Deployments currently reference `:latest` images (example: `docker.io/flowdesk/auth-service:latest`).

Recommendation for stronger release control:

1. Use immutable tags per build (`BUILD_NUMBER` or git SHA)
2. Patch deployment image tags during pipeline deploy step

## 8. Kubernetes access from Jenkins

Two common options:

1. Jenkins runs inside cluster with service account permissions
2. Jenkins runs outside cluster and uses kubeconfig credential

For option 2:

1. Store kubeconfig as Jenkins secret file
2. Expose it in pipeline stage and set `KUBECONFIG` before `kubectl apply`

## 9. Production smoke tests

Current `Smoke Tests` stage curls localhost endpoints. For production this may not represent end-user traffic path.

Recommended:

1. Curl ingress/public URL health endpoints
2. Add retries/timeouts
3. Fail build on unhealthy critical services

## 10. Security hardening checklist

1. Move plaintext Kubernetes secrets to sealed-secrets or external secret manager
2. Rotate JWT and Django secrets
3. Restrict Jenkins credential access by folder/job
4. Restrict who can run production deploy jobs
5. Enable audit logs on Jenkins and cluster

## 11. Suggested release flow

1. Developer pushes branch -> local CI (`LOCAL_ONLY=true`)
2. Merge to protected deployment branch
3. Production pipeline run with `LOCAL_ONLY=false`
4. Verify smoke checks and service health dashboards

## 12. Production go-live checklist

1. Jenkins agent has `docker`, `kubectl`, `python3`, `venv`
2. Registry credentials present and tested
3. Kube access configured and tested (`kubectl get ns`)
4. `k8s/secret.yaml` and ingress hostnames updated
5. First full pipeline run ends `SUCCESS`

