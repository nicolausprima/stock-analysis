"""
SHAP Explainability for XGBoost model.
Generates global & local feature importance without modifying model file.
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config import TICKERS

MODEL_PATH = PROJECT_ROOT / "models" / "best_xgboost_optuna.pkl"
SCALER_PATH = PROJECT_ROOT / "models" / "standard_scaler.pkl"
OUTPUT_PATH = PROJECT_ROOT / "data" / "shap_explanations.json"

_explainer = None
_model = None
_scaler = None
_feature_cols = None

def _patch_shap_xgb_compatibility():
    """Fix XGBoost 2.x base_score format '[...]' incompatibility in SHAP TreeExplainer."""
    try:
        import shap.explainers._tree as st
        orig_read_xgb_params = getattr(st.XGBTreeModelLoader, "read_xgb_params", None)
        if orig_read_xgb_params and not getattr(st.XGBTreeModelLoader, "_patched_base_score", False):
            def safe_read_xgb_params(xgb_model):
                learner = orig_read_xgb_params(xgb_model)
                bs = learner.get("learner_model_param", {}).get("base_score")
                if isinstance(bs, str) and bs.startswith("["):
                    learner["learner_model_param"]["base_score"] = bs.strip("[]")
                return learner
            st.XGBTreeModelLoader.read_xgb_params = staticmethod(safe_read_xgb_params)
            st.XGBTreeModelLoader._patched_base_score = True
    except Exception:
        pass

def _load_model_and_scaler():
    global _model, _scaler
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    if _scaler is None:
        _scaler = joblib.load(SCALER_PATH)

def _get_feature_columns():
    """Return expected feature columns matching trained model and scaler."""
    global _feature_cols
    if not _feature_cols:
        _load_model_and_scaler()
        if hasattr(_model, "feature_names_in_"):
            _feature_cols = list(_model.feature_names_in_)
        elif hasattr(_scaler, "feature_names_in_"):
            _feature_cols = list(_scaler.feature_names_in_)
        else:
            _feature_cols = [
                'RSI_14', 'MACD_Diff', 'SMA_20', 'SMA_50', 'ATR_14', 'ADX_14',
                'RVOL', 'Volume_Z', 'Return_1d', 'Return_2d', 'Return_3d', 'Return_5d',
                'Embed_RSI_Norm', 'Embed_MACD_Diff', 'Embed_SMA20_Ratio',
                'Embed_SMA50_Ratio', 'Embed_Volatility_ATR', 'Embed_Return_1d',
                'Embed_Return_2d', 'Embed_Return_3d', 'Embed_Return_5d',
                'Embed_Log_Volume', 'Embed_IHSG_Return', 'Embed_ADX_Norm',
                'Embed_RVOL', 'Embed_Volume_Z', 'Embed_MFI_Norm', 'Embed_Stoch_Norm',
                'Embed_Williams_Norm', 'Embed_EMA_Cross', 'Embed_CCI_Norm'
            ]
    return _feature_cols

def get_explainer():
    global _explainer
    if _explainer is None:
        _load_model_and_scaler()
        _patch_shap_xgb_compatibility()
        # Use tree explainer for XGBoost (fast, exact)
        _explainer = shap.TreeExplainer(_model)
    return _explainer

def explain_single_prediction(ticker: str, features_df: pd.DataFrame) -> dict:
    """
    Generate SHAP values for a single ticker's latest features.
    Returns top 5 contributing features with SHAP values.
    """
    explainer = get_explainer()
    feature_cols = _get_feature_columns()

    # AI-06: kolom hilang / NaN (warm-up) DITOLAK, bukan default 0.0.
    # SHAP atas nilai palsu = eksplanasi menyesatkan.
    df_clean = pd.DataFrame(index=[0])
    for col in feature_cols:
        if isinstance(features_df, pd.DataFrame) and col in features_df.columns and not features_df[col].empty:
            try:
                df_clean[col] = float(features_df[col].iloc[-1])
            except (ValueError, TypeError):
                df_clean[col] = np.nan
        else:
            df_clean[col] = np.nan
    df_clean.replace([np.inf, -np.inf], np.nan, inplace=True)
    bad = df_clean.columns[df_clean.isna().any()].tolist()
    if bad:
        raise ValueError(
            f"SHAP menolak fitur NaN/warm-up {bad}: lengkapi histori dulu")
            
    X_scaled = pd.DataFrame(_scaler.transform(df_clean[feature_cols]), columns=feature_cols)
    
    shap_values = explainer.shap_values(X_scaled)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]  # Class 1 (positive) for binary classification
    
    # Get top 5 features by absolute SHAP value
    sv = shap_values[0]
    top_indices = np.argsort(np.abs(sv))[::-1][:5]
    
    result = {
        "ticker": ticker,
        "top_contributors": []
    }
    
    for idx in top_indices:
        col = feature_cols[idx]
        val = float(X_scaled.iloc[0, idx])
        sv_val = float(sv[idx])
        direction = "positive" if sv_val > 0 else "negative"
        result["top_contributors"].append({
            "feature": col,
            "feature_value": round(val, 4),
            "shap_value": round(sv_val, 4),
            "direction": direction
        })
    
    return result

def generate_global_shap_summary(sample_size: int = 500) -> dict:
    """
    Generate global feature importance using SHAP on a sample of training data.
    Saves to data/shap_explanations.json for dashboard consumption.
    """
    from dashboard.backend.yf_client import download_with_timeout
    from src.features.build_features import build_features_for_ticker
    from src.features.embedding import extract_chart_feature_embeddings
    
    _load_model_and_scaler()
    explainer = get_explainer()
    
    # Get sample of data
    try:
        ihsg = download_with_timeout('^JKSE', period='6mo', progress=False)
        if isinstance(ihsg.columns, pd.MultiIndex):
            ihsg_close = ihsg['Close'].iloc[:, 0]
        else:
            ihsg_close = ihsg['Close']
        ihsg_returns = pd.DataFrame({'IHSG_Return': ihsg_close.pct_change()}, index=ihsg.index)
        if ihsg_returns.index.tz is not None:
            ihsg_returns.index = ihsg_returns.index.tz_localize(None)
    except Exception:  # IHSG benchmark opsional; kosong = guard AI-06 pakai flat
        ihsg_returns = pd.DataFrame()
    
    all_data = []
    for t in TICKERS[:50]:  # Sample 50 tickers for speed
        try:
            df = build_features_for_ticker(t, ihsg_returns)
            if not df.empty:
                embed_df = extract_chart_feature_embeddings(df)
                combined = pd.concat([df, embed_df], axis=1)
                all_data.append(combined)
        except Exception:  # satu ticker gagal -> lanjut (batch best-effort)
            continue
    
    if not all_data:
        return {"error": "No data for SHAP computation"}
    
    full = pd.concat(all_data).dropna()
    feature_cols = _get_feature_columns()
    X = full[feature_cols].sample(min(sample_size, len(full)), random_state=42)
    X_scaled = _scaler.transform(X)
    
    shap_values = explainer.shap_values(X_scaled)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]
    
    # Mean absolute SHAP per feature
    mean_abs_shap = np.mean(np.abs(shap_values), axis=0)
    
    global_importance = []
    for i, col in enumerate(feature_cols):
        global_importance.append({
            "feature": col,
            "mean_abs_shap": float(mean_abs_shap[i])
        })
    
    global_importance.sort(key=lambda x: x["mean_abs_shap"], reverse=True)
    
    result = {"global_importance": global_importance[:20]}
    
    # Save to file
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(result, f, indent=2)
    
    return result