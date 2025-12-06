# Example Configurations

**IMPORTANT**: The files in this directory are **EXAMPLES ONLY** and are not directly deployable.

For actual deployment configurations, see:

- **Local development**: `/deploy/environments/local/`
- **Homelab pre-prod**: `/deploy/environments/homelab/`
- **Canary testing**: `/deploy/environments/canary/`
- **Shared resources**: `/deploy/shared/` (Grafana dashboards, datasources)

## Purpose

These examples are provided for documentation purposes to illustrate:

- Configuration patterns
- Expected file structure
- Environment variable usage

## DO NOT

- Copy these files directly to production
- Modify these files expecting changes to take effect
- Use these as the source of truth for deployment

## Source of Truth

The canonical deployment configurations live in `/deploy/`. Any changes should be made there.
