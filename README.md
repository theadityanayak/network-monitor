# Network Monitoring Microservice

> **Resume line:** *"Developed a containerized network monitoring microservice using Python, Prometheus, and Grafana, implementing ICMP reachability checks and SNMP polling to collect and visualize real-time network device health metrics."*

A production-grade, fully containerized network observability stack that bridges CCNA-level networking knowledge (SNMP, ICMP) with modern DevOps tooling.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Network (bridge)                 │
│                                                             │
│  ┌──────────────────┐    scrape     ┌──────────────────┐   │
│  │  Python Exporter │◄──────────────│   Prometheus     │   │
│  │   port 9200      │  /metrics     │   port 9090      │   │
│  │                  │               └────────┬─────────┘   │
│  │  • ICMP ping     │                        │ query        │
│  │  • SNMP v2c GET  │               ┌────────▼─────────┐   │
│  │  • prom_client   │               │    Grafana        │   │
│  └────────┬─────────┘               │    port 3000      │   │
│           │                         └──────────────────┘   │
│     polls every 30s                                         │
└───────────┼─────────────────────────────────────────────────┘
            │
    ┌───────▼────────────────────┐
    │  Your Network Devices      │
    │  • Routers (SNMP + ICMP)   │
    │  • Switches                │
    │  • Servers / Hosts         │
    └────────────────────────────┘
```

## Stack

| Component | Role |
|-----------|------|
| **Python 3.12** | Custom exporter: ICMP ping + SNMP polling |
| **pysnmp** | SNMPv2c GET/WALK for interface & system OIDs |
| **prometheus-client** | Exposes metrics on `:9200/metrics` |
| **Prometheus 2.51** | Scrapes exporter, evaluates alert rules, stores TSDB |
| **Grafana 10.4** | Dashboards auto-provisioned from JSON, visualises all metrics |
| **Docker Compose** | Single-command deployment of all three services |

---

## Quick Start

### Prerequisites

- Docker Engine 24+
- Docker Compose v2 (`docker compose`)
- Devices reachable from the Docker host

### 1 — Configure your devices

Edit `devices.yaml` to list the hosts you want to monitor:

```yaml
devices:
  - name: "core-router"
    ip: "192.168.1.1"
    location: "rack-A"
    snmp_community: "public"
    snmp_enabled: true

  - name: "web-server"
    ip: "10.0.0.50"
    location: "dmz"
    snmp_enabled: false     # ICMP-only
