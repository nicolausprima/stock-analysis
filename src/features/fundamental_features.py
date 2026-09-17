"""
Merge fundamental data into technical feature matrix.
Model file is not touched — this only enriches narrative / reason generation.
"""
import numpy as np

def compute_valuation_score(per: float, pbv: float, roe: float, debt_to_equity: float) -> dict:
    score = 0.0
    notes = []
    
    if 0 < per < 15:
        score += 2.0
        notes.append("Valuasi Murah (PER < 15x)")
    elif 15 <= per < 25:
        score += 1.0
        notes.append("Valuasi Wajar (PER 15-25x)")
    elif per >= 35:
        score -= 1.5
        notes.append("Valuasi Mahal (PER > 35x)")
    
    if 0 < pbv < 1.0:
        score += 1.5
        notes.append("PBV < 1x (Di bawah nilai buku)")
    elif pbv >= 5.0:
        score -= 1.0
        notes.append("PBV Premium > 5x")
    
    if roe and roe > 0.15:
        score += 2.0
        notes.append(f"ROE Kuat ({roe*100:.1f}%)")
    elif roe and roe < 0.05:
        score -= 1.0
    
    if debt_to_equity and debt_to_equity > 200:
        score -= 1.0
        notes.append("Leverage Tinggi (DER > 200%)")
    
    return {"valuation_score": round(score, 2), "valuation_notes": notes}
