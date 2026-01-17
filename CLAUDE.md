# Investment Assistant | 投资助手

> A comprehensive personal fund investment monitoring and analysis tool.
>
> 一个全面的个人基金投资监控与分析工具。

---

## Project Overview | 项目概述

**English:**
A multi-dimensional investment analysis system that combines market data, technical analysis, sentiment indicators, and AI-powered news analysis to generate actionable investment insights.

**中文:**
一个多维度投资分析系统，结合市场数据、技术分析、情绪指标和AI驱动的新闻分析，生成可操作的投资建议。

### Key Features | 核心功能

| Feature | 功能 | Description |
|---------|------|-------------|
| Market Data | 市场数据 | A-share/US indices, north flow, sector flow |
| Technical Analysis | 技术分析 | MA trend, RSI, smart signals |
| Sentiment Analysis | 情绪分析 | Margin balance, market breadth, VIX, USD |
| News Analysis | 新闻分析 | LLM-powered sentiment & resonance detection |
| Portfolio Valuation | 持仓估值 | NAV-based & index-based calculation |
| Contextual Recommendations | 情境化建议 | Position-aware investment advice |

---

## Quick Start | 快速开始

```bash
# Activate virtual environment | 激活虚拟环境
source .venv/bin/activate

# Run full report | 运行完整报告
python run.py

# Quick mode (indices only) | 快速模式
python run.py --quick

# Skip specific modules | 跳过特定模块
python run.py --no-news          # Skip news | 跳过新闻
python run.py --no-llm           # Skip LLM analysis | 跳过LLM分析
python run.py --no-valuation     # Skip valuation | 跳过估值
python run.py --no-technical     # Skip technical | 跳过技术分析
python run.py --no-sentiment     # Skip sentiment | 跳过情绪分析

# Import Alipay bill | 导入支付宝账单
python run.py --import-bill /path/to/alipay_bill.csv

# Install dependencies | 安装依赖
pip install -r requirements.txt
```

---

## Architecture | 架构

```
run.py                      # CLI entry point | 命令行入口
├── src/market.py           # Market data collection | 市场数据采集
│   ├── A-share indices     # A股指数 (akshare)
│   ├── US indices          # 美股指数 (yfinance + akshare fallback)
│   ├── North flow          # 北向资金
│   └── Sector flow         # 行业资金流向
│
├── src/technical.py        # Technical analysis | 技术分析
│   ├── Trend analysis      # 趋势分析 (MA10/20/60, RSI)
│   ├── Smart signals       # 智能信号 (综合多因子)
│   ├── Valuation           # 估值分析 (PE/PB分位)
│   └── Recommendations     # 情境化投资建议
│
├── src/sentiment.py        # Sentiment analysis | 情绪分析
│   ├── Margin balance      # 融资余额趋势
│   ├── Market breadth      # 涨跌家数/涨停跌停
│   ├── Bond yield          # 国债收益率
│   ├── Equity-bond ratio   # 股债性价比
│   ├── VIX index           # 恐慌指数
│   └── USD/CNH             # 美元指数/离岸人民币
│
├── src/news.py             # News analysis | 新闻分析
│   ├── CLS telegraph       # 财联社电报
│   ├── CCTV news           # 新闻联播要点
│   ├── Macro data          # 宏观数据 (GDP/CPI/PMI)
│   └── LLM analysis        # AI语义分析 + 逻辑共振
│
├── src/portfolio.py        # Portfolio management | 持仓管理
│   └── Alipay bill parser  # 支付宝账单解析
│
├── src/valuation.py        # Valuation calculation | 估值计算
│   ├── NAV-based (A-share) # 净值法 (A股基金)
│   └── Index-based (QDII)  # 指数法 (QDII基金)
│
└── src/report.py           # Report generation | 报告生成
    └── Markdown output     # Markdown格式输出

config.yaml                 # Configuration | 配置文件
data/portfolio.json         # Holdings data | 持仓数据
data/data_*.json            # Daily snapshots | 每日快照
reports/report_*.md         # Generated reports | 生成的报告
```

---

## Analysis Dimensions | 分析维度

### 1. Technical Analysis | 技术分析

| Indicator | 指标 | Description | 说明 |
|-----------|------|-------------|------|
| MA Position | 均线位置 | Price vs MA10/20/60 | 价格与均线关系 |
| MA20 Slope | MA20斜率 | Trend direction | 趋势方向 |
| RSI(14) | RSI指标 | Overbought/oversold | 超买超卖 |
| Volume | 成交量 | vs 5-day average | 对比5日均量 |
| Smart Signal | 智能信号 | Multi-factor composite | 多因子综合 |

**Signal Logic | 信号逻辑:**
- Buy signals | 买入信号: Above MA20, MA20 rising, RSI < 70, volume expansion
- Sell signals | 卖出信号: Below MA20, MA20 falling, RSI > 70, volume shrinking

### 2. Sentiment Analysis | 情绪分析

| Indicator | 指标 | Source | 数据源 | Signal |
|-----------|------|--------|--------|--------|
| Margin Balance | 融资余额 | akshare | Leverage sentiment | 杠杆情绪 |
| Rise/Fall Ratio | 涨跌比 | akshare | Market breadth | 市场广度 |
| 10Y Bond Yield | 10年国债 | akshare | Risk-free rate | 无风险利率 |
| Equity-Bond Ratio | 股债性价比 | Calculated | Asset allocation | 大类配置 |
| VIX | 恐慌指数 | yfinance/akshare | Global risk | 全球风险 |
| USD Index | 美元指数 | yfinance/akshare | Capital flow | 资金流向 |