```

### 2 — Start the stack

```bash
docker compose up -d --build
```

### 3 — Open the interfaces

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| Exporter metrics | http://localhost:9200/metrics | — |

The **Network Monitor — Overview** dashboard is pre-loaded automatically.

---

## Metrics Reference

### ICMP Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `device_up` | Gauge | 1 = reachable, 0 = down |
| `ping_rtt_ms` | Gauge | Average round-trip time (ms) |
| `ping_packet_loss_percent` | Gauge | % packets lost |

Labels on all ICMP metrics: `device`, `ip`, `location`

### SNMP Metrics

| Metric | Type | OID | Description |
|--------|------|-----|-------------|
| `snmp_sys_uptime_seconds` | Gauge | 1.3.6.1.2.1.1.3.0 | Device uptime |
| `snmp_cpu_load_percent` | Gauge | UCD-SNMP | 1-minute CPU load average |
| `snmp_interface_oper_status` | Gauge | ifOperStatus | 1=up, 2=down, 3=testing |
| `snmp_interface_in_octets_total` | Gauge | ifInOctets | Cumulative bytes received |
| `snmp_interface_out_octets_total` | Gauge | ifOutOctets | Cumulative bytes sent |

Labels: `device`, `ip`; interface metrics also have `interface`

### Poller Health

| Metric | Type | Description |
|--------|------|-------------|
| `poller_errors_total` | Counter | Errors by device and type |
| `poller_poll_duration_seconds` | Histogram | Time to poll each device |

---

## Grafana Dashboard Panels

The pre-built **Network Monitor — Overview** dashboard includes:

- **Device Status** — colour-coded UP/DOWN stat panels
- **Current RTT** — per-device latency with threshold colouring
- **Packet Loss %** — live and historical view
- **Device Uptime** — SNMP sysUpTime in human-readable form
- **ICMP RTT over time** — time-series graph for all devices
- **Packet Loss over time** — trend detection
- **Interface Throughput** — `rate()` of ifIn/OutOctets → bytes/sec
- **Interface Operational Status** — table with UP/DOWN colour mapping
- **Poller Errors** — 5-minute error rate per device
- **Poll Duration Percentiles** — p50/p95 latency of the poller itself

---

## Alert Rules

Pre-configured Prometheus alerts in `prometheus/rules/network_alerts.yml`:

| Alert | Severity | Condition |
|-------|----------|-----------|
| `DeviceDown` | critical | `device_up == 0` for 1 min |
| `HighPacketLoss` | warning | `>10%` loss for 2 min |
| `HighLatency` | warning | `>200ms` RTT for 2 min |
| `InterfaceDown` | warning | `ifOperStatus == 2` for 2 min |
| `HighCPULoad` | warning | `>80%` CPU for 5 min |
| `PollerErrorsHigh` | warning | `>5` errors in 5 min |

View firing alerts at: http://localhost:9090/alerts

---

## Configuration Reference

### `devices.yaml` fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | required | Friendly name (used as Prometheus label) |
| `ip` | string | required | IPv4 address to target |
| `location` | string | `"unknown"` | Freeform location label |
| `snmp_enabled` | bool | `true` | Enable SNMP polling |
| `snmp_community` | string | `"public"` | SNMPv2c community string |
| `snmp_port` | int | `161` | SNMP UDP port |

### Environment variables (exporter)

| Variable | Default | Description |
|----------|---------|-------------|
| `CONFIG_PATH` | `/etc/exporter/devices.yaml` | Path to devices config |
| `METRICS_PORT` | `9200` | Port for Prometheus scraping |
| `POLL_INTERVAL` | `30` | Seconds between poll cycles |

---

## Useful Commands

```bash
# Tail exporter logs
docker compose logs -f exporter

# Reload Prometheus config without restart
curl -X POST http://localhost:9090/-/reload

# Check targets in Prometheus
open http://localhost:9090/targets

# Shell into exporter for debugging
docker compose exec exporter bash

# Manual SNMP test inside container
docker compose exec exporter python -c "
from pysnmp.hlapi import *
for (ei, es, _, vbs) in nextCmd(
    SnmpEngine(), CommunityData('public'),
    UdpTransportTarget(('192.168.1.1', 161)),
    ContextData(), ObjectType(ObjectIdentity('1.3.6.1.2.1.2.2.1.2')),
    lexicographicMode=False):
    if ei: break
    for vb in vbs: print(vb)
"

# Stop everything
docker compose down

# Destroy volumes (clears all metric history)
docker compose down -v
```

---

## Extending the Project

### Add a new SNMP metric

1. Define a new `Gauge` in `exporter/exporter.py`
2. Add the OID constant
3. Call `snmp_get()` or `snmp_walk()` in `poll_device()`
4. Rebuild: `docker compose up -d --build exporter`

### Add SNMPv3 support

Replace `CommunityData(community)` with:

```python
from pysnmp.hlapi import UsmUserData
UsmUserData('username', authKey='authpass', privKey='privpass',
            authProtocol=usmHMACSHAAuthProtocol,
            privProtocol=usmAesCfb128Protocol)
```

### Connect Alertmanager

Uncomment the `alerting:` section in `prometheus/prometheus.yml` and add an Alertmanager service to `docker-compose.yml`.

---

## Project Structure

```
network-monitor/
├── docker-compose.yml
├── devices.yaml                      # ← Edit this to add your devices
├── exporter/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── exporter.py                   # Core poller logic
├── prometheus/
│   ├── prometheus.yml
│   └── rules/
│       └── network_alerts.yml
└── grafana/
    ├── dashboards/
    │   └── network_overview.json     # Pre-built dashboard
    └── provisioning/
        ├── datasources/
        │   └── prometheus.yml
        └── dashboards/
            └── default.yml
```
