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

This builds images locally, skips Docker Hub, deploys to Kubernetes, and runs smoke tests. If pods fail with `ImagePullBackOff`, the Kubernetes runtime cannot see Jenkins' local Docker images; use a registry or load the images into the cluster runtime.

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
