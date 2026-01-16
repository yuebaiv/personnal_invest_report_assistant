# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A personal fund investment monitoring tool that:
- Collects daily market data (A-share/US indices, capital flow)
- Manages fund holdings (supports Alipay bill import)
- Generates analysis reports for investment decisions

## Development Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Run full report (with valuation, news, capital flow)
python run.py

# Quick mode (indices only, skip valuation and news)
python run.py --quick

# Skip news collection
python run.py --no-news

# Skip valuation calculation
python run.py --no-valuation

# Import Alipay fund bill
python run.py --import-bill /path/to/alipay_bill.csv

# Print only (no file save)
python run.py --print-only

# Install dependencies
pip install -r requirements.txt
```

## Architecture

```
run.py                    # CLI entry point, orchestrates all modules
├── src/market.py         # Market data: A-share/US indices, north flow, sector flow
├── src/portfolio.py      # Holdings: Alipay bill parsing, fund code lookup
├── src/valuation.py      # Valuation: NAV-based (A-share) or index-based (QDII)
├── src/news.py           # News: CCTV, CLS telegraph, macro data
└── src/report.py         # Report: Markdown generation

config.yaml               # Index list, fund-index mapping, tracking ratios
data/portfolio.json       # Imported holdings data
data/data_*.json          # Daily raw data snapshots
reports/report_*.md       # Generated daily reports
```

### Valuation Logic

**A-share funds**: Use actual NAV history
- Calculate NAV confirmation date (T+1 rule based on order time)
- Compute shares = amount / confirmation NAV
- Market value = total shares × current NAV

**QDII funds** (US market): Use tracking index estimation
- NAV updates are delayed (T+2+), so index estimation is more accurate
- Market value = amount × (1 + index change × tracking_ratio)

The `fund_index_mapping` in `config.yaml` defines which index each fund tracks and the tracking ratio (>1 for enhanced index funds).

### Data Sources

- **A-share**: akshare (eastmoney)
- **US stocks**: yfinance
- **News**: akshare (CLS, CCTV, macro data)

## Analysis Workflow

When user requests analysis, Claude should:

1. Read today's report: `reports/report_YYYY-MM-DD.md`
2. Read holdings: `data/portfolio.json`
3. Consider: market trends, north flow, sector rotation, US market impact
4. Provide analysis with disclaimer that this is based on public data and does not constitute investment advice

## Configuration

Key settings in `config.yaml`:

```yaml
# Tracked indices
indices:
  a_share:
    - code: "000300"      # CSI 300
    - code: "000688"      # STAR 50
  us_stock:
    - code: "^GSPC"       # S&P 500

# Fund-to-index mapping for valuation
fund_index_mapping:
  "022746":               # Fund code
    index_code: "000510"  # Tracked index
    tracking_ratio: 1.15  # Enhanced fund ratio
    market: "us"          # Only for QDII funds
```