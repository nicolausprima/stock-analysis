# ML Pipeline Robustness Review

**Project**: stock-analysis  
**Files Reviewed**: 
- `src/scheduler/daily_scheduler.py` (lines 95-180)
- `src/collector/polars_batch_collector.py`
- `src/collector/batch_collector.py`
- `src/features/technical_indicators.py`
- `src/features/embedding.py`
- `src/features/build_features.py`
- `src/features/fundamental_features.py`
- `src/explainability/shap_explainer.py`
- `src/database/duckdb_market.py`
- `src/database/market_db.py`
- `dashboard/backend/routes/sentiment_filter.py`
- `notebooks/02_Preprocessing.ipynb`
- `notebooks/03_Modelling.ipynb`

---

## 🔴 CRITICAL: Data Leakage (Lookahead Bias)

### 1. Training Target Uses Tomorrow's HIGH (Unobservable at Decision Time)
**File**: `notebooks/02_Preprocessing.ipynb`, line 68-70
```python
next_open = df['Open'].shift(-1)
next_high = df['High'].shift(-1)
df['Target'] = ((next_high - next_open) / next_open >= PROFIT_THRESHOLD).astype(int)
```
**Problem**: Model trained to predict if `(High_t+1 - Open_t+1)/Open_t+1 >= 3%`. At 09:00 WIB (market open), you ONLY know `Open_t+1`, not `High_t+1`. The target is unknowable at inference time → **model learns cheating signals**.

### 2. Target Definition Mismatch: Training vs. Retraining Pipeline
**File**: `src/features/build_features.py`, lines 46-50
```python
df['Next_Day_Return'] = (df['Next_Day_Close'] - df['Next_Day_Open']) / df['Next_Day_Open']
df['Target'] = (df['Next_Day_Return'] >= PROFIT_THRESHOLD).astype(int)
```
**Problem**: Uses `Close_t+1` (close-to-open return). Different from training notebook's `High_t+1` target. If `build_features.py` used for retraining, **model learns different task**.

---

## 🔴 CRITICAL: Feature/Target Mismatch (Train/Serving Skew)

### 3. SHAP Explainer Uses Different Feature Set Than Training
**File**: `src/explainability/shap_explainer.py`, lines 62-68
```python
_feature_cols = [
    'RSI_14', 'MACD_Diff', 'SMA_20', 'SMA_50', 'ATR_14', 'Return_1d', 'Return_2d',
    'Return_3d', 'Return_5d', 'Embed_RSI_Norm', 'Embed_MACD_Diff',
    'Embed_SMA20_Ratio', 'Embed_SMA50_Ratio', 'Embed_Volatility_ATR',
    'Embed_Return_1d', 'Embed_Return_2d', 'Embed_Return_3d', 'Embed_Return_5d',
    'Embed_Log_Volume', 'Embed_IHSG_Return'
]
```
**Missing vs Training (02_Preprocessing.ipynb line 85-92)**: `ADX_14`, `RVOL`, `Volume_Z`, `Embed_ADX_Norm`, `Embed_RVOL`, `Embed_Volume_Z`, `Embed_MFI_Norm`, `Embed_Stoch_Norm`, `Embed_Williams_Norm`, `Embed_EMA_Cross`, `Embed_CCI_Norm`  
**Impact**: SHAP explanations are **meaningless** — wrong features, wrong importance.

### 4. Scaler Fit on 50 Tickers, Applied to 700+ Tickers
**Training**: `notebooks/02_Preprocessing.ipynb` line 43: `sample_tickers = TICKERS[:50]`  
**Serving**: `daily_scheduler.py` processes all 700+ tickers from DB  
**Risk**: Distribution shift — scaler statistics (mean/std) don't represent full universe.

### 5. Time-Based Split Not Respected in Training
**File**: `notebooks/02_Preprocessing.ipynb`, lines 101-103
```python
split_idx = int(len(X) * 0.8)
X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
```
**Problem**: Concatenates all tickers then splits by row index. **No temporal separation** — future data from same tickers leaks into train. Should split by date cutoff per ticker.

---

## 🟠 HIGH: NaN Handling — `fillna(0)` Masks Real Bugs

