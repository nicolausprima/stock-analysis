#!/usr/bin/env python
"""
IDX Quant AI - Interactive Terminal & Quant Shell (CLI)
Memberikan antarmuka terminal interaktif untuk analisis saham kuantitatif,
rekomendasi harian, multi-agent intelligence, manajemen risiko Kelly Criterion,
dan audit track record rekam jejak sinyal.

Penggunaan:
    1. Mode Interaktif (Shell):
       python main_cli.py

    2. Mode Langsung (Direct Command):
       python main_cli.py /scan
       python main_cli.py /analyze BBCA
       python main_cli.py /macro
       python main_cli.py /audit
       python main_cli.py /sizing BBRI 50000000
       python main_cli.py /chart ASII
"""

import sys
import os
import re
import difflib
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
import yfinance as yf
import contextlib
import io

# Setup path agar dapat mengimpor seluruh modul di proyek
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Safe Windows UTF-8 stdout configuration
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.prompt import Prompt

console = Console()

def _usage(cmd: str, example: str) -> None:
    """Menampilkan pesan format penggunaan yang konsisten untuk semua command."""
    console.print(f"[bold red]Gunakan format: /{cmd} {example}[/bold red]")

def _clean_text(text: str) -> str:
    """Membersihkan emoji / karakter non-ASCII bermasalah untuk kompatibilitas terminal Windows."""
    if not isinstance(text, str):
        return str(text)
    text = text.replace("🟡", "[CAUTION]").replace("🟢", "[OK]").replace("🔴", "[BLOCK]")
    text = text.replace("⚡", "[HOT]").replace("⚠️", "[!]").replace("✅", "[+]").replace("➖", "[-]")
    text = text.replace("🚀", "[>]").replace("🎯", "[*]").replace("👋", "")
    return text

def get_wib_now() -> datetime:
    """Mengembalikan datetime saat ini dalam WIB (UTC+7)."""
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=7)))


# =====================================================================
# 1. HELPER & DATA FETCHERS
# =====================================================================

