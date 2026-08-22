document.addEventListener('DOMContentLoaded', () => {
    // Tangkap API key dari URL (?api_key=xxx), simpan ke localStorage,
    // lalu segera hapus dari address bar agar tidak tertinggal di browser history.
    const urlKey = new URLSearchParams(window.location.search).get('api_key');
    if (urlKey) {
        localStorage.setItem('api_key', urlKey);
        const params = new URLSearchParams(window.location.search);
        params.delete('api_key');
        const qs = params.toString();
        history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
    }

    // Fetch wrapper: lampirkan X-API-Key jika tersedia
    const apiFetch = (url, opts = {}) => {
        const key = localStorage.getItem('api_key');
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

    const rsiColor = r => r < 40 ? 'green' : r > 65 ? 'red' : 'amber';
    const rsiW     = r => Math.min(Math.max(r, 0), 100);

    // Initial load: render IHSG chart
    renderIHSGChart(1);
    runAuditAndLoad();

    // Progressive Scan Loader & Elapsed Timer
    let scanTimerInterval = null;
    let scanPhaseInterval = null;
    const scanPhases = [
        "Scanning 700+ IDX Tickers...",
        "Calculating 20+ Technical Indicators & MFI...",
        "Extracting Continuous Feature Embeddings...",
        "Evaluating Asymmetric News Sentiment & Catalysts...",
        "Running 5-Agent Consensus & Kelly Sizing...",
        "Finalizing Top High-Probability Recommendations..."
    ];

    function startScanLoader() {
        const timerEl = document.getElementById('loader-timer');
        const labelEl = document.getElementById('loader-shimmer-label');
        const startTime = Date.now();

        if (timerEl) timerEl.textContent = '0.0s';
        if (labelEl) labelEl.textContent = scanPhases[0];

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
        }, 1200);
    }

    function stopScanLoader() {
        clearInterval(scanTimerInterval);
        clearInterval(scanPhaseInterval);
    }

    scanBtn.addEventListener('click', async () => {
        // Disable button, show loader
        scanBtn.disabled = true;
        loader.classList.remove('hidden');
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
            if (lastScan) lastScan.textContent = 'Updated ' + new Date().toLocaleTimeString('en-US');
            loadTrackRecord();

            // Smooth scroll to results
            setTimeout(() => {
                results.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 80);

            // Render Charts after DOM updates
            setTimeout(() => {
                renderIHSGChart(1);
                renderAllMiniCharts(data.data);
            }, 150);

        } catch (err) {
            errorText.textContent = err.message;
            errorBox.classList.remove('hidden');
            emptyState.classList.remove('hidden');
        } finally {
            stopScanLoader();
            loader.classList.add('hidden');
            scanBtn.disabled = false;
        }
    });

    function buildTable(stocks) {
        stocks.forEach((s, i) => {
            const rc             = rsiColor(s.rsi);
            const rw             = rsiW(s.rsi);
            const macdClass      = s.macd_signal.toLowerCase();
            const trendClass     = s.trend.toLowerCase();
            const isBuy          = s.signal === 1;
            const sentStatus     = s.sentiment_status || 'NEUTRAL';
            const sentImpact     = s.sentiment_impact || 'NEUTRAL';
            const sentBadgeClass = sentStatus === 'POSITIF' ? 'booster' : (sentStatus === 'NEGATIF' ? 'veto' : 'neutral-sent');

            const tpPct = (s.close_price > 0 && s.target_price > 0)
                ? (((s.target_price - s.close_price) / s.close_price) * 100).toFixed(1)
                : '3.0';
            const slPct = (s.close_price > 0 && s.stop_loss > 0)
                ? (((s.stop_loss - s.close_price) / s.close_price) * 100).toFixed(1)
                : '-1.5';

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
                        <span class="score-val">${s.probability.toFixed(1)}%</span>
                    </div>
                </td>
                <td>
                    <span class="sig-pill ${isBuy ? 'buy' : 'watch'}">
                        <span class="sig-dot ${isBuy ? 'green' : 'blue'}"></span>
                        ${isBuy ? 'BUY' : 'WATCH'}
                    </span>
                </td>
            `;
            tableBody.appendChild(row);
        });
    }

    function buildCards(stocks) {
        stocks.forEach(s => {
            const rc             = rsiColor(s.rsi);
            const macdClass      = s.macd_signal.toLowerCase();
            const trendClass     = s.trend.toLowerCase();
            const rsiClass       = rc === 'green' ? 'bullish' : rc === 'red' ? 'bearish' : 'uptrend';
            const isBuy          = s.signal === 1;
            const sentStatus     = s.sentiment_status || 'NEUTRAL';
            const sentImpact     = s.sentiment_impact || 'NEUTRAL';
            const sentBadgeClass = sentStatus === 'POSITIF' ? 'booster' : (sentStatus === 'NEGATIF' ? 'veto' : 'neutral-sent');

            const tpPct = (s.close_price > 0 && s.target_price > 0)
                ? (((s.target_price - s.close_price) / s.close_price) * 100).toFixed(1)
                : '3.0';
            const slPct = (s.close_price > 0 && s.stop_loss > 0)
                ? (((s.stop_loss - s.close_price) / s.close_price) * 100).toFixed(1)
                : '-1.5';
            const card = document.createElement('div');
            card.className = 'detail-card';
            card.setAttribute('role', 'listitem');
            card.setAttribute('aria-label', `Stock ${s.ticker.replace('.JK','')} with Quant Score ${s.probability.toFixed(1)}%`);
            card.innerHTML = `
                <div class="dc-head">
                    <div>
                        <div class="dc-ticker">${s.ticker.replace('.JK', '')}</div>
                        <span class="dc-code">${s.ticker}</span>
                    </div>
                    <div>
                        <div class="dc-score">${s.probability.toFixed(1)}%</div>
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

                <div id="chart-${s.ticker.replace('.JK', '')}" class="mini-chart-container"></div>

                <div class="dc-quant-metrics">
                    ${s.sector ? `<span class="qm-tag"><span class="qm-lbl">Sektor:</span> <strong>${esc(s.sector)}</strong>${s.is_leading_sector ? ' <span class="qm-leading">· Leading</span>' : ''}</span>` : ''}
                    <span class="qm-tag"><span class="qm-lbl">Risk/Reward:</span> <strong>1:${esc(s.risk_reward_ratio || '2.0')}</strong></span>
                    <span class="qm-tag"><span class="qm-lbl">Saran Modal:</span> <strong style="color:var(--c-green);">${esc(s.kelly_allocation || '10')}%</strong></span>
                </div>

                <div class="dc-badges">
                    ${s.is_leading_sector ? '<span class="badge booster">Leading Sector</span>' : ''}
                    ${s.rvol ? `<span class="badge ${s.rvol >= 1.2 ? 'booster' : 'neutral-sent'}">RVOL ${esc(s.rvol)}x</span>` : ''}
                    ${s.adx ? `<span class="badge ${s.adx >= 25 ? 'bullish' : 'neutral-sent'}">ADX ${esc(s.adx)}</span>` : ''}
                    <span class="badge ${macdClass}">MACD ${esc(s.macd_signal)}</span>
                    <span class="badge ${trendClass}">${esc(s.trend)}</span>
                    <span class="badge ${rsiClass}">RSI ${esc(s.rsi)}</span>
                    <span class="badge ${sentBadgeClass}">${esc(sentImpact)}</span>
                    <span class="sig-pill sig-pill--sm ${isBuy ? 'buy' : 'watch'}">
                        <span class="sig-dot ${isBuy ? 'green' : 'blue'}"></span>
                        ${isBuy ? 'BUY' : 'WATCH'}
                    </span>
                    <button class="agent-toggle-btn" id="btn-ma-${s.ticker.replace('.JK', '')}">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                        Multi-Agent
                    </button>
                </div>

                <div id="ma-box-${s.ticker.replace('.JK', '')}" class="multi-agent-card hidden"></div>

                <div class="dc-reason">
                    <span class="dc-reason-lbl">Quantitative Analysis (Technicals &amp; News)</span>
                    <div id="narasi-${s.ticker.replace('.JK', '')}">
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
            const res = await apiFetch(`/api/chart/${ticker}?days=${days}`);
            const json = await res.json();
            if (res.ok && json.status === 'success') {
                return { data: json.data, intraday: json.intraday };
            }
        } catch (e) {
            console.error('Failed to fetch chart data for', ticker, e);
        }
        return { data: [], intraday: false };
    }

    async function renderIHSGChart(days = 60) {
        const ihsgChartDiv = document.getElementById('ihsg-chart');
        const ihsgPriceVal = document.getElementById('hero-ihsg-price');
        const ihsgDesc    = document.getElementById('ihsg-desc');
        ihsgChartDiv.innerHTML = '';
        ihsgPriceVal.textContent = '...';

        // Update tab active state
        document.querySelectorAll('.chart-tab').forEach(t => t.classList.remove('active'));
        document.getElementById(days === 1 ? 'tab-1d' : 'tab-60d').classList.add('active');
        ihsgDesc.textContent = days === 1
            ? "Today's price movement (5-min interval)"
            : 'Overall market trend over the past 60 days';

        if (typeof LightweightCharts === 'undefined') {
            ihsgPriceVal.textContent = 'Error: Library not loaded';
            return;
        }

        const { data, intraday } = await fetchChartData('IHSG', days);
        if (!data || data.length === 0) {
            ihsgPriceVal.textContent = 'Data unavailable';
            return;
        }

        const lastPrice  = data[data.length - 1].value;
        const firstPrice = data[0].value;
        const isUp = lastPrice >= firstPrice;
        ihsgPriceVal.textContent = new Intl.NumberFormat('id-ID', {style:'currency', currency:'IDR', minimumFractionDigits:0}).format(lastPrice);
        ihsgPriceVal.style.color = isUp ? 'var(--c-charcoal)' : 'var(--c-red)';

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

            window.addEventListener('resize', () => {
                if (ihsgChartDiv.clientWidth > 0) chart.resize(ihsgChartDiv.clientWidth, 200);
            });
        } catch (e) {
            ihsgChartDiv.innerHTML = '<p class="chart-msg chart-msg--err">Chart error: ' + (e.message || e) + '</p>';
            ihsgPriceVal.textContent = 'Error';
            console.error('IHSG Chart Error:', e);
        }
    }

    // Global function for onclick in HTML
    window.switchIhsgRange = function(days) {
        renderIHSGChart(days);
    };


    async function renderAllMiniCharts(stocks) {
        for (const s of stocks) {
            const cleanTicker = s.ticker.replace('.JK', '');
            const container = document.getElementById(`chart-${cleanTicker}`);
            if (!container) continue;

            const { data } = await fetchChartData(cleanTicker, 60);
            if (!data || data.length === 0) {
                container.innerHTML = '<span class="chart-msg chart-msg--sm chart-msg--muted">No chart data</span>';
                continue;
            }

            const isUp = s.trend.toLowerCase() === 'uptrend' || (data[data.length - 1].value >= data[0].value);
            const isBuy = s.signal === 1;

            // Cobalt/rose rules for BUY (index palette), soft gray for WATCH
            const lineColor = isBuy
                ? (isUp ? '#0051C3' : '#DE5052')
                : '#8C8C8C';
            const topColor = isBuy
                ? (isUp ? 'rgba(0, 81, 195, 0.1)' : 'rgba(222, 80, 82, 0.1)')
                : 'rgba(140, 140, 140, 0.1)';

            try {
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
            } catch (e) {
                container.innerHTML = '<span class="chart-msg chart-msg--sm chart-msg--err">Chart Error</span>';
                console.error(e);
            }
        }
    }

    async function fetchNarrative(s, card) {
        const cleanTicker = s.ticker.replace('.JK', '');
        const container = card.querySelector(`#narasi-${cleanTicker}`);
        if (!container) return;

        const fallbackText = `Saham ${cleanTicker} menunjukkan momentum positif dengan RSI ${s.rsi} (${s.rsi_signal}) dan indikator MACD ${s.macd_signal} pada tren ${s.trend}. Target profit ditetapkan pada ${fmtPrice(s.target_price)} dan Stop Loss pada ${fmtPrice(s.stop_loss)}.`;

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
                    container.innerHTML = data.narasi;
                    return;
                }
            }
        } catch (err) {
            console.warn('AI narrative unavailable, displaying quantitative summary:', err);
        }

        container.innerHTML = fallbackText;
    }

    function setupMultiAgentToggle(s, card) {
        const cleanTicker = s.ticker.replace('.JK', '');
        const btn = card.querySelector(`#btn-ma-${cleanTicker}`);
        const box = card.querySelector(`#ma-box-${cleanTicker}`);
        if (!btn || !box) return;

        let loaded = false;

        btn.addEventListener('click', async () => {
            if (box.classList.contains('hidden')) {
                box.classList.remove('hidden');
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
                                sentiment_status: s.sentiment_status || 'NEUTRAL',
                                sentiment_impact: s.sentiment_impact || 'NEUTRAL'
                            })
                        });
                        const json = await res.json();
                        if (res.ok && json.status === 'success' && json.data) {
                            const d = json.data;
                            const isBuyVerdict = (d.risk_verdict || '').includes('BELI') || (d.risk_verdict || '').includes('BUY');
                            const verdictBadgeClass = isBuyVerdict ? 'pill-verdict-buy' : 'pill-verdict-watch';
                            
                            box.innerHTML = `
                                <div class="ma-header">
                                    <div class="ma-title">Multi-Agent Framework Consensus</div>
                                    <span class="risk-pill ${verdictBadgeClass}">${d.risk_verdict}</span>
                                </div>
                                <div class="ma-subcard bull">
                                    <div class="ma-card-label label-bull">Bull Case (Buyer Analysis)</div>
                                    <div>${d.bull_case}</div>
                                </div>
                                <div class="ma-subcard bear">
                                    <div class="ma-card-label label-bear">Bear Case (Seller Caution)</div>
                                    <div>${d.bear_case}</div>
                                </div>
                                <div class="ma-subcard risk">
                                    <div class="ma-card-label label-risk">Risk Manager Verdict</div>
                                    <div class="ma-rr-row">
                                        <span>Target Risk/Reward Ratio:</span>
                                        <span class="risk-pill pill-rr">${d.risk_reward_ratio}x R:R</span>
                                    </div>
                                </div>
                            `;

                            loaded = true;
                        } else {
                            box.innerHTML = `<span class="ma-err">Failed to load agent consensus: ${json.detail || 'Error'}</span>`;
                        }
                    } catch (err) {
                        box.innerHTML = `<span class="ma-err">Error: ${err.message}</span>`;
                    }

                }
            } else {
                box.classList.add('hidden');
            }
        });
    }


        // Audit & Monthly Recap State
        let allMonthlyData = [];
        let isMonthlyExpanded = false;
        let allAuditData = [];
        let isAuditExpanded = false;

        async function runAuditAndLoad() {
            try {
                await apiFetch('/api/audit/run');
            } catch (e) {
                console.error('Failed to run audit:', e);
            }
            await loadTrackRecord();
            await loadAuditRecapAndChart();
        }

        async function loadTodayAudit() {
            const container = document.getElementById('today-audit-container');
            if (!container) return;

            try {
                const res = await apiFetch('/api/audit/today');
                const data = await res.json();

                if (res.ok && data.status === 'success' && data.signals?.length > 0) {
                    let signalsHtml = '';
                    data.signals.forEach((s, idx) => {
                        const tpPct = (s.entry_price > 0 && s.target_price > 0)
                            ? (((s.target_price - s.entry_price) / s.entry_price) * 100).toFixed(1)
                            : '3.0';
                        const slPct = (s.entry_price > 0 && s.stop_loss > 0)
                            ? (((s.stop_loss - s.entry_price) / s.entry_price) * 100).toFixed(1)
                            : '-1.5';
                        const retVal = s.status === 'LOSS' ? -1.5 : (s.return_pct != null ? s.return_pct : 0);
                        const retSign = retVal >= 0 ? '+' : '';
                        const badge = s.status === 'WIN' ? `<span class="badge bullish">WIN ${retSign}${retVal.toFixed(1)}%</span>` :
                                      (s.status === 'LOSS' ? `<span class="badge bearish">LOSS ${retVal.toFixed(1)}%</span>` : '<span class="badge netral">PENDING</span>');  
                        signalsHtml += `
                            <tr>
                                <td>${idx + 1}</td>
                                <td class="td-ticker-cell">${s.ticker}</td>
                                <td>${fmtPrice(s.entry_price)}</td>
                                <td class="td-win">${fmtPrice(s.target_price)} <span class="td-pct">(+${tpPct}%)</span></td>
                                <td class="td-loss">${fmtPrice(s.stop_loss)} <span class="td-pct">(${slPct}%)</span></td>
                                <td>${s.probability.toFixed(1)}%</td>
                                <td>${badge}</td>
                            </tr>
                        `;
                    });

                    const gainSign = data.total_gain >= 0 ? '+' : '';

                    container.innerHTML = `
                        <div class="glass-card today-card">
                            <div class="today-hd">
                                <div>
                                    <h4 class="today-title">
                                        Today's Trading Audit Results (${data.date})
                                    </h4>
                                    <p class="today-sub">
                                        Evaluation of trading signals executed on this market day
                                    </p>
                                </div>
                                <span class="chip ${data.total_gain >= 0 ? 'green' : 'red'} today-chip">
                                    Daily Gain: ${gainSign}${data.total_gain.toFixed(1)}%
                                </span>
                            </div>

                            <div class="today-meta">
                                <span>Signal Outcome: <strong class="win">${data.win_count} WIN</strong> / <strong class="loss">${data.loss_count} LOSS</strong> ${data.pending_count > 0 ? `/ <strong>${data.pending_count} PENDING</strong>` : ''}</span>
                                <span>Today's Win Rate: <strong>${data.win_rate.toFixed(1)}%</strong></span>
                            </div>

                            <div class="table-scroll" tabindex="0">
                                <table class="stock-table">
                                    <thead>
                                        <tr>
                                            <th>#</th>
                                            <th>Stock</th>
                                            <th>Entry Price</th>
                                            <th>Target Profit</th>
                                            <th>Stop Loss</th>
                                            <th>Quant Score</th>
                                            <th>Audit Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>${signalsHtml}</tbody>
                                </table>
                            </div>
                        </div>
                    `;
                } else {
                    container.innerHTML = '';
                }
            } catch (e) {
                console.error('Failed to load today audit:', e);
            }
        }

        window.switchMainTab = function(tabName) {
            const resultsDiv = document.getElementById('results');
            const auditSec = document.getElementById('audit-section');
            const btnRecom = document.getElementById('tab-btn-recom');
            const btnAudit = document.getElementById('tab-btn-audit');

            const setActive = (activeBtn, inactiveBtn) => {
                activeBtn.classList.add('is-active');
                inactiveBtn.classList.remove('is-active');
            };

            if (tabName === 'recom') {
                if (resultsDiv) resultsDiv.classList.remove('hidden');
                if (auditSec) auditSec.style.display = 'block';
                if (btnRecom && btnAudit) setActive(btnRecom, btnAudit);
                if (resultsDiv) resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } else if (tabName === 'audit') {
                if (resultsDiv) resultsDiv.classList.remove('hidden');
                if (auditSec) auditSec.style.display = 'block';
                if (btnRecom && btnAudit) setActive(btnAudit, btnRecom);
                if (auditSec) auditSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        };

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
            if (!body) return;

            if (allAuditData.length === 0) {
                if (toggleBtn) toggleBtn.classList.remove('shown');
                return;
            }

            const visibleRows = isAuditExpanded ? allAuditData : allAuditData.slice(0, 5);
            body.innerHTML = '';

            visibleRows.forEach(s => {
                const row = document.createElement('tr');
                const statusClass = s.status.toLowerCase();
                const tpPct = (s.entry_price > 0 && s.target_price > 0)
                    ? (((s.target_price - s.entry_price) / s.entry_price) * 100).toFixed(1)
                    : '3.0';
                const slPct = (s.entry_price > 0 && s.stop_loss > 0)
                    ? (((s.stop_loss - s.entry_price) / s.entry_price) * 100).toFixed(1)
                    : '-1.5';

                const retVal = s.status === 'LOSS' ? -1.5 : (s.return_pct != null ? s.return_pct : 0);
                const retSign = retVal >= 0 ? '+' : '';
                const badge = s.status === 'WIN' ? `<span class="badge bullish">WIN ${retSign}${retVal.toFixed(1)}% ✅</span>` :
                              (s.status === 'LOSS' ? `<span class="badge bearish">LOSS ${retVal.toFixed(1)}% ❌</span>` : `<span class="badge netral">PENDING ⏳</span>`);

                row.innerHTML = `
                    <td>${s.trading_date || (s.updated_at || s.created_at).split(' ')[0]}</td>
                    <td class="td-ticker-cell">${s.ticker}</td>
                    <td>${fmtPrice(s.entry_price)}</td>
                    <td class="td-win">${fmtPrice(s.target_price)} <span class="td-pct">(+${tpPct}%)</span></td>
                    <td class="td-loss">${fmtPrice(s.stop_loss)} <span class="td-pct">(${slPct}%)</span></td>
                    <td>${s.probability.toFixed(1)}%</td>
                    <td>${badge}</td>
                `;
                body.appendChild(row);
            });

            if (toggleBtn) {
                if (allAuditData.length > 5) {
                    toggleBtn.classList.add('shown');
                    toggleBtn.textContent = isAuditExpanded 
                        ? 'Hide ↑' 
                        : `View More (${allAuditData.length - 5} More Signals) ↓`;
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
                    winLossEl.textContent = `${s.win_count} WIN / ${s.loss_count} LOSS`;
                    profitEl.textContent = `${s.total_profit_pct >= 0 ? '+' : ''}${s.total_profit_pct.toFixed(1)}%`;
                    profitEl.classList.toggle('stat-val--neg', s.total_profit_pct < 0);

                    // Save monthly data & render table
                    allMonthlyData = data.monthly_breakdown || [];
                    renderMonthlyTable();

                    // Render Equity Curve Chart
                    if (chartDiv && typeof LightweightCharts !== 'undefined' && data.equity_curve?.length > 0) {
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

                            areaSeries.setData(data.equity_curve);
                            chart.timeScale().fitContent();

                            window.addEventListener('resize', () => {
                                if (chartDiv.clientWidth > 0) chart.resize(chartDiv.clientWidth, 220);
                            });
                        } catch (ce) {
                            console.error('Equity chart error:', ce);
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
                    <td>${m.total_signals} Signals</td>
                    <td class="td-win">${m.win_count} WIN</td>
                    <td class="td-loss">${m.loss_count} LOSS</td>
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
        };

        window.toggleAuditLog = function() {
            isAuditExpanded = !isAuditExpanded;
            renderAuditTable();
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
                    alert('Failed to generate simulation: ' + (data.message || 'Error'));
                }
            } catch (err) {
                alert('Simulation error: ' + err.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg> Run 6-Month Performance Simulation`;
                }
            }
        };
    });


