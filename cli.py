#!/usr/bin/env python
"""
IDX Quant AI - CLI Entry Point Wrapper
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main_cli import main

if __name__ == "__main__":
    main()