| File | Line | Issue |
|------|------|-------|
| `daily_scheduler.py` | 139, 141 | `IHSG_Return.fillna(0)` — masks failed IHSG download |
| `daily_scheduler.py` | 156 | `combined_df.fillna(0, inplace=True)` — **aggressive fill on ALL columns** |
| `daily_scheduler.py` | 170 | `X.fillna(0, inplace=True)` — second aggressive fill on feature matrix |
| `embedding.py` | 70-71 | `embeddings.fillna(0.0, inplace=True)` — masks missing indicator values |
| `technical_indicators.py` | 54-56, 70-71, 74, 77-78, 81, 84 | Inconsistent defaults: `fillna(20)`, `fillna(50)`, `fillna(0)`, `fillna(1)`, `fillna(-50)` |

**Why it's bad**: 
- RSI=0 means "extremely oversold" — not "missing data"
- Volume_Z=0 means "average volume" — not "no volume data"
- ADX=20 means "weak trend" — not "insufficient history"
- Model receives **fake "neutral" signals** for tickers with insufficient history

**Correct approach**: Drop tickers with insufficient lookback (< 50 days for SMA_50, ADX_14, etc.) or use `fillna(method='ffill')` for time-series continuity.

---

## 🟠 HIGH: Silent Failures (Errors Swallowed)

| File | Line | Pattern | Consequence |
|------|------|---------|-------------|
| `polars_batch_collector.py` | 75-76 | `except Exception: continue` | Failed ticker silently skipped |
| `polars_batch_collector.py` | 93 | `except Exception as e: print(...)` | Batch error logged but processing continues |
| `batch_collector.py` | 57-58 | `except Exception: continue` | Failed ticker silently skipped |
| `daily_scheduler.py` | 79-80, 92-93, 242-243, 271-272, 296-297, 316-317, 334-335, 363-364 | `except Exception: print(...)` | Macro agent, IHSG, audit, telegram, all scheduler jobs — **fail silently** |
| `sentiment_filter.py` | 54-55 | `except Exception: headlines = []` | Failed news fetch → neutral sentiment assumed |
| `shap_explainer.py` | 42-43 | `except Exception: pass` | SHAP XGBoost compat patch fails silently |
| `shap_explainer.py` | 158-159 | `except: continue` | Failed ticker skipped in global SHAP |
| `duckdb_market.py` | — | No connection cleanup on error | Connection leaks if exception mid-transaction |

**Impact**: Pipeline appears "green" while producing degraded/stale results. No alerting on partial failures.

---

## 🟠 HIGH: DuckDB Connection Leaks

**File**: `src/database/duckdb_market.py`
- Line 19: Global `_connection = None` (module-level singleton)
- Line 21-30: `get_duckdb_connection()` creates persistent connection, never closed
- Line 125-130: `close_connection()` exists but **never called anywhere**
- No context manager, no `atexit` registration, no `try/finally` in callers

**Callers that leak**:
- `polars_batch_collector.py` → `save_daily_prices_polars()` → `get_duckdb_connection()`
- `daily_scheduler.py` → `get_all_histories_polars()` → `get_duckdb_connection()`

**Risk**: File locks, memory growth, connection exhaustion on repeated scheduler runs.

---

## 🟡 MEDIUM: Model Versioning — None Exists

**File**: `daily_scheduler.py`, lines 49-58
```python
model_path = PROJECT_ROOT / 'models' / 'best_xgboost_optuna.pkl'
scaler_path = PROJECT_ROOT / 'models' / 'standard_scaler.pkl'
model = joblib.load(model_path)
scaler = joblib.load(scaler_path)
expected_cols = list(scaler.feature_names_in_)
```

**Missing**:
- No model metadata (training date, data cutoff, git commit, feature schema hash)
- No version check: `scaler.feature_names_in_` assumed compatible
- No rollback mechanism
- No A/B testing support
- `best_xgboost_optuna.pkl` name implies Optuna tuning but `03_Modelling.ipynb` uses fixed params (no Optuna)

---

## 🟡 MEDIUM: Scaling / Rate Limit Handling

**File**: `src/config.py`, lines 13-14
```python
BATCH_SIZE = 50
BATCH_DELAY_SECONDS = 2
```

