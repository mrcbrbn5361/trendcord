#!/usr/bin/env python
"""Calisan SQLite dosyalarini kilitlemeden guvenli kopyalar (online backup).
Kullanim: python backup_data.py <kaynak_klasor> <hedef_klasor>"""
import os, sys, sqlite3, shutil

src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)
DB_EXT = (".db", ".sqlite", ".sqlite3")

for name in os.listdir(src):
    s = os.path.join(src, name)
    d = os.path.join(dst, name)
    if not os.path.isfile(s):
        continue
    try:
        if name.endswith(DB_EXT):
            con = sqlite3.connect(s)
            bak = sqlite3.connect(d)
            con.backup(bak)
            bak.close()
            con.close()
        else:
            shutil.copy2(s, d)
        print("ok:", name)
    except Exception as e:
        print("atlandi:", name, "-", e)
