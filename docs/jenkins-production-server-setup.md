# FlowDesk Jenkins Production Server Guide

This guide covers the production-side setup that remains after local CI is working.

## Goal

Run the full pipeline with `LOCAL_ONLY=false` so Jenkins performs:

1. Lint
2. Unit tests
3. Docker image build
4. Optional image push to registry
5. Kubernetes deployment
6. Smoke checks

## 1. Production infrastructure prerequisites

1. A VPS or server where Jenkins agent can run shell commands
2. Docker daemon available to Jenkins runner
3. Kubernetes cluster reachable from Jenkins runner
4. Container registry account (Docker Hub or private registry)
5. DNS/TLS configured for production ingress domain

If Jenkins and Kubernetes run on the same server and Kubernetes can see the images built by Jenkins, the registry account is optional.

## 2. Jenkins runtime requirements

Your Jenkins execution environment must include:

1. `python3`, `pip`, `venv`
2. `docker` CLI plus permission to use Docker daemon
3. `kubectl`
4. `git`

The bundled `Dockerfile.jenkins` provides `kubectl` through the mounted k3s binary. If you use a different Jenkins agent image, install `kubectl` or provide an equivalent wrapper.

## 3. Jenkins credentials required

Create these in Jenkins Credentials:

1. Registry credential (Username/Password), default id: `DOCKER_CREDENTIALS`
2. Kubernetes access credential (preferred: Secret File with kubeconfig)
3. Git credential (only if repository is private)

For Docker Hub, the username in `DOCKER_CREDENTIALS` must be able to push to the configured `IMAGE_NAMESPACE`. If your Docker Hub username is `my-user`, use `IMAGE_NAMESPACE=my-user`; use `flowdesk` only when the credential has access to the `flowdesk` Docker Hub organization.

## 4. Pipeline parameter for production

In `Build with Parameters`, set:

1. `LOCAL_ONLY=false`
2. `PUSH_TO_REGISTRY=false` for same-server deploys that use locally built images
3. `PUSH_TO_REGISTRY=true` only when Kubernetes needs to pull images from Docker Hub or another registry

This enables build/deploy/smoke stages. The push stage runs only when `PUSH_TO_REGISTRY=true`.

## 5. Registry configuration checklist

Confirm these `Jenkinsfile` environment values are correct for production:

1. `REGISTRY` parameter (default `docker.io`)
2. `IMAGE_NAMESPACE` parameter (default `flowdesk`; set this to your Docker Hub username or organization)
3. `DOCKER_CREDENTIALS_ID` parameter (default `DOCKER_CREDENTIALS`)
4. `PUSH_TO_REGISTRY` parameter (default `false`)
5. `IMAGE_TAG` (`${BUILD_NUMBER}`)

Current image naming format:

1. `${REGISTRY}/${IMAGE_NAMESPACE}/${service}:${IMAGE_TAG}`
2. `${REGISTRY}/${IMAGE_NAMESPACE}/${service}:latest`

For same-server deployment without Docker Hub, Jenkins still builds these image names locally, then imports them into the Kubernetes runtime before deployment. On k3s/containerd servers, the Jenkins agent must be able to run `k3s ctr -n k8s.io images import`, `ctr -n k8s.io images import`, or `nerdctl -n k8s.io load`. If pods enter `ImagePullBackOff`, the import step did not run successfully; either fix runtime image import access or enable `PUSH_TO_REGISTRY=true`.

When the k3s containerd socket is mounted as `root:root` with mode `660`, the Jenkins job user must be in group `0` or the import command fails with `permission denied`.

If rebuilding the Jenkins image fails because the server cannot resolve package repositories such as `deb.debian.org`, you can still apply the permission fix to the existing Jenkins image:

```bash
cd /var/www/flowdesk
docker compose up -d --no-build --force-recreate --no-deps jenkins
docker exec -u root flowdesk-jenkins usermod -aG root jenkins
docker restart flowdesk-jenkins
docker exec -u jenkins flowdesk-jenkins id
```

The final `id` output must include `0(root)` before rerunning the pipeline with `PUSH_TO_REGISTRY=false`.

If there is no existing Jenkins image and Docker reports `No such image: flowdesk-jenkins:latest`, rebuild it after confirming the Compose file includes `build.network: host` for the Jenkins service:

```bash
cd /var/www/flowdesk
docker compose build --no-cache jenkins
docker compose up -d --force-recreate --no-deps jenkins
docker exec -u jenkins flowdesk-jenkins id
```

The bundled Flowdesk Jenkins service uses host networking and runs Jenkins on port `8081` by default so it does not conflict with another Jenkins instance on port `8080`.

```bash
cd /var/www/flowdesk
docker compose up -d --force-recreate --no-deps jenkins
docker exec -u jenkins flowdesk-jenkins id
```

If the Jenkins setup wizard says the instance is offline, Jenkins cannot reach the update center from inside the container. The bundled Compose service sets public DNS resolvers for Jenkins. After updating Compose, recreate Jenkins:

```bash
cd /var/www/flowdesk
docker compose up -d --force-recreate --no-deps jenkins
```

If `git pull` refuses to merge because of local server edits to `Dockerfile.jenkins` or `docker-compose.yml`, save those edits before pulling:

```bash
cd /var/www/flowdesk
git stash push -m "server jenkins compose edits" Dockerfile.jenkins docker-compose.yml
git pull
```

If Compose then reports that container name `/flowdesk-jenkins` is already in use, remove only that old Jenkins container and recreate it. The Jenkins data is kept in the `jenkins_data` Docker volume:

```bash
docker rm -f flowdesk-jenkins
docker compose up -d --build --force-recreate --no-deps jenkins
docker exec flowdesk-jenkins env | grep KUBECONFIG
docker exec flowdesk-jenkins ls -l /etc/rancher/k3s/k3s.yaml
docker exec flowdesk-jenkins kubectl get nodes -o wide
```

If the push fails with `insufficient_scope: authorization failed`, verify:

1. Jenkins has a Username/Password credential with the id from `DOCKER_CREDENTIALS_ID`
2. The credential uses a valid registry password or access token
3. `IMAGE_NAMESPACE` is a namespace that credential can push to
4. The target repository exists or the registry account is allowed to create it

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

For bundled same-server k3s deployments, the included Compose service mounts `/etc/rancher/k3s/k3s.yaml` and sets `KUBECONFIG=/etc/rancher/k3s/k3s.yaml`. Recreate Jenkins after pulling Compose changes:

```bash
docker compose up -d --build --force-recreate --no-deps jenkins
docker exec flowdesk-jenkins kubectl get nodes -o wide
```

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
