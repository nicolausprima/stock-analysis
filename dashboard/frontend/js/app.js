document.addEventListener('DOMContentLoaded', () => {
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
        : '<span style="color:#94a3b8;font-style:italic">—</span>';

    const rsiColor = r => r < 40 ? 'green' : r > 65 ? 'red' : 'amber';
    const rsiW     = r => Math.min(Math.max(r, 0), 100);

    // Initial load: render IHSG chart
    renderIHSGChart(1);
    runAuditAndLoad();

    scanBtn.addEventListener('click', async () => {
        // Disable button, show loader
        scanBtn.disabled = true;
        loader.classList.remove('hidden');
        errorBox.classList.add('hidden');
        results.classList.add('hidden');
        emptyState.classList.add('hidden');
        tableBody.innerHTML = '';
        cardsGrid.innerHTML = '';

        try {
            const res  = await fetch('/api/recommendations');
            const data = await res.json();

            if (!res.ok) throw new Error(data.detail || 'Server error');
            if (!data.data?.length) throw new Error(
                'Tidak ada sinyal beli ditemukan. Kondisi pasar sedang tidak kondusif saat ini.'
            );

            buildTable(data.data);
            buildCards(data.data);
            results.classList.remove('hidden');
            if (lastScan) lastScan.textContent = 'Updated ' + new Date().toLocaleTimeString('id-ID');
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
            const sentStatus     = s.sentiment_status || 'NETRAL';
            const sentImpact     = s.sentiment_impact || 'NETRAL';
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
                    <div class="t-name">${s.ticker.replace('.JK', '')}</div>
                    <div class="t-code">${s.ticker}</div>
                </td>
                <td class="td-price">${fmtPrice(s.close_price)}</td>
                <td class="td-target">
                    <span style="font-weight:600; color:var(--c-green);">${fmtPrice(s.target_price)}</span>
                    <span style="font-size:11px; font-weight:600; color:var(--c-green); margin-left:2px;">(+${tpPct}%)</span>
                </td>
                <td class="td-sl">
                    <span style="font-weight:600; color:var(--c-red);">${fmtPrice(s.stop_loss)}</span>
                    <span style="font-size:11px; font-weight:600; color:var(--c-red); margin-left:2px;">(${slPct}%)</span>
                </td>
                <td>
                    <div class="rsi-cell">
                        <span class="rsi-val">${s.rsi}</span>
                        <div class="rsi-track">
                            <div class="rsi-fill ${rc}" style="width:${rw}%"></div>
                        </div>
                        <span class="rsi-sig">${s.rsi_signal}</span>
                    </div>
                </td>
                <td><span class="badge ${macdClass}">${s.macd_signal}</span></td>
                <td><span class="badge ${trendClass}">${s.trend}</span></td>
                <td><span class="badge ${sentBadgeClass}">${sentImpact}</span></td>
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
            const sentStatus     = s.sentiment_status || 'NETRAL';
            const sentImpact     = s.sentiment_impact || 'NETRAL';
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
            card.setAttribute('aria-label', `Saham ${s.ticker.replace('.JK','')} dengan AI Score ${s.probability.toFixed(1)}%`);
            card.innerHTML = `
                <div class="dc-head">
                    <div>
                        <div class="dc-ticker">${s.ticker.replace('.JK', '')}</div>
                        <span class="dc-code">${s.ticker}</span>
                    </div>
                    <div>
                        <div class="dc-score">${s.probability.toFixed(1)}%</div>
                        <div class="dc-score-lbl">AI Score</div>
                    </div>
                </div>

                <div class="dc-prices">
                    <div class="dc-price-col">
                        <div class="dc-plbl">Harga</div>
                        <div class="dc-pval primary">${s.close_price > 0 ? idr(s.close_price) : '—'}</div>
                    </div>
                    <div class="dc-price-col">
                        <div class="dc-plbl">Target Profit</div>
                        <div class="dc-pval green">${s.target_price > 0 ? idr(s.target_price) : '—'} <span style="font-size:11px; font-weight:600;">(+${tpPct}%)</span></div>
                    </div>
                    <div class="dc-price-col">
                        <div class="dc-plbl">Stop Loss</div>
                        <div class="dc-pval red">${s.stop_loss > 0 ? idr(s.stop_loss) : '—'} <span style="font-size:11px; font-weight:600;">(${slPct}%)</span></div>
                    </div>
                </div>

                <div id="chart-${s.ticker.replace('.JK', '')}" class="mini-chart-container"></div>

                <div class="dc-badges">
                    <span class="badge ${macdClass}">MACD ${s.macd_signal}</span>
                    <span class="badge ${trendClass}">${s.trend}</span>
                    <span class="badge ${rsiClass}">RSI ${s.rsi}</span>
                    <span class="badge ${sentBadgeClass}">${sentImpact}</span>
                    <span class="sig-pill ${isBuy ? 'buy' : 'watch'}" style="font-size:10px;padding:2px 8px">
                        <span class="sig-dot ${isBuy ? 'green' : 'blue'}"></span>
                        ${isBuy ? 'BUY' : 'WATCH'}
                    </span>
                </div>

                <div class="dc-reason">
                    <span class="dc-reason-lbl">Analisis AI Terpadu (Teknikal & Berita)</span>
                    <div id="narasi-${s.ticker.replace('.JK', '')}">
                        <div class="ai-loading">Menganalisis teknikal & sentimen dengan AI...</div>
                    </div>
                </div>
            `;

            cardsGrid.appendChild(card);
            fetchNarrative(s, card);
        });
    }

    // Charting Logic
    async function fetchChartData(ticker, days = 60) {
        try {
            const res = await fetch(`/api/chart/${ticker}?days=${days}`);
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
            ? 'Pergerakan harga hari ini (interval 5 menit)'
            : 'Tren pasar keseluruhan selama 60 hari terakhir';

        if (typeof LightweightCharts === 'undefined') {
            ihsgPriceVal.textContent = 'Error: Library tidak termuat';
            return;
        }

        const { data, intraday } = await fetchChartData('IHSG', days);
        if (!data || data.length === 0) {
            ihsgPriceVal.textContent = 'Data tidak tersedia';
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
                    textColor: '#1C1C1C',
                    fontFamily: 'Epilogue, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
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
                lineColor: isUp ? '#1C1C1C' : '#B85C66',
                topColor: isUp ? 'rgba(28, 28, 28, 0.15)' : 'rgba(184, 92, 102, 0.15)',
                bottomColor: 'rgba(0,0,0,0)',
                lineWidth: 2,
            });

            areaSeries.setData(data);
            chart.timeScale().fitContent();

            window.addEventListener('resize', () => {
                if (ihsgChartDiv.clientWidth > 0) chart.resize(ihsgChartDiv.clientWidth, 200);
            });
        } catch (e) {
            ihsgChartDiv.innerHTML = '<p style="color:var(--c-red);font-size:12px;padding:8px">Chart error: ' + (e.message || e) + '</p>';
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
                container.innerHTML = '<span style="font-size:10px;color:var(--c-muted)">No chart data</span>';
                continue;
            }

            const isUp = s.trend.toLowerCase() === 'uptrend' || (data[data.length - 1].value >= data[0].value);
            const isBuy = s.signal === 1;

            // Soft B&W rules for BUY (charcoal/rose), soft dark gray for WATCH
            const lineColor = isBuy 
                ? (isUp ? '#1C1C1C' : '#B85C66') 
                : '#4A4A4A';
            const topColor = isBuy 
                ? (isUp ? 'rgba(28, 28, 28, 0.1)' : 'rgba(184, 92, 102, 0.1)') 
                : 'rgba(74, 74, 74, 0.1)';

            try {
                const chart = LightweightCharts.createChart(container, {
                    width: container.clientWidth || 240,
                    height: 80,
                    layout: { 
                        background: { type: 'solid', color: 'transparent' },
                        fontFamily: 'Epilogue, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
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
                container.innerHTML = '<span style="font-size:10px;color:var(--c-red)">Chart Error</span>';
                console.error(e);
            }
        }
    }

    async function fetchNarrative(s, card) {
        const cleanTicker = s.ticker.replace('.JK', '');
        const container = card.querySelector(`#narasi-${cleanTicker}`);
        if (!container) return;

        try {
            const res = await fetch('/api/narasi', {
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
            const data = await res.json();
            if (res.ok && data.status === 'success') {
                container.innerHTML = data.narasi;
            } else {
                container.innerHTML = `<span style="color:var(--c-red);font-size:13px">Gagal memuat narasi: ${data.detail || 'Error'}</span>`;
            }
        } catch (err) {
            container.innerHTML = `<span style="color:var(--c-red);font-size:13px">Gagal memuat narasi: ${err.message}</span>`;
        }
    }

        // Audit & Monthly Recap State
        let allMonthlyData = [];
        let isMonthlyExpanded = false;
        let allAuditData = [];
        let isAuditExpanded = false;

        async function runAuditAndLoad() {
            try {
                await fetch('/api/audit/run');
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
                const res = await fetch('/api/audit/today');
                const data = await res.json();

                if (res.ok && data.status === 'success' && data.signals?.length > 0) {
                    let signalsHtml = '';
                    data.signals.forEach((s, idx) => {
                        const badge = s.status === 'WIN' ? '<span class="badge bullish">WIN ✅</span>' :
                                      (s.status === 'LOSS' ? '<span class="badge bearish">LOSS ❌</span>' : '<span class="badge netral">PENDING ⏳</span>');
                        signalsHtml += `
                            <tr>
                                <td>${idx + 1}</td>
                                <td style="font-family: var(--font-accent); font-weight:600; font-size: 16px;">${s.ticker}</td>
                                <td>${fmtPrice(s.entry_price)}</td>
                                <td style="color: var(--c-charcoal);">${fmtPrice(s.target_price)}</td>
                                <td style="color: var(--c-red);">${fmtPrice(s.stop_loss)}</td>
                                <td>${s.probability.toFixed(1)}%</td>
                                <td>${badge}</td>
                            </tr>
                        `;
                    });

                    const gainSign = data.total_gain >= 0 ? '+' : '';

                    container.innerHTML = `
                        <div class="glass-card" style="padding: 20px; border-radius: 12px; margin-bottom: 16px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
                                <div>
                                    <h4 style="font-family: var(--font-accent); font-size: 18px; font-weight: 700; color: var(--c-charcoal); margin:0;">
                                        🔥 Hasil Audit Trading Hari Ini (${data.date})
                                    </h4>
                                    <p style="font-size: 13px; color: var(--c-soft-gray); margin: 4px 0 0 0;">
                                        Evaluasi sinyal perdagangan yang berjalan pada hari bursa ini
                                    </p>
                                </div>
                                <span class="chip ${data.total_gain >= 0 ? 'green' : 'red'}" style="font-size: 14px; font-weight: 700;">
                                    Gain Harian: ${gainSign}${data.total_gain.toFixed(1)}%
                                </span>
                            </div>

                            <div style="display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 16px; font-size: 13px; font-weight: 500;">
                                <span>Hasil Sinyal: <strong style="color: var(--c-green);">${data.win_count} WIN</strong> / <strong style="color: var(--c-red);">${data.loss_count} LOSS</strong> ${data.pending_count > 0 ? `/ <strong>${data.pending_count} PENDING</strong>` : ''}</span>
                                <span>Win Rate Hari Ini: <strong>${data.win_rate.toFixed(1)}%</strong></span>
                            </div>

                            <div class="table-scroll" tabindex="0">
                                <table class="stock-table">
                                    <thead>
                                        <tr>
                                            <th>#</th>
                                            <th>Saham</th>
                                            <th>Harga Entry</th>
                                            <th>Target (+3.0%)</th>
                                            <th>Stop Loss (-1.5%)</th>
                                            <th>AI Score</th>
                                            <th>Status Audit</th>
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

            if (tabName === 'recom') {
                if (resultsDiv) resultsDiv.classList.remove('hidden');
                if (auditSec) auditSec.style.display = 'block';
                if (btnRecom) {
                    btnRecom.style.background = 'var(--c-charcoal)';
                    btnRecom.style.color = '#FFF';
                }
                if (btnAudit) {
                    btnAudit.style.background = 'rgba(0,0,0,0.05)';
                    btnAudit.style.color = 'var(--c-charcoal)';
                }
                if (resultsDiv) resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } else if (tabName === 'audit') {
                if (resultsDiv) resultsDiv.classList.remove('hidden');
                if (auditSec) auditSec.style.display = 'block';
                if (btnAudit) {
                    btnAudit.style.background = 'var(--c-charcoal)';
                    btnAudit.style.color = '#FFF';
                }
                if (btnRecom) {
                    btnRecom.style.background = 'rgba(0,0,0,0.05)';
                    btnRecom.style.color = 'var(--c-charcoal)';
                }
                if (auditSec) auditSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        };

        async function loadTrackRecord() {
            const body = document.getElementById('audit-table-body');
            if (!body) return;

            try {
                const res = await fetch('/api/audit/track-record');
                const data = await res.json();

                if (res.ok && data.status === 'success' && data.data?.length > 0) {
                    allAuditData = data.data;
                    renderAuditTable();
                } else {
                    allAuditData = [];
                    body.innerHTML = `
                        <tr>
                            <td colspan="7" style="text-align: center; padding: 24px; color: var(--c-soft-gray); font-size: 14px;">
                                Belum ada riwayat sinyal di database. Klik <strong>Simulasi Performance 6 Bulan</strong> untuk uji coba.
                            </td>
                        </tr>
                    `;
                }
            } catch (err) {
                body.innerHTML = `
                    <tr>
                        <td colspan="7" style="text-align: center; padding: 24px; color: var(--c-red); font-size: 14px;">
                            Gagal memuat track record: ${err.message}
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
                if (toggleBtn) toggleBtn.style.display = 'none';
                return;
            }

            const visibleRows = isAuditExpanded ? allAuditData : allAuditData.slice(0, 5);
            body.innerHTML = '';

            visibleRows.forEach(s => {
                const row = document.createElement('tr');
                const statusClass = s.status.toLowerCase();
                row.innerHTML = `
                    <td>${(s.updated_at || s.created_at).split(' ')[0]}</td>
                    <td style="font-family: var(--font-accent); font-weight:600; font-size: 16px;">${s.ticker}</td>
                    <td>${fmtPrice(s.entry_price)}</td>
                    <td style="color: var(--c-charcoal)">${fmtPrice(s.target_price)}</td>
                    <td style="color: var(--c-red)">${fmtPrice(s.stop_loss)}</td>
                    <td>${s.probability.toFixed(1)}%</td>
                    <td><span class="badge ${statusClass}">${s.status}</span></td>
                `;
                body.appendChild(row);
            });

            if (toggleBtn) {
                if (allAuditData.length > 5) {
                    toggleBtn.style.display = 'inline-block';
                    toggleBtn.textContent = isAuditExpanded 
                        ? 'Sembunyikan ↑' 
                        : `Lihat Selengkapnya (${allAuditData.length - 5} Sinyal Lagi) ↓`;
                } else {
                    toggleBtn.style.display = 'none';
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
                const res = await fetch('/api/audit/recap');
                const data = await res.json();

                if (res.ok && data.status === 'success') {
                    const s = data.summary;
                    winRateEl.textContent = s.win_rate > 0 ? `${s.win_rate.toFixed(1)}%` : '0.0%';
                    winLossEl.textContent = `${s.win_count} WIN / ${s.loss_count} LOSS`;
                    profitEl.textContent = `${s.total_profit_pct >= 0 ? '+' : ''}${s.total_profit_pct.toFixed(1)}%`;
                    profitEl.style.color = s.total_profit_pct >= 0 ? 'var(--c-green)' : 'var(--c-red)';

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
                                    textColor: '#1C1C1C',
                                    fontFamily: 'Epilogue, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
                                },
                                grid: { vertLines: { visible: false }, horzLines: { color: 'rgba(0, 0, 0, 0.05)' } },
                                rightPriceScale: { borderVisible: false },
                                timeScale: { borderVisible: false, secondsVisible: false },
                                crosshair: { mode: 0 },
                                handleScroll: false,
                                handleScale: false
                            });

                            const areaSeries = chart.addAreaSeries({
                                lineColor: '#10B981',
                                topColor: 'rgba(16, 185, 129, 0.25)',
                                bottomColor: 'rgba(16, 185, 129, 0.0)',
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
                        <td colspan="6" style="text-align: center; padding: 20px; color: var(--c-soft-gray);">
                            Belum ada data rekapitulasi bulanan.
                        </td>
                    </tr>
                `;
                if (toggleBtn) toggleBtn.style.display = 'none';
                return;
            }

            const visibleRows = isMonthlyExpanded ? allMonthlyData : allMonthlyData.slice(0, 3);
            monthlyBody.innerHTML = '';

            visibleRows.forEach(m => {
                const row = document.createElement('tr');
                const isPos = m.monthly_profit_pct >= 0;
                row.innerHTML = `
                    <td style="font-family: var(--font-accent); font-weight:600;">${m.month_name}</td>
                    <td>${m.total_signals} Sinyal</td>
                    <td style="color: var(--c-green); font-weight:600;">${m.win_count} WIN</td>
                    <td style="color: var(--c-red); font-weight:600;">${m.loss_count} LOSS</td>
                    <td><span class="badge ${m.win_rate >= 60 ? 'uptrend' : 'bearish'}">${m.win_rate.toFixed(1)}%</span></td>
                    <td style="font-weight:700; color: ${isPos ? 'var(--c-green)' : 'var(--c-red)'}">${isPos ? '+' : ''}${m.monthly_profit_pct.toFixed(1)}%</td>
                `;
                monthlyBody.appendChild(row);
            });

            if (toggleBtn) {
                if (allMonthlyData.length > 3) {
                    toggleBtn.style.display = 'inline-block';
                    toggleBtn.textContent = isMonthlyExpanded 
                        ? 'Sembunyikan ↑' 
                        : `Lihat Selengkapnya (${allMonthlyData.length - 3} Bulan Lagi) ↓`;
                } else {
                    toggleBtn.style.display = 'none';
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
                btn.textContent = 'Menghasilkan simulasi...';
            }

            try {
                const res = await fetch('/api/audit/seed-simulation');
                const data = await res.json();
                if (res.ok && data.status === 'success') {
                    await runAuditAndLoad();
                } else {
                    alert('Gagal menghasilkan simulasi: ' + (data.message || 'Error'));
                }
            } catch (err) {
                alert('Error simulasi: ' + err.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg> Simulasi Performance 6 Bulan`;
                }
            }
        };
    });


