#!/data/data/com.termux/files/usr/bin/python3
# Trendcord reverse proxy - bot düşerse bakım sayfası göster
# Port 8000'de çalışır, bot 8001'de

import socket
import sys
import threading
import time
import os
import re

MAINTENANCE_PAGE = b"""HTTP/1.1 503 Service Unavailable\r
Content-Type: text/html; charset=utf-8\r
Retry-After: 30\r
Cache-Control: no-cache\r
\r
<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Trendcord - Bakımda</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>body{font-family:Inter,sans-serif}.gradient-bg{background:linear-gradient(135deg,#0f0f23 0%,#1a1a3e 50%,#2d1b69 100%)}.pulse-glow{animation:pulse-glow 2s ease-in-out infinite}@keyframes pulse-glow{0%,100%{opacity:0.4;transform:scale(1)}50%{opacity:0.8;transform:scale(1.05)}}.floating{animation:floating 3s ease-in-out infinite}@keyframes floating{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}</style></head>
<body class="gradient-bg min-h-screen flex items-center justify-center text-white">
<div class="text-center px-6 max-w-lg">
<div class="mb-8 floating"><div class="w-24 h-24 mx-auto bg-purple-500/20 rounded-full flex items-center justify-center pulse-glow">
<svg class="w-12 h-12 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg></div></div>
<h1 class="text-4xl font-bold mb-4 bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">Trendcord</h1>
<div class="bg-white/5 backdrop-blur-sm rounded-2xl p-8 border border-white/10 mb-8">
<div class="flex items-center justify-center gap-2 mb-4">
<span class="relative flex h-3 w-3"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span><span class="relative inline-flex rounded-full h-3 w-3 bg-yellow-500"></span></span>
<span class="text-yellow-400 font-semibold text-sm uppercase tracking-wider">Bakımda</span></div>
<p class="text-gray-300 text-lg leading-relaxed">Sunucu şu anda bakım modunda.<br><span class="text-purple-300 font-medium">Yakın zamanda geri döneceğiz!</span></p></div>
<div class="flex items-center justify-center gap-2 text-gray-400 text-sm"><div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div><span>Sistem izleniyor</span></div></div>
<script>setTimeout(function(){location.reload()},30000)</script></body></html>
"""

BOT_PORT = 8001
PROXY_PORT = 8000

def proxy_thread(client_sock):
    try:
        req = client_sock.recv(65536)
        if not req:
            return
        bot_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        bot_sock.settimeout(3)
        try:
            bot_sock.connect(("127.0.0.1", BOT_PORT))
            bot_sock.sendall(req)
            resp = b""
            while True:
                chunk = bot_sock.recv(65536)
                if not chunk:
                    break
                resp += chunk
            client_sock.sendall(resp)
        except:
            client_sock.sendall(MAINTENANCE_PAGE)
        finally:
            bot_sock.close()
    except:
        pass
    finally:
        try:
            client_sock.close()
        except:
            pass

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PROXY_PORT))
    server.listen(256)
    while True:
        client, addr = server.accept()
        threading.Thread(target=proxy_thread, args=(client,), daemon=True).start()

if __name__ == "__main__":
    main()
