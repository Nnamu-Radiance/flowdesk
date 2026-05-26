# FlowDesk

FlowDesk is a hybrid architecture project for enterprise document workflow automation.

Architecture:
- Client-Server: browser -> Nginx gateway
- Microservices: 5 Django services
- Event-Driven: Redis Pub/Sub + Celery queues

Services:
- `auth-service` (`:8001`) - JWT, users, roles
- `workflow-service` (`:8002`) - documents, workflows, CSV import
- `approval-service` (`:8003`) - approval chains, decisions, SLA
- `notification-service` (`:8004`) - WebSocket + email notifications
- `analytics-service` (`:8005`) - dashboards and reports

## Tech Stack
- Python 3.12, Django 5, DRF
- PostgreSQL 15 + pgvector
- Redis 7, Celery, Celery Beat
- Nginx gateway
- Docker Compose (local)
- Kubernetes manifests (`k8s/`)
- Jenkins CI/CD (`Jenkinsfile`)
- Ansible IaC (`ansible/`)
- Prometheus + Grafana (`monitoring/`)

## Repository Layout
```text
flowdesk/
  services/
    auth-service/
    workflow-service/
    approval-service/
    notification-service/
    analytics-service/
  shared/
    events/
    auth/
    utils/
  frontend/
    templates/
    static/
  monitoring/
  ansible/
  k8s/
  nginx/
  sql/
  docker-compose.yml
  Jenkinsfile
```

## Local Setup
1. Copy env file:
```bash
cp .env.example .env.local
```

2. Start database and Redis:
```bash
docker compose up -d postgres redis
```

3. Run migrations per service:
```bash
docker compose run --rm auth-service python manage.py migrate
docker compose run --rm workflow-service python manage.py migrate
docker compose run --rm approval-service python manage.py migrate
docker compose run --rm notification-service python manage.py migrate
docker compose run --rm analytics-service python manage.py migrate
```

4. Start full stack:
```bash
docker compose up -d --build
```

5. Validate health:
```bash
curl http://localhost:8001/health/
curl http://localhost:8002/health/
curl http://localhost:8003/health/
curl http://localhost:8005/health/
```

## Gateway Routes
- `/api/auth/*` -> auth-service
- `/api/workflows/*` -> workflow-service
- `/api/approvals/*` -> approval-service
- `/api/analytics/*` -> analytics-service
- `/ws/*` -> notification-service

Frontend rule: all browser API calls are gateway-relative (example: `fetch('/api/workflows/')`).

## Testing
Per service:
```bash
docker compose run --rm auth-service pytest tests/ -v --cov=apps --cov-fail-under=80
```

All services:
```bash
for svc in auth-service workflow-service approval-service notification-service analytics-service; do
  docker compose run --rm $svc pytest tests/ -v --cov=apps
 done
```

## Jenkins Pipeline
Jenkins-only CI/CD pipeline is defined in `Jenkinsfile`:
1. Checkout
2. Lint (flake8 per service)
3. Unit tests (pytest + coverage)
4. Build Docker images (per service)
5. Push images
6. Deploy Kubernetes manifests
7. Smoke checks

## Kubernetes
Apply all manifests:
```bash
kubectl apply -k k8s/
```

## Monitoring
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Dashboards and datasource provisioning are in `monitoring/grafana/`.
