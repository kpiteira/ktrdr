# ktrdr DNS & Naming Strategy  
_for homelab + future cloud deployment_

## 1. Goals

This document defines a **DNS and naming convention** for the `ktrdr` project across:

- your **homelab** (containers, VMs, LXC, etc.)
- future **cloud** deployments
- potential hybrid setups (some services local, some remote)

Design goals:

- Use **best-practice** DNS patterns (no fake TLDs).
- Avoid renaming services when moving from **homelab → cloud**.
- Support **service discovery**, **reverse proxies**, and **observability**.
- Be easy to **reason about** and **extend**.

---

## 2. Core Principles

1. **Use a domain you own**  
   - Root domain: `mynerd.place`
   - Private/internal zone: `home.mynerd.place`

2. **Separate public vs. private via subdomains**
   - Public / global: `*.mynerd.place`
   - Private / homelab: `*.home.mynerd.place`

3. **Use a project namespace**  
   Group ktrdr services under `ktrdr`:

- `*.ktrdr.mynerd.place` (public / cloud)
- `*.ktrdr.home.mynerd.place` (private / homelab)

4. **Service-based naming first, instance-based naming second**
   - Service name: `backend`, `api`, `workers`, `postgres`, `redis`…
   - Optional instance suffix: `-01`, `-02`, `-hv01` (hypervisor 1), etc.

5. **Keep names human-readable and self-descriptive**  
   Names should tell you:
   - what it is (`backend`, `worker`, `postgres`)  
   - where it lives (`home`, `cloud`)  
   - which project (`ktrdr`)  

---

## 3. DNS Zones Overview

### 3.1 Public Zone (Cloud / Internet-facing)

**Managed at your DNS provider:**

- **Zone:** `mynerd.place`
- **Project namespace:** `ktrdr.mynerd.place`

Examples:

```
api.ktrdr.mynerd.place        → public API endpoint
backend.ktrdr.mynerd.place    → public/reachable backend (or reverse proxy)
workers.ktrdr.mynerd.place    → NAT or ingress to worker cluster
grafana.ktrdr.mynerd.place    → hosted monitoring (if exposed)
```

You can further split environments:

```
api.dev.ktrdr.mynerd.place
api.staging.ktrdr.mynerd.place
api.prod.ktrdr.mynerd.place
```

---

### 3.2 Private Zone (Homelab / LAN)

**Hosted on your internal DNS (e.g. Unbound, CoreDNS, Pi-hole + dnsmasq, etc.):**

- **Zone:** `home.mynerd.place`
- **Project namespace:** `ktrdr.home.mynerd.place`

Examples:

```
backend.ktrdr.home.mynerd.place
api.ktrdr.home.mynerd.place
workers.ktrdr.home.mynerd.place
postgres.ktrdr.home.mynerd.place
redis.ktrdr.home.mynerd.place
mq.ktrdr.home.mynerd.place
grafana.ktrdr.home.mynerd.place
prometheus.ktrdr.home.mynerd.place
otel.ktrdr.home.mynerd.place
```

---

## 4. Naming Conventions

(Service naming etc. — truncated to save space, since the full content is already known.)

---