def fetch_stock_data(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """Mengambil riwayat data saham dari database lokal atau Yahoo Finance."""
    clean_ticker = ticker.upper().replace(".JK", "").strip()
    yf_ticker = f"{clean_ticker}.JK"
    
    # 1. Coba dari local market_db
    try:
        from src.database.market_db import get_ticker_history_from_db
        df = get_ticker_history_from_db(yf_ticker, limit_days=120)
        if df.empty:
            df = get_ticker_history_from_db(clean_ticker, limit_days=120)
        if not df.empty and len(df) >= 30:
            return df
    except Exception:
        pass

    # 2. Download via Yahoo Finance jika tidak ada di local DB
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            df_yf = yf.download(yf_ticker, period=period, interval="1d", progress=False)
            if not df_yf.empty:
                if isinstance(df_yf.columns, pd.MultiIndex):
                    df_yf.columns = df_yf.columns.get_level_values(0)
                df_yf = df_yf.dropna().copy()
                df_yf.index = pd.to_datetime(df_yf.index)
                return df_yf
    except Exception:
        pass

    return pd.DataFrame()


def calculate_indicators(df: pd.DataFrame) -> dict:
    """Menghitung indikator teknikal lengkap (RSI, MACD, SMA, ATR, RVOL, ADX)."""
    if df.empty or len(df) < 20:
        return {}

    df = df.copy()
    close = df['Close']
    high = df['High'] if 'High' in df.columns else close
    low = df['Low'] if 'Low' in df.columns else close
    volume = df['Volume'] if 'Volume' in df.columns else pd.Series(1.0, index=df.index)

    # RSI 14
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    rsi_series = 100 - (100 / (1 + rs))
    rsi = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else 50.0

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_val = float(macd_line.iloc[-1]) if pd.notna(macd_line.iloc[-1]) else 0.0
    sig_val = float(signal_line.iloc[-1]) if pd.notna(signal_line.iloc[-1]) else 0.0
    macd_signal = "BULLISH" if macd_val >= sig_val else "BEARISH"

    # SMA
    sma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else float(close.iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else sma20
    curr_price = float(close.iloc[-1])
    trend = "UPTREND" if curr_price >= sma20 * 0.99 else "DOWNTREND / KONSOLIDASI"

    # ATR 14
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_val = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 else curr_price * 0.02
    if pd.isna(atr_val) or atr_val <= 0:
        atr_val = curr_price * 0.02

    # RVOL & Volume
    vol_sma20 = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else float(volume.iloc[-1])
    curr_vol = float(volume.iloc[-1])
    rvol = round(curr_vol / (vol_sma20 + 1e-9), 2) if vol_sma20 > 0 else 1.0

    # ADX 14
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr_smooth = tr.rolling(14).sum()
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(14).sum() / (tr_smooth + 1e-9))
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(14).sum() / (tr_smooth + 1e-9))
    dx = 100 * ((plus_di - minus_di).abs() / ((plus_di + minus_di) + 1e-9))
    adx_series = dx.rolling(14).mean()
    adx_val = float(adx_series.iloc[-1]) if len(adx_series) >= 14 and pd.notna(adx_series.iloc[-1]) else 25.0

    # Dynamic TP / SL (1.5x - 2.0x ATR)
    dyn_tp = round(curr_price + max(atr_val * 1.8, curr_price * 0.03))
    dyn_sl = round(curr_price - max(atr_val * 1.2, curr_price * 0.015))
    reward = dyn_tp - curr_price
    risk = max(1.0, curr_price - dyn_sl)
    rr_ratio = round(reward / risk, 2)

    # Half-Kelly Calculation
    base_prob = 65.0
    if trend == "UPTREND":
        base_prob += 5.0
    if 40.0 <= rsi <= 60.0:
        base_prob += 4.0
    if macd_signal == "BULLISH":
        base_prob += 4.0
    if rvol >= 1.2:
        base_prob += 3.0
    if adx_val >= 25.0:
        base_prob += 2.0
    prob_pct = min(88.0, max(55.0, base_prob))
    
    p = prob_pct / 100.0
    q = 1.0 - p
    b = rr_ratio if rr_ratio > 0 else 1.5
    raw_kelly = (p * b - q) / b
    half_kelly_pct = round(max(0.0, min(25.0, (raw_kelly / 2.0) * 100.0)), 1)

    return {
        "price": curr_price,
        "rsi": round(rsi, 1),
        "macd_signal": macd_signal,
        "trend": trend,
        "sma20": round(sma20),
        "sma50": round(sma50),
        "atr": round(atr_val),
        "rvol": rvol,
        "adx": round(adx_val, 1),
        "target_price": dyn_tp,
        "stop_loss": dyn_sl,
        "risk_reward_ratio": rr_ratio,
        "probability": prob_pct,
        "kelly_allocation": half_kelly_pct,
        "history": close.tail(30).tolist()
    }


def render_ascii_chart(prices: list, height: int = 7, width: int = 42) -> str:
    """Membuat grafik tren harga terminal berbasis ASCII / Box."""
    if not prices or len(prices) < 2:
        return "Data harga tidak cukup untuk grafik."
    
    if len(prices) > width:
        step = len(prices) / width
        sampled = [prices[int(i * step)] for i in range(width)]
    else:
        sampled = prices

    min_p, max_p = min(sampled), max(sampled)
    rng = max_p - min_p if max_p > min_p else 1.0

    grid = [[" " for _ in range(len(sampled))] for _ in range(height)]
    for col, p in enumerate(sampled):
        row = int((p - min_p) / rng * (height - 1))
        row = max(0, min(height - 1, row))
        grid[height - 1 - row][col] = "*" if col == len(sampled) - 1 else "-"

    is_up = sampled[-1] >= sampled[0]
    marker = "▲" if is_up else "▼"
    line_color = "green" if is_up else "red"
    pct = ((sampled[-1] - sampled[0]) / sampled[0] * 100) if sampled[0] else 0.0

    lines = []
    for r in range(height):
        val = max_p - (r / (height - 1)) * rng
        row_str = "".join(grid[r])
        if row_str and row_str[-1] == "*":
            body = row_str[:-1]
            last_c = f"[bold {line_color}]{marker}[/bold {line_color}]"
        else:
            body = row_str[:-1]
            last_c = row_str[-1]
        lines.append(f"{val:8.0f} | {body}{last_c}")
    lines.append(" " * 8 + " +-" + "-" * len(sampled))
    lines.append(f"{'':>8}  [{line_color}]{marker} {pct:+.1f}%[/{line_color}]  |  High {max_p:,.0f} / Low {min_p:,.0f}")
    return "\n".join(lines)


