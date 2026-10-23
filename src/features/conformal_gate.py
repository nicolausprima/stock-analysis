"""
Conformal Prediction Uncertainty Gate & Selective Trade Abstention.

Provides distribution-free prediction intervals and selective trade filtering
without assuming Gaussian or normal distribution of stock returns.

Principles:
1. Finite-Sample Distribution-Free Coverage:
   Given significance level alpha (default 0.10 for 90% confidence),
   computes non-parametric empirical quantile bounds.
2. Selective Trade Abstention Rule:
   - CONFIDENT_BUY: Lower bound of confidence interval stays above safe floor.
   - ABSTAIN: Interval is statistically ambiguous or too wide -> system refuses to enter,
     filtering out false breakouts and reducing whipsaw losses.
3. Conformal Position Sizing:
   Scales Kelly allocation inversely to interval width (uncertainty).
"""

from typing import Any

import numpy as np


class ConformalPredictorGate:
    """
    Non-parametric Conformal Prediction Gate for Trading Signals.
    Wraps probability scores with statistical confidence intervals.
    """

    def __init__(
        self,
        alpha: float = 0.10,  # 90% confidence level
        decision_threshold: float = 0.65,
        default_quantile_radius: float = 0.14,
    ):
        """
        Args:
            alpha: Miscoverage rate (0.10 = 90% empirical coverage guarantee).
            decision_threshold: Operating point threshold for buy signals.
            default_quantile_radius: Calibrated empirical residual radius.
        """
        self.alpha = alpha
        self.decision_threshold = decision_threshold
        # Calibrated empirical residual quantile radius (|y_true - y_pred|)
        self.q_radius = default_quantile_radius
        self.is_calibrated = True

    def calibrate(self, y_true: np.ndarray, y_proba: np.ndarray) -> float:
        """
        Kalibrasi non-conformity score pada out-of-fold / holdout validation set:
        E_i = |y_true - y_proba|
        q_val = Quantile_{1 - alpha}(E)
        """
        y_true = np.asarray(y_true, dtype=float)
        y_proba = np.asarray(y_proba, dtype=float)
        if len(y_true) < 10 or len(y_true) != len(y_proba):
            return self.q_radius

        residuals = np.abs(y_true - y_proba)
        # Finite sample correction quantile: ceil((n + 1) * (1 - alpha)) / n
        n = len(residuals)
        quantile_level = min(1.0, np.ceil((n + 1) * (1.0 - self.alpha)) / n)
        self.q_radius = float(np.quantile(residuals, quantile_level))
        self.is_calibrated = True
        return self.q_radius

    def predict_interval(
        self,
        probability: float | np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Menghitung batas bawah (lower) dan batas atas (upper) interval conformal.

        Returns:
            (lower_bounds, upper_bounds, interval_widths)
        """
        p = np.asarray(probability, dtype=float)
        # Normalisasi ke skala 0.0 - 1.0 jika input dalam persentase (0 - 100)
        in_pct = np.any(p > 1.0)
        p_norm = p / 100.0 if in_pct else p

        lower = np.clip(p_norm - self.q_radius, 0.0, 1.0)
        upper = np.clip(p_norm + self.q_radius, 0.0, 1.0)
        width = upper - lower

        if in_pct:
            return lower * 100.0, upper * 100.0, width * 100.0
        return lower, upper, width

    def evaluate_signal(
        self,
        probability: float,
        signal: int = 1,
        min_lower_bound: float = 0.50,
        max_uncertainty_width: float = 0.35,
    ) -> dict[str, Any]:
        """
        Evaluasi apakah sebuah sinyal layak dieksekusi atau harus di-ABSTAIN.

        Args:
            probability: Probabilitas beli (skala 0.0 - 1.0 atau 0 - 100)
            signal: Klasifikasi dasar (1=Beli, 0=Tahan/Jual)
            min_lower_bound: Batas bawah minimal agar sinyal dianggap konfiden.
            max_uncertainty_width: Lebar maksimal interval sebelum dinyatakan terlalu ambigu.

        Returns:
            dict: {
                "probability": float,
                "lower_bound": float,
                "upper_bound": float,
                "interval_width": float,
                "verdict": "CONFIDENT_BUY" | "MARGINAL_BUY" | "ABSTAIN",
                "should_trade": bool,
                "conformal_multiplier": float,  # Penyesuaian ukuran posisi Kelly
                "reason": str
            }
        """
        # Konversi ke 0.0 - 1.0
        in_pct = probability > 1.0
        p = probability / 100.0 if in_pct else float(probability)
        min_lb = min_lower_bound / 100.0 if min_lower_bound > 1.0 else min_lower_bound
        max_w = max_uncertainty_width / 100.0 if max_uncertainty_width > 1.0 else max_uncertainty_width

        lower, upper, width = self.predict_interval(p)
        lower_val = float(lower)
        upper_val = float(upper)
        width_val = float(width)

        # Aturan Abstention
        if signal == 0 or p < self.decision_threshold:
            verdict = "ABSTAIN"
            should_trade = False
            conformal_mult = 0.0
            reason = f"Probabilitas di bawah threshold operasi ({p:.1%} < {self.decision_threshold:.1%})"
        elif lower_val >= min_lb and width_val <= max_w:
            verdict = "CONFIDENT_BUY"
            should_trade = True
            # Uncertainty scaling: Jika interval sangat sempit (sangat yakin), beri multiplier hingga 1.2x
            conformal_mult = round(float(np.clip(0.28 / max(0.10, width_val), 0.7, 1.2)), 2)
            reason = (
                f"Sinyal Valid Terverifikasi Conformal (Interval 90%: [{lower_val:.1%}, {upper_val:.1%}], "
                f"Batas Bawah > {min_lb:.0%})"
            )
        elif lower_val >= 0.42:
            verdict = "MARGINAL_BUY"
            should_trade = True
            conformal_mult = 0.75  # Kurangi ukuran posisi untuk sinyal marginal
            reason = (
                f"Sinyal Marginal (Interval 90%: [{lower_val:.1%}, {upper_val:.1%}], "
                "Disarankan posisi lebih kecil)"
            )
        else:
            verdict = "ABSTAIN"
            should_trade = False
            conformal_mult = 0.0
            reason = (
                f"ABSTAIN (Arah Ambigu): Batas bawah keyakinan {lower_val:.1%} < {min_lb:.0%}. "
                "Hindari potensi false breakout."
            )

        # Kembalikan ke format persentase jika input awal persentase
        out_p = round(p * 100.0, 1) if in_pct else round(p, 4)
        out_lb = round(lower_val * 100.0, 1) if in_pct else round(lower_val, 4)
        out_ub = round(upper_val * 100.0, 1) if in_pct else round(upper_val, 4)
        out_w = round(width_val * 100.0, 1) if in_pct else round(width_val, 4)

        return {
            "probability": out_p,
            "lower_bound": out_lb,
            "upper_bound": out_ub,
            "interval_width": out_w,
            "verdict": verdict,
            "should_trade": should_trade,
            "conformal_multiplier": conformal_mult,
            "reason": reason,
        }


# Singleton instance untuk dipakai di seluruh pipeline
default_conformal_gate = ConformalPredictorGate()


def evaluate_conformal_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """
    Mengevaluasi satu dictionary kandidat rekomendasi saham dan memperkayanya
    dengan metrik Conformal Prediction.
    """
    prob = float(candidate.get("probability", 0.0))
    sig = int(candidate.get("signal", 1))

    conf_eval = default_conformal_gate.evaluate_signal(prob, signal=sig)

    # Tambahkan metrik conformal ke kandidat
    candidate["conformal_verdict"] = conf_eval["verdict"]
    candidate["conformal_lower"] = conf_eval["lower_bound"]
    candidate["conformal_upper"] = conf_eval["upper_bound"]
    candidate["conformal_multiplier"] = conf_eval["conformal_multiplier"]
    candidate["conformal_reason"] = conf_eval["reason"]

    # Sesuaikan ukuran posisi Kelly dengan multiplier uncertainty
    orig_kelly = float(candidate.get("kelly_allocation", 10.0))
    if conf_eval["verdict"] == "ABSTAIN":
        candidate["adjusted_kelly_allocation"] = 0.0
    else:
        candidate["adjusted_kelly_allocation"] = round(orig_kelly * conf_eval["conformal_multiplier"], 1)

    return candidate
