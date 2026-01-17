<p align="center">
  <h1 align="center">Fund Investment Assistant</h1>
  <h3 align="center">基金投资助手</h3>
  <p align="center">
    A comprehensive multi-dimensional investment analysis system<br/>
    一个全面的多维度投资分析系统
  </p>
</p>

<p align="center">
  <a href="#features--功能特点">Features</a> •
  <a href="#installation--安装">Installation</a> •
  <a href="#quick-start--快速开始">Quick Start</a> •
  <a href="#configuration--配置">Configuration</a> •
  <a href="#architecture--架构">Architecture</a> •
  <a href="#license">License</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License"/>
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"/>
</p>

---

## Overview | 概述

**English:**
Fund Investment Assistant is a Python-based personal investment monitoring tool that combines market data, technical analysis, sentiment indicators, and AI-powered news analysis to generate actionable investment insights. It supports importing holdings from Alipay bills and generates comprehensive daily reports.

**中文:**
基金投资助手是一个基于 Python 的个人投资监控工具，结合市场数据、技术分析、情绪指标和 AI 驱动的新闻分析，生成可操作的投资建议。支持从支付宝账单导入持仓，并生成全面的每日报告。

---

## Features | 功能特点

### Core Features | 核心功能

| Feature | 功能 | Description | 描述 |
|---------|------|-------------|------|
| 📊 Market Data | 市场数据 | A-share/US indices, north flow, sector flow | A股/美股指数、北向资金、行业资金流 |
| 📈 Technical Analysis | 技术分析 | MA trend, RSI, smart multi-factor signals | 均线趋势、RSI、智能多因子信号 |
| 🎭 Sentiment Analysis | 情绪分析 | Margin balance, market breadth, VIX, USD | 融资余额、涨跌家数、VIX、美元指数 |
| 🤖 AI News Analysis | AI新闻分析 | LLM-powered sentiment & resonance detection | LLM情感分析与逻辑共振检测 |
| 💰 Portfolio Valuation | 持仓估值 | NAV-based (A-share) & index-based (QDII) | 净值法与指数估算法 |
| 🎯 Smart Recommendations | 智能建议 | Context-aware, position-based advice | 情境化、基于持仓的投资建议 |

### Analysis Dimensions | 分析维度

```
┌─────────────────────────────────────────────────────────────────┐
│                    Investment Analysis System                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Technical   │  │  Sentiment   │  │     News     │          │
│  │  Analysis    │  │  Analysis    │  │   Analysis   │          │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤          │
│  │ • MA Trend   │  │ • Margin     │  │ • CLS News   │          │
│  │ • RSI        │  │ • Breadth    │  │ • CCTV       │          │
│  │ • Volume     │  │ • Bond Yield │  │ • Macro Data │          │
│  │ • Valuation  │  │ • VIX/USD    │  │ • LLM Analyze│          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └─────────────────┼─────────────────┘                   │
│                           ▼                                     │
│              ┌────────────────────────┐                        │
│              │  Contextual            │                        │
│              │  Recommendations       │                        │
│              │  情境化投资建议         │                        │
│              └────────────────────────┘                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### LLM Resonance Detection | LLM共振检测

The system uses AI to analyze the relationship between news and capital flows:

系统使用AI分析新闻与资金流向的关系：

| Type | 类型 | Condition | Implication |
|------|------|-----------|-------------|
| 🟢 Logic Resonance | 逻辑共振 | News + Capital aligned | Trend sustainable |
| 🟡 Capital Driven | 资金驱动 | No news support | May pullback |
| ⚡ Bad News Ignored | 利空不跌 | Bad news + Inflow | Main force support |

---

## Installation | 安装

### Requirements | 环境要求

- Python 3.10+
- pip

### Steps | 步骤

```bash
# Clone the repository | 克隆仓库
git clone https://github.com/yourusername/invest.git
cd invest

# Create virtual environment | 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or .venv\Scripts\activate  # Windows

