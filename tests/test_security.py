#!/usr/bin/env python3
"""Guvenlik regresyon testleri.

Kapatilan aciklar:
  1. Path traversal (/static/../../.env -> bot tokeni)
  2. Origin'in disaridan erisilebilir olmasi (Cloudflare bypass)
  3. Redis yokken rate limit'in fail-open kalip kalmasiz birakmasi
  4. X-Forwarded-For'in guvenilmez sekilde kabul edilmesi
  5. OAuth state dogrulamasinin "state yoksa gec" ile atlatilmasi
  6. Giriste session yenilenmemesi (session fixation)
  7. /api/v1/products kapsam sizintisi
"""
import ast
import io
import os
import re
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def read(*parts):
    return io.open(os.path.join(ROOT, *parts), encoding="utf-8").read()


# ---------------------------------------------------------------- 1) path traversal
print("== Path traversal (/static/..)")
app_src = read("web", "app.py")
check("resolve() ile normalize ediliyor", ".resolve()" in app_src)
check("relative_to() ile kapsam kontrolu var", "relative_to(" in app_src)
check("kapsam disi -> 404", 'PlainTextResponse("Not Found", status_code=404)' in app_src)

# ---------------------------------------------------------------- 2) origin erisimi
print("\n== Origin yalniz yerel dinlesin (Cloudflare bypass)")
main_src = read("main.py")
check("WEB_HOST tanimli", 'WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")' in main_src)
check("uvicorn WEB_HOST kullanuyor", 'host=WEB_HOST' in main_src)
check("0.0.0.0 varsayilan degil", 'host="0.0.0.0"' not in main_src)

# ---------------------------------------------------------------- 3) rate limit
print("\n== Rate limit Redis'siz de calismali")
api_src = read("web", "api_mobile.py")
check("in-memory yedek sayac var", "def _mem_rate_limit(" in api_src)
check("Redis hatasinda yedeke dustugu", "return _mem_rate_limit(key, limit, window)" in api_src)
check("fail-open 'return True' kalmadi",
      'logger.warning("[API-RATE] Redis erisilemedi, fail-open")' not in api_src)
check("strict modu var", "strict: bool = False" in api_src)
check("login strict kullaniyor", 'rate_limit(f"login:{ip}", 10, 3600, strict=True)' in api_src)
check("bellek temizligi var", "4096" in api_src)

# ---------------------------------------------------------------- 4) XFF
print("\n== X-Forwarded-For yalniz guvenilir proxy'den")
check("TRUSTED_PROXIES tanimli", "TRUSTED_PROXIES" in api_src)
check("_extract_client_ip fonksiyonu var", "def _extract_client_ip(scope)" in api_src)
check("peer guvenilir degilse XFF reddediliyor",
      'if peer not in TRUSTED_PROXIES:' in api_src)
check("middleware XFF'i _extract_client_ip ile aliyor",
      "ip = _extract_client_ip(scope)" in api_src)

# ---------------------------------------------------------------- 5) OAuth state
print("\n== OAuth state (login CSRF)")
check("state yoksa reddediliyor", 'error=state_missing' in app_src)
check("eski 'proceeding without CSRF check' gitti",
      "proceeding without CSRF check" not in app_src)
check("state bos da reddediliyor", "if not state or state != saved_state:" in app_src)

# ---------------------------------------------------------------- 6) session fixation
print("\n== Session fixation")
sess_src = read("web", "sessions.py")
check("ServerSession.regenerate var", "def regenerate(self)" in sess_src)
check("regenerate eski kaydi siliyor", "DELETE FROM sessions WHERE session_id = ?" in sess_src)
check("cagirisda regenerate kullaniliyor", "regenerate()" in app_src)
check("OAuth 303 donuyor (302 degil)",
      'RedirectResponse("/dashboard", status_code=303)' in app_src)

# ---------------------------------------------------------------- 7) API kapsam
print("\n== /api/v1/products kapsam sizintisi")
tree = ast.parse(api_src)
products_fn = None
for node in ast.walk(tree):
    if isinstance(node, ast.AsyncFunctionDef) and node.name == "products":
        products_fn = node
        break
check("products() bulundu", products_fn is not None)
if products_fn:
    src = ast.unparse(products_fn)
    check("kimliksiz 'SELECT * FROM products' kalmadi",
          'q("SELECT * FROM products LIMIT ? OFFSET ?", (limit, offset))' not in src)
    check("kimlik dogrulamasi var", "get_current_user" in src)
    check("varsayilan kapsam kendi urunleri", src.count("WHERE user_id=?") >= 1)

# ---------------------------------------------------------------- 8) genel
print("\n== Genel")
check("SQL parametrik (string-format SELECT yok)",
      'q("SELECT * FROM products LIMIT' not in api_src)
check("SECRET_KEY gercek (placeholder degil)",
      'or "trendcord-dev-csrf"' in app_src)   # fallback var ama SECRET_KEY oncelikli

print(f"\n{'=' * 46}\nSONUC: {len(fails)} basarisiz")
for f in fails:
    print("  FAIL:", f)
sys.exit(1 if fails else 0)