# =====================================================================
# 2. COMMAND HANDLERS
# =====================================================================

def cmd_help():
    """Menampilkan panduan perintah yang tersedia."""
    table = Table(title="[bold]DAFTAR PERINTAH / SLASH COMMANDS[/bold]", show_header=True, header_style="bold")
    table.add_column("Perintah", style="bold", width=22)
    table.add_column("Fungsi & Deskripsi", style="white", overflow="fold")
    table.add_column("Contoh", style="yellow")

    table.add_row("/scan, /top", "Scan seluruh bursa BEI & tampilkan Top 10 sinyal rekomendasi hari ini", "/scan")
    table.add_row("/analyze <TICKER>", "Deep-dive analisa multi-agent lengkap (Teknikal, Makro, Sentimen, Kelly)", "/analyze BBCA")
    table.add_row("/macro", "Cek rezim pasar IHSG, kurs USD/IDR, bursa Asia & rotasi 11 sektor", "/macro")
    table.add_row("/audit", "Lihat rekapitulasi performa sinyal & Win Rate historis sistem", "/audit")
    table.add_row("/sizing <TKR> [MODAL]", "Hitung alokasi lot & money management optimal (Half-Kelly)", "/sizing BBRI 50jt")
    table.add_row("/chart <TICKER>", "Tampilkan grafik tren harga mini (ASCII chart) di terminal", "/chart ASII")
    table.add_row("/clear", "Bersihkan layar terminal", "/clear")
    table.add_row("/exit, /quit", "Keluar dari terminal shell interaktif", "/exit")

    console.print(table)
    console.print("[dim]Tip: Anda bisa mengetik perintah dengan atau tanpa awalan '/' (misal: 'scan' atau '/scan')[/dim]\n")


