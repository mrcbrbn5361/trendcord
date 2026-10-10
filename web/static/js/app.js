/* Trendcord - ortak istemci davranislari
   Tum sayfalar bu dosyayi yukler; sayfaya ozel inline <script> ve onclick
   yoktur (CSP uyumlu, tek indirilebilir ve onbelleklenebilir). */
(function () {
    'use strict';

    var FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]):not([type=hidden]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

    /* ---------------- Tema ---------------- */
    function applyThemeIcon() {
        var isDark = document.documentElement.classList.contains('dark');
        document.querySelectorAll('.theme-toggle-icon').forEach(function (icon) {
            var use = icon.tagName === 'svg' ? icon.querySelector('use') : null;
            if (use) {
                use.setAttribute('href', isDark ? '#i-light_mode' : '#i-dark_mode');
            }
            icon.classList.add('rotate');
            setTimeout(function () { icon.classList.remove('rotate'); }, 400);
        });
        var label = document.getElementById('themeLabel');
        if (label) label.textContent = isDark ? 'Açık Tema' : 'Koyu Tema';
    }

    function toggleTheme() {
        var html = document.documentElement;
        if (html.classList.contains('dark')) {
            html.classList.remove('dark');
            localStorage.setItem('trendcord-theme', 'light');
        } else {
            html.classList.add('dark');
            localStorage.setItem('trendcord-theme', 'dark');
        }
        applyThemeIcon();
        /* Tema bagimli gorseller (orn. fiyat grafigi) kendini yenilesin */
        document.dispatchEvent(new CustomEvent('themechange', { detail: { dark: html.classList.contains('dark') } }));
    }

    /* ---------------- Modal / Drawer ---------------- */
    var openModal = null;
    var lastFocused = null;

    function focusablesIn(el) {
        return Array.prototype.filter.call(
            el.querySelectorAll(FOCUSABLE),
            function (n) { return n.offsetParent !== null || n === document.activeElement; }
        );
    }

    function lockPage(on) {
        document.body.style.overflow = on ? 'hidden' : '';
    }

    /* Ekrani modal arkasinda erisilemaz yapar (klavye + ekran okuyucu)
       Modal her zaman <body> cocugu olmak zorunda degil (dashboard'da
       <main> icinde). Govde cocuklarini inert yapmak modalun kendisini de
       inert yapar; bu yuzden modalden <body>'ye kadar her seviyede yalnizca
       kardesleri inertliyoruz. */
    function setBackgroundInert(on, exceptEl) {
        if (!on) {
            document.querySelectorAll('[data-was-inert]').forEach(function (n) {
                n.removeAttribute('inert');
                n.removeAttribute('data-was-inert');
            });
            return;
        }
        var node = exceptEl;
        while (node && node !== document.body) {
            var parent = node.parentElement;
            if (!parent) break;
            Array.prototype.forEach.call(parent.children, function (sib) {
                if (sib === node) return;
                if (sib.classList.contains('icon-sprite')) return;
                if (sib.hasAttribute('inert')) return;
                sib.setAttribute('data-was-inert', '');
                sib.setAttribute('inert', '');
            });
            node = parent;
        }
    }

    function showModal(el) {
        if (!el || el === openModal) return;
        if (openModal) hideModal(openModal);
        lastFocused = document.activeElement;
        openModal = el;
        el.hidden = false;
        lockPage(true);
        setBackgroundInert(true, el);
        requestAnimationFrame(function () {
            requestAnimationFrame(function () { el.dataset.modalOpen = 'true'; });
        });
        var f = focusablesIn(el);
        if (f.length) f[0].focus();
        document.querySelectorAll('[data-modal-open-btn="' + el.id + '"]').forEach(function (b) {
            b.setAttribute('aria-expanded', 'true');
        });
    }

    function hideModal(el) {
        if (!el) return;
        el.dataset.modalOpen = 'false';
        clearTimeout(el._closeTimer);
        el._closeTimer = setTimeout(function () {
            if (el.dataset.modalOpen !== 'true') el.hidden = true;
        }, 300);
        if (openModal === el) {
            openModal = null;
            lockPage(false);
            setBackgroundInert(false, el);
            if (lastFocused && document.contains(lastFocused)) lastFocused.focus();
            lastFocused = null;
        }
        document.querySelectorAll('[data-modal-open-btn="' + el.id + '"]').forEach(function (b) {
            b.setAttribute('aria-expanded', 'false');
        });
    }

    function toggleModal(id) {
        var el = document.getElementById(id);
        if (!el) return;
        if (el.dataset.modalOpen === 'true' || !el.hidden) hideModal(el);
        else showModal(el);
    }

    /* Klavye: Escape kapatir, Tab modal icinde hapsolur */
    document.addEventListener('keydown', function (e) {
        if (!openModal) return;
        if (e.key === 'Escape') {
            e.preventDefault();
            hideModal(openModal);
            return;
        }
        if (e.key !== 'Tab') return;
        var f = focusablesIn(openModal);
        if (!f.length) return;
        var first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });

    /* ---------------- Form dogrulama (alert yerine erisilebilir mesaj) ---------------- */
    function fieldError(input, message) {
        var box = input.closest('form') && input.closest('form').querySelector('[data-form-error]');
        if (box) {
            box.textContent = message;
            box.hidden = false;
        }
        input.setAttribute('aria-invalid', 'true');
        input.focus();
    }
    function clearFieldError(input) {
        var box = input.closest('form') && input.closest('form').querySelector('[data-form-error]');
        if (box) { box.textContent = ''; box.hidden = true; }
        input.removeAttribute('aria-invalid');
    }

    /* ---------------- Olay delegasyonu ---------------- */
    document.addEventListener('click', function (e) {
        var t = e.target;
        if (!(t instanceof Element)) return;

        var themeBtn = t.closest('[data-theme-toggle]');
        if (themeBtn) { toggleTheme(); return; }

        var openBtn = t.closest('[data-modal-open-btn]');
        if (openBtn) {
            toggleModal(openBtn.dataset.modalOpenBtn);
            if (openBtn.hasAttribute('data-also-theme')) toggleTheme();
            return;
        }

        /* Arka plana tiklama: yalnizca kendi kendine tiklanan hedef kapatir */
        if (t.matches('[data-modal-backdrop]') && t === e.target) {
            var holder = t.closest('[id]');
            if (holder && holder.dataset.modalOpen === 'true') hideModal(holder);
            return;
        }

        var closeBtn = t.closest('[data-modal-close]');
        if (closeBtn) { hideModal(closeBtn.closest('[id]')); return; }

        var dismiss = t.closest('[data-dismiss]');
        if (dismiss) {
            var raw = parseInt(dismiss.dataset.dismiss, 10);
            var depth = isNaN(raw) ? 1 : raw;
            var node = dismiss;
            for (var i = 0; i < depth; i++) node = node.parentElement;
            if (node) node.remove();
            return;
        }

        var tab = t.closest('[data-tab]');
        if (tab) { showTab(tab.dataset.tab); return; }

        var prodFilter = t.closest('[data-filter-products]');
        if (prodFilter) { filterRows(prodFilter.dataset.filterProducts || ''); return; }

        var copy = t.closest('[data-copy]');
        if (copy) { copyToClipboard(copy); return; }
    });

    document.addEventListener('input', function (e) {
        var t = e.target;
        if (!(t instanceof Element)) return;
        if (t.matches('[data-filter-input]')) { filterRows(t.value); return; }
        if (t.matches('input,textarea')) clearFieldError(t);
    });

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!(form instanceof Element)) return;

        if (form.hasAttribute('data-requires-guild')) {
            var g = form.querySelector('[name=guild_id]');
            if (!g || !g.value) {
                e.preventDefault();
                fieldError(g || form.querySelector('input,select'), 'Lütfen önce bir sunucu seçin.');
                return;
            }
        }
        var msg = form.getAttribute('data-confirm');
        if (msg && !window.confirm(msg)) e.preventDefault();
    });

    function copyToClipboard(btn) {
        var text = btn.dataset.copy;
        var done = function () {
            var old = btn.dataset.copyLabel || btn.getAttribute('aria-label');
            btn.dataset.copyLabel = old;
            btn.setAttribute('aria-label', 'Kopyalandı');
            btn.classList.add('copied');
            setTimeout(function () {
                btn.setAttribute('aria-label', old);
                btn.classList.remove('copied');
            }, 1600);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(done, done);
        } else {
            var ta = document.createElement('textarea');
            ta.value = text; document.body.appendChild(ta); ta.select();
            try { document.execCommand('copy'); } catch (err) { /* yoksay */ }
            ta.remove(); done();
        }
    }

    /* ---------------- Sekmeler ---------------- */
    function showTab(name) {
        var panel = document.getElementById('panel-' + name);
        if (!panel) return;
        document.querySelectorAll('.tab-panel').forEach(function (p) {
            p.hidden = true;
            p.classList.add('hidden');
        });
        panel.hidden = false;
        panel.classList.remove('hidden');
        document.querySelectorAll('[data-tab]').forEach(function (t) {
            var on = t.dataset.tab === name;
            t.setAttribute('aria-selected', on ? 'true' : 'false');
            t.setAttribute('tabindex', on ? '0' : '-1');
            t.classList.toggle('bg-primary', on);
            t.classList.toggle('text-on-primary', on);
            t.classList.toggle('bg-surface-container-high', !on);
            t.classList.toggle('text-on-surface-variant', !on);
        });
    }

    /* ---------------- Arama / filtreleme ----------------
       Satirlar data-filter-row + data-name ile isaretlidir; boylece ic ice
       baglanti/bolum farklari filtreyi bozmaz. */
    function filterRows(query) {
        var q = (query || '').toLowerCase().trim();
        var rows = document.querySelectorAll('[data-filter-row]');
        var shown = 0;
        rows.forEach(function (r) {
            var hit = !q || (r.dataset.name || '').toLowerCase().includes(q);
            r.hidden = !hit;
            r.style.display = hit ? (r.dataset.filterShow || '') : 'none';
            if (hit) shown++;
        });
        document.querySelectorAll('[data-filter-empty]').forEach(function (box) {
            box.hidden = shown !== 0;
        });
        document.querySelectorAll('[data-filter-count]').forEach(function (el) {
            el.textContent = String(shown);
        });
        syncBulkBar();
    }


    /* ---------------- Scroll golgesi ---------------- */
    /* Kaydirma container'i govde (bkz. input.css): html sabit, body kayar.
       Bu yuzden window.scrollY degil, body's scrollTop okunur. */
    function scrollTop() {
        return document.body ? document.body.scrollTop : (window.scrollY || 0);
    }
    var scrollTicking = false;
    var scrollHost = document.body || window;
    scrollHost.addEventListener('scroll', function () {
        if (scrollTicking) return;
        scrollTicking = true;
        requestAnimationFrame(function () {
            document.querySelectorAll('[data-site-header]').forEach(function (h) {
                h.classList.toggle('is-scrolled', scrollTop() > 24);
            });
            scrollTicking = false;
        });
    }, { passive: true });

    /* ---------------- Scroll reveal ---------------- */
    function initReveal() {
        var cards = document.querySelectorAll('.glass-card');
        if (!cards.length) return;
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        document.querySelectorAll('.grid').forEach(function (grid) {
            grid.querySelectorAll(':scope > .glass-card').forEach(function (card, i) {
                card.style.setProperty('--reveal-delay', Math.min(i * 80, 320) + 'ms');
            });
        });
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            });
        }, { threshold: 0.08, rootMargin: '0px 0px -32px 0px' });
        cards.forEach(function (card) {
            card.classList.add('reveal');
            observer.observe(card);
        });
    }

    /* ---------------- Gorsel hata yonetimi ----------------
       Uzak gorsel yuklenemediginde yerel SVG'ye gecer. Boylece ucuncu
       taraf (placehold.co) HTML'de hic geçmez ve CSP skiple uyumludur. */
    var PLACEHOLDER = '/static/img/placeholder.svg';
    var AVATAR_FALLBACK = '/static/img/avatar-fallback.svg';
    window.addEventListener('error', function (e) {
        var el = e.target;
        if (!(el instanceof HTMLImageElement)) return;
        if (el.dataset.fallbackDone) return;
        el.dataset.fallbackDone = '1';
        if (el.hasAttribute('data-hide-on-error')) {
            el.style.display = 'none';
            var next = el.nextElementSibling;
            if (next && el.hasAttribute('data-show-next')) next.style.display = el.dataset.showNext;
            return;
        }
        var kind = el.dataset.fallback;
        if (!kind) kind = /\/avatars\/|\/icons\//.test(el.src) ? 'avatar' : 'product';
        el.src = kind === 'avatar' ? AVATAR_FALLBACK : PLACEHOLDER;
    }, true);

    /* ---------------- Baslat ---------------- */
    function adoptOpenModals() {
        /* Sunucu tarafi acilan dialog'lar (orn. ?added=1 basari modali):
           zaten acik gelirler; odak tuzagini ve arka plan inert'ini devral. */
        var open = document.querySelectorAll('[data-modal-open="true"]');
        if (!open.length) return;
        var el = open[open.length - 1];
        openModal = el;
        lockPage(true);
        setBackgroundInert(true, el);
        var f = focusablesIn(el);
        if (f.length) f[0].focus();
    }

    /* ---------- Toplu urun secimi / silme ---------- */
    function bulkBoxes() {
        return Array.prototype.slice.call(document.querySelectorAll('[data-bulk-check]'));
    }
    function syncBulkBar() {
        var bar = document.querySelector('[data-bulk-bar]');
        if (!bar) return;
        var boxes = bulkBoxes().filter(function (b) { return b.offsetParent !== null; });
        var checked = boxes.filter(function (b) { return b.checked; });
        var count = bar.querySelector('[data-bulk-count]');
        var ids = bar.querySelector('[data-bulk-ids]');
        var allBtn = document.querySelector('[data-bulk-select-all]');
        if (count) count.textContent = String(checked.length);
        if (ids) ids.value = checked.map(function (b) { return b.value; }).join(',');
        if (allBtn) {
            var allOn = boxes.length > 0 && checked.length === boxes.length;
            allBtn.setAttribute('aria-pressed', allOn ? 'true' : 'false');
            allBtn.textContent = allOn ? 'Seçimi Kaldır' : 'Tümünü Seç';
        }
        if (checked.length) bar.removeAttribute('hidden');
        else bar.setAttribute('hidden', '');
    }
    function initBulk() {
        var bar = document.querySelector('[data-bulk-bar]');
        if (!bar) return;
        document.addEventListener('change', function (e) {
            if (e.target instanceof Element && e.target.matches('[data-bulk-check]')) syncBulkBar();
        });
        var allBtn = document.querySelector('[data-bulk-select-all]');
        if (allBtn) {
            allBtn.addEventListener('click', function () {
                var boxes = bulkBoxes().filter(function (b) { return b.offsetParent !== null; });
                var turnOn = boxes.some(function (b) { return !b.checked; });
                boxes.forEach(function (b) { b.checked = turnOn; });
                syncBulkBar();
            });
        }
        var clear = bar.querySelector('[data-bulk-clear]');
        if (clear) {
            clear.addEventListener('click', function () {
                bulkBoxes().forEach(function (b) { b.checked = false; });
                syncBulkBar();
            });
        }
        syncBulkBar();
    }

    function init() {
        applyThemeIcon();
        initReveal();
        initBulk();
        document.querySelectorAll('[data-modal-open-btn]').forEach(function (b) {
            b.setAttribute('aria-expanded', 'false');
        });
        adoptOpenModals();
        /* Bakim sayfasi: data-auto-reload="30000" ile periyodik yenileme */
        var reload = document.querySelector('[data-auto-reload]');
        if (reload) setTimeout(function () { location.reload(); }, parseInt(reload.dataset.autoReload, 10) || 30000);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
