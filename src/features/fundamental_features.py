"""
Merge fundamental data into technical feature matrix.
Model file is not touched — this only enriches narrative / reason generation.
"""

def compute_valuation_score(per, pbv, roe, debt_to_equity) -> dict:
    """Skor valuasi. None/NaN = data missing -> skor 0 + catatan, bukan 0.0 murah.

    AI-07: PER=0/PBV=0 dulu terbaca 'murah' (0 < per < 15). Sekarang
    missing tidak menambah/mengurangi skor.
    """
    import math
    score = 0.0
    notes = []

    def _nan(v):
        return isinstance(v, float) and math.isnan(v)

    if per is None or _nan(per):
        notes.append("PER n/a (data belum tersedia)")
    elif 0 < per < 15:
        score += 2.0
        notes.append("Valuasi Murah (PER < 15x)")
    elif 15 <= per < 25:
        score += 1.0
        notes.append("Valuasi Wajar (PER 15-25x)")
    elif per >= 35:
        score -= 1.5
        notes.append("Valuasi Mahal (PER > 35x)")

    if pbv is None or _nan(pbv):
        notes.append("PBV n/a (data belum tersedia)")
    elif 0 < pbv < 1.0:
        score += 1.5
        notes.append("PBV < 1x (Di bawah nilai buku)")
    elif pbv >= 5.0:
        score -= 1.0
        notes.append("PBV Premium > 5x")

    if roe is not None and not _nan(roe):
        if roe > 0.15:
            score += 2.0
            notes.append(f"ROE Kuat ({roe*100:.1f}%)")
        elif roe < 0.05:
            score -= 1.0
    else:
        notes.append("ROE n/a")

    if debt_to_equity is not None and not _nan(debt_to_equity) and debt_to_equity > 200:
        score -= 1.0
        notes.append("Leverage Tinggi (DER > 200%)")
    
    return {"valuation_score": round(score, 2), "valuation_notes": notes}
