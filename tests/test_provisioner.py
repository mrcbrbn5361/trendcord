#!/usr/bin/env python3
"""Provisioner regresyon testleri (saf, Discord API'si gerektirmez)."""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ""))
    if not ok:
        fails.append(name)


class Role:
    def __init__(self, rid, name, managed=False):
        self.id, self.name, self.managed = rid, name, managed


class FakeGuild:
    default_role = Role(1, "@everyone")
    owner_id = 777

    class me:
        top_role = type("T", (), {"id": 999})()

    roles = [Role(1, "@everyone"), Role(2, "Member"), Role(3, "Bot", managed=True),
             Role(999, "Bot-ust"), Role(777, "Owner-role"), Role(4, "Mod")]


print("== reset: korumali roller silinmemeli")
from provisioner.official.runner import _deletable_roles, reset_official  # noqa: E402

silinecek = [r.name for r in _deletable_roles(FakeGuild())]
check("sadece yonetilebilir roller", silinecek == ["Member", "Mod"], str(silinecek))
check("@everyone korundu", "@everyone" not in silinecek)
check("bot rolu korundu", "Bot" not in silinecek)
check("botun en ust rolu korundu", "Bot-ust" not in silinecek)
check("sahip rolu korundu", "Owner-role" not in silinecek)

print("\n== /provision-official reset yolu tam mi")
src = open(os.path.join(ROOT, "cogs", "provision_official.py"), encoding="utf-8").read()
classes = [n.name for n in ast.parse(src).body if isinstance(n, ast.ClassDef)]
check("ResetConfirm sinifi tanimli", "ResetConfirm" in classes, str(classes))
check("reset komutu view.onay kontrolu var", "view.wait()" in src and "view.onay" in src)
check("requester_id zorunlu", "def __init__(self, requester_id: int" in src)
check("reset icin iki buton var", src.count("@discord.ui.button") >= 2)

rsrc = open(os.path.join(ROOT, "provisioner", "official", "runner.py"), encoding="utf-8").read()
rfns = [n.name for n in ast.parse(rsrc).body
        if isinstance(n, ast.AsyncFunctionDef)]
check("runner.reset_official mevcut", "reset_official" in rfns)
check("reset apply_official cagirir", "await apply_official(" in rsrc)

print("\n== /icerik-guncelle: kanal temizleme")
csrc = open(os.path.join(ROOT, "provisioner", "common", "content.py"),
            encoding="utf-8").read()
check("is_content_message var", "def is_content_message(" in csrc)
check("clean_channel var", "async def clean_channel(" in csrc)
check("force modunda temizlik cagriliyor", "await clean_channel(guild, ch)" in csrc)
check("silinen mesaj sayaci var", 'stats["deleted"]' in csrc)

print("\n== Icerik yardimcisi")
hrc = open(os.path.join(ROOT, "cogs", "product_commands.py"), encoding="utf-8").read()
check("COMMAND_HELP tek tanim", hrc.count("COMMAND_HELP") >= 1)
check("icerik-guncelle kapsam secenekleri", hrc.count("app_commands.Choice") >= 3)

print(f"\n{'=' * 46}\nSONUC: {len(fails)} basarisiz")
for f in fails:
    print("  FAIL:", f)
sys.exit(1 if fails else 0)