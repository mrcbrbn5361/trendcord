"""Trendcord web katmani duman testleri (CSRF, guvenlik basligi, rota kapilari).

Calistirma:
    COOKIE_SECURE=0 venv/bin/python tests/test_web_smoke.py

`COOKIE_SECURE=0` zorunludur: session cookie'si `Secure` isaretli oldugu icin
tarayici benzeticisi duz HTTP uzerinde gondermez ve CSRF belirteci eslesmez.
Uretimde deger 1 (guvenli) kalmalidir.
"""
import http.cookiejar
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, "/data/data/com.termux/files/home/trendcord")
import uvicorn

PORT = int(os.environ.get("SMOKE_PORT", "8823"))
BASE = f"http://127.0.0.1:{PORT}"
Q = '"'
fails = []


def run():
    uvicorn.run("web.app:app", host="127.0.0.1", port=PORT, log_level="error", lifespan="on")


threading.Thread(target=run, daemon=True).start()
for _ in range(60):
    try:
        urllib.request.urlopen(BASE + "/", timeout=3).read()
        break
    except Exception:
        time.sleep(0.5)
else:
    print("sunucu baslamadi")
    sys.exit(1)

cj = http.cookiejar.CookieJar()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj), NoRedirect)


def req(path, data=None, method="GET", headers=None):
    r = urllib.request.Request(BASE + path, data=data, method=method)
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    try:
        resp = op.open(r, timeout=15)
        return resp.status, resp.read().decode("utf-8", "replace"), {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), {k.lower(): v for k, v in e.headers.items()}


def post_form(path, fields):
    data = urllib.parse.urlencode(fields).encode()
    return req(path, data, "POST", {"Content-Type": "application/x-www-form-urlencoded"})


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{(' -> ' + detail) if detail else ''}")
    if not cond:
        fails.append(name)


# ---------------------------------------------------------------- GET / temel
st, html, hdrs = req("/")
tok = re.search(r'name="csrf_token" value="([^"]+)"', html)
print("== Temel GET")
check("GET / 200", st == 200, str(st))
check("csrf alani var", tok is not None)
check("session cerezi", "session" in [c.name for c in cj], str([c.name for c in cj]))

# ---------------------------------------------------------- guvenlik basliklari
print("\n== Guvenlik basliklari")
for h, need in [
    ("content-security-policy", True), ("permissions-policy", True),
    ("x-content-type-options", "nosniff"), ("x-frame-options", "DENY"),
    ("referrer-policy", True), ("cross-origin-opener-policy", True),
]:
    v = hdrs.get(h)
    check(h, (v is not None) if need is True else (v == need), str(v)[:70])
check("CSP script-src 'self' (inline script yok)", "script-src 'self'" in hdrs.get("content-security-policy", ""), "")
check("CSP frame-ancestors", "frame-ancestors 'none'" in hdrs.get("content-security-policy", ""))
check("HSTS yok (http yerel)", "strict-transport-security" not in {k.lower() for k in hdrs})

# --------------------------------------------------------------- CSRF reddi
print("\n== CSRF reddi (403 olmali)")
for name, path, fields in [
    ("gecersiz token", "/notifications/save", {"csrf_token": "SAHTE"}),
    ("bos token", "/notifications/save", {"csrf_token": ""}),
    ("token yok", "/notifications/save", {}),
    ("gecersiz, admin davet", "/admin/servers/1/invite", {"csrf_token": "SAHTE"}),
    ("gecersiz, urun ekle", "/product/add", {"csrf_token": "x", "url": "https://x"}),
]:
    st, _, _ = post_form(path, fields)
    check(name, st == 403, f"HTTP {st}")

# -------------------------------------------------------- CSRF gecerli -> rotaya ulasir
print("\n== Gecerli token rotaya ulasmali (403 olmamali)")
if tok:
    good = tok.group(1)
    for name, path, fields in [
        ("notifications/save", "/notifications/save", {}),
        ("product/add", "/product/add", {"url": "https://www.trendyol.com/ornek-urun"}),
    ]:
        st, body, h = post_form(path, {**fields, "csrf_token": good})
        check(name, st != 403, f"HTTP {st}")
        check(f"{name} 400 degil", st != 400, f"HTTP {st}")