# Install dependencies | 安装依赖
pip install -r requirements.txt
```

### Optional: LLM Setup | 可选：LLM配置

For AI-powered news analysis, set environment variables:

如需AI新闻分析，配置环境变量：

```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"  # Or compatible endpoint
export LLM_MODEL="gpt-4o-mini"
```

---

## Quick Start | 快速开始

### 1. Import Alipay Bill | 导入支付宝账单

Export transaction history CSV from Alipay app, then run:

从支付宝APP导出交易明细CSV文件，然后运行：

```bash
python run.py --import-bill 支付宝交易明细.csv
```

### 2. Generate Daily Report | 生成每日报告

```bash
# Full report (all features) | 完整报告
python run.py

# Quick mode (indices only) | 快速模式
python run.py --quick

# Skip specific modules | 跳过特定模块
python run.py --no-news        # Skip news | 跳过新闻
python run.py --no-llm         # Skip LLM | 跳过AI分析
python run.py --no-sentiment   # Skip sentiment | 跳过情绪分析
python run.py --no-technical   # Skip technical | 跳过技术分析
python run.py --no-valuation   # Skip valuation | 跳过估值
```

Reports are saved to `reports/report_YYYY-MM-DD.md`

报告保存到 `reports/report_YYYY-MM-DD.md`

---

## Report Preview | 报告预览

### Investment Recommendations | 投资建议

```markdown
| 指数 | 建议 | 情境 | 信心 | 趋势 | 估值 | 仓位 | 风险 |
|------|------|------|------|------|------|------|------|
| 科创50 | ⚪ 持有观望 | 方向不明 | ●●○○○ | 强势 | 未知 | 重仓 | 🟢低 |
| 中证A500 | ⚪ 持有观望 | 方向不明 | ●●○○○ | 强势 | 未知 | 重仓 | 🟢低 |
| 沪深300 | 🟡 小仓试探 | 高位追涨 | ●●○○○ | 强势 | 高估(97%) | 轻仓 | 🟡中 |
```

### Market Sentiment | 市场情绪

```markdown
### 无风险利率

- 中国10年国债收益率: **1.84%**
- 股债性价比(沪深300): 🟢 **4.06** (极具吸引力)

> ⚠️ **特殊情境说明**: 受无风险利率大幅下行影响(10年国债1.84%)，
> 股票资产相对价值凸显(股债比4.06)，但绝对估值已处于近三年97%分位。
```

### LLM Resonance Analysis | LLM共振分析

```markdown
**行业逻辑共振分析:**

| 行业 | 类型 | 分析 |
|------|------|------|
| 半导体 | 🟢 逻辑共振 | 新闻利好(AI芯片)+资金流入142亿，趋势较持久 |
| 软件开发 | 🟡 资金驱动 | 无明显新闻支撑但资金流出，谨慎观望 |
```

---

## Configuration | 配置

### config.yaml

```yaml
# Tracked indices | 跟踪指数
indices:
  a_share:
    - code: "000300"
      name: "沪深300"
    - code: "000688"
      name: "科创50"
    - code: "000510"
      name: "中证A500"
  us_stock:
    - code: "^GSPC"
      name: "标普500"
    - code: "^IXIC"
      name: "纳斯达克"

# Fund-to-index mapping | 基金指数映射
fund_index_mapping:
  # A-share funds (NAV-based) | A股基金（净值法）
  "022746":                    # Fund code | 基金代码
    index_code: "000510"       # Tracked index | 跟踪指数
    index_name: "中证A500"
    tracking_ratio: 1.15       # Enhanced ratio | 增强系数

  # QDII funds (index-based) | QDII基金（指数法）
  "017639":
    index_code: "^GSPC"
    index_name: "标普500"
    tracking_ratio: 0.95
    market: "us"               # Mark as QDII | 标记为QDII
