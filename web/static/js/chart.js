/* Trendcord - urun fiyat gecgisi grafigi
   Veri <script type="application/json" id="chartData"> icinden okunur;
   renkler CSS ozelliklerinden okunur, boylece tema degisimini izler. */
(function () {
    'use strict';

    function cssVar(name, fallback) {
        var v = getComputedStyle(document.documentElement).getPropertyValue(name);
        return (v && v.trim()) || fallback;
    }

    function render() {
        var holder = document.getElementById('chartData');
        var wrap = document.getElementById('chart-wrap');
        if (!holder || !wrap) return;

        var data;
        try { data = JSON.parse(holder.textContent); } catch (e) { return; }
        if (!data || data.length < 2) return;

        var primary = cssVar('--color-primary', '#B0410C');
        var success = cssVar('--color-success', '#15803D');
        var error = cssVar('--color-error', '#C1121F');
        var muted = cssVar('--color-on-surface-variant', '#6A625E');

        var W = 640, H = 220, PL = 14, PR = 14, PT = 30, PB = 30;
        var prices = data.map(function (d) { return d.p; });
        var min = Math.min.apply(null, prices), max = Math.max.apply(null, prices);
        if (min === max) { min -= 1; max += 1; }
        var pad = (max - min) * 0.08; min -= pad; max += pad;

        var x = function (i) { return PL + i * (W - PL - PR) / (data.length - 1); };
        var y = function (p) { return PT + (1 - (p - min) / (max - min)) * (H - PT - PB); };

        var pts = data.map(function (d, i) { return [x(i), y(d.p)]; });
        var line = pts.map(function (p) { return p.join(','); }).join(' ');
        var area = 'M' + PL + ',' + (H - PB) + ' L' + line.replace(/ /g, ' L') + ' L' + (W - PR) + ',' + (H - PB) + ' Z';

        var iMin = prices.indexOf(Math.min.apply(null, prices));
        var iMax = prices.indexOf(Math.max.apply(null, prices));

        var fmt = function (n) { return '₺' + Math.round(n).toLocaleString('tr-TR'); };

        function label(i, color, below) {
            var px = pts[i][0], py = pts[i][1], tx = px, anchor = 'middle';
            if (px < 75) { anchor = 'start'; tx = px - 2; }
            else if (px > W - 75) { anchor = 'end'; tx = px + 2; }
            var ty = below ? py + 22 : py - 12;
            ty = Math.max(13, Math.min(H - PB + 4, ty));
            return '<text x="' + tx + '" y="' + ty + '" font-size="12" font-weight="800" fill="' +
                color + '" text-anchor="' + anchor + '">' + fmt(prices[i]) + '</text>';
        }

        var minLbl = label(iMin, success, true);
        var maxLbl = iMin !== iMax ? label(iMax, error, false) : '';
        if (iMin !== iMax && Math.abs(pts[iMin][0] - pts[iMax][0]) < 95 &&
            Math.abs(pts[iMin][1] - pts[iMax][1]) < 34) {
            minLbl = label(iMin, success, false);
        }

        var last = pts[pts.length - 1];
        var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" class="w-full h-auto" role="img" ' +
            'aria-label="Fiyat değişim grafiği, ' + data.length + ' veri noktası">' +
            '<defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">' +
            '<stop offset="0" stop-color="' + primary + '" stop-opacity=".22"/>' +
            '<stop offset="1" stop-color="' + primary + '" stop-opacity="0"/>' +
            '</linearGradient></defs>' +
            '<path d="' + area + '" fill="url(#ag)"/>' +
            '<polyline points="' + line + '" fill="none" stroke="' + primary +
            '" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>' +
            '<circle cx="' + pts[iMin][0] + '" cy="' + pts[iMin][1] + '" r="4.5" fill="' + success + '"/>' +
            (iMin !== iMax ? '<circle cx="' + pts[iMax][0] + '" cy="' + pts[iMax][1] + '" r="4.5" fill="' + error + '"/>' : '') +
            '<circle cx="' + last[0] + '" cy="' + last[1] + '" r="5.5" fill="' + primary +
            '" stroke="var(--color-surface-container-high)" stroke-width="2"/>' +
            minLbl + maxLbl +
            '<text x="' + PL + '" y="' + (H - 6) + '" font-size="10" fill="' + muted + '">' + data[0].t + '</text>' +
            '<text x="' + (W - PR) + '" y="' + (H - 6) + '" font-size="10" fill="' + muted +
            '" text-anchor="end">' + data[data.length - 1].t + '</text>' +
            '</svg>';
        wrap.innerHTML = svg;
    }

    render();
    /* Tema degisince grafigi yeniden ciz (etiket renkleri degisir) */
    document.addEventListener('themechange', render);
})();
