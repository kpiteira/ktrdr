# Project 5: Pre-prod Deployment

**Status**: Ready for Implementation
**Estimated Effort**: Large
**Prerequisites**: Project 4 (Secrets & Deployment CLI)

---

## Goal

Fully operational pre-production environment on Proxmox with monitoring, following all design principles from [DESIGN.md](DESIGN.md).

---

## Context

This project brings together all previous work to deploy KTRDR to the Proxmox homelab. LXC provisioning is manual (per DESIGN.md Decision 9), but deployment is automated via the CLI from Project 4.

---

## Tasks

### Task 5.1: Verify Proxmox Infrastructure

**Goal**: Ensure LXCs are provisioned and accessible

**Prerequisites** (manual, per OPERATIONS.md):
- Node A LXC: ktrdr-core (16GB RAM)
- Node B LXC: ktrdr-workers-b (16GB RAM)
- Node C LXC: ktrdr-workers-c (8GB RAM)
- Static IPs assigned
- SSH keys configured
- Docker installed on each LXC

**Verification Steps**:
1. SSH to each LXC
2. Verify Docker is installed and running
3. Verify disk space available
4. Verify network connectivity between LXCs
5. Document IPs and hostnames

**Commands**:
```bash
# Test SSH access
ssh backend.ktrdr.home.mynerd.place 'echo ok'
ssh workers-b.ktrdr.home.mynerd.place 'echo ok'
ssh workers-c.ktrdr.home.mynerd.place 'echo ok'

# Check Docker
ssh backend.ktrdr.home.mynerd.place 'docker --version && docker ps'

# Check disk space
ssh backend.ktrdr.home.mynerd.place 'df -h'

# Test inter-LXC connectivity
ssh workers-b.ktrdr.home.mynerd.place 'ping -c 3 backend.ktrdr.home.mynerd.place'
```

**Acceptance Criteria**:
- [ ] All 3 LXCs accessible via SSH
- [ ] Docker installed and running on each
- [ ] Sufficient disk space (>20GB free on core)
- [ ] Network connectivity between LXCs verified

---

### Task 5.2: Configure DNS

**Goal**: DNS entries resolve correctly

**Required DNS Entries** (in local DNS server):
```
backend.ktrdr.home.mynerd.place     -> Node A IP
postgres.ktrdr.home.mynerd.place    -> Node A IP
grafana.ktrdr.home.mynerd.place     -> Node A IP
prometheus.ktrdr.home.mynerd.place  -> Node A IP
workers-b.ktrdr.home.mynerd.place   -> Node B IP
workers-c.ktrdr.home.mynerd.place   -> Node C IP
```

**Actions**:
1. Add DNS entries to local DNS server (BIND, Pi-hole, etc.)
2. Test resolution from each LXC
3. Test resolution from deployment machine

**Verification**:
```bash
# From deployment machine
dig backend.ktrdr.home.mynerd.place
dig workers-b.ktrdr.home.mynerd.place

# From core LXC
ssh backend.ktrdr.home.mynerd.place 'nslookup workers-b.ktrdr.home.mynerd.place'
```

**Acceptance Criteria**:
- [ ] All DNS entries configured
- [ ] Resolution works from deployment machine
- [ ] Resolution works between LXCs

---

### Task 5.3: Set Up NFS Shared Storage

**Goal**: NFS share accessible from all LXCs

**On Core LXC** (NFS server):
```bash
# Create share directory
mkdir -p /srv/ktrdr-shared/{data,results,models,db-backups}

# Install NFS server
apt install nfs-kernel-server

# Configure exports
echo "/srv/ktrdr-shared *(rw,sync,no_subtree_check,no_root_squash)" >> /etc/exports

# Start NFS
exportfs -a
systemctl enable nfs-kernel-server
systemctl start nfs-kernel-server
```

**On Worker LXCs** (NFS clients):
```bash
# Create mount point
mkdir -p /mnt/ktrdr-shared

# Add to fstab
echo "backend.ktrdr.home.mynerd.place:/srv/ktrdr-shared /mnt/ktrdr-shared nfs defaults 0 0" >> /etc/fstab

# Mount
mount -a
```

**Verification**:
```bash
# On worker LXC
ls /mnt/ktrdr-shared
touch /mnt/ktrdr-shared/test-from-worker-b
rm /mnt/ktrdr-shared/test-from-worker-b
```

**Acceptance Criteria**:
- [ ] NFS server running on core LXC
- [ ] NFS mounted on worker LXCs
- [ ] Can read/write from workers
- [ ] Persists across reboots

---

### Task 5.4: Create Deployment Directories

**Goal**: Prepare directories for compose files

**On Core LXC**:
```bash
mkdir -p /opt/ktrdr-core
# Copy docker-compose.core.yml here
# Copy .env.core here (non-secrets only)
# Copy monitoring configs here
```

**On Worker LXCs**:
```bash
mkdir -p /opt/ktrdr-workers-{b,c}
# Copy docker-compose.workers.yml here
# Copy .env.workers here (customized per node)
```