```

### Parameter Description | 参数说明

| Parameter | 参数 | Description | 说明 |
|-----------|------|-------------|------|
| `index_code` | 指数代码 | A-share: numeric, US: Yahoo symbol | A股数字代码，美股Yahoo代码 |
| `index_name` | 指数名称 | Display name in reports | 报告显示名称 |
| `tracking_ratio` | 跟踪系数 | >1 for enhanced funds | 增强型基金>1 |
| `market` | 市场类型 | Set `"us"` for QDII | QDII基金设为`"us"` |

---

## Architecture | 架构

```
invest/
├── run.py                 # CLI entry point | 命令行入口
├── config.yaml            # Configuration | 配置文件
├── requirements.txt       # Dependencies | 依赖列表
│
├── src/
│   ├── market.py          # Market data (indices, north flow, sectors)
│   │                      # 市场数据（指数、北向资金、板块）
│   │
│   ├── technical.py       # Technical analysis (MA, RSI, signals, recommendations)
│   │                      # 技术分析（均线、RSI、信号、建议）
│   │
│   ├── sentiment.py       # Sentiment (margin, breadth, VIX, USD, bond)
│   │                      # 情绪分析（融资、涨跌、VIX、美元、国债）
│   │
│   ├── news.py            # News collection & LLM analysis
│   │                      # 新闻采集与LLM分析
│   │
│   ├── portfolio.py       # Portfolio management, Alipay parser
│   │                      # 持仓管理、支付宝解析
│   │
│   ├── valuation.py       # NAV & index-based valuation
│   │                      # 净值与指数估值计算
│   │
│   └── report.py          # Markdown report generation
│                          # Markdown报告生成
│
├── data/
│   ├── portfolio.json     # Holdings data | 持仓数据
│   └── data_*.json        # Daily snapshots | 每日快照
│
└── reports/
    └── report_*.md        # Generated reports | 生成报告
```

---

## Valuation Logic | 估值逻辑

### A-Share Funds | A股基金

Uses actual NAV history:

使用实际基金净值：

```
1. Determine NAV confirmation date (T+1 rule)
   确定净值确认日期（T+1规则）
   - Before 15:00 on trading day → Same day NAV
   - After 15:00 or non-trading day → Next trading day NAV

2. Calculate shares = Amount / Confirmation NAV
   计算份额 = 金额 / 确认日净值

3. Market value = Total shares × Latest NAV
   市值 = 总份额 × 最新净值
```

### QDII Funds | QDII基金

Uses tracking index estimation (NAV delayed T+2+):

使用跟踪指数估算（净值延迟T+2+）：

```
1. Get index price at purchase date
   获取买入日指数点位

2. Calculate index change to today
   计算到今日的指数涨跌幅

3. Market value = Amount × (1 + Index change × Tracking ratio)
   市值 = 金额 × (1 + 指数涨跌幅 × 跟踪系数)
```

---

## Data Sources | 数据源

| Data | Source | Fallback |
|------|--------|----------|
| A-share indices | akshare (eastmoney) | akshare (sina) |
| US indices | yfinance | akshare |
| North flow | akshare | - |
| Margin balance | akshare | - |
| Bond yield | akshare | - |
| VIX | yfinance | akshare |
| USD index | yfinance | akshare |
| News | akshare (CLS, CCTV) | - |

---

## Troubleshooting | 故障排除

| Issue | Solution |
|-------|----------|
| yfinance rate limited | System auto-fallbacks to akshare |
| Margin balance shows 0 | Displays "数据未更新" instead |
| LLM analysis fails | Use `--no-llm` flag |
| Macro data outdated | Fixed: data sorted by date |
| Import error | Check CSV encoding (UTF-8) |

---

## Contributing | 贡献

Contributions are welcome! Please feel free to submit a Pull Request.

欢迎贡献！请随时提交 Pull Request。

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## Disclaimer | 免责声明

**English:**
This tool is for personal reference only and does not constitute investment advice. The valuation calculations may have errors, and actual returns are subject to the fund company's announcements. Please make investment decisions based on your own judgment.

**中文:**
本工具仅供个人投资参考，不构成投资建议。估值计算存在误差，实际收益以基金公司公布为准。请根据自身判断做出投资决策。

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

<p align="center">
  Made with ❤️ for personal investment tracking
</p>
