"""Trendcord web katmani duman testleri (CSRF, guvenlik basligi, rota kapilari).

Calistirma:
    COOKIE_SECURE=0 venv/bin/python tests/test_web_smoke.py

`COOKIE_SECURE=0` zorunludur: session cookie'si `Secure` isaretli oldugu icin
tarayici benzeticisi duz HTTP uzerinde gondermez ve CSRF belirteci eslesmez.
Uretimde deger 1 (guvenli) kalmalidir.
"""
import glob
import http.cookiejar
import io
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
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
csp = hdrs.get("content-security-policy", "")
check("CSP script-src 'self' (inline script yok)",
      "script-src 'self'" in csp and "engelsizforum.com" in csp, "")
check("CSP frame-ancestors", "frame-ancestors 'none'" in hdrs.get("content-security-policy", ""))
check("HSTS yok (http yerel)", "strict-transport-security" not in {k.lower() for k in hdrs})

print("\n== EngelsizForum erisilebilirlik widget'i")
lay = io.open(os.path.join(ROOT, "web/templates/layout.html"), encoding="utf-8").read()
check("widget scripti layout'ta", "engelsizforum.com/widget/engelsiz-accessibility.js" in lay)
check("widget rengi Trendcord turuncusu", 'data-color="#F27A1A"' in lay)
check("eski mavi renk kalmadi", 'data-color="#185886"' not in lay)
check("widget async+defer", "async" in lay and "defer" in lay)
check("CSP frame-src acik", "frame-src" in csp and "engelsizforum.com" in csp)
check("CSP connect-src acik", "connect-src 'self' https://engelsizforum.com" in csp)

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
check("dinamik HTML private", "private" in cc, cc)
check("dinamik HTML no-cache (revalidate)", "no-cache" in cc, cc)
check("dinamik HTML must-revalidate", "must-revalidate" in cc, cc)
# `no-store` Chrome'da bfcache'i devre disi birakir; HTML belgelerinde kullanilmaz.
check("dinamik HTML no-store kullanmiyor (bfcache)", "no-store" not in cc, cc)
vary = h.get("vary", "")
check("Vary: Cookie", "cookie" in vary.lower(), vary)
check("Vary: Accept-Encoding", "accept-encoding" in vary.lower(), vary)
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

# ------------------------------------------- statik varliklarda Set-Cookie yok
print("\n== Statik varliklarda session cookie uretilmemeli")
for a in ["/static/css/tailwind.min.css", "/static/js/app.js", "/static/fonts/nunito-sans.woff2"]:
    st, _, h = req(a)
    # urllib cookie jar yalnizca sunucudan gercekten Set-Cookie gelirse dolar
    check(f"{a.split('/')[-1]} Set-Cookie yok", "session" not in h, h.get("set-cookie", "-"))
# Taze istemci (bos cerez sepeti) HTML isteginde session almalı; boylece
# oturumun statik yollarda degil, sadece dinamik sayfalarda kuruldugu
# dogrulanir. Mevcut istemcide cookie zaten varsa sunucu tekrar gondermez.
fresh = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect)
try:
    fr = fresh.open(BASE + "/", timeout=15)
    fh = {k.lower(): v for k, v in fr.headers.items()}
    fr.read()
except urllib.error.HTTPError as e:
    fh = {k.lower(): v for k, v in e.headers.items()}
check("HTML taze istemciye session cookie verir", "session" in fh.get("set-cookie", ""),
      fh.get("set-cookie", "-")[:44])

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

# ------------------------------------------------------- SVG ikon sprite gecerliligi
# Bu kontrol bir regresyona kilit: ikon `d` degerleri bosluksuzlastirilirken
# sayi tokenlari arasindaki bosluk kaybolursa `M11 13` -> `m1113` olur; Chrome
# "Expected number" hatasi verir (Lighthouse Best Practices duser) ve ikon
# yanlis geometriyle cizilir. Sprite'i ureten kod `tools/gen_icons.py`.
print("\n== SVG ikon sprite gecerliligi")
sys.path.insert(0, os.path.join(ROOT, "tools"))
try:
    from gen_icons import strict_check as _svg_path_ok
except Exception as _e:  # pragma: no cover
    _svg_path_ok = None
    check("gen_icons.strict_check yuklenebildi", False, str(_e))

sprite = io.open(os.path.join(ROOT, "web/templates/_icons.html"), encoding="utf-8").read()
syms = re.findall(r'<symbol id="i-([a-z0-9_]+)" viewBox="([^"]+)"><path d="([^"]+)"', sprite)
check("sprite ikon sayisi", len(syms) == 68, f"{len(syms)} ikon")
_num_re = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
_bad_d, _bad_vb, _oob = [], [], []
for _n, _vb, _d in syms:
    if _vb != "0 0 24 24":
        _bad_vb.append(_n)
    if _svg_path_ok is not None and not _svg_path_ok(_d)[0]:
        _bad_d.append(_n)
    # viewBox 0 0 24 24: koordinatlar disariya tasmamali
    if any(abs(float(_m.group())) > 24.5 for _m in _num_re.finditer(_d)):
        _oob.append(_n)
check("ikon yollari sozdizimsel gecerli", not _bad_d, ", ".join(_bad_d[:6]) or "hepsi gecerli")
check("tum ikonlar viewBox 0 0 24 24", not _bad_vb, ", ".join(_bad_vb[:6]) or "hepsi ayni")
check("ikonlar 24x24 kutusu icinde", not _oob, ", ".join(_oob[:6]) or "hepsi icinde")
_defined = {n for n, _, _ in syms}
_used = set()
for _f in glob.glob(os.path.join(ROOT, "web/templates/**/*.html"), recursive=True):
    _used |= set(re.findall(r'#i-([a-z0-9_]+)', io.open(_f, encoding="utf-8").read()))
for _f in ["web/static/js/app.js", "web/static/js/chart.js"]:
    _used |= set(re.findall(r'#i-([a-z0-9_]+)', io.open(os.path.join(ROOT, _f), encoding="utf-8").read()))
check("kullanilan her ikon sprite'ta var", not (_used - _defined), ", ".join(sorted(_used - _defined)) or "hepsi var")

print("\n== Statik varliklar")
for a, ctype in [("/static/js/app.js", "javascript"), ("/static/js/chart.js", "javascript"),
                 ("/static/css/tailwind.min.css", "css"), ("/static/img/placeholder.svg", "svg")]:
    st, _, h = req(a)
    check(a, st == 200 and ctype in h.get("content-type", ""), f"{st} {h.get('Content-Type')}")

print("\n== Path traversal korumasi (/static/..)")
for a in ["/static/../../.env", "/static/../../main.py", "/static/../.env",
          "/static/..%2f..%2f.env", "/static/img/../../.env",
          "/static/../../../../etc/passwd"]:
    st, body, _ = req(a)
    leaked = "DISCORD_TOKEN" in (body or "") or "root:" in (body or "")
    check(f"{a} engellendi", st == 404 and not leaked, f"{st} leaked={leaked}")

print(f"\n{'='*46}\nSONUC: {len(fails)} basarisiz")
for f in fails:
    print("  FAIL:", f)
