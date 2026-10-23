"""
Unit tests for Pre-Market Commodity Cues.
"""

from unittest.mock import patch

import pandas as pd

from src.collector.commodity_cues import (
    get_global_commodity_cues,
    get_ticker_commodity_boost,
)


def test_get_ticker_commodity_boost_empty():
    boost = get_ticker_commodity_boost("ADRO", None)
    assert boost == 0.0


@patch("src.collector.commodity_cues.download_with_timeout")
def test_commodity_cues_bullish(mock_dl):
    # Simulasi harga komoditas naik +3%
    mock_df = pd.DataFrame({"Close": [100.0, 103.5]})
    mock_dl.return_value = mock_df

    cues = get_global_commodity_cues()
    assert cues["status"] == "success"
    assert "COAL" in cues["cues"]
    assert cues["cues"]["COAL"]["booster"] > 0
    # Saham batubara harus mendapatkan booster positif
    adro_boost = get_ticker_commodity_boost("ADRO", cues)
    assert adro_boost > 0
