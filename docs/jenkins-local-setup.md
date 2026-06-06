# FlowDesk Jenkins Local Setup Guide

This guide is for running the FlowDesk Jenkins pipeline fully on a local machine without VPS/Kubernetes deployment.

## What this local pipeline does

With the current `Jenkinsfile`, local runs use `LOCAL_ONLY=true` by default and execute:

1. `Checkout`
2. `Lint` (all 5 services)
3. `Unit Tests` (all 5 services, coverage gate at 80%)

It skips:

1. `Build Docker Images`
2. `Push to Registry`
3. `Deploy to Kubernetes`
4. `Smoke Tests`

## Prerequisites

1. Docker Engine / Docker Desktop
2. Git
3. Internet access for Python package installation inside pipeline stages
4. Repo cloned locally

## 1. Clone repository

```bash
git clone https://github.com/Nnamu-Radiance/flowdesk.git
cd flowdesk
```

## 2. Start Jenkins locally (Docker Compose)

FlowDesk already includes a Jenkins service in `docker-compose.yml`.

```bash
docker compose build jenkins
docker compose up -d jenkins
```

Open Jenkins:

```text
http://localhost:8080
```

Get initial admin password:

```bash
docker exec -it flowdesk-jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

## 3. Install Jenkins plugins

Install suggested plugins plus these required ones:

1. `Pipeline`
2. `Git`
3. `Credentials Binding`
4. `Workspace Cleanup`
5. `Timestamper`

Recommended:

1. `GitHub` / `GitHub Branch Source` (if using multibranch or GitHub webhooks)

## 4. Configure global tools (recommended)

To remove noisy warnings like `Selected Git installation does not exist. Using Default`:

1. Go to `Manage Jenkins` -> `Tools`
2. Under `Git installations`, add one named `Default`
3. Save

The warning is non-fatal, but this keeps logs cleaner.

## 5. Create the Jenkins pipeline job

Use either:

1. `Pipeline` job (simplest)
2. `Multibranch Pipeline` (recommended for team branches)

### For a standard Pipeline job

1. New Item -> `Pipeline`
2. Under `Pipeline`, select `Pipeline script from SCM`
3. SCM: `Git`
4. Repository URL: `https://github.com/Nnamu-Radiance/flowdesk.git`
5. Branch Specifier: `*/ray` (or your target branch)
6. Script Path: `Jenkinsfile`
7. Save

## 6. Run local CI

Run `Build Now` (or `Build with Parameters` and keep `LOCAL_ONLY=true`, which is the default).

Expected successful result:

1. Checkout succeeds
2. Lint succeeds for all services
3. Unit tests succeed for all services
4. Build is `SUCCESS`

If Jenkins reaches `Push to Registry`, the job is not running with `LOCAL_ONLY=true`. Re-run with parameters and keep `LOCAL_ONLY` checked for local CI.

## Same-server deploy without Docker Hub

If Jenkins and Kubernetes are on the same server and Kubernetes can use Jenkins' locally built Docker images, run `Build with Parameters` with:

1. `LOCAL_ONLY=false`
2. `PUSH_TO_REGISTRY=false`

This builds images locally, skips Docker Hub, imports the built images into the Kubernetes runtime, deploys to Kubernetes, and runs smoke tests. On k3s/containerd servers, the Jenkins agent must be able to run `k3s ctr -n k8s.io images import`, `ctr -n k8s.io images import`, or `nerdctl -n k8s.io load`; if those tools are not available, use a registry instead.

To debug only Kubernetes manifests/deploy/smoke tests after lint, unit tests, and image build have already passed, run `Build with Parameters` with:

1. `LOCAL_ONLY=false`
2. `DEPLOY_ONLY=true`
3. `PUSH_TO_REGISTRY=false`
4. `DEPLOY_IMAGE_TAG=<previous successful image tag>` if you want to repoint app deployments to a known tag
5. Leave `DEPLOY_IMAGE_TAG` blank if you only want to re-apply Kubernetes manifests and keep the currently deployed app images

For a faster run that still rebuilds images, use `SKIP_CI_CHECKS=true` and keep `SKIP_IMAGE_BUILD=false`.

For bundled same-server k3s deploys, the Jenkins container also needs the host kubeconfig. The included Compose service mounts `/etc/rancher/k3s/k3s.yaml` and sets `KUBECONFIG=/etc/rancher/k3s/k3s.yaml`, so recreate Jenkins after pulling changes to `docker-compose.yml`:

```bash
docker compose up -d --build --force-recreate --no-deps jenkins
docker exec flowdesk-jenkins kubectl get nodes -o wide
```

The bundled Jenkins Compose service adds Jenkins to group `0` because the k3s containerd socket is commonly mounted as `root:root` with mode `660`. If the pipeline prints `/run/k3s/containerd/containerd.sock` as another group, add that host group id to the Jenkins service as well.

When using the bundled Docker Compose Jenkins service, rebuild/recreate Jenkins after changing the runtime mounts or Jenkins user/security settings:

```bash
docker compose up -d --build --force-recreate jenkins
```

If the rebuild fails because the server cannot resolve package repositories such as `deb.debian.org`, recreate Jenkins from the existing local image and apply the Jenkins group change inside the container:

```bash
cd /var/www/flowdesk
docker compose up -d --no-build --force-recreate --no-deps jenkins
docker exec -u root flowdesk-jenkins usermod -aG root jenkins
docker restart flowdesk-jenkins
docker exec -u jenkins flowdesk-jenkins id
```

The final `id` output must include `0(root)`. If it does not, the Jenkins job will still be unable to open `/run/k3s/containerd/containerd.sock`.

If there is no existing Jenkins image and Docker reports `No such image: flowdesk-jenkins:latest`, the image must be rebuilt. The bundled Compose file builds Jenkins with host networking so package repository DNS uses the host network:

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

Then open Flowdesk Jenkins on port `8081`.

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

## 7. Verify the job is running your latest commit

In build logs, confirm the checkout commit hash matches your branch head.

Local check:

```bash
git rev-parse --short HEAD
```

If Jenkins is building an old commit:

1. Confirm changes are committed and pushed
2. Confirm job branch points to the correct branch
3. Re-run build

## 8. Common issues and fixes

### Issue: stale workspace or strange test behavior

Fix:

1. Ensure `cleanWs()` remains in `post { always { ... } }`
2. Use `Wipe out current workspace` once from Jenkins UI

### Issue: pip install failures

Fix:

1. Verify internet/DNS on Jenkins container host
2. Rebuild Jenkins image if networking changed:

```bash
docker compose build --no-cache jenkins
docker compose up -d jenkins
```

### Issue: branch builds but code changes not reflected

Fix:

1. Check `git status` is clean before push
2. Check remote branch contains your commit:

```bash
git log --oneline --decorate -n 5
```

## 9. Local CI done criteria

Your local Jenkins setup is complete when:

1. A pushed branch commit is checked out correctly
2. `Lint` and `Unit Tests` pass
3. Jenkins build ends `SUCCESS`
