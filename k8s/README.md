# Deploying the MCP Registry on AWS EKS

## Topology

```
                 Route53 → ACM (TLS)
                        │
                ┌───────▼────────┐  ALB Ingress (internet-facing)
                │  registry.yourco.com   agent.yourco.com
                └───┬───────────────────────┬───┘
        ClusterIP   │                        │  ClusterIP
            ┌───────▼──────┐         ┌────────▼─────┐
            │  registry     │         │  agent svc    │
            │  :8000        │         │  :8800        │
            └───┬───────────┘         └───────────────┘
                │ in-cluster DNS (private), by URL
   ┌────────────┼─────────────────────────┐
   ▼            ▼                          ▼
 pr-agent   atlassian-read           atlassian-write     (ClusterIP only — not exposed)
  :9003        :9004                     :9005
                │
        MongoDB → Atlas (managed, external)   ← recommended over self-hosting
```

Each service is its own Deployment + ClusterIP Service. Only **registry** and **agent**
are exposed via the ALB; the MCP servers stay internal.

## One-time cluster prerequisites
1. **EKS cluster** + `kubectl`/`eksctl` configured.
2. **AWS Load Balancer Controller** installed (for `ingressClassName: alb`).
3. **ACM certificate** covering `registry.yourco.com` and `agent.yourco.com`; put its ARN in `40-ingress.yaml`.
4. **MongoDB Atlas** cluster (or run Mongo in-cluster with an EBS-backed StatefulSet — Atlas is simpler).
5. **Secrets**: ideally the External Secrets Operator or Secrets Store CSI driver pulling from AWS Secrets Manager. `02-secrets.example.yaml` shows the required keys.

## Build & push images to ECR
The registry, agent, and pr-agent are your images; `atlassian-read/write` use the public `ghcr.io/sooperset/mcp-atlassian` image directly.

```bash
ACCOUNT=123456789012; REGION=ap-south-1
ECR=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR
for n in mcp-registry mcp-agent pr-agent-bbs; do aws ecr create-repository --repository-name $n --region $REGION || true; done

# registry  (repo root)
docker build -t $ECR/mcp-registry:latest . && docker push $ECR/mcp-registry:latest
# agent
docker build -t $ECR/mcp-agent:latest agent/ && docker push $ECR/mcp-agent:latest
# pr-agent
docker build -t $ECR/pr-agent-bbs:latest servers/pr_agent_bitbucket/ && docker push $ECR/pr-agent-bbs:latest
```
Then replace `ACCOUNT.dkr.ecr.REGION.amazonaws.com` in `10-registry.yaml`, `20-agent.yaml`,
`30-mcp-servers.yaml` (or template with kustomize/helm).

## Deploy
```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-config.yaml
kubectl apply -f k8s/02-secrets.example.yaml      # or your External Secrets setup
kubectl apply -f k8s/10-registry.yaml
kubectl apply -f k8s/20-agent.yaml
kubectl apply -f k8s/30-mcp-servers.yaml
kubectl apply -f k8s/40-ingress.yaml
kubectl -n mcp get pods,svc,ingress
```

## Post-deploy: publish the servers to the catalog
The registry learns its upstreams from the catalog (stored in Mongo), using in-cluster URLs:
```bash
REG=https://registry.yourco.com
curl -X POST $REG/catalog -H 'Content-Type: application/json' -d '{"name":"Atlassian","base_url":"http://atlassian.mcp.svc.cluster.local:9004/mcp","transport":"http","forward_auth":true}'
curl -X POST $REG/catalog -H 'Content-Type: application/json' -d '{"name":"PR Agent (Bitbucket Server)","base_url":"http://pr-agent.mcp.svc.cluster.local:9003/mcp","transport":"http","forward_auth":false}'
```

## Must-do before real users
- **🚨 Real auth.** Replace the `X-User-Id` header / `/mcp/<user>` path identity (`app/deps.py`)
  with verified JWT/SSO. This is the launch blocker — without it anyone can impersonate anyone.
- **SSRF allowlist.** `ALLOW_PRIVATE_NETWORKS=true` is needed for in-cluster calls; tighten to a
  host allowlist of the MCP Service DNS names so arbitrary private URLs can't be published.
- **Mongo indexes**: unique `slug` (catalog), `(user_id, catalog_id)` (connections), `(user_id, name)` (agents).
- **Atlassian (single instance)**: the shared service account configured on it MUST be **read-only**
  in Jira/Confluence — that's what stops no-token users from writing via the shared account. A user's
  own forwarded PAT (forward_auth=true) then enables writes as them. Confirm mcp-atlassian honors the
  per-request `Authorization` token over its configured fallback.
- **HPA / PodDisruptionBudgets**, NetworkPolicies (lock MCP servers to registry only), and a shared
  session store if you scale the agent service beyond 1 replica.
```
