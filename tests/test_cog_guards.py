#!/usr/bin/env python3
"""Cog regresyon kontrolleri (statik).

discord.py 2.7'de:
  * commands.Context.defer(thinking=...)  -> YOK (sadece ephemeral)
  * commands.Context.followup             -> YOK (sadece Interaction.followup)
  * CommandTree.on_error                  -> dekorator degil, varsayilan logger

Bu testler cog'lerde bu API'lerin yanlis kullanimini yakalar.
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TARGETS = sorted(
    os.path.join(ROOT, "cogs", f) for f in os.listdir(os.path.join(ROOT, "cogs"))
    if f.endswith(".py") and not f.startswith("__")
) + [os.path.join(ROOT, "main.py")]

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def window(path, lineno, span=16):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    return "".join(lines[max(0, lineno - span):lineno])


print("== Hybrid komutlarda korumasiz ctx.followup")
bad = []
for path in TARGETS:
    tree = ast.parse(open(path, encoding="utf-8").read())
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Attribute) and n.attr == "followup"):
            continue
        base = ast.unparse(n.value)
        if "interaction" in base.lower():
            continue                      # interaction.followup her zaman guvenli
        w = window(path, n.lineno)
        if "commands.Context" in w or "discord.Interaction" in w:
            continue                      # isinstance guard'li -> guvenli
        bad.append(f"{os.path.basename(path)}:{n.lineno} ({base}.followup)")
check("ctx.followup yalniz Interaction dalinda", not bad, ", ".join(bad) or "hepsi guard'li")

print("\n== Context.defer(thinking=...) kullanimi yok")
bad = []
for path in TARGETS:
    tree = ast.parse(open(path, encoding="utf-8").read())
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "defer"):
            continue
        if not (isinstance(n.func.value, ast.Name)
                and n.func.value.id == "ctx"):
            continue                      # ctx.response.defer(thinking=) GECERLI
        if any(k.arg == "thinking" for k in n.keywords):
            bad.append(f"{os.path.basename(path)}:{n.lineno}")
check("ctx.defer(thinking=) kullanilmiyor", not bad, ", ".join(bad) or "temiz")

print("\n== @tree.on_error dekoratoru kullanilmiyor")
bad = []
for path in TARGETS:
    src = open(path, encoding="utf-8").read()
    if "tree.on_error" in src:
        bad.append(os.path.basename(path))
check("tree.on_error yerine tree.error", not bad, ", ".join(bad) or "temiz")

print("\n== Duyarli dosyalar repoda degil")
tracked = os.popen(f'cd "{ROOT}" && git ls-files').read().split()
leaks = [t for t in tracked
         if os.path.basename(t) == ".env" or t.endswith((".pem", ".key"))]
check("gizli dosya git'te yok", not leaks, ", ".join(leaks) or "temiz")

print(f"\n{'=' * 46}\nSONUC: {len(fails)} basarisiz")
for f in fails:
    print("  FAIL:", f)
sys.exit(1 if fails else 0)