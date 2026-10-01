"""Material Symbols woff2'den ikon SVG yollarini dogru sekilde cikarir.

Sorun: onceki sprite uretimi `d` degerlerini bosluksuzlastirirken sayi
tokenlari arasindaki boslugu sildi; `M11 13` -> `m1113` gibi degerler
olusup hem "Expected number" hatasi hem de bozuk geometri uretti.
Simdi dogrudan font glyf outline'ini (fontTools SVGPathPen) kullanarak,
sayilarin arasi tek boslukla ayrilmis ve hicbir sey kaybolmayan yollar
yaziyoruz.

Kullanim:  python tools/gen_icons.py <font.woff2> <cikti.html>
"""
import io
import re
import sys

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

VIEWBOX = 24  # Material Symbols emri 24x24 koordinat sisteminde

# Bu font surumunde bulunmayan ikon adlari -> ayni anlama gelen glyf.
# `local_offer` (fiyat etiketi) bu surumde `sell` adiyla var.
ALIASES = {"local_offer": "sell"}


def safe_minify(d):
    """Yalnizca GUVENLI bosluklari kaldirir.

    SVG sayi sozdiziminde iki sayi, ikincisi `-`, `+`, `.` ile basliyorsa
    veya bir komut harfi ise bosluksuz yazilabilir. Ikinci sayi RAKAMLA
    basliyorsa (`11 13`) ayirici zorunludur; onceki hatanin sebebi de buydu
    (`M11 13` -> `m1113`).
    """
    out, i, n = [], 0, len(d)
    while i < n:
        c = d[i]
        if c.isspace():
            i += 1
            continue
        if c.isalpha():
            j = i
            while j < n and d[j].isalpha():
                j += 1
            # komut harfi alfabetik oldugu icin kendini ayirt eder,
            # onceki sayidan ayirici bosluk gerekmez
            out.append(d[i:j])
            i = j
            continue
        j = i
        m = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?").match(d, i)
        j = m.end() if m else i + 1
        tok = d[i:j]
        if out and out[-1] and out[-1][-1].isdigit() and tok[0].isdigit():
            out.append(" ")  # rakam|rakam ayiricisi zorunlu
        out.append(tok)
        i = j
    return "".join(out)


def glyph_names(font):
    return set(font.getGlyphOrder())


def extract(font, name):
    """Tek bir glyfi 24x24 koordinat sistemine normalize ederek yol cikarir.

    Material Symbols glyfleri UPEM=1000 olan bir izgarada cizilir ve tam
    24x24 ikon kutusuna 24/1000 ile olceklenir. Bu olcek uygulanmazsa
    koordinatlar 840'a kadar cikiyor ve `viewBox="0 0 24 24"` icinde
    ikonlar kirpilir.
    """
    gs = font.getGlyphSet()
    name = ALIASES.get(name, name)
    if name not in glyph_names(font):
        return None
    scale = VIEWBOX / font["head"].unitsPerEm
    pen = SVGPathPen(gs, ntos=lambda v: f"{round(v * scale, 2):g}")
    gs[name].draw(pen)
    d = pen.getCommands()
    return d or None


def strict_check(d):
    """Tarayici kurallarina gore dogrula (kucuk/b buyuk komutlar dahil)."""
    args = {"M": 2, "L": 2, "T": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "A": 7, "Z": 0}
    num = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
    i, n, need = 0, len(d), None
    while i < n:
        c = d[i]
        if c in args:
            need = args[c] or None
            i += 1
        elif c.isspace():
            i += 1
        else:
            m = num.match(d, i)
            if not m:
                return False, f"beklenmeyen {c!r} @{i}: ...{d[max(0,i-12):i+12]}"
            i = m.end()
            if need is not None:
                need -= 1
                if need == 0:
                    need = None
    if need:
        return False, f"eksik {need} arguman"
    return True, ""


if __name__ == "__main__":
    font_path = sys.argv[1]
    out_path = sys.argv[2]

    font = TTFont(font_path)
    have = glyph_names(font)

    # Mevcut sprite'daki ikon adlarini oku (sira korunsun)
    prev = io.open(out_path, encoding="utf-8").read()
    names = re.findall(r'<symbol id="i-([a-z0-9_]+)"', prev)
    print(f"hedef ikon sayisi: {len(names)} | font glyf: {len(have)}")

    missing = [n for n in names if n not in have]
    if missing:
        print("FONT'TA BULUNAMADI:", ", ".join(missing))

    rows, bad, fixed = [], 0, 0
    for n in names:
        d = extract(font, n)
        if d is None:
            rows.append((n, None))
            bad += 1
            continue
        dmin = safe_minify(d)
        ok1, why1 = strict_check(d)
        ok2, why2 = strict_check(dmin)
        if not ok1:
            bad += 1
            print(f"  !! {n} (ham): {why1}")
        elif not ok2:
            bad += 1
            print(f"  !! {n} (minify): {why2}")
        else:
            rows.append((n, dmin))
            if dmin != d:
                fixed += 1

    body = "\n".join(
        f'<symbol id="i-{n}" viewBox="0 0 {VIEWBOX} {VIEWBOX}"><path d="{d}"/></symbol>'
        for n, d in rows
    )

    head = prev.split("<symbol", 1)[0]
    head = head.rstrip("\n")
    io.open(out_path, "w", encoding="utf-8").write(head + "\n" + body + "\n")
    print(f"yazildi: {out_path}")
    print(f"  ikon: {len(rows)} | hatali: {bad} | guvenli minify edilen: {fixed}")
    print(f"  boyut: {len(io.open(out_path, encoding='utf-8').read())} bayt")
