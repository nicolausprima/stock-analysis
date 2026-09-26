document.addEventListener('DOMContentLoaded', () => {
    // Keamanan kredensial:
    // - JANGAN terima API key via URL (?api_key=...): bocor ke browser history,
    //   proxy/access log, dan header Referer.
    // - JANGAN pakai localStorage persisten: rentan dibaca XSS jangka panjang.
    // - Pakai sessionStorage (hilang saat tab ditutup). Set manual via:
    //     window.setStockAIApiKey('xxx')  -> simpan ke sessionStorage
    //     window.clearStockAIApiKey()     -> hapus
    if (new URLSearchParams(window.location.search).has('api_key')) {
        console.warn('[security] Parameter ?api_key= diabaikan. Set key via window.setStockAIApiKey().');
        const params = new URLSearchParams(window.location.search);
        params.delete('api_key');
        const qs = params.toString();
        history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
    }
    try {
        if (localStorage.getItem('api_key')) {
            console.warn('[security] Migrasi api_key dari localStorage ke sessionStorage.');
            sessionStorage.setItem('api_key', localStorage.getItem('api_key'));
            localStorage.removeItem('api_key');
        }
    } catch (_) { /* storage unavailable */ }
    window.setStockAIApiKey = (k) => { try { sessionStorage.setItem('api_key', String(k || '')); } catch (_) {} };
    window.clearStockAIApiKey = () => { try { sessionStorage.removeItem('api_key'); } catch (_) {} };

    // Fetch wrapper: lampirkan X-API-Key jika tersedia
    const apiFetch = (url, opts = {}) => {
        let key = '';
        try { key = sessionStorage.getItem('api_key') || ''; } catch (_) { key = ''; }
        opts.headers = { ...(opts.headers || {}), ...(key ? { 'X-API-Key': key } : {}) };
        return fetch(url, opts);
    };

    const scanBtn    = document.getElementById('scan-btn');
    const loader     = document.getElementById('loader');
    const errorBox   = document.getElementById('error-box');
    const errorText  = document.getElementById('error-text');
    const results    = document.getElementById('results');
    const tableBody  = document.getElementById('table-body');
    const cardsGrid  = document.getElementById('cards-grid');
    const lastScan   = document.getElementById('last-scan-time');
    const emptyState = document.getElementById('empty-state');

    // Referensi handler resize disimpan agar bisa dilepas saat chart dirender ulang (anti memory-leak)
    // Helpers
    const idr = v => new Intl.NumberFormat('id-ID', {
        style: 'currency', currency: 'IDR', minimumFractionDigits: 0
    }).format(v);
    const fmtPrice = v => (v && v > 0)
        ? idr(v)
        : '<span class="price-null">—</span>';

    const esc = v => String(v ?? '').replace(/[&<>"']/g, c => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
    // ID DOM aman dari ticker (Backend: ^[A-Z0-9.]+$, tapi defense-in-depth).
    const safeId = v => String(v ?? '').replace('.JK', '').replace(/[^A-Za-z0-9_-]/g, '');
    // Nama kelas CSS aman (whitelist) — cegah breakout atribut class.
    const cls = v => String(v ?? '').toLowerCase().replace(/[^a-z0-9_-]/g, '');
    // Helper persen TP/SL tunggal (dulu duplikasi literal '3.0'/'-1.5' di 4 tempat).
    const pctStr = (entry, exit, fallback) => (entry > 0 && exit > 0)
        ? (((exit - entry) / entry) * 100).toFixed(1)
        : fallback;
    const tpPctOf = s => pctStr(s.close_price ?? s.entry_price ?? 0, s.target_price ?? 0, '3.0');
    const slPctOf = s => pctStr(s.close_price ?? s.entry_price ?? 0, s.stop_loss ?? 0, '-1.5');
    // Kontrak sentimen backend = 'NETRAL' (ID). Normalisasi 'NEUTRAL' lama -> 'NETRAL'.
    const normSent = v => {
        const t = String(v || 'NETRAL').toUpperCase();
        return t === 'NEUTRAL' ? 'NETRAL' : t;
    };
    const showError = (msg) => {
        if (errorText) errorText.textContent = String(msg || 'Error');
        if (errorBox) errorBox.classList.remove('hidden');
    };
    // Error actions: Coba lagi = ulangi scan; Tutup = sembunyikan + kembalikan fokus.
    (function wireErrorActions() {
        const retryBtn = document.getElementById('error-retry-btn');
        const dismissBtn = document.getElementById('error-dismiss-btn');
        if (retryBtn) retryBtn.addEventListener('click', () => { if (scanBtn) scanBtn.click(); });
        if (dismissBtn) dismissBtn.addEventListener('click', () => {
            if (errorBox) errorBox.classList.add('hidden');
            if (scanBtn) { try { scanBtn.focus({ preventScroll: true }); } catch (_) { scanBtn.focus(); } }
        });
    })();
    // Compact range select tampil hanya bila tab tidak muat (<=400px).
    // UX-03: kontrol chart tidak boleh hilang di layar sempit.
    (function wireCompactRange() {
        const tabs = document.getElementById('ihsg-range-tabs');
        const sel = document.getElementById('ihsg-range-select');
        const b1 = document.getElementById('tab-1d');
        const b60 = document.getElementById('tab-60d');
        if (!tabs || !sel) return;
        const mq = window.matchMedia ? window.matchMedia('(max-width: 400px)') : null;
        const apply = () => {
            const compact = mq ? mq.matches : window.innerWidth <= 400;
            sel.hidden = !compact;
            if (b1) b1.style.display = compact ? 'none' : '';
            if (b60) b60.style.display = compact ? 'none' : '';
        };
        apply();
        if (mq && mq.addEventListener) mq.addEventListener('change', apply);
        else window.addEventListener('resize', apply, { passive: true });
    })();

    const rsiColor = r => r < 40 ? 'green' : r > 65 ? 'red' : 'amber';
    const rsiW     = r => Math.min(Math.max(r, 0), 100);

    // --- Chart registry: SATU resize listener + ResizeObserver (anti-leak, responsif) ---
    // Tinggi adaptif HP: IHSG 200->160, mini 80->72, equity 220->180 bila lebar <420px.
    const liveCharts = new Map(); // container -> { chart, baseHeight }
    const adaptiveHeight = (container, base) => {
        try {
            const w = container.clientWidth || window.innerWidth || base;
            if (w <= 360) return Math.round(base * 0.75);
            if (w <= 480) return Math.round(base * 0.85);
            return base;
        } catch (_) { return base; }
    };
    const disposeChart = (container) => {
        const entry = liveCharts.get(container);
        if (entry) {
            try { entry.chart.remove(); } catch (_) { /* already disposed */ }
            liveCharts.delete(container);
        }
        try { if (chartObserver) chartObserver.unobserve(container); } catch (_) { /* noop */ }
        try { delete container._chart; } catch (_) { /* noop */ }
    };
    const registerChart = (container, chart, baseHeight) => {
        disposeChart(container);
        liveCharts.set(container, { chart, baseHeight });
        try { container._chart = chart; } catch (_) { /* noop */ }
        try {
            if (chartObserver && document.contains(container)) chartObserver.observe(container);
        } catch (_) { /* noop */ }
        // Terapkan tinggi adaptif segera setelah daftar
        try {
            const h = adaptiveHeight(container, baseHeight);
            if (h !== baseHeight) chart.resize(container.clientWidth || 300, h);
        } catch (_) { /* noop */ }
    };
    const resizeOneChart = (container) => {
        const entry = liveCharts.get(container);
        if (!entry) return;
        try {
            if (document.contains(container) && container.clientWidth > 0) {
                entry.chart.resize(container.clientWidth, adaptiveHeight(container, entry.baseHeight));
            } else {
                disposeChart(container);
            }
        } catch (_) { disposeChart(container); }
    };
    let _resizeTimer = null;
    const scheduleResizeAll = () => {
        clearTimeout(_resizeTimer);
        _resizeTimer = setTimeout(() => {
            liveCharts.forEach((_, container) => resizeOneChart(container));
        }, 150);
    };
    window.addEventListener('resize', scheduleResizeAll, { passive: true });
    window.addEventListener('orientationchange', scheduleResizeAll, { passive: true });
    let chartObserver = null;
    try {
        if ('ResizeObserver' in window) {
            let roTimer = null;
            chartObserver = new ResizeObserver(() => {
                clearTimeout(roTimer);
                roTimer = setTimeout(() => {
                    liveCharts.forEach((_, container) => resizeOneChart(container));
                }, 120);
            });
        }
    } catch (_) { chartObserver = null; }

    // Initial load: render IHSG chart
    renderIHSGChart(1);
    wireAuditFilters();
    runAuditAndLoad();

    // Progressive Scan Loader & Elapsed Timer (UX-05: query class, bukan id —
    // label/timer aria-hidden agar SR hanya dengar satu status ringkas).
    let scanTimerInterval = null;
    let scanPhaseInterval = null;
    const scanPhases = [
        "Memindai 700+ ticker IDX...",
        "Menghitung 20+ indikator teknikal & MFI...",
        "Mengekstrak feature embeddings...",
        "Menilai sentimen berita & katalis...",
        "Menjalankan konsensus 5 agen...",
        "Menyusun kandidat hasil skrining..."
    ];

    function startScanLoader() {
        const box = loader ? loader.querySelector('.loader-box') : null;
        const timerEl = loader ? loader.querySelector('.loader-timer') : null;
        const labelEl = loader ? loader.querySelector('.loader-shimmer-text') : null;
        const srEl = document.getElementById('loader-sr');
        const startTime = Date.now();

        if (timerEl) timerEl.textContent = '0.0s';
        if (labelEl) labelEl.textContent = scanPhases[0];
        if (loader) loader.classList.remove('hidden');
        if (box) box.setAttribute('aria-label', scanPhases[0]);
        if (srEl) srEl.textContent = 'Memindai pasar, mohon tunggu.';

        clearInterval(scanTimerInterval);
        clearInterval(scanPhaseInterval);

        scanTimerInterval = setInterval(() => {
            const elapsed = (Date.now() - startTime) / 1000;
            if (timerEl) {
                timerEl.textContent = elapsed < 60
                    ? `${elapsed.toFixed(1)}s`
                    : `${Math.floor(elapsed / 60)}m ${(elapsed % 60).toFixed(1)}s`;
            }
        }, 100);

        let phaseIdx = 0;
        scanPhaseInterval = setInterval(() => {
            phaseIdx = (phaseIdx + 1) % scanPhases.length;
            if (labelEl) labelEl.textContent = scanPhases[phaseIdx];
            const box = loader ? loader.querySelector('.loader-box') : null;
            if (box) box.setAttribute('aria-label', scanPhases[phaseIdx]);
        }, 1200);
    }

    function stopScanLoader() {
        clearInterval(scanTimerInterval);
        clearInterval(scanPhaseInterval);
    }

    scanBtn.addEventListener('click', async () => {
        // Disable button, show loader
        if (scanBtn) { scanBtn.disabled = true; scanBtn.setAttribute('aria-busy', 'true'); }
        startScanLoader();
        errorBox.classList.add('hidden');
        results.classList.add('hidden');
        emptyState.classList.add('hidden');
        tableBody.innerHTML = '';
        cardsGrid.innerHTML = '';

        try {
            const res  = await apiFetch('/api/recommendations');
            const data = await res.json();

            if (!res.ok) throw new Error(data.detail || 'Server error');
            if (!data.data?.length) throw new Error(
                'No buy signals found. Current market conditions are not conducive.'
            );

            buildTable(data.data);
            buildCards(data.data);
            results.classList.remove('hidden');
            // Tandai data contoh/simulasi agar tak disangka hasil scan nyata.
            try {
                const tag = document.getElementById('sample-data-tag');
                if (tag) {
                    const isSample = !!(data && (data.is_sample || data.stale));
                    tag.classList.toggle('hidden', !isSample);
                    if (isSample) {
                        const why = (data && data.fallback_reason) ? String(data.fallback_reason) : 'data-contoh';
                        tag.textContent = `DATA CONTOH (${why}) — bukan hasil scan. Jalankan scan harian untuk data nyata.`;
                        tag.setAttribute('role', 'status');
                    }
                }
            } catch (_) { /* noop */ }
            try {
                window.switchMainTab('recom', { scroll: false, focus: false });
            } catch (_) {
                const auditSec = document.getElementById('audit-section');
                if (auditSec) auditSec.style.display = 'none';
                const bR = document.getElementById('tab-btn-recom');
                const bA = document.getElementById('tab-btn-audit');
                if (bR && bA) {
                    bR.classList.add('is-active'); bR.setAttribute('aria-selected', 'true');
                    bA.classList.remove('is-active'); bA.setAttribute('aria-selected', 'false');
                }
            }
            if (lastScan) {
                const tsRaw = data && data.timestamp;
                let scanLabel = '';
                if (tsRaw && /^\d{4}-\d{2}-\d{2}/.test(String(tsRaw))) {
                    const parsed = new Date(String(tsRaw).replace(' ', 'T'));
                    if (!isNaN(parsed)) {
                        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
                        const dd = String(parsed.getDate()).padStart(2, '0');
                        const mmm = months[parsed.getMonth()];
                        const yyyy = parsed.getFullYear();
                        const hh = String(parsed.getHours()).padStart(2, '0');
                        const mm = String(parsed.getMinutes()).padStart(2, '0');
                        scanLabel = `Data scan ${dd} ${mmm} ${yyyy} ${hh}:${mm}`;
                    }
                }
                if (!scanLabel) {
                    scanLabel = 'Data scan ' + new Date().toLocaleString('id-ID', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) + ' (waktu buka)';
                }
                lastScan.textContent = scanLabel;
            }
            loadTrackRecord();

            // Smooth scroll ke hasil (auto bila reduced-motion)
            setTimeout(() => {
                const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                results.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
            }, 80);

            // Render Charts after DOM updates
            setTimeout(() => {
                renderIHSGChart(1);
                renderAllMiniCharts(data.data);
            }, 150);

        } catch (err) {
            showError(err && err.message ? err.message : 'Gagal memuat. Coba lagi.');
            emptyState.classList.remove('hidden');
            try {
                const retryBtn = document.getElementById('error-retry-btn');
                if (retryBtn) retryBtn.focus({ preventScroll: true });
                else errorBox.focus && errorBox.setAttribute('tabindex', '-1'), errorBox.focus({ preventScroll: true });
            } catch (_) { /* noop */ }
        } finally {
            stopScanLoader();
            loader.classList.add('hidden');
            if (scanBtn) { scanBtn.disabled = false; scanBtn.removeAttribute('aria-busy'); }
        }
    });

    function buildTable(stocks) {
        stocks.forEach((s, i) => {
            const rc             = rsiColor(s.rsi);
            const rw             = rsiW(s.rsi);
            const macdClass      = cls(s.macd_signal);
            const trendClass     = cls(s.trend);
            const isBuy          = s.signal === 1;
            const isFiller       = s.is_high_conviction === false;
            const showBuy        = isBuy && !isFiller;
            const probFinal      = Number(s.probability);
            const probRaw        = Number(s.probability_raw);
            const hasRawDiff     = Number.isFinite(probRaw) && Number.isFinite(probFinal) && Math.abs(probRaw - probFinal) >= 0.05;
            const scoreLabel     = hasRawDiff
                ? probFinal.toFixed(1) + '% (' + probRaw.toFixed(1) + ')'
                : probFinal.toFixed(1) + '%';
            const fillerTip      = 'Pengisi Top 10 — keyakinan model rendah, bukan sinyal beli';
            const sentStatus     = normSent(s.sentiment_status);
            const sentImpact     = normSent(s.sentiment_impact);
            const sentBadgeClass = sentStatus === 'POSITIF' ? 'booster' : (sentStatus === 'NEGATIF' ? 'veto' : 'neutral-sent');

            const tpPct = tpPctOf(s);
            const slPct = slPctOf(s);

            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="td-rank">${i + 1}</td>
                <td class="td-ticker">
                    <div class="t-name">${esc(s.ticker.replace('.JK', ''))}</div>
                    <div class="t-code">${esc(s.ticker)}</div>
                </td>
                <td class="td-price">${fmtPrice(s.close_price)}</td>
                <td class="td-target">${fmtPrice(s.target_price)} <span class="td-pct">(+${tpPct}%)</span></td>
                <td class="td-sl">${fmtPrice(s.stop_loss)} <span class="td-pct">(${slPct}%)</span></td>
                <td>
                    <div class="rsi-cell">
                        <span class="rsi-val">${esc(s.rsi)}</span>
                        <div class="rsi-track">
                            <div class="rsi-fill ${rc}" style="width:${rw}%"></div>
                        </div>
                        <span class="rsi-sig">${esc(s.rsi_signal)}</span>
                    </div>
                </td>
                <td><span class="badge ${macdClass}">${esc(s.macd_signal)}</span></td>
                <td><span class="badge ${trendClass}">${esc(s.trend)}</span></td>
                <td><span class="badge ${sentBadgeClass}">${esc(sentImpact)}</span></td>
                <td>
                    <div class="score-cell">
                        <div class="score-track">
                            <div class="score-fill" style="width:${s.probability}%"></div>
                        </div>
                        <span class="score-val"${hasRawDiff ? ` title="Skor mentah model: ${probRaw.toFixed(1)}"` : ''}>${scoreLabel}</span>
                    </div>
                </td>
                <td>
                    <span class="sig-pill ${showBuy ? 'buy' : 'watch'}"${isFiller ? ` title="${fillerTip}"` : ''}>
                        <span class="sig-dot ${showBuy ? 'green' : 'blue'}"></span>
                        ${showBuy ? 'BUY' : 'WATCH'}
                    </span>${isFiller ? `<br><span class="badge neutral-sent" title="${fillerTip}">Pengisi</span>` : ''}
                </td>
            `;
            tableBody.appendChild(row);
        });
    }

    function buildCards(stocks) {
        stocks.forEach(s => {
            const rc             = rsiColor(s.rsi);
            const macdClass      = cls(s.macd_signal);
            const trendClass     = cls(s.trend);
            const rsiClass       = rc === 'green' ? 'bullish' : rc === 'red' ? 'bearish' : 'uptrend';
            const isBuy          = s.signal === 1;
            const isFiller       = s.is_high_conviction === false;
            const showBuy        = isBuy && !isFiller;
            const probFinal      = Number(s.probability || 0);
            const probRaw        = Number(s.probability_raw);
            const hasRawDiff     = Number.isFinite(probRaw) && Number.isFinite(probFinal) && Math.abs(probRaw - probFinal) >= 0.05;
            const scoreLabel     = hasRawDiff
                ? probFinal.toFixed(1) + '% (' + probRaw.toFixed(1) + ')'
                : probFinal.toFixed(1) + '%';
            const fillerTip      = 'Pengisi Top 10 — keyakinan model rendah, bukan sinyal beli';
            const sentStatus     = normSent(s.sentiment_status);
            const sentImpact     = normSent(s.sentiment_impact);
            const sentBadgeClass = sentStatus === 'POSITIF' ? 'booster' : (sentStatus === 'NEGATIF' ? 'veto' : 'neutral-sent');

            const tpPct = tpPctOf(s);
            const slPct = slPctOf(s);
            const tickShort = safeId(s.ticker);
            const card = document.createElement('div');
            card.className = 'detail-card';
            card.setAttribute('role', 'listitem');
            card.setAttribute('aria-label', `Saham ${tickShort}, skor kuantitatif ${scoreLabel} persen${isFiller ? '. Pengisi Top 10, keyakinan model rendah' : ''}. Sinyal riset, bukan perintah beli atau jual.`);
            card.innerHTML = `
                <div class="dc-head">
                    <div>
                        <div class="dc-ticker">${esc(tickShort)}</div>
                        <span class="dc-code">${esc(s.ticker)}</span>${isFiller ? `<br><span class="badge neutral-sent" title="${fillerTip}">Pengisi</span>` : ''}
                    </div>
                    <div>
                        <div class="dc-score"${hasRawDiff ? ` title="Skor mentah model: ${probRaw.toFixed(1)}"` : ''}>${scoreLabel}</div>
                        <div class="dc-score-lbl">Quant Score</div>
                    </div>
                </div>

                <div class="dc-prices">
                    <div class="dc-price-col">
                        <div class="dc-plbl">Price</div>
                        <div class="dc-pval primary">${s.close_price > 0 ? idr(s.close_price) : '—'}</div>
                    </div>
                    <div class="dc-price-col">
                        <div class="dc-plbl">Target Profit</div>
                        <div class="dc-pval green">${s.target_price > 0 ? idr(s.target_price) : '—'} <span class="dc-pct">(+${tpPct}%)</span></div>
                    </div>
                    <div class="dc-price-col">
                        <div class="dc-plbl">Stop Loss</div>
                        <div class="dc-pval red">${s.stop_loss > 0 ? idr(s.stop_loss) : '—'} <span class="dc-pct">(${slPct}%)</span></div>
                    </div>
                </div>

                <div id="chart-${esc(tickShort)}" class="mini-chart-container" role="img" aria-label="Grafik mini ${esc(tickShort)} 60 hari. Sinyal ${showBuy ? 'riset beli' : 'pantau'}${isFiller ? ', pengisi Top 10 keyakinan rendah' : ''}, tren ${esc(s.trend || 'tidak diketahui')}, skor ${scoreLabel} persen."></div>
                <p class="legal-microcopy" style="margin:4px 0 8px">Sinyal riset — bukan perintah beli/jual. Saham berisiko rugi. DYOR.</p>

                <div class="dc-quant-metrics">
                    ${s.sector ? `<span class="qm-tag"><span class="qm-lbl">Sektor:</span> <strong>${esc(s.sector)}</strong>${s.is_leading_sector ? ' <span class="qm-leading">· Leading</span>' : ''}</span>` : ''}
                    <span class="qm-tag"><span class="qm-lbl">Risk/Reward model:</span> <strong>1:${esc(s.risk_reward_ratio || '2.0')}</strong></span>
                    <span class="qm-tag"><span class="qm-lbl">Alokasi model generik:</span> <strong style="color:var(--c-green);">${esc(s.kelly_allocation || '10')}% (bukan saran portofolio personal)</strong></span>
                </div>

                <div class="dc-badges">
                    ${s.is_leading_sector ? '<span class="badge booster">Leading Sector</span>' : ''}
                    ${s.rvol ? `<span class="badge ${s.rvol >= 1.2 ? 'booster' : 'neutral-sent'}">RVOL ${esc(s.rvol)}x</span>` : ''}
                    ${s.adx ? `<span class="badge ${s.adx >= 25 ? 'bullish' : 'neutral-sent'}">ADX ${esc(s.adx)}</span>` : ''}
                    <span class="badge ${macdClass}">MACD ${esc(s.macd_signal)}</span>
                    <span class="badge ${trendClass}">${esc(s.trend)}</span>
                    <span class="badge ${rsiClass}">RSI ${esc(s.rsi)}</span>
                    <span class="badge ${sentBadgeClass}">${esc(sentImpact)}</span>
                    <span class="sig-pill sig-pill--sm ${showBuy ? 'buy' : 'watch'}" title="${isFiller ? fillerTip : (showBuy ? 'Sinyal riset — bukan perintah beli' : 'Pantau — bukan perintah jual/beli')}">
                        <span class="sig-dot ${showBuy ? 'green' : 'blue'}" aria-hidden="true"></span>
                        ${showBuy ? 'SINYAL RISET' : 'PANTAU'}
                    </span>${isFiller ? `<span class="badge neutral-sent" title="${fillerTip}">Pengisi</span>` : ''}
                    <button class="agent-toggle-btn" id="btn-ma-${esc(tickShort)}" aria-expanded="false" aria-controls="ma-box-${esc(tickShort)}">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                        Multi-Agent
                    </button>
                </div>

                <div id="ma-box-${esc(tickShort)}" class="multi-agent-card hidden"></div>

                <div class="dc-reason">
                    <span class="dc-reason-lbl">Quantitative Analysis (Technicals &amp; News)</span>
                    <div id="narasi-${esc(tickShort)}">
                        <div class="ai-loading">Analyzing technicals &amp; sentiment data...</div>
                    </div>
                </div>
            `;

            cardsGrid.appendChild(card);
            fetchNarrative(s, card);
            setupMultiAgentToggle(s, card);
        });
    }

    // Charting Logic
    async function fetchChartData(ticker, days = 60) {
        try {
            const res = await apiFetch(`/api/chart/${encodeURIComponent(ticker)}?days=${encodeURIComponent(days)}`);
            const json = await res.json();
            if (res.ok && json.status === 'success') {
                return { data: json.data, intraday: json.intraday };
            }
        } catch (e) {
            console.error('Failed to fetch chart data for', ticker, e);
        }
        return { data: [], intraday: false };
    }

    const ihsgSummary = () => document.getElementById('ihsg-summary');

    async function renderIHSGChart(days = 60) {
        const ihsgChartDiv = document.getElementById('ihsg-chart');
        const ihsgPriceVal = document.getElementById('hero-ihsg-price');
        const ihsgDesc    = document.getElementById('ihsg-desc');
        if (!ihsgChartDiv || !ihsgPriceVal) return;
        disposeChart(ihsgChartDiv);
        ihsgChartDiv.innerHTML = '';
        ihsgPriceVal.textContent = '...';

        // Update tab active state (+ aria-pressed untuk SR)
        document.querySelectorAll('.chart-tab').forEach(t => { t.classList.remove('active'); t.setAttribute('aria-pressed', 'false'); });
        const activeTab = document.getElementById(days === 1 ? 'tab-1d' : 'tab-60d');
        if (activeTab) { activeTab.classList.add('active'); activeTab.setAttribute('aria-pressed', 'true'); }
        const rangeSelect = document.getElementById('ihsg-range-select');
        if (rangeSelect) rangeSelect.value = String(days);
        if (ihsgDesc) ihsgDesc.textContent = days === 1
            ? "Today's price movement (5-min interval)"
            : 'Overall market trend over the past 60 days';

        if (typeof LightweightCharts === 'undefined') {
            ihsgPriceVal.textContent = 'Error: Library not loaded';
            return;
        }

        const { data, intraday } = await fetchChartData('IHSG', days);
        if (!data || data.length === 0) {
            ihsgPriceVal.textContent = 'Data unavailable';
            const sEl = ihsgSummary();
            if (sEl) sEl.textContent = 'Data chart IHSG tidak tersedia saat ini.';
            return;
        }

        const lastPrice  = data[data.length - 1].value;
        const firstPrice = data[0].value;
        const isUp = lastPrice >= firstPrice;
        const pct = firstPrice > 0 ? (((lastPrice - firstPrice) / firstPrice) * 100) : 0;
        ihsgPriceVal.textContent = new Intl.NumberFormat('id-ID', {style:'currency', currency:'IDR', minimumFractionDigits:0}).format(lastPrice);
        ihsgPriceVal.style.color = isUp ? 'var(--c-charcoal)' : 'var(--c-red)';
        // Ringkasan tekstual untuk SR + pengguna yang tak baca chart (UX-04).
        const sEl = ihsgSummary();
        if (sEl) sEl.textContent = `IHSG ${days === 1 ? 'intraday' : '60 hari'}: ${isUp ? 'menguat' : 'melemah'} ${Math.abs(pct).toFixed(2)}% ke ${ihsgPriceVal.textContent}.`;

        try {
            const chart = LightweightCharts.createChart(ihsgChartDiv, {
                width: ihsgChartDiv.clientWidth || 600,
                height: 200,
                layout: {
                    background: { type: 'solid', color: 'transparent' },
                    textColor: '#595959',
                    fontFamily: 'Montserrat, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
                },
                grid: { vertLines: { visible: false }, horzLines: { color: 'rgba(0, 0, 0, 0.05)' } },
                rightPriceScale: { borderVisible: false },
                timeScale: {
                    borderVisible: false,
                    timeVisible: intraday,
                    secondsVisible: false
                },
                crosshair: { mode: 0 },
                handleScroll: false,
                handleScale: false
            });

            const areaSeries = chart.addAreaSeries({
                lineColor: isUp ? '#0051C3' : '#DE5052',
                topColor: isUp ? 'rgba(0, 81, 195, 0.15)' : 'rgba(222, 80, 82, 0.15)',
                bottomColor: 'rgba(0,0,0,0)',
                lineWidth: 2,
            });

            areaSeries.setData(data);
            chart.timeScale().fitContent();
            registerChart(ihsgChartDiv, chart, 200);
        } catch (e) {
            ihsgChartDiv.innerHTML = '<p class="chart-msg chart-msg--err">Chart error: ' + esc(e.message || e) + '</p>';
            ihsgPriceVal.textContent = 'Error';
            console.error('IHSG Chart Error:', e);
        }
    }

    // Global function for onclick in HTML
    window.switchIhsgRange = function(days) {
        renderIHSGChart(days);
    };


    async function renderOneMiniChart(s) {
        const cleanTicker = safeId(s.ticker);
        const container = document.getElementById(`chart-${cleanTicker}`);
        if (!container) return;

        const { data } = await fetchChartData(cleanTicker, 60);
        if (!document.contains(container)) return;
        if (!data || data.length === 0) {
            disposeChart(container);
            container.innerHTML = '<span class="chart-msg chart-msg--sm chart-msg--muted">No chart data</span>';
            return;
        }

        const isUp = String(s.trend || '').toLowerCase() === 'uptrend' || (data[data.length - 1].value >= data[0].value);
        const isBuy = s.signal === 1;

        // Cobalt/rose rules for BUY (index palette), soft gray for WATCH
        const lineColor = isBuy
            ? (isUp ? '#0051C3' : '#DE5052')
            : '#8C8C8C';
        const topColor = isBuy
            ? (isUp ? 'rgba(0, 81, 195, 0.1)' : 'rgba(222, 80, 82, 0.1)')
            : 'rgba(140, 140, 140, 0.1)';

        try {
            disposeChart(container);
            const chart = LightweightCharts.createChart(container, {
                width: container.clientWidth || 240,
                height: 80,
                layout: {
                    background: { type: 'solid', color: 'transparent' },
                    fontFamily: 'Montserrat, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
                },
                grid: { vertLines: { visible: false }, horzLines: { visible: false } },
                rightPriceScale: { visible: false },
                leftPriceScale: { visible: false },
                timeScale: { visible: false },
                crosshair: {
                    horzLine: { visible: false, labelVisible: false },
                    vertLine: { visible: true, style: 3, width: 1, color: lineColor, labelVisible: false }
                },
                handleScroll: false,
                handleScale: false
            });

            const areaSeries = chart.addAreaSeries({
                lineColor: lineColor,
                topColor: topColor,
                bottomColor: 'rgba(0, 0, 0, 0)',
                lineWidth: 2,
                crosshairMarkerVisible: true
            });

            areaSeries.setData(data);
            chart.timeScale().fitContent();
            registerChart(container, chart, 80);
        } catch (e) {
            disposeChart(container);
            container.innerHTML = '<span class="chart-msg chart-msg--sm chart-msg--err">Chart Error</span>';
            console.error(e);
        }
    }

    async function renderAllMiniCharts(stocks) {
        // Guard library (remote fix): jika gagal dimuat, tandai semua container & hentikan.
        if (typeof LightweightCharts === 'undefined') {
            stocks.forEach(x => {
                const c = document.getElementById(`chart-${safeId(x.ticker)}`);
                if (c) c.innerHTML = '<span class="chart-msg chart-msg--sm chart-msg--muted">Chart library unavailable</span>';
            });
            return;
        }
        // Paralel (dulu sequential for...of await) + batasi 5 konkurensi
        // agar 10 fetch /api/chart tidak menumpuk melebihi rate-limit.
        const queue = [...stocks];
        const workers = Array.from({ length: Math.min(5, queue.length) }, async () => {
            while (queue.length) {
                const s = queue.shift();
                if (!s) break;
                try { await renderOneMiniChart(s); } catch (e) { console.error(e); }
            }
        });
        await Promise.all(workers);
    }

    async function fetchNarrative(s, card) {
        const cleanTicker = safeId(s.ticker);
        const container = card.querySelector(`#narasi-${CSS.escape(cleanTicker)}`);
        if (!container) return;

        // Narasi adalah teks polos -> pakai textContent (anti-XSS).
        // Backend sudah html.escape; textContent menampilkan aman apa adanya.
        const fallbackText = `Saham ${cleanTicker} menunjukkan momentum positif dengan RSI ${s.rsi} (${s.rsi_signal}) dan indikator MACD ${s.macd_signal} pada tren ${s.trend}.`;

        try {
            const res = await apiFetch('/api/narasi', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ticker: s.ticker,
                    close_price: s.close_price,
                    target_price: s.target_price,
                    stop_loss: s.stop_loss,
                    rsi: s.rsi,
                    macd_signal: s.macd_signal,
                    trend: s.trend,
                    probability: s.probability,
                    sentiment_status: s.sentiment_status || 'NETRAL',
                    sentiment_impact: s.sentiment_impact || 'NETRAL'
                })
            });
            if (res.ok) {
                const data = await res.json();
                if (data && data.status === 'success' && data.narasi) {
                    container.textContent = data.narasi;
                    return;
                }
            }
        } catch (err) {
            console.warn('AI narrative unavailable, displaying quantitative summary:', err);
        }

        container.textContent = fallbackText;
    }

    function setupMultiAgentToggle(s, card) {
        const cleanTicker = safeId(s.ticker);
        const btn = card.querySelector(`#btn-ma-${CSS.escape(cleanTicker)}`);
        const box = card.querySelector(`#ma-box-${CSS.escape(cleanTicker)}`);
        if (!btn || !box) return;

        let loaded = false;

        btn.addEventListener('click', async () => {
            if (box.classList.contains('hidden')) {
                box.classList.remove('hidden');
                btn.setAttribute('aria-expanded', 'true');
                if (!loaded) {
                    box.innerHTML = '<div class="ai-loading">Processing 4-Agent Analysis (Technical, Sentiment, Bull/Bear Debate, Risk Manager)...</div>';
                    try {
                        const res = await apiFetch('/api/narasi/multi-agent', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                ticker: s.ticker,
                                close_price: s.close_price,
                                target_price: s.target_price,
                                stop_loss: s.stop_loss,
                                rsi: s.rsi,
                                macd_signal: s.macd_signal,
                                trend: s.trend,
                                probability: s.probability,
                                sentiment_status: normSent(s.sentiment_status),
                                sentiment_impact: normSent(s.sentiment_impact)
                            })
                        });
                        const json = await res.json();
                        if (res.ok && json.status === 'success' && json.data) {
                            const d = json.data;
                            const isBuyVerdict = (d.risk_verdict || '').includes('BELI') || (d.risk_verdict || '').includes('BUY');
                            const verdictBadgeClass = isBuyVerdict ? 'pill-verdict-buy' : 'pill-verdict-watch';

                            // Defense-in-depth: esc() semua string eksternal walau backend sudah sanitize.
                            box.innerHTML = `
                                <div class="ma-header">
                                    <div class="ma-title">Multi-Agent Framework Consensus</div>
                                    <span class="risk-pill ${verdictBadgeClass}">${esc(d.risk_verdict)}</span>
                                </div>
                                <div class="ma-subcard bull">
                                    <div class="ma-card-label label-bull">Bull Case (Buyer Analysis)</div>
                                    <div>${esc(d.bull_case)}</div>
                                </div>
                                <div class="ma-subcard bear">
                                    <div class="ma-card-label label-bear">Bear Case (Seller Caution)</div>
                                    <div>${esc(d.bear_case)}</div>
                                </div>
                                <div class="ma-subcard risk">
                                    <div class="ma-card-label label-risk">Risk Manager Verdict</div>
                                    <div class="ma-rr-row">
                                        <span>Target Risk/Reward Ratio:</span>
                                        <span class="risk-pill pill-rr">${esc(d.risk_reward_ratio)}x R:R</span>
                                    </div>
                                </div>
                            `;

                            loaded = true;
                        } else {
                            box.textContent = `Failed to load agent consensus: ${json.detail || 'Error'}`;
                        }
                    } catch (err) {
                        box.textContent = `Error: ${err.message}`;
                    }

                }
            } else {
                box.classList.add('hidden');
                btn.setAttribute('aria-expanded', 'false');
            }
        });
    }


        // Audit & Monthly Recap State
        let allMonthlyData = [];
        let isMonthlyExpanded = false;
        let allAuditData = [];
        let isAuditExpanded = false;
        // Filter tabel audit: default = scan 30 hari terakhir.
        let auditSourceFilter = 'scan';
        let auditRangeFilter = '30';
        let auditTickerFilter = '';

        function auditRowDate(s) {
            return s.trading_date || (s.updated_at || s.created_at || '').split(' ')[0] || '';
        }

        function getFilteredAuditData() {
            const q = auditTickerFilter.trim().toUpperCase();
            let rows = allAuditData.filter(s => {
                const src = String(s.source || 'scan').toLowerCase();
                if (auditSourceFilter !== 'all' && src !== auditSourceFilter) return false;
                if (q && !String(s.ticker || '').toUpperCase().includes(q)) return false;
                return true;
            });
            if (auditRangeFilter !== 'all') {
                const days = Number(auditRangeFilter);
                if (Number.isFinite(days) && days > 0) {
                    const now = new Date();
                    now.setHours(0, 0, 0, 0);
                    const cutoff = new Date(now.getTime() - (days - 1) * 86400000);
                    const cutoffStr = cutoff.getFullYear() + '-' +
                        String(cutoff.getMonth() + 1).padStart(2, '0') + '-' +
                        String(cutoff.getDate()).padStart(2, '0');
                    rows = rows.filter(s => auditRowDate(s) >= cutoffStr);
                }
            }
            // Grup tampilan per tanggal tetap sort DESC (allAuditData sudah sort DESC).
            return rows;
        }

        function wireAuditFilters() {
            const srcSel = document.getElementById('audit-source-filter');
            const rangeSel = document.getElementById('audit-range-filter');
            const tickerIn = document.getElementById('audit-ticker-filter');
            if (srcSel) srcSel.addEventListener('change', () => {
                auditSourceFilter = srcSel.value;
                isAuditExpanded = false;
                renderAuditTable();
            });
            if (rangeSel) rangeSel.addEventListener('change', () => {
                auditRangeFilter = rangeSel.value;
                isAuditExpanded = false;
                renderAuditTable();
            });
            if (tickerIn) {
                let t = null;
                tickerIn.addEventListener('input', () => {
                    clearTimeout(t);
                    t = setTimeout(() => {
                        auditTickerFilter = tickerIn.value;
                        isAuditExpanded = false;
                        renderAuditTable();
                    }, 200);
                });
            }
        }
                async function runAuditAndLoad() {
            // Jangan panggil /api/audit/run anonim di setiap page-load:
            // endpoint butuh API key (401 percuma) + membebani server.
            // Hanya refresh bila user sudah set key via window.setStockAIApiKey().
            let hasKey = false;
            try { hasKey = !!(sessionStorage.getItem('api_key') || ''); } catch (_) { hasKey = false; }
            if (hasKey) {
                try {
                    await apiFetch('/api/audit/run');
                } catch (e) {
                    console.error('Failed to run audit:', e);
                }
            }
            await loadTrackRecord();
            await loadAuditRecapAndChart();
        }

        window.switchMainTab = function(tabName, opts = {}) {
            const resultsDiv = document.getElementById('results');
            const auditSec = document.getElementById('audit-section');
            const btnRecom = document.getElementById('tab-btn-recom');
            const btnAudit = document.getElementById('tab-btn-audit');
            const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

            const setActive = (activeBtn, inactiveBtn) => {
                if (!activeBtn || !inactiveBtn) return;
                activeBtn.classList.add('is-active');
                activeBtn.setAttribute('aria-selected', 'true');
                activeBtn.setAttribute('tabindex', '0');
                inactiveBtn.classList.remove('is-active');
                inactiveBtn.setAttribute('aria-selected', 'false');
                inactiveBtn.setAttribute('tabindex', '-1');
            };

            const scrollTo = (el) => {
                if (!el || opts.scroll === false) return;
                try {
                    el.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
                    const focusTarget = el.hasAttribute('tabindex') ? el : null;
                    if (opts.focus !== false && focusTarget && document.activeElement !== focusTarget) {
                        try { focusTarget.focus({ preventScroll: true }); } catch (_) { /* noop */ }
                    }
                } catch (_) { /* noop */ }
            };

            if (tabName === 'recom') {
                const hasScanResults = tableBody && tableBody.children.length > 0;
                if (resultsDiv) resultsDiv.classList.toggle('hidden', !hasScanResults);
                if (emptyState) emptyState.classList.toggle('hidden', hasScanResults);
                if (auditSec) auditSec.style.display = 'none';
                if (btnRecom && btnAudit) setActive(btnRecom, btnAudit);
                try {
                    sessionStorage.setItem('aksa-main-tab', 'recom');
                    if (opts.hash !== false && location.hash !== '#rekomendasi') history.replaceState(null, '', '#rekomendasi');
                } catch (_) { /* noop */ }
                scrollTo(resultsDiv);
            } else if (tabName === 'audit') {
                if (resultsDiv) resultsDiv.classList.add('hidden');
                if (emptyState) emptyState.classList.add('hidden');
                if (auditSec) auditSec.style.display = 'block';
                // Chart equity dibuat saat panel tersembunyi (clientWidth 0) → resize ulang setelah layout tersedia.
                try {
                    const eqChart = document.getElementById('audit-equity-chart');
                    if (eqChart) {
                        requestAnimationFrame(() => {
                            requestAnimationFrame(() => {
                                try {
                                    if (typeof resizeOneChart === 'function') {
                                        resizeOneChart(eqChart);
                                        const c = eqChart._chart;
                                        if (c) c.timeScale().fitContent();
                                    } else if (eqChart._chart) {
                                        eqChart._chart.resize(eqChart.clientWidth || 600, eqChart.clientHeight || 220);
                                        eqChart._chart.timeScale().fitContent();
                                    }
                                } catch (_) { /* noop */ }
                            });
                        });
                    }
                } catch (_) { /* noop */ }
                if (btnRecom && btnAudit) setActive(btnAudit, btnRecom);
                try {
                    sessionStorage.setItem('aksa-main-tab', 'audit');
                    if (opts.hash !== false && location.hash !== '#simulasi') history.replaceState(null, '', '#simulasi');
                } catch (_) { /* noop */ }
                scrollTo(auditSec);
            }
        };

        // Arrow-key nav antar tab (roving tabindex) + deep-link #rekomendasi/#simulasi.
        // Panah scroll tabs di HP: tampil hanya bila bar overflow; sentuh >=44px.
        (function wireMainTabsArrows() {
            const bar = document.getElementById('main-tabs-bar');
            const prev = document.getElementById('tabs-arrow-prev');
            const next = document.getElementById('tabs-arrow-next');
            if (!bar || !prev || !next) return;
            const step = () => Math.max(160, Math.floor(bar.clientWidth * 0.7));
            const update = () => {
                const overflow = bar.scrollWidth > bar.clientWidth + 4;
                prev.hidden = next.hidden = !overflow;
                prev.classList.toggle('is-visible', overflow);
                next.classList.toggle('is-visible', overflow);
                if (!overflow) return;
                const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                prev.disabled = bar.scrollLeft <= 1;
                next.disabled = bar.scrollLeft >= bar.scrollWidth - bar.clientWidth - 1;
                prev.style.opacity = prev.disabled ? '0.4' : '';
                next.style.opacity = next.disabled ? '0.4' : '';
                void reduce;
            };
            prev.addEventListener('click', () => bar.scrollBy({ left: -step(), behavior: 'smooth' }));
            next.addEventListener('click', () => bar.scrollBy({ left: step(), behavior: 'smooth' }));
            bar.addEventListener('scroll', update, { passive: true });
            window.addEventListener('resize', update, { passive: true });
            update();
            // Tab aktif selalu terlihat di HP
            const mo = new MutationObserver(update);
            try { mo.observe(bar, { childList: true, subtree: true }); } catch (_) { /* noop */ }
            window.scrollActiveMainTab = () => {
                try {
                    const active = bar.querySelector('.main-tab-btn.is-active');
                    if (active) active.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
                } catch (_) { /* noop */ }
            };
        })();
        window.mainTabKeyNav = function(e) {
            const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End'];
            if (!keys.includes(e.key)) return;
            e.preventDefault();
            const onAudit = document.activeElement && document.activeElement.id === 'tab-btn-audit';
            let next;
            if (e.key === 'ArrowRight') next = 'recom';
            else if (e.key === 'ArrowLeft') next = 'audit';
            else if (e.key === 'Home') next = 'recom';
            else next = 'audit';
            if ((next === 'recom' && !onAudit && (e.key === 'ArrowRight' || e.key === 'Home')) ||
                (next === 'audit' && onAudit && (e.key === 'ArrowLeft' || e.key === 'End'))) {
                // Sudah di tab tujuan; tetap pastikan state sinkron tanpa pindah fokus.
                window.switchMainTab(next, { focus: false });
                return;
            }
            window.switchMainTab(next);
            const btn = document.getElementById(next === 'recom' ? 'tab-btn-recom' : 'tab-btn-audit');
            if (btn) btn.focus();
        };

        (function initMainTabFromHash() {
            try {
                const h = (location.hash || '').toLowerCase();
                let tab = h === '#simulasi' ? 'audit' : h === '#rekomendasi' ? 'recom' : null;
                if (!tab) { try { tab = sessionStorage.getItem('aksa-main-tab'); } catch (_) { tab = null; } }
                if (tab === 'audit' || tab === 'recom') {
                    window.switchMainTab(tab, { scroll: false, focus: false, hash: false });
                } else {
                    // Default: tab rekomendasi aktif, panel audit tampil (landing lama).
                    const bR = document.getElementById('tab-btn-recom');
                    const bA = document.getElementById('tab-btn-audit');
                    if (bR) bR.setAttribute('tabindex', '0');
                    if (bA) bA.setAttribute('tabindex', '-1');
                }
            } catch (_) { /* noop */ }
        })();

        async function loadTrackRecord() {
            const body = document.getElementById('audit-table-body');
            if (!body) return;

            try {
                const res = await apiFetch('/api/audit/track-record');
                const data = await res.json();

                if (res.ok && data.status === 'success' && data.data?.length > 0) {
                    allAuditData = data.data.sort((a, b) => {
                        const dA = a.trading_date || (a.updated_at || a.created_at).split(' ')[0];
                        const dB = b.trading_date || (b.updated_at || b.created_at).split(' ')[0];
                        return dB.localeCompare(dA);
                    });
                    renderAuditTable();
                } else {
                    allAuditData = [];
                    body.innerHTML = `
                        <tr>
                            <td colspan="7" class="table-empty">
                                No signal history in database. Click <strong>Run 6-Month Performance Simulation</strong> to test.
                            </td>
                        </tr>
                    `;
                }
            } catch (err) {
                body.innerHTML = `
                    <tr>
                        <td colspan="7" class="table-empty table-empty--err">
                            Failed to load track record: ${err.message}
                        </td>
                    </tr>
                `;
            }
        }

        function renderAuditTable() {
            const body = document.getElementById('audit-table-body');
            const toggleBtn = document.getElementById('toggle-audit-btn');
            const countEl = document.getElementById('audit-filter-count');
            if (!body) return;

            if (allAuditData.length === 0) {
                if (toggleBtn) toggleBtn.classList.remove('shown');
                if (countEl) countEl.textContent = '';
                return;
            }

            const filtered = getFilteredAuditData();
            if (countEl) {
                countEl.textContent = filtered.length === allAuditData.length
                    ? `${filtered.length} sinyal`
                    : `${filtered.length} dari ${allAuditData.length} sinyal`;
            }

            if (filtered.length === 0) {
                body.innerHTML = `
                    <tr>
                        <td colspan="7" class="table-empty">
                            Tidak ada sinyal cocok dengan filter. Ubah sumber, rentang tanggal, atau ticker.
                        </td>
                    </tr>
                `;
                if (toggleBtn) toggleBtn.classList.remove('shown');
                return;
            }

            const visibleRows = isAuditExpanded ? filtered : filtered.slice(0, 5);
            body.innerHTML = '';

            visibleRows.forEach(s => {
                const row = document.createElement('tr');
                const tpPct = (s.entry_price > 0 && s.target_price > 0)
                    ? (((s.target_price - s.entry_price) / s.entry_price) * 100).toFixed(1)
                    : '3.0';
                const slPct = (s.entry_price > 0 && s.stop_loss > 0)
                    ? (((s.stop_loss - s.entry_price) / s.entry_price) * 100).toFixed(1)
                    : '-1.5';

                const retVal = s.status === 'LOSS' ? -1.5 : (s.return_pct != null ? s.return_pct : 0);
                const retSign = retVal >= 0 ? '+' : '';
                const isFillerAudit = s.is_high_conviction === false;
                const probFinalAudit = Number(s.probability);
                const probRawAudit = Number(s.probability_raw);
                const hasRawDiffAudit = Number.isFinite(probRawAudit) && Number.isFinite(probFinalAudit) && Math.abs(probRawAudit - probFinalAudit) >= 0.05;
                const scoreLabelAudit = Number.isFinite(probFinalAudit)
                    ? (hasRawDiffAudit ? probFinalAudit.toFixed(1) + '% (' + probRawAudit.toFixed(1) + ')' : probFinalAudit.toFixed(1) + '%')
                    : '—';
                const statusKey = String(s.status || 'PENDING').toUpperCase();
                const badge = statusKey === 'WIN' ? `<span class="badge bullish">SIM-WIN ${retSign}${retVal.toFixed(1)}%</span>` :
                              (statusKey === 'LOSS' ? `<span class="badge bearish">SIM-LOSS ${retVal.toFixed(1)}%</span>` : `<span class="badge neutral-sent">SIM-PENDING</span>`);

                row.innerHTML = `
                    <td>${s.trading_date || (s.updated_at || s.created_at).split(' ')[0]}</td>
                    <td class="td-ticker-cell">${s.ticker}</td>
                    <td>${fmtPrice(s.entry_price)}</td>
                    <td class="td-win">${fmtPrice(s.target_price)} <span class="td-pct">(+${tpPct}%)</span></td>
                    <td class="td-loss">${fmtPrice(s.stop_loss)} <span class="td-pct">(${slPct}%)</span></td>
                    <td${hasRawDiffAudit ? ` title="Skor mentah model: ${probRawAudit.toFixed(1)}"` : ''}>${scoreLabelAudit}${isFillerAudit ? ' <span class="badge neutral-sent" title="Pengisi Top 10 — keyakinan model rendah, bukan sinyal beli">Pengisi</span>' : ''}</td>
                    <td>${badge}</td>
                `;
                body.appendChild(row);
            });

            if (toggleBtn) {
                if (filtered.length > 5) {
                    toggleBtn.classList.add('shown');
                    toggleBtn.textContent = isAuditExpanded 
                        ? 'Hide ↑' 
                        : `View More (${filtered.length - 5} More Signals) ↓`;
                } else {
                    toggleBtn.classList.remove('shown');
                }
            }
        }

        async function loadAuditRecapAndChart() {
            const winRateEl = document.getElementById('stat-win-rate');
            const winLossEl = document.getElementById('stat-win-loss');
            const profitEl = document.getElementById('stat-total-profit');
            const monthlyBody = document.getElementById('monthly-recap-body');
            const chartDiv = document.getElementById('audit-equity-chart');

            if (!winRateEl || !monthlyBody) return;

            try {
                const res = await apiFetch('/api/audit/recap');
                const data = await res.json();

                if (res.ok && data.status === 'success') {
                    const s = data.summary;
                    winRateEl.textContent = s.win_rate > 0 ? `${s.win_rate.toFixed(1)}%` : '0.0%';
                    winLossEl.textContent = `${s.win_count} SIM-WIN / ${s.loss_count} SIM-LOSS`;
                    profitEl.textContent = `${s.total_profit_pct >= 0 ? '+' : ''}${s.total_profit_pct.toFixed(1)}%`;
                    profitEl.classList.toggle('stat-val--neg', s.total_profit_pct < 0);
                    // Ringkasan tekstual equity (UX-04): SR dengar angka tanpa baca chart.
                    const eqSum = document.getElementById('equity-summary');
                    if (eqSum) eqSum.textContent = `Hasil simulasi: win rate ${Number(s.win_rate || 0).toFixed(1)} persen, ${s.win_count} SIM-WIN / ${s.loss_count} SIM-LOSS, kumulatif ${profitEl.textContent}. Bukan hasil nyata.`;

                    // Save monthly data & render table
                    allMonthlyData = data.monthly_breakdown || [];
                    renderMonthlyTable();

                    // Render Equity Curve Chart (tunda bila panel tersembunyi: clientWidth 0)
                    if (chartDiv && typeof LightweightCharts !== 'undefined' && data.equity_curve?.length > 0) {
                        const equityData = data.equity_curve;
                        const buildEquityChart = () => {
                        disposeChart(chartDiv);
                        chartDiv.innerHTML = '';
                        try {
                            const chart = LightweightCharts.createChart(chartDiv, {
                                width: chartDiv.clientWidth || 600,
                                height: 220,
                                layout: {
                                    background: { type: 'solid', color: 'transparent' },
                                    textColor: '#595959',
                                    fontFamily: 'Montserrat, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
                                },
                                grid: { vertLines: { visible: false }, horzLines: { color: 'rgba(0, 0, 0, 0.05)' } },
                                rightPriceScale: { borderVisible: false },
                                timeScale: { borderVisible: false, secondsVisible: false },
                                crosshair: { mode: 0 },
                                handleScroll: false,
                                handleScale: false
                            });

                            const areaSeries = chart.addAreaSeries({
                                lineColor: '#0051C3',
                                topColor: 'rgba(0, 81, 195, 0.15)',
                                bottomColor: 'rgba(0, 81, 195, 0.0)',
                                lineWidth: 2,
                            });

                            areaSeries.setData(equityData);
                            chart.timeScale().fitContent();
                            registerChart(chartDiv, chart, 220);
                        } catch (ce) {
                            console.error('Equity chart error:', ce);
                        }
                        };
                        if (chartDiv.clientWidth > 0) {
                            buildEquityChart();
                        } else {
                            requestAnimationFrame(function retryEquityChart() {
                                if (chartDiv.clientWidth > 0) buildEquityChart();
                                else requestAnimationFrame(retryEquityChart);
                            });
                        }
                    }
                }
            } catch (err) {
                console.error('Failed to load audit recap:', err);
            }
        }

        function renderMonthlyTable() {
            const monthlyBody = document.getElementById('monthly-recap-body');
            const toggleBtn = document.getElementById('toggle-monthly-btn');
            if (!monthlyBody) return;

            if (allMonthlyData.length === 0) {
                monthlyBody.innerHTML = `
                    <tr>
                        <td colspan="6" class="table-empty">
                            No monthly recap data available yet.
                        </td>
                    </tr>
                `;
                if (toggleBtn) toggleBtn.classList.remove('shown');
                return;
            }

            const visibleRows = isMonthlyExpanded ? allMonthlyData : allMonthlyData.slice(0, 3);
            monthlyBody.innerHTML = '';

            visibleRows.forEach(m => {
                const row = document.createElement('tr');
                const isPos = m.monthly_profit_pct >= 0;
                row.innerHTML = `
                    <td class="td-month-cell">${m.month_name}</td>
                    <td>${m.total_signals} Sinyal (sim)</td>
                    <td class="td-win">${m.win_count} SIM-WIN</td>
                    <td class="td-loss">${m.loss_count} SIM-LOSS</td>
                    <td><span class="badge ${m.win_rate >= 60 ? 'uptrend' : 'bearish'}">${m.win_rate.toFixed(1)}%</span></td>
                    <td class="td-profit ${isPos ? 'pos' : 'neg'}">${isPos ? '+' : ''}${m.monthly_profit_pct.toFixed(1)}%</td>
                `;
                monthlyBody.appendChild(row);
            });

            if (toggleBtn) {
                if (allMonthlyData.length > 3) {
                    toggleBtn.classList.add('shown');
                    toggleBtn.textContent = isMonthlyExpanded 
                        ? 'Hide ↑' 
                        : `View More (${allMonthlyData.length - 3} More Months) ↓`;
                } else {
                    toggleBtn.classList.remove('shown');
                }
            }
        }

        window.toggleMonthlyRecap = function() {
            isMonthlyExpanded = !isMonthlyExpanded;
            renderMonthlyTable();
            const btn = document.getElementById('toggle-monthly-btn');
            if (btn) btn.setAttribute('aria-expanded', String(isMonthlyExpanded));
        };

        window.toggleAuditLog = function() {
            isAuditExpanded = !isAuditExpanded;
            renderAuditTable();
            const btn = document.getElementById('toggle-audit-btn');
            if (btn) btn.setAttribute('aria-expanded', String(isAuditExpanded));
        };

        window.runAuditSimulationSeed = async function() {
            const btn = document.getElementById('seed-sim-btn');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Generating simulation...';
            }

            try {
                const res = await apiFetch('/api/audit/seed-simulation');
                const data = await res.json();
                if (res.ok && data.status === 'success') {
                    await runAuditAndLoad();
                } else {
                    showError('Failed to generate simulation: ' + (data.message || data.detail || 'Error'));
                }
            } catch (err) {
                showError('Simulation error: ' + err.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg> Run 6-Month Performance Simulation`;
                }
            }
        };
    });