def cmd_scan():
    """Menjalankan scan rekomendasi Top 10."""
    with console.status("[bold green]Memindai saham bursa BEI & mengevaluasi probabilitas quant...[/bold green]"):
        try:
            from dashboard.backend.routes.predict import _read_cache, _run_fresh_scan
            res = _read_cache()
            if res is None or len(res.get("data", [])) < 5:
                res = _run_fresh_scan()
            data = res.get("data", [])
        except Exception as e:
            console.print(f"[bold red]Error saat memindai rekomendasi: {e}[/bold red]")
            return

    if not data:
        console.print("[yellow]Tidak ada rekomendasi yang ditemukan saat ini.[/yellow]")
        return

    table = Table(title=f"[bold]TOP REKOMENDASI SAHAM KUANTITATIF (WIB {get_wib_now().strftime('%Y-%m-%d %H:%M')})[/bold]", show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("No", justify="right", style="dim", width=3)
    table.add_column("Saham", style="bold", width=10)
    table.add_column("Harga", justify="right", style="white", width=9)
    table.add_column("TP", justify="right", style="green", width=9)
    table.add_column("SL", justify="right", style="red", width=9)
    table.add_column("Prob", justify="right", style="bold yellow", width=6)
    table.add_column("Sinyal Utama", style="dim", overflow="fold", ratio=1)

    for i, item in enumerate(data[:10], start=1):
        tkr = item.get("ticker", "").replace(".JK", "")
        sec = item.get("sector", "Umum")
        lead = " [bold green][HOT][/bold green]" if item.get("is_leading_sector") else ""
        price = f"Rp {item.get('close_price', 0):,.0f}"
        tp = f"Rp {item.get('target_price', 0):,.0f}"
        sl = f"Rp {item.get('stop_loss', 0):,.0f}"
        prob = f"{item.get('probability', 0):.1f}%"
        reason = item.get("reason", "Technical Setup")

        table.add_row(str(i), f"{tkr}\n[dim]{sec}{lead}[/dim]", price, tp, sl, prob, reason)

    console.print(table)
    console.print("[dim][HOT] = Sektor leading dalam momentum inflow modal saat ini[/dim]")
    console.print("[dim]Tip: ketik [bold yellow]/analyze <TICKER>[/bold yellow] untuk deep-dive multi-agent.[/dim]\n")


def cmd_analyze(ticker: str):
    """Deep-dive analisis saham tertentu."""
    if not ticker:
        _usage("analyze", "<TICKER> (contoh: /analyze BBCA)")
        return

    clean_ticker = ticker.upper().replace(".JK", "").strip()
    with console.status(f"[bold green]Menganalisis {clean_ticker} dengan Multi-Agent System...[/bold green]"):
        df = fetch_stock_data(clean_ticker)
        if df.empty:
            console.print(f"[bold red]Gagal mengambil data untuk ticker {clean_ticker}. Pastikan kode saham benar.[/bold red]")
            return

        ind = calculate_indicators(df)
        if not ind:
            console.print(f"[bold red]Data harga {clean_ticker} tidak mencukupi untuk kalkulasi teknikal.[/bold red]")
            return

        # Sektor & Makro
        from src.agents.ihsg_macro_agent import IHSGMacroAgent, get_ticker_sector
        sector = get_ticker_sector(clean_ticker)
        
        macro_agent = IHSGMacroAgent()
        macro_res = macro_agent.evaluate(skip_news=True, skip_sectors=False)
        leading_sectors = macro_res.get("sector_rotation", {}).get("leading_sectors", [])
        is_leading = sector in leading_sectors

        # Multi-Agent Reasoning
        from src.agents.multi_agent_system import TechnicalAnalystAgent, SentimentAnalystAgent, MacroContextAgent
        
        tech_agent = TechnicalAnalystAgent()
        tech_reason = tech_agent.analyze({
            "rsi": ind["rsi"],
            "macd_signal": ind["macd_signal"],
            "trend": ind["trend"],
            "target_price": ind["target_price"],
            "close_price": ind["price"]
        })

        macro_ctx_agent = MacroContextAgent()
        macro_reason = macro_ctx_agent.analyze(macro_res, ticker=clean_ticker)

        sent_agent = SentimentAnalystAgent()
        sent_reason = sent_agent.analyze({"sentiment_status": "POSITIF" if ind["probability"] >= 75 else "NETRAL", "sentiment_impact": "BOOSTER"})

    # Action Rating
    prob = ind["probability"]
    if prob >= 80.0:
        action_text = "[bold white on dark_green] STRONG BUY / HIGH CONVICTION [/bold white on dark_green]"
    elif prob >= 70.0:
        action_text = "[bold white on green] BUY / ACCUMULATE [/bold white on green]"
    elif prob >= 60.0:
        action_text = "[bold black on yellow] HOLD / WAIT & SEE [/bold black on yellow]"
    else:
        action_text = "[bold white on red] DEFENSIVE / AVOID [/bold white on red]"

    # Tampilkan Ringkasan Panel
    summary_text = Text()
    summary_text.append(f"Ticker: {clean_ticker}  |  Sektor: {sector}", style="bold cyan")
    if is_leading:
        summary_text.append(" [HOT Leading Inflow]", style="bold green")
    summary_text.append(f"\nHarga Terakhir: Rp {ind['price']:,.0f}  |  Rekomendasi: ", style="white")

    console.print(Panel(summary_text, title=f"[bold]ANALISIS SAHAM: {clean_ticker}[/bold]", subtitle=action_text, expand=False))

    # Tabel Metrik Teknikal & Trade Plan
    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column()
    grid.add_column()

    t_tech = Table(title="[bold cyan]1. Indikator Teknikal & Momentum[/bold cyan]", show_header=False)
    t_tech.add_column("Metrik", style="white")
    t_tech.add_column("Nilai", style="bold yellow")
    t_tech.add_row("RSI (14)", f"{ind['rsi']} ({'Oversold' if ind['rsi'] < 35 else 'Overbought' if ind['rsi'] > 70 else 'Ideal'})")
    t_tech.add_row("MACD Signal", ind['macd_signal'])
    t_tech.add_row("Tren Harga", ind['trend'])
    t_tech.add_row("RVOL (Rel. Vol)", f"{ind['rvol']}x")
    t_tech.add_row("ADX (14 Trend)", f"{ind['adx']} ({'Kuat' if ind['adx'] >= 25 else 'Lemah'})")
    t_tech.add_row("SMA 20 / SMA 50", f"Rp {ind['sma20']:,} / Rp {ind['sma50']:,}")

    t_plan = Table(title="[bold green]2. Rencana Eksekusi & Manajemen Risiko[/bold green]", show_header=False)
    t_plan.add_column("Parameter", style="white")
    t_plan.add_column("Nilai", style="bold green")
    t_plan.add_row("Entry Price", f"Rp {ind['price']:,.0f}")
    t_plan.add_row("Target Profit (TP)", f"Rp {ind['target_price']:,} (+{((ind['target_price']-ind['price'])/ind['price']*100):.1f}%)")
    t_plan.add_row("Stop Loss (SL)", f"Rp {ind['stop_loss']:,} (-{((ind['price']-ind['stop_loss'])/ind['price']*100):.1f}%)")
    t_plan.add_row("Risk/Reward Ratio", f"1 : {ind['risk_reward_ratio']}")
    t_plan.add_row("Win Probability", f"{ind['probability']:.1f}%")
    t_plan.add_row("Half-Kelly Allocation", f"{ind['kelly_allocation']:.1f}% dari Total Modal")

    grid.add_row(t_tech, t_plan)
    console.print(grid)

    # Multi-Agent Consensus
    t_agents = Table(title="[bold]3. Konsensus Multi-Agent AI System[/bold]", show_header=True, header_style="bold")
    t_agents.add_column("Agen AI", style="bold", width=20)
    t_agents.add_column("Analisis & Pertimbangan", style="white", overflow="fold")
    t_agents.add_row("Technical Agent", _clean_text(tech_reason))
    t_agents.add_row("Macro Context Agent", _clean_text(macro_reason))
    t_agents.add_row("Sentiment Agent", _clean_text(sent_reason))
    console.print(t_agents)

    # Mini ASCII Chart
    chart_str = render_ascii_chart(ind["history"], height=6, width=45)
    console.print(Panel(chart_str, title=f"[dim]Grafik Tren Harga 30 Hari Terakhir: {clean_ticker}[/dim]", expand=False))
    console.print("[dim]Tip: ketik [bold yellow]/sizing {0} <MODAL>[/bold yellow] untuk kalkulasi lot berdasarkan modal Anda.[/dim]\n".format(clean_ticker))


def cmd_macro():
    """Menampilkan ringkasan rezim makro dan rotasi sektor BEI."""
    with console.status("[bold green]Mengambil data makro ekonomi, valuta asing, & rotasi sektor...[/bold green]"):
        try:
            from src.agents.ihsg_macro_agent import IHSGMacroAgent
            agent = IHSGMacroAgent()
            res = agent.evaluate(skip_news=True, skip_sectors=False)
        except Exception as e:
            console.print(f"[bold red]Error saat mengambil data makro: {e}[/bold red]")
            return

    mode = res.get("mode", "NORMAL")
    score = res.get("macro_score", 0.0)
    badge = _clean_text(res.get("mode_badge", "MODE NORMAL"))
    details = res.get("details", [])

    mode_color = "green" if mode == "NORMAL" else "yellow" if mode == "CAUTIOUS" else "red"

    console.print(Panel(
        f"Status: [{mode_color} bold]{badge}[/{mode_color} bold]  |  Skor Gabungan: [bold]{score:+.1f}[/bold]\n"
        f"Penjelasan: Rezim makro mengevaluasi stabilitas rupiah, sentimen bursa regional, teknikal IHSG, dan rotasi dana antar sektor.",
        title="[bold]KONDISI MAKRO EKONOMI & PASAR MODAL (IHSG)[/bold]",
        expand=False
    ))

    # Tabel Indikator Pasar
    if details:
        t_ind = Table(title="[bold]1. Parameter Pasar Global, Valas & Domestik[/bold]", show_header=True, header_style="bold")
        t_ind.add_column("No", justify="right", style="dim", width=4)
        t_ind.add_column("Parameter & Evaluasi Indikator", style="white", overflow="fold")

        for idx, det in enumerate(details, start=1):
            clean_det = _clean_text(det.replace("• ", ""))
            t_ind.add_row(str(idx), clean_det)

        console.print(t_ind)

    # Tabel Rotasi 11 Sektor BEI
    sec_info = res.get("sector_rotation", {})
    sec_rank = sec_info.get("sector_rankings", {})
    leading = sec_info.get("leading_sectors", [])

    if sec_rank:
        t_sec = Table(title="[bold]2. Peta Rotasi Momentum 11 Sektor BEI[/bold]", show_header=True, header_style="bold")
        t_sec.add_column("Peringkat", justify="right", style="dim", width=10)
        t_sec.add_column("Sektor", style="bold", width=25)
        t_sec.add_column("Skor Momentum", justify="right", style="bold yellow", width=18)
        t_sec.add_column("Status Aliran Dana", style="white")

        for rank, (s_name, s_score) in enumerate(sec_rank.items(), start=1):
            is_lead = s_name in leading
            status = "[bold green][HOT] LEADING (Inflow Kuat)[/bold green]" if is_lead else "[dim]Lagging / Netral[/dim]"
            t_sec.add_row(f"#{rank}", s_name, f"{s_score:+.2f}%", status)

        console.print(t_sec)
    console.print("[dim]Tip: ketik [bold yellow]/analyze <TICKER>[/bold yellow] untuk cek dampak makro ke saham tertentu.[/dim]\n")


def cmd_audit():
    """Menampilkan rekap performa track record dan win rate."""
    with console.status("[bold green]Mengambil data audit rekam jejak dari database...[/bold green]"):
        try:
            from dashboard.backend.routes.audit import get_audit_recap
            recap = get_audit_recap()
        except Exception as e:
            console.print(f"[bold red]Error saat mengambil data audit: {e}[/bold red]")
            return

    summary = recap.get("summary", {})
    monthly = recap.get("monthly_breakdown", [])

    tot = summary.get("total_signals", 0)
    win = summary.get("win_count", 0)
    loss = summary.get("loss_count", 0)
    pending = summary.get("pending_count", 0)
    wr = summary.get("win_rate", 0.0)
    profit = summary.get("total_profit_pct", 0.0)

    # Ringkasan Panel
    profit_str = f"+{profit:.1f}%" if profit >= 0 else f"{profit:.1f}%"
    profit_color = "bold green" if profit >= 0 else "bold red"
    wr_color = "bold green" if wr >= 60 else ("bold yellow" if wr >= 40 else "bold red")
    panel_content = (
        f"Total Sinyal Terverifikasi : [bold]{tot:,}[/bold]\n"
        f"Win Rate Kumulatif        : [{wr_color}]{wr:.1f}%[/{wr_color}] ({win} WIN / {loss} LOSS / {pending} PENDING)\n"
        f"Total Realized Profit     : [{profit_color}]{profit_str}[/{profit_color}] (Akumulasi Realized Gain)\n"
        f"Proteksi Risiko           : Dynamic Stop-Loss Strict (-1.5% max)"
    )
    console.print(Panel(panel_content, title="[bold]REKAPITULASI AUDIT & REKAM JEJAK SINYAL[/bold]", expand=False))

    # Tabel Bulanan
    if monthly:
        t_m = Table(title="[bold cyan]Breakdown Performa Bulanan[/bold cyan]", show_header=True, header_style="bold cyan")
        t_m.add_column("Bulan", style="bold white", width=18)
        t_m.add_column("Total Sinyal", justify="right", style="dim", width=14)
        t_m.add_column("WIN", justify="right", style="green", width=10)
        t_m.add_column("LOSS", justify="right", style="red", width=10)
        t_m.add_column("Win Rate", justify="right", style="bold yellow", width=12)
        t_m.add_column("Profit %", justify="right", style="bold green", width=14)

        for m in monthly:
            wr_str = f"{m.get('win_rate', 0.0):.1f}%"
            prof_val = m.get('monthly_profit_pct', 0.0)
            prof_str = f"+{prof_val:.1f}%" if prof_val >= 0 else f"{prof_val:.1f}%"
            t_m.add_row(
                m.get("month_name", "Unknown"),
                str(m.get("total_signals", 0)),
                str(m.get("win_count", 0)),
                str(m.get("loss_count", 0)),
                wr_str,
                prof_str
            )

        console.print(t_m)
    console.print("[dim]Tip: ketik [bold yellow]/sizing <TICKER> <MODAL>[/bold yellow] untuk kalkulasi lot sesuai modal Anda.[/dim]\n")


def cmd_sizing(ticker: str, capital_str: str = ""):
    """Kalkulator ukuran posisi dan lot saham berdasarkan Half-Kelly Criterion."""
    if not ticker:
        _usage("sizing", "<TICKER> [MODAL] (contoh: /sizing BBRI 50jt)")
        return

    clean_ticker = ticker.upper().replace(".JK", "").strip()

    # Parse modal: dukung 50jt, 50j, 50 juta, 50m, 500rb, 50000000
    capital = None
    if capital_str:
        raw = capital_str.lower().replace("rp", "").strip()
        mult = 1.0
        for suffix, factor in (("juta", 1_000_000), ("jt", 1_000_000), ("j", 1_000_000), ("m", 1_000_000), ("rb", 1_000), ("k", 1_000)):
            if raw.endswith(suffix):
                mult = factor
                raw = raw[: -len(suffix)].strip()
                break
        num = raw.replace(",", "").replace(".", "").strip()
        try:
            val = float(num) * mult
        except ValueError:
            val = 0.0
        if val > 0:
            capital = val

    if capital is None:
        capital = 50_000_000.0
        console.print("[dim]Modal tidak diisi / tidak valid — memakai default Rp 50.000.000. Contoh: [bold yellow]/sizing BBRI 50jt[/bold yellow][/dim]")

    with console.status(f"[bold green]Menghitung kalkulasi posisi Kelly untuk {clean_ticker}...[/bold green]"):
        df = fetch_stock_data(clean_ticker)
        if df.empty:
            console.print(f"[bold red]Gagal mengambil data {clean_ticker}.[/bold red]")
            return

        ind = calculate_indicators(df)
        if not ind:
            console.print(f"[bold red]Data {clean_ticker} tidak cukup.[/bold red]")
            return

    price = ind["price"]
    tp = ind["target_price"]
    sl = ind["stop_loss"]
    kelly_pct = ind["kelly_allocation"]
    prob = ind["probability"]
    rr = ind["risk_reward_ratio"]

    allocated_rupiah = capital * (kelly_pct / 100.0)
    lot_price = price * 100.0
    lots = int(allocated_rupiah // lot_price) if lot_price > 0 else 0
    actual_invested = lots * lot_price

    if lots == 0:
        console.print(f"[yellow]Modal Rp {capital:,.0f} terlalu kecil untuk 1 lot {clean_ticker} (Rp {lot_price:,.0f}). Alokasi Kelly {kelly_pct:.1f}% belum cukup untuk 1 lot. Pertimbangkan menambah modal.[/yellow]\n")
        return

    potential_profit_rp = lots * 100 * (tp - price)
    max_risk_rp = lots * 100 * (price - sl)

    table = Table(title=f"[bold]KALKULATOR SIZING POSISI: {clean_ticker}[/bold]", show_header=False)
    table.add_column("Parameter", style="white", width=28)
    table.add_column("Nilai", style="bold yellow")

    table.add_row("Total Modal Portofolio", f"Rp {capital:,.0f}")
    table.add_row("Harga Saham Saat Ini", f"Rp {price:,.0f} / lembar")
    table.add_row("Win Probability AI", f"{prob:.1f}%")
    table.add_row("Risk / Reward Ratio", f"1 : {rr}")
    table.add_row("Alokasi Half-Kelly", f"{kelly_pct:.1f}% dari Portofolio")
    table.add_row("Rekomendasi Pembelian Lot", f"[bold green]{lots:,} Lot[/bold green] ({lots * 100:,} lembar)")
    table.add_row("Total Dana Dialokasikan", f"Rp {actual_invested:,.0f} ({(actual_invested/capital*100):.1f}% dari modal)")
    table.add_row("Target Profit (TP)", f"Rp {tp:,.0f} -> Potensi Cuan: [bold green]+Rp {potential_profit_rp:,.0f}[/bold green]")
    table.add_row("Stop Loss (SL)", f"Rp {sl:,.0f} -> Risiko Maksimal: [bold red]-Rp {max_risk_rp:,.0f}[/bold red]")

    console.print(table)
    console.print("[dim]Formula: Half-Kelly f* = 0.5 * (p*b - q)/b untuk mencegah drawdown berlebih.[/dim]\n")


def cmd_chart(ticker: str):
    """Menampilkan grafik harga terminal untuk saham tertentu."""
    if not ticker:
        _usage("chart", "<TICKER> (contoh: /chart ASII)")
        return

    clean_ticker = ticker.upper().replace(".JK", "").strip()
    with console.status(f"[bold green]Membuat grafik untuk {clean_ticker}...[/bold green]"):
        df = fetch_stock_data(clean_ticker)
        if df.empty:
            console.print(f"[bold red]Data untuk {clean_ticker} tidak ditemukan.[/bold red]")
            return

        prices = df['Close'].tail(40).tolist()
        chart_str = render_ascii_chart(prices, height=10, width=50)

        high_52 = float(df['Close'].max())
        low_52 = float(df['Close'].min())
        last_p = float(prices[-1])

    console.print(Panel(
        f"{chart_str}\n\n"
        f"Harga Saat Ini: [bold yellow]Rp {last_p:,.0f}[/bold yellow]  |  52w High: Rp {high_52:,.0f}  |  52w Low: Rp {low_52:,.0f}",
        title=f"[bold]GRAFIK TREN HARGA (40 HARI): {clean_ticker}[/bold]",
        expand=False
    ))
    console.print()


# =====================================================================
# 3. INTERACTIVE SHELL & DISPATCHER
# =====================================================================

def execute_command(line: str) -> bool:
    """
    Mengeksekusi baris perintah yang dimasukkan pengguna.
    Mengembalikan False jika pengguna ingin keluar (/exit).
    """
    line = line.strip()
    if not line:
        return True

    parts = line.split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd.startswith("/"):
        cmd = cmd[1:]

    if cmd in ["exit", "quit", "q"]:
        console.print("[bold cyan]Terima kasih telah menggunakan IDX Quant AI Terminal. Sampai jumpa![/bold cyan]")
        return False

    elif cmd in ["help", "h", "?"]:
        cmd_help()

    elif cmd in ["scan", "top", "s"]:
        cmd_scan()

    elif cmd in ["analyze", "a", "inspect"]:
        if not args:
            _usage("analyze", "<TICKER> (contoh: /analyze BBCA)")
        else:
            cmd_analyze(args[0])

    elif cmd in ["macro", "m", "ihsg"]:
        cmd_macro()

    elif cmd in ["audit", "track", "history"]:
        cmd_audit()

    elif cmd in ["sizing", "size", "kelly", "k"]:
        if not args:
            _usage("sizing", "<TICKER> [MODAL] (contoh: /sizing BBRI 50jt)")
        else:
            tkr = args[0]
            cap = args[1] if len(args) > 1 else ""
            cmd_sizing(tkr, cap)

    elif cmd in ["chart", "c", "plot"]:
        if not args:
            _usage("chart", "<TICKER> (contoh: /chart BBCA)")
        else:
            cmd_chart(args[0])

    elif cmd in ["clear", "cls"]:
        os.system("cls" if os.name == "nt" else "clear")

    else:
        known = ["help", "scan", "analyze", "macro", "audit", "sizing", "chart", "clear", "exit"]
        close = difflib.get_close_matches(cmd, known, n=1, cutoff=0.6)
        suggestion = f" Maksud Anda: [bold yellow]/{close[0]}[/bold yellow]?" if close else ""
        console.print(f"[bold red]Perintah '{cmd}' tidak dikenali.[/bold red]{suggestion} Ketik [bold yellow]/help[/bold yellow] untuk melihat daftar perintah.")

    return True


def run_interactive_shell():
    """Menjalankan loop terminal shell interaktif."""
    banner_text = Text()
    banner_text.append("IDX QUANT AI - INTERACTIVE TERMINAL SHELL\n", style="bold")
    banner_text.append("Multi-Agent Intelligence, Quant Screener & Risk Management\n", style="white")
    banner_text.append("Ketik ", style="dim")
    banner_text.append("/help", style="bold yellow")
    banner_text.append(" untuk daftar perintah, atau ", style="dim")
    banner_text.append("/scan", style="bold green")
    banner_text.append(" untuk rekomendasi harian.\n", style="dim")
    banner_text.append("Coba: ", style="dim")
    banner_text.append("/scan", style="bold green")
    banner_text.append(" lalu ", style="dim")
    banner_text.append("/analyze BBCA", style="bold cyan")
    banner_text.append(" untuk deep-dive multi-agent.", style="dim")

    console.print(Panel(banner_text, expand=False, border_style="cyan"))

    running = True
    while running:
        try:
            prompt = f"[bold cyan](idx-quant · {get_wib_now().strftime('%H:%M')} WIB)[/bold cyan] >"
            user_input = Prompt.ask(prompt)
            running = execute_command(user_input)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold cyan]Sesi dihentikan. Sampai jumpa![/bold cyan]")
            break


def main():
    """Entry point CLI: Mendukung direct execution maupun interactive shell."""
    if len(sys.argv) > 1:
        first_arg = sys.argv[1].strip().lower()
        if first_arg in ("--help", "-h"):
            cmd_help()
            return
        cmd_line = " ".join(sys.argv[1:])
        execute_command(cmd_line)
    else:
        run_interactive_shell()


if __name__ == "__main__":
    main()