**Actions**:
1. Create directories on each LXC
2. Copy compose files from repository
3. Copy environment files (non-secrets only)
4. Copy monitoring configs to core

**Acceptance Criteria**:
- [ ] Directories created on all LXCs
- [ ] Compose files in place
- [ ] Monitoring configs in place on core
- [ ] Environment files customized per node

---

### Task 5.5: Update Compose Files for Pre-prod

**Goal**: Ensure compose files are correct for pre-prod topology

**docker-compose.core.yml Updates**:
1. Verify image references use GHCR
2. Update Prometheus config path
3. Update Grafana provisioning paths
4. Verify volume mounts
5. Verify network configuration

**docker-compose.workers.yml Updates**:
1. Customize WORKER_HOSTNAME per node
2. Set correct KTRDR_API_URL
3. Set correct OTLP_ENDPOINT
4. Set correct DB_HOST
5. Update WORKER_PUBLIC_BASE_URL per node

**Node B Example**:
```yaml
environment:
  WORKER_PUBLIC_BASE_URL: http://workers-b.ktrdr.home.mynerd.place:5003
  KTRDR_API_URL: http://backend.ktrdr.home.mynerd.place:8000
  OTLP_ENDPOINT: http://backend.ktrdr.home.mynerd.place:4317
  DB_HOST: backend.ktrdr.home.mynerd.place
```

**Acceptance Criteria**:
- [ ] Core compose file correct
- [ ] Worker compose files customized per node
- [ ] All URLs point to correct hostnames
- [ ] Image references use GHCR

---

### Task 5.6: Create Pre-prod Prometheus Config

**File**: `/opt/ktrdr-core/monitoring/prometheus.yml`

**Goal**: Prometheus scrapes all services

**Configuration**:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'backend'
    static_configs:
      - targets: ['backend:8000']

  - job_name: 'workers-b'
    static_configs:
      - targets:
        - 'workers-b.ktrdr.home.mynerd.place:5003'
        - 'workers-b.ktrdr.home.mynerd.place:5004'
        - 'workers-b.ktrdr.home.mynerd.place:5005'
        - 'workers-b.ktrdr.home.mynerd.place:5006'

  - job_name: 'workers-c'
    static_configs:
      - targets:
        - 'workers-c.ktrdr.home.mynerd.place:5003'
        - 'workers-c.ktrdr.home.mynerd.place:5004'
        - 'workers-c.ktrdr.home.mynerd.place:5005'
        - 'workers-c.ktrdr.home.mynerd.place:5006'
```

**Acceptance Criteria**:
- [ ] Config includes backend
- [ ] Config includes all workers on both nodes
- [ ] Targets use correct hostnames/ports

---

### Task 5.7: Deploy Core Stack

**Goal**: Core services running on Node A

**Actions**:
1. Run deployment CLI
2. Wait for services to start
3. Verify all services healthy

**Commands**:
```bash
# Deploy all core services
ktrdr deploy core all

# Check services
ssh backend.ktrdr.home.mynerd.place 'docker compose -f /opt/ktrdr-core/docker-compose.core.yml ps'

# Check logs
ssh backend.ktrdr.home.mynerd.place 'docker compose -f /opt/ktrdr-core/docker-compose.core.yml logs --tail 50'
```

**Verification**:
```bash
# Health checks
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/health
curl http://grafana.ktrdr.home.mynerd.place:3000/api/health
curl http://backend.ktrdr.home.mynerd.place:16686/api/services
```

**Acceptance Criteria**:
- [ ] All core services running
- [ ] Backend API accessible
- [ ] Grafana accessible
- [ ] Jaeger accessible
- [ ] Prometheus accessible
- [ ] Database healthy

---

### Task 5.8: Deploy Worker Stacks

**Goal**: Workers running on Nodes B and C

**Actions**:
1. Deploy workers to Node B
2. Deploy workers to Node C
3. Verify workers register with backend

**Commands**:
```bash
# Deploy to Node B
ktrdr deploy workers B

# Deploy to Node C
ktrdr deploy workers C

# Check worker registration
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq
```

**Acceptance Criteria**:
- [ ] Workers running on Node B
- [ ] Workers running on Node C
- [ ] All workers registered with backend
- [ ] Workers show as AVAILABLE

---

### Task 5.9: Verify Full System

**Goal**: End-to-end system verification

**Verification Steps**:
1. Check all services via API
2. Run sample operation
3. Verify metrics in Prometheus
4. Verify traces in Jaeger
5. Check NFS access from workers

**Commands**:
```bash
# 1. Check registered workers
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq

# 2. Check Prometheus targets
curl http://backend.ktrdr.home.mynerd.place:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# 3. Run test operation (via CLI or API)
# Example: data download or simple backtest

# 4. Check Jaeger for traces
curl http://backend.ktrdr.home.mynerd.place:16686/api/services | jq

