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

print("\n== Rate limit korumasi")
rc = open(os.path.join(ROOT, "provisioner", "common", "ratelimit.py"),
          encoding="utf-8").read()
check("provision_lock tanimli", "provision_lock = asyncio.Lock()" in rc)
check("MESSAGE_PACE tanimli", "MESSAGE_PACE" in rc)
check("STRUCTURE_PACE tanimli", "STRUCTURE_PACE" in rc)
check("RESET_PACE tanimli", "RESET_PACE" in rc)
check("pace() yardimcisi", "async def pace(" in rc)

check("reset kanal silerken pace", "await pace(RESET_PACE)" in rsrc)
check("reset kilit aliyor", "async with provision_lock:" in rsrc)
check("reset sonrasi bekleme", "await pace(3.0)" in rsrc)
check("rol olusturmada pace", "await pace(STRUCTURE_PACE)" in rsrc)
check("kanal olusturmada pace", "await pace(STRUCTURE_PACE)" in rsrc)
check("icerik gonderiminde pace", "await pace(MESSAGE_PACE)" in csrc)
check("mesaj silmede pace", "await pace(0.25)" in csrc)

print("\n== Silinen kanala cevap")
psrc = open(os.path.join(ROOT, "cogs", "provision_official.py"),
            encoding="utf-8").read()
check("_safe_reply tanimli", "async def _safe_reply(" in psrc)
check("_safe_reply DM yedeği", "create_dm()" in psrc)
check("reset sonrasi cevaplar _safe_reply kullanir",
      psrc.count("self._safe_reply(ctx") >= 5)

print("\n== Rol dagitimi (uye/bot)")
import asyncio  # noqa: E402
from provisioner.official.runner import (distribute_member_roles,  # noqa: E402
                                         MEMBER_ROLE_NAME, BOT_ROLE_NAME)


class _Role:
    def __init__(self, rid, name):
        self.id, self.name = rid, name


class _Member:
    def __init__(self, uid, bot, roles):
        self.id, self.bot, self.name = uid, bot, f"u{uid}"
        self.roles = list(roles)

    async def add_roles(self, role, reason=None):
        self.roles.append(role)


class _Guild:
    id = 12345

    def __init__(self, roles, members):
        self.roles, self._m = roles, members

    @property
    def members(self):
        return self._m


_u, _b = _Role(1, MEMBER_ROLE_NAME), _Role(2, BOT_ROLE_NAME)
_g = _Guild([_u, _b], [_Member(10, False, []), _Member(11, True, []),
                       _Member(12, False, [_u]), _Member(13, True, [_b])])
r1 = asyncio.run(distribute_member_roles(_g, delay=0))
check("insana Uye rolu verildi", r1["member"] == 1, str(r1))
check("bota Bot rolu verildi", r1["bot"] == 1, str(r1))
check("tum uyeler tarandi", r1["scanned"] == 4, str(r1))
r2 = asyncio.run(distribute_member_roles(_g, delay=0))
check("idempotent (tekrar vermez)", r2["member"] == 0 and r2["bot"] == 0, str(r2))

_g2 = _Guild([_u, _b], [_Member(i, False, []) for i in range(20)])
r3 = asyncio.run(distribute_member_roles(_g2, batch_size=5, delay=0))
check("batch siniri uygulanir", r3["scanned"] == 5, str(r3))

_r4 = asyncio.run(distribute_member_roles(_Guild([], []), delay=0))
check("rol yoksa cokmez", _r4["scanned"] == 0, str(_r4))

psrc2 = psrc
check("reset rol dagitimi cagirir", "distribute_member_roles(guild)" in rsrc)
check("auto_sync kademeli dagitir",
      "batch_size=ROLE_BATCH" in psrc2)
check("ROLE_BATCH ayari var", "ROLE_BATCH" in psrc2)
check("/provision-official dagit secenegi",
      'value="dagit"' in psrc2 and 'eylem == "dagit"' in psrc2)

print(f"\n{'=' * 46}\nSONUC: {len(fails)} basarisiz")
for f in fails:
    print("  FAIL:", f)
sys.exit(1 if fails else 0)