**Special Context | 特殊情境:**
When equity-bond ratio is high (>1.5) but PE percentile is also high (>70%), the system adds an explanation:
当股债性价比高(>1.5)但PE分位也高(>70%)时，系统会添加说明：

> "受无风险利率大幅下行影响，股票资产相对价值凸显，但绝对估值已处于近三年高位。建议关注利率拐点风险。"

### 3. News & LLM Analysis | 新闻与AI分析

**LLM Resonance Detection | LLM共振检测:**

The system uses LLM to analyze news against sector fund flows:
系统使用LLM分析新闻与行业资金流向的关系：

| Type | 类型 | Condition | 条件 | Implication | 含义 |
|------|------|-----------|------|-------------|------|
| Logic Resonance | 逻辑共振 | News positive + Capital inflow | 新闻利好+资金流入 | Trend sustainable | 趋势持久 |
| Capital Driven | 资金驱动 | No news + Capital inflow | 无新闻+资金流入 | May pullback | 易回调 |
| Bad News Ignored | 利空不跌 | News negative + Capital inflow | 新闻利空+资金流入 | Main force support | 主力托底 |

### 4. Contextual Recommendations | 情境化建议

Recommendations are generated based on actual holdings, not all market indices.
建议基于实际持仓生成，而非所有市场指数。

**Context Scenarios | 情境场景:**

| Context | 情境 | Condition | 条件 | Recommendation |
|---------|------|-----------|------|----------------|
| 低位机会 | Low opportunity | Undervalued + Uptrend | 低估+上升趋势 | Accumulate |
| 高位追涨 | Chasing high | Overvalued + Strong trend | 高估+强势趋势 | Small position |
| 高位风险 | High risk | Overvalued + Weak trend | 高估+弱势趋势 | Reduce |
| 底部反转 | Bottom reversal | Undervalued + Trend reversal | 低估+趋势反转 | Aggressive buy |
| 趋势延续 | Trend continues | Normal valuation + Uptrend | 中估+上升趋势 | Hold/Add |

---

## Data Sources | 数据源

| Data | 数据 | Primary | 主数据源 | Fallback | 备选方案 |
|------|------|---------|----------|----------|----------|
| A-share Indices | A股指数 | akshare (eastmoney) | akshare (sina) |
| US Indices | 美股指数 | yfinance | akshare (index_global_spot_em) |
| North Flow | 北向资金 | akshare | - |
| Margin Balance | 融资余额 | akshare (margin_sse/szse) | akshare (margin_account_info) |
| Bond Yield | 国债收益率 | akshare (bond_zh_us_rate) | - |
| VIX | 恐慌指数 | yfinance | akshare (index_global_spot_em) |
| USD Index | 美元指数 | yfinance | akshare (index_global_spot_em) |
| News | 新闻 | akshare (CLS, CCTV) | - |

---

## Configuration | 配置

### config.yaml

```yaml
# Tracked indices | 跟踪指数
indices:
  a_share:
    - code: "000300"    # CSI 300 | 沪深300
      name: "沪深300"
    - code: "000688"    # STAR 50 | 科创50
      name: "科创50"
  us_stock:
    - code: "^GSPC"     # S&P 500 | 标普500
      name: "标普500"

# Fund-to-index mapping | 基金指数映射
fund_index_mapping:
  "022746":              # Fund code | 基金代码
    index_code: "000510" # Tracked index | 跟踪指数
    index_name: "中证A500"
    tracking_ratio: 1.15 # Enhanced ratio | 增强比例
  "017639":
    index_code: "^GSPC"
    index_name: "标普500"
    market: "us"         # For QDII funds | QDII基金标记
```

### Environment Variables | 环境变量

For LLM analysis (optional):
用于LLM分析（可选）：

```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"  # Or compatible endpoint
export LLM_MODEL="gpt-4o-mini"
```

---

## Report Sections | 报告章节

1. **市场指数** - A-share and US indices with price and change
2. **趋势分析** - Technical indicators and smart signals
3. **投资建议** - Contextual recommendations for holdings
4. **估值分析** - PE/PB percentiles
5. **资金流向** - North flow and sector flow
6. **市场情绪** - Margin, breadth, bond yield, global linkage
7. **今日要闻** - News with LLM analysis and resonance

---

## Analysis Workflow | 分析流程

When analyzing investments:
分析投资时：

1. Read today's report | 阅读今日报告: `reports/report_YYYY-MM-DD.md`
2. Check holdings | 检查持仓: `data/portfolio.json`
3. Consider dimensions | 考虑维度:
   - Technical trend | 技术趋势
   - Valuation level | 估值水平
   - Capital flow | 资金流向
   - Sentiment indicators | 情绪指标
   - News resonance | 新闻共振
4. Provide advice with disclaimer | 提供建议并附免责声明

> **Disclaimer | 免责声明:**
> This tool is for personal reference only and does not constitute investment advice.
> 本工具仅供个人参考，不构成投资建议。

---

## Troubleshooting | 故障排除

| Issue | 问题 | Solution | 解决方案 |
|-------|------|----------|----------|
| yfinance rate limited | yfinance限流 | System auto-fallbacks to akshare | 系统自动切换到akshare |
| Margin balance shows 0 | 融资余额显示0 | Display "数据未更新" | 显示"数据未更新" |
| LLM analysis fails | LLM分析失败 | Use `--no-llm` flag | 使用 `--no-llm` 参数 |
| Macro data outdated | 宏观数据过旧 | Data sorted by date before extraction | 数据按日期排序后提取 |

---

## Dependencies | 依赖

- Python 3.10+
- akshare >= 1.18
- yfinance
- pandas
- pyyaml
- openai (optional, for LLM)