# 5. Verify results in NFS
ssh workers-b.ktrdr.home.mynerd.place 'ls /mnt/ktrdr-shared/results'
```

**Acceptance Criteria**:
- [ ] All workers registered (expected: 4 on B, 4 on C)
- [ ] Prometheus shows all targets UP
- [ ] Sample operation completes successfully
- [ ] Traces visible in Jaeger
- [ ] Results written to NFS share

---

### Task 5.10: Create Pre-prod Grafana Dashboards

**Goal**: Adapted dashboards for pre-prod topology

**Actions**:
1. Copy dashboards from local dev (Project 3)
2. Update targets for pre-prod hostnames
3. Add node-specific panels (Node B vs Node C)
4. Add aggregate views
5. Test with real pre-prod data

**Dashboard Updates**:
- System Overview: Show all nodes
- Worker Status: Group by node
- Operations: Show distribution across nodes
- Add: Node health comparison panel

**Acceptance Criteria**:
- [ ] Dashboards loaded in pre-prod Grafana
- [ ] Show data from all nodes
- [ ] Node grouping visible
- [ ] Useful for pre-prod monitoring

---

### Task 5.11: Test Rollback Procedure

**Goal**: Verify can rollback to previous version

**Actions**:
1. Note current image tag
2. Deploy new version (or re-deploy same)
3. Rollback to previous tag
4. Verify services work

**Commands**:
```bash
# Deploy specific older tag
ktrdr deploy core all --tag sha-abc1234
ktrdr deploy workers B --tag sha-abc1234
ktrdr deploy workers C --tag sha-abc1234

# Verify
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/health
```

**Acceptance Criteria**:
- [ ] Can deploy specific tag
- [ ] Services start with older version
- [ ] System functions correctly

---

### Task 5.12: Document Operational Procedures

**File**: Update `docs/architecture/pre-prod-deployment/OPERATIONS.md`

**Goal**: Complete operational documentation

**Sections to Add/Update**:
1. Daily operations checklist
2. Deployment procedures
3. Scaling procedures
4. Backup procedures
5. Troubleshooting guide
6. Disaster recovery

**Content**:
- How to check system health
- How to deploy updates
- How to scale workers
- How to backup database
- Common issues and solutions
- How to restore from backup

**Acceptance Criteria**:
- [ ] All operational procedures documented
- [ ] Clear step-by-step instructions
- [ ] Troubleshooting guide complete
- [ ] Runnable by team members

---

## Validation

**Final System Verification**:
```bash
# 1. All services healthy
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/health
curl http://grafana.ktrdr.home.mynerd.place:3000/api/health

# 2. Workers registered
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq 'length'
# Expected: 8 (4 per node)

# 3. Prometheus targets
curl -s http://backend.ktrdr.home.mynerd.place:9090/api/v1/targets | \
  jq '[.data.activeTargets[] | select(.health=="up")] | length'
# Expected: All targets UP

# 4. Run full operation
ktrdr data load AAPL 1d --start-date 2024-01-01
ktrdr operations list

# 5. Check traces
curl http://backend.ktrdr.home.mynerd.place:16686/api/traces?service=ktrdr-backend&limit=1 | jq

# 6. Check Grafana dashboards
# Open http://grafana.ktrdr.home.mynerd.place:3000
# Verify all dashboards show data

# 7. Test worker failover (optional)
# Stop one worker, verify operations still work

# 8. Test rollback
ktrdr deploy core backend --tag sha-previous
# Verify still works
```

---

## Success Criteria

- [ ] All 3 LXCs operational
- [ ] DNS resolving correctly
- [ ] NFS shared storage working
- [ ] Core stack deployed and healthy
- [ ] 8 workers deployed and registered
- [ ] Prometheus scraping all targets
- [ ] Grafana dashboards showing data
- [ ] Jaeger receiving traces
- [ ] Sample operations completing
- [ ] Rollback procedure verified
- [ ] Documentation complete

---

## Dependencies

**Depends on**:
- Project 2 (CI/CD & GHCR) - need images to pull
- Project 3 (Observability Dashboards) - dashboards to evolve
- Project 4 (Secrets & Deployment CLI) - need deployment commands

**Blocks**: Nothing (final project)

---

## Notes

- LXC provisioning is manual (per DESIGN.md)
- First deployment will pull all images (slow)
- Subsequent deployments only pull changed layers (fast)
- Workers use profile-based scaling (see DESIGN.md Decision 11)

---

## Post-Deployment

After successful deployment:
1. Monitor for 24-48 hours
2. Run various operation types
3. Check resource usage
4. Fine-tune configurations if needed
5. Set up backup schedule
6. Consider alerting rules (future enhancement)

---

**Previous Project**: [Project 4: Secrets & Deployment CLI](PLAN_4_SECRETS_CLI.md)

---

## Complete Project Summary

| Project | Description | Status |
|---------|-------------|--------|
| 1a | Dependencies & Dockerfile | Ready |
| 1b | Local Dev Environment | Ready |
| 2 | CI/CD & GHCR | Ready |
| 3 | Observability Dashboards | Ready |
| 4 | Secrets & Deployment CLI | Ready |
| 5 | Pre-prod Deployment | Ready |

**Dependency Flow**:
```
1a ──> 1b ──> 3
  \         /
   └──> 2 ──> 4 ──> 5
```

**Total Estimated Effort**: Medium-Large (all projects combined)
