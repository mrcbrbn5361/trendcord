#!/data/data/com.termux/files/usr/bin/python3
# Trendcord DNS Failover
# Bot düştüğünde DNS'i GitHub Pages'e yönlendirir

import os
import json
import time
import socket
import urllib.request
import subprocess
from pathlib import Path

# .env dosyasından oku
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

API_TOKEN = os.environ.get("CF_API_TOKEN", "")
ZONE_ID = os.environ.get("CF_ZONE_ID", "")
ZONE_NAME = os.environ.get("CF_ZONE_NAME", "miracdeveloper.com.tr")
RECORD_NAME = os.environ.get("CF_RECORD_NAME", "trendcord.miracdeveloper.com.tr")
GITHUB_PAGES_CNAME = os.environ.get("CF_GITHUB_PAGES", "mrcbrbn5361.github.io")
TUNNEL_CNAME = os.environ.get("CF_TUNNEL_CNAME", "a42d6853-0530-41dd-be93-b501a66dd5d3.cfargotunnel.com")

if not API_TOKEN:
    print("⚠️  CF_API_TOKEN .env dosyasında tanımlı değil. DNS failover çalışmaz.")
    print("   .env dosyasına ekleyin: CF_API_TOKEN=cfut_...")

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def api_call(method, path, data=None):
    url = f"https://api.cloudflare.com/client/v4{path}"
    req_data = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=req_data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_dns_record():
    result = api_call("GET", f"/zones/{ZONE_ID}/dns_records?name={RECORD_NAME}&type=A")
    if result.get("success") and len(result.get("result", [])) > 0:
        return result["result"][0]
    result = api_call("GET", f"/zones/{ZONE_ID}/dns_records?name={RECORD_NAME}&type=CNAME")
    if result.get("success") and len(result.get("result", [])) > 0:
        return result["result"][0]
    return None

def set_dns_target(target_cname, proxied):
    record = get_dns_record()
    if not record:
        api_call("POST", f"/zones/{ZONE_ID}/dns_records", {
            "type": "CNAME", "name": RECORD_NAME,
            "content": target_cname, "ttl": 120, "proxied": proxied
        })
        return f"CNAME → {target_cname} (proxied={proxied})"
    record_id = record["id"]
    current_content = record.get("content", "")
    current_proxied = record.get("proxied", True)
    if current_content == target_cname and current_proxied == proxied:
        return "no_change"
    api_call("PUT", f"/zones/{ZONE_ID}/dns_records/{record_id}", {
        "type": "CNAME", "name": RECORD_NAME,
        "content": target_cname, "ttl": 120, "proxied": proxied
    })
    return f"CNAME → {target_cname} (proxied={proxied})"

def is_bot_alive():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", 8000))
        s.close()
        return True
    except:
        return False

LOG_FILE = "/data/data/com.termux/files/home/workspace/trendcord/logs/dns_failover.log"
LOG_MAX_SIZE = 5 * 1024 * 1024  # 5MB
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def log(msg):
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > LOG_MAX_SIZE:
            backup = LOG_FILE + ".1"
            if os.path.exists(backup):
                os.remove(backup)
            os.rename(LOG_FILE, backup)
    except: pass
    with open(LOG_FILE, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}\n")
    print(msg)

if __name__ == "__main__":
    bot_was_down = False
    while True:
        alive = is_bot_alive()
        if alive and bot_was_down:
            result = set_dns_target(TUNNEL_CNAME, True)
            log(f"🟢 Bot geri geldi → Tunnel: {result}")
            bot_was_down = False
        elif not alive and not bot_was_down:
            result = set_dns_target(GITHUB_PAGES_CNAME, False)
            log(f"🔴 Bot düştü → GitHub Pages: {result}")
            bot_was_down = True
        time.sleep(30)
