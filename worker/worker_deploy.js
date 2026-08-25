export default {
    async fetch(request, env) {
        const url = new URL(request.url);
        try {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 5000);
            const originResponse = await fetch(request, { signal: controller.signal });
            clearTimeout(timeout);
            if (originResponse.ok) return originResponse;
        } catch (e) {}
        return new Response('<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Trendcord - Bakımda</title><script src="https://cdn.tailwindcss.com"></script><style>body{font-family:Inter,sans-serif}.gradient-bg{background:linear-gradient(135deg,#0f0f23,#1a1a3e,#2d1b69)}</style></head><body class="gradient-bg min-h-screen flex items-center justify-center text-white"><div class="text-center px-6 max-w-lg"><div class="mb-4"><div class="w-24 h-24 mx-auto bg-purple-500/20 rounded-full flex items-center justify-center"><svg class="w-12 h-12 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg></div></div><h1 class="text-4xl font-bold mb-4 bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">Trendcord</h1><div class="bg-white/5 backdrop-blur-sm rounded-2xl p-8 border border-white/10 mb-8"><div class="flex items-center justify-center gap-2 mb-4"><span class="relative flex h-3 w-3"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span><span class="relative inline-flex rounded-full h-3 w-3 bg-yellow-500"></span></span><span class="text-yellow-400 font-semibold text-sm uppercase tracking-wider">Bakımda</span></div><p class="text-gray-300 text-lg leading-relaxed">Sunucu şu anda bakım modunda.<br><span class="text-purple-300 font-medium">Yakın zamanda geri döneceğiz!</span></p></div></div><script>setTimeout(function(){location.reload()},30000)</script></body></html>', {
            status: 503,
            headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Retry-After': '30' },
        });
    },
};