# ------------------------------------------------- API CSRF muafiyeti
print("\n== API CSRF muafiyeti (403 almamali)")
for name, path, body in [
    ("POST /api/v1/products", "/api/v1/products", b'{"url":"x"}'),
    ("POST /api/v1/auth/login", "/api/v1/auth/login", b'{"code":"x"}'),
    ("DELETE /api/v1/products/1", "/api/v1/products/1", None),
]:
    st, _, _ = req(path, body, "POST" if body is not None else "DELETE",
                   {"Content-Type": "application/json"} if body is not None else {})
    check(name + " CSRF bypass (403 degil)", st != 403, f"HTTP {st}")

# ------------------------------------------------- logout POST'a tasindi
print("\n== /logout")
st, _, _ = req("/logout")
check("GET /logout 405", st == 405, f"HTTP {st}")
st, _, _ = post_form("/logout", {"csrf_token": "SAHTE"})
check("POST /logout gecersiz token 403", st == 403, f"HTTP {st}")
if tok:
    st, body, _ = post_form("/logout", {"csrf_token": tok.group(1)})
    check("POST /logout gecerli token 200", st == 200, f"HTTP {st}")
    if st != 200:
        print("      govde:", body[:200])

# ------------------------------------------------- HEAD + cache politikasi
print("\n== HEAD destegi (RFC 9110)")
for p in ["/", "/features", "/how-it-works", "/servers", "/compare", "/stats"]:
    st, body, h = req(p, method="HEAD")
    check(f"HEAD {p} 200", st == 200, f"HTTP {st}")
    check(f"HEAD {p} govde bos", len(body) == 0, f"{len(body)} bayt")
st, _, h = req("/static/css/tailwind.min.css", method="HEAD")
check("HEAD /static/css 200", st == 200, f"HTTP {st}")

print("\n== Cache politikasi")
st, _, h = req("/")
cc = h.get("cache-control", "")
check("dinamik HTML no-store", "no-store" in cc, cc)
check("dinamik HTML private", "private" in cc, cc)
st, _, h = req("/api/v1/me")
check("API no-store", "no-store" in h.get("cache-control", ""), h.get("cache-control", "-"))
for a in ["/static/css/tailwind.min.css?v=9", "/static/js/app.js?v=2", "/static/js/chart.js?v=1",
          "/static/img/placeholder.svg", "/static/fonts/nunito-sans.woff2?v=2"]:
    st, _, h = req(a)
    cc = h.get("cache-control", "")
    check(f"{a.split('/')[-1]} immutable", "immutable" in cc, cc)
# Surumsuz istek bilincli olarak kisa cache alir: URL degismedigi icin
# dosya guncellenirse istemci eski icerigi gormemesi icin immutable verilmez.
for a in ["/static/js/app.js", "/static/js/chart.js"]:
    st, _, h = req(a)
    cc = h.get("cache-control", "")
    check(f"{a.split('/')[-1]} surumsuz -> 86400", "max-age=86400" in cc, cc)

# ------------------------------------------------------------ sayfa kontrolleri
print("\n== Sayfa kontrolleri")
for p in ["/", "/features", "/how-it-works", "/servers", "/users", "/compare", "/stats", "/privacy", "/terms"]:
    st, body, h = req(p)
    ok = st == 200
    check(f"GET {p}", ok, f"HTTP {st} {len(body):,}b")
    if ok:
        bad = len(re.findall(r'\son(?:click|submit|input|change|error)="', body))
        check(f"{p} inline handler yok", bad == 0, str(bad))
        check(f"{p} placehold.co yok", "placehold.co" not in body)
        check(f"{p} material-symbols yok", "material-symbols" not in body)
        check(f"{p} app.js var", "/static/js/app.js" in body)

print("\n== Statik varliklar")
for a, ctype in [("/static/js/app.js", "javascript"), ("/static/js/chart.js", "javascript"),
                 ("/static/css/tailwind.min.css", "css"), ("/static/img/placeholder.svg", "svg")]:
    st, _, h = req(a)
    check(a, st == 200 and ctype in h.get("content-type", ""), f"{st} {h.get('Content-Type')}")

print(f"\n{'='*46}\nSONUC: {len(fails)} basarisiz")
for f in fails:
    print("  FAIL:", f)
