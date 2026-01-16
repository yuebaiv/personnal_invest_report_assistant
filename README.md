# Fund Investment Monitor

一个基于 Python 的基金投资监控工具，支持从支付宝账单导入持仓，自动计算收益，生成每日投资报告。

## 功能特点

- **支付宝账单导入**：自动解析支付宝交易明细，提取基金买入记录
- **精准收益计算**：
  - A股基金：基于实际基金净值计算，考虑净值确认日期（T+1规则）
  - QDII基金：基于跟踪指数估算，避免净值更新延迟问题
- **实时市场数据**：获取A股、美股指数实时行情
- **资金流向分析**：北向资金、行业板块资金流向
- **财经新闻聚合**：财联社、东方财富等多源新闻
- **每日报告生成**：Markdown格式，方便阅读和分享

## 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/fund-monitor.git
cd fund-monitor

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

## 快速开始

### 1. 导入支付宝账单

从支付宝APP导出交易明细CSV文件，然后运行：

```bash
python run.py --import-bill 支付宝交易明细.csv
```

### 2. 生成每日报告

```bash
python run.py
```

报告将保存到 `reports/report_YYYY-MM-DD.md`

## 配置说明

编辑 `config.yaml` 配置基金与指数的映射关系：

```yaml
fund_index_mapping:
  # A股基金 - 使用净值计算
  "022746":  # 博道中证A500指数增强C
    index_code: "000510"
    index_name: "中证A500"
    tracking_ratio: 1.15  # 增强型基金超额收益系数

  # QDII基金 - 使用指数估算
  "017639":  # 摩根标普500指数(QDII)C
    index_code: "^GSPC"
    index_name: "标普500"
    tracking_ratio: 0.95
    market: "us"  # 标记为美股QDII
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `index_code` | 跟踪指数代码（A股用数字代码，美股用Yahoo Finance代码） |
| `index_name` | 指数名称，用于报告显示 |
| `tracking_ratio` | 跟踪系数，增强型基金可设为>1 |
| `market` | 设为 `"us"` 表示美股QDII，将使用指数估算而非净值 |

## 项目结构

```
fund-monitor/
├── run.py              # 主入口
├── config.yaml         # 配置文件
├── requirements.txt    # 依赖列表
├── src/
│   ├── market.py       # 市场数据获取（指数、资金流向）
│   ├── news.py         # 财经新闻聚合
│   ├── portfolio.py    # 持仓管理、账单解析
│   ├── valuation.py    # 估值计算核心逻辑
│   └── report.py       # 报告生成
├── data/
│   └── portfolio.json  # 持仓数据（自动生成）
└── reports/
    └── report_*.md     # 每日报告
```

## 估值计算逻辑

### A股基金

使用基金实际净值计算，流程：

1. 根据下单时间确定净值确认日期
   - 交易日 15:00 前下单 → 当日净值
   - 交易日 15:00 后或非交易日 → 下一交易日净值
2. 获取确认日净值，计算买入份额
3. 当前市值 = 总份额 × 最新净值

### QDII基金

QDII基金净值更新有延迟（T+2或更久），使用跟踪指数估算：

1. 获取每笔买入日的指数点位
2. 计算从买入日到今天的指数涨跌幅
3. 估算市值 = 买入金额 × (1 + 指数涨跌幅 × 跟踪系数)

## 报告示例

```markdown
## 持仓分析

### 总览

- 总投入: ¥8,300.00
- 估算市值: **¥8,387.37**
- 累计盈亏: 📈 **¥87.37** (+1.05%)
- 今日估算: 📈 **¥25.61** (+0.31%)

### 持仓明细

| 基金名称 | 估算市值 | 累计盈亏 | 今日估算 | 跟踪指数 |
|----------|----------|----------|----------|----------|
| 易方达科创50联接C | ¥3,046.95 | +1.57% | +1.28% | 科创50 |
| 博道中证A500指数增强C | ¥2,738.21 | +1.42% | -0.49% | 中证A500 |
| ... | ... | ... | ... | ... |
```

## 数据来源

- **A股数据**：[AKShare](https://github.com/akfamily/akshare)
- **美股数据**：[yfinance](https://github.com/ranaroussi/yfinance)
- **新闻数据**：财联社、东方财富

## 注意事项

1. 本工具仅供个人投资参考，不构成投资建议
2. 估值计算存在误差，实际收益以基金公司公布为准
3. 增强型基金的超额收益不稳定，`tracking_ratio` 需根据实际情况调整
4. 首次运行需要下载较多数据，请耐心等待

## License

MIT License