**Issues**:
- 700+ tickers / 50 = 14 batches × 2s = **28s minimum** + download time
- yfinance undocumented rate limits (~2000 req/hr); no 429 handling
- No exponential backoff, no retry logic
- `threads=True` in yfinance but no connection pooling / semaphore
- Scheduler blocks on download (line 62: `download_universe_in_batches()` sync)

**File**: `polars_batch_collector.py` line 40
```python
df_batch = yf.download(ticker_str, period="100d", progress=False, group_by="ticker", threads=True)
```
Multi-ticker download reduces HTTP calls but **single failure poisons entire batch** (line 64-78: one ticker error → whole chunk processing continues but that ticker lost).

---

## 🟡 MEDIUM: Polars vs Pandas Feature Parity Risk

**File**: `duckdb_market.py`, lines 135-210 — `add_technical_indicators_polars()`  
**File**: `technical_indicators.py` — `add_technical_indicators()` (pandas + `ta` lib)

**Risk**: Two implementations of same indicators. `daily_scheduler.py` uses pandas version. If Polars version used for bulk feature generation, **results will diverge** (different rolling window behaviors, NaN handling, fill defaults).

---

## 🟡 MEDIUM: Timezone Handling Inconsistencies

Multiple `tz_localize(None)` calls with inconsistent guards:
- `daily_scheduler.py` lines 90-91, 136-137: checks `if df.index.tz is not None:`
- `build_features.py` lines 39-40: same check
- `02_Preprocessing.ipynb` lines 32-33, 61-62: same
- `shap_explainer.py` lines 145-146: same

**Risk**: Mix of tz-aware/naive indexes causes silent misalignment on join.

---

## 🟢 LOW: IHSG Return Join Fragility

**File**: `daily_scheduler.py` lines 84-91, 135-141
- Separate `yf.download('^JKSE')` call — can fail independently
- On failure: `ihsg_returns = pd.DataFrame()` → all tickers get `IHSG_Return = 0` (line 141)
- No fallback, no alert, feature degraded silently

---

## 🟢 LOW: Scheduler Race Conditions

**File**: `daily_scheduler.py` lines 338-369
- Background thread with `time.sleep(20)` polling
- `last_run` dict not thread-safe (single writer but readable from main thread)
- No persistence — restart loses `last_run` state → duplicate runs possible
- No job timeout — hung job blocks schedule

---

## Summary: Priority Fixes

| Priority | Issue | Files to Fix |
|----------|-------|--------------|
| **P0** | Fix training target: use `Close_t+1` not `High_t+1` | `02_Preprocessing.ipynb`, `build_features.py` |
| **P0** | Align SHAP feature list with training | `shap_explainer.py` |
| **P0** | Replace `fillna(0)` with proper NaN policy (drop/ffill) | `daily_scheduler.py`, `embedding.py`, `technical_indicators.py` |
| **P0** | Add explicit error handling + alerting (no bare `except:`) | All collector/scheduler files |
| **P1** | Implement DuckDB connection context manager + cleanup | `duckdb_market.py`, callers |
| **P1** | Add model version metadata + schema validation | `daily_scheduler.py`, training notebook |
| **P1** | Fix time-based train/test split (by date, not row index) | `02_Preprocessing.ipynb` |
| **P2** | Add retry/backoff for yfinance rate limits | `polars_batch_collector.py`, `batch_collector.py` |
| **P2** | Unify Polars/Pandas indicator implementations | `duckdb_market.py`, `technical_indicators.py` |
| **P3** | Add scheduler persistence + job timeouts | `daily_scheduler.py` |

---

## Recommended Immediate Actions

1. **Retrain model with corrected target** (next day close-to-open return) — current model is fundamentally flawed
2. **Add feature schema validation** at model load: `assert list(scaler.feature_names_in_) == EXPECTED_FEATURES`
3. **Replace all `fillna(0)` with `dropna(thresh=...)` or forward-fill** for time-series features
4. **Wrap DuckDB connection in context manager** and call `close_connection()` at scheduler end
5. **Add structured logging + error counters** — alert if >5% tickers fail per batch