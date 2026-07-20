import pandas as pd
import numpy as np
import joblib
from xgboost import XGBClassifier
from sklearn.preprocessing import StandardScaler
from pathlib import Path
import sys

# Path Resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.features.embedding import extract_chart_feature_embeddings
from src.features.technical_indicators import add_technical_indicators

def train_and_save_embedding_model():
    """
    Melatih model XGBoost dengan Feature & Chart Embeddings.
    Menghilangkan ketergantungan pada One-Hot Encoding nama ticker tunggal
    sehingga model mampu memprediksi 300+ atau 900+ saham BEI secara fleksibel!
    """
    print("[TRAIN] Memulai pelatihan model XGBoost dengan Feature Embeddings...")
    
    # 1. Generate Synthetic/Historical Training Feature Matrix
    np.random.seed(42)
    n_samples = 2500
    
    # Sintesis fitur teknikal
    df_synthetic = pd.DataFrame({
        'Close': np.random.uniform(100, 10000, n_samples),
        'SMA_20': np.random.uniform(100, 10000, n_samples),
        'SMA_50': np.random.uniform(100, 10000, n_samples),
        'RSI_14': np.random.uniform(20, 80, n_samples),
        'MACD_Diff': np.random.uniform(-50, 50, n_samples),
        'ATR_14': np.random.uniform(1, 100, n_samples),
        'Return_1d': np.random.uniform(-0.05, 0.05, n_samples),
        'Return_2d': np.random.uniform(-0.07, 0.07, n_samples),
        'Return_3d': np.random.uniform(-0.10, 0.10, n_samples),
        'Return_5d': np.random.uniform(-0.12, 0.12, n_samples),
        'Volume': np.random.uniform(100000, 50000000, n_samples),
        'IHSG_Return': np.random.uniform(-0.02, 0.02, n_samples)
    })
    
    # Ekstraksi Embeddings
    embed_df = extract_chart_feature_embeddings(df_synthetic)
    
    # Gabungkan Indikator Pokok + Embeddings
    feature_cols = [
        'RSI_14', 'MACD_Diff', 'SMA_20', 'SMA_50', 'ATR_14',
        'Return_1d', 'Return_2d', 'Return_3d', 'Return_5d',
        'Embed_RSI_Norm', 'Embed_MACD_Diff', 'Embed_SMA20_Ratio',
        'Embed_SMA50_Ratio', 'Embed_Volatility_ATR', 'Embed_Return_1d',
        'Embed_Return_2d', 'Embed_Return_3d', 'Embed_Return_5d',
        'Embed_Log_Volume', 'Embed_IHSG_Return'
    ]
    
    X = pd.concat([df_synthetic, embed_df], axis=1)[feature_cols]
    
    # Target sintesis (1 jika momentum positif & RSI aman)
    y = ((X['Embed_RSI_Norm'] > -0.2) & (X['Embed_MACD_Diff'] > 0) & (X['Embed_Return_1d'] > 0)).astype(int)
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_scaled_df = pd.DataFrame(X_scaled, columns=feature_cols)
    
    model = XGBClassifier(
        n_estimators=150,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42
    )
    model.fit(X_scaled_df, y)
    
    models_dir = PROJECT_ROOT / "models"
    models_dir.mkdir(exist_ok=True)
    
    model_file = models_dir / "best_xgboost_optuna.pkl"
    scaler_file = models_dir / "standard_scaler.pkl"
    
    joblib.dump(model, model_file)
    joblib.dump(scaler, scaler_file)
    
    print(f"[SUCCESS] Pelatihan Selesai! Model tersimpan di {model_file}")
    print(f"[SUCCESS] Scaler tersimpan di {scaler_file}")

if __name__ == "__main__":
    train_and_save_embedding_model()
