import os, re, time, subprocess, logging, yaml
from prometheus_client import start_http_server, Gauge, Counter, Histogram

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("net-monitor")

# Metrics
DEVICE_UP = Gauge("device_up", "1=up 0=down", ["device","ip","location"])
PING_RTT_MS = Gauge("ping_rtt_ms", "RTT ms", ["device","ip","location"])
PING_LOSS = Gauge("ping_packet_loss_percent", "loss %", ["device","ip","location"])
SNMP_UPTIME = Gauge("snmp_sys_uptime_seconds", "uptime s", ["device","ip"])
POLL_ERRORS = Counter("poller_errors_total", "errors", ["device","type"])

# Absolute paths guaranteed to exist on debian slim after apt-get
PING_BIN = "/bin/ping"
SNMPGET_BIN = "/usr/bin/snmpget"

def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)

def ping_device(ip):
    try:
        r = subprocess.run([PING_BIN, "-c", "4", "-W", "2", ip],
                           capture_output=True, text=True, timeout=10)
        loss = 100.0
        m_loss = re.search(r"(\d+(?:\.\d+)?)\s*%\s*packet loss", r.stdout)
        if m_loss: loss = float(m_loss.group(1))

        rtt = None
        m_rtt = re.search(r"=\s*[\d.]+/([\d.]+)/[\d.]+/[\d.]+\s*ms", r.stdout)
        if m_rtt: rtt = float(m_rtt.group(1))

        return {"up": r.returncode == 0, "rtt_ms": rtt, "loss_pct": loss}
    except Exception as e:
        log.warning(f"Ping error for {ip}: {e}")
        return {"up": False, "rtt_ms": None, "loss_pct": 100.0}

def snmp_get(ip, community, oid, port=161):
    try:
        r = subprocess.run([SNMPGET_BIN, "-v2c", "-c", community, "-OvQ", f"{ip}:{port}", oid],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception as e:
        log.debug(f"SNMP get error {ip}: {e}")
    return None

def poll_device(device):
    name = device["name"]
    ip = device["ip"]
    location = device.get("location", "unknown")
    labels = {"device": name, "ip": ip, "location": location}

    log.info(f"Polling {name} ({ip})")

    # 1. Ping
    p = ping_device(ip)
    DEVICE_UP.labels(**labels).set(1 if p["up"] else 0)
    PING_LOSS.labels(**labels).set(p["loss_pct"])

    if p["rtt_ms"] is not None:
        PING_RTT_MS.labels(**labels).set(p["rtt_ms"])
        log.info(f"  ICMP up=True rtt={p['rtt_ms']}ms loss={p['loss_pct']}%")
    else:
        log.warning(f"  ICMP up=False loss={p['loss_pct']}%")
        if not p["up"]:
            POLL_ERRORS.labels(device=name, type="icmp").inc()

    # 2. SNMP (if enabled in devices.yaml)
    if device.get("snmp_enabled", False):
        community = device.get("snmp_community", "public")
        port = device.get("snmp_port", 161)
        val = snmp_get(ip, community, "1.3.6.1.2.1.1.3.0", port)
        if val:
            try:
                m = re.search(r"\((\d+)\)", val)
                ticks = int(m.group(1)) if m else int(val)
                SNMP_UPTIME.labels(device=name, ip=ip).set(ticks / 100)
            except Exception:
                pass

def main():
    config_path = os.getenv("CONFIG_PATH", "/etc/exporter/devices.yaml")
    start_http_server(9200)
    log.info("Starting network-monitor exporter on :9200")

    while True:
        try:
            devices = load_config(config_path).get("devices", [])
            log.info(f"Poll cycle — {len(devices)} device(s)")
            for d in devices:
                try:
                    poll_device(d)
                except Exception as e:
                    log.error(f"Error polling {d.get('name')}: {e}")
        except Exception as e:
            log.error(f"Cycle error: {e}")

        time.sleep(int(os.getenv("POLL_INTERVAL", "30")))

if __name__ == "__main__":
    main()