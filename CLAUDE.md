# 投资助手 - Claude Code 协作指南

## 项目概述

这是一个个人基金投资辅助系统，用于：
- 每日采集市场数据（A股/美股指数、资金流向）
- 管理基金持仓（支持支付宝账单导入）
- 生成分析报告供决策参考

## 使用流程

### 每日操作流程（建议下午2点左右）

1. **运行数据采集**
   ```bash
   cd /Users/mt/IdeaProjects/invest
   source .venv/bin/activate
   python run.py
   ```

2. **查看生成的报告**
   - 报告位置: `reports/report_YYYY-MM-DD.md`
   - 原始数据: `data/data_YYYY-MM-DD.json`

3. **与 Claude 讨论**
   - 读取今日报告后，Claude 可以帮助分析市场情况
   - 结合持仓情况给出操作建议

### 常用命令

```bash
# 完整报告（含估值、新闻、资金流向）
python run.py

# 快速模式（只看指数，跳过估值和新闻）
python run.py --quick

# 跳过新闻收集（加快速度）
python run.py --no-news

# 跳过估值计算（如果只关心市场数据）
python run.py --no-valuation

# 导入支付宝账单
python run.py --import-bill /path/to/alipay_bill.csv

# 只打印不保存
python run.py --print-only
```

## 配置说明

配置文件: `config.yaml`

### 关注的指数

```yaml
indices:
  a_share:
    - code: "000300"    # 沪深300
    - code: "000688"    # 科创50
    - code: "930050"    # 中证A500
  us_stock:
    - code: "^GSPC"     # 标普500
    - code: "^IXIC"     # 纳斯达克
```

### 手动维护持仓

在 `config.yaml` 中添加：

```yaml
portfolio:
  "000001": 1000.00    # 基金代码: 持有份额
  "110011": 500.00
```

或导入支付宝账单后自动保存到 `data/portfolio.json`

## 数据来源

- **A股指数**: 东方财富 (via akshare)
- **美股指数**: Yahoo Finance (via yfinance)
- **资金流向**: 东方财富 (via akshare)
- **基金估值**: 东方财富 (via akshare)

## 分析辅助

当用户请求分析时，Claude 应该：

1. **先读取今日报告**
   ```
   Read reports/report_YYYY-MM-DD.md
   ```

2. **了解用户持仓**
   ```
   Read data/portfolio.json
   ```

3. **提供分析时考虑**
   - 大盘整体走势（上证、深证、创业板）
   - 重点指数表现（中证A500、科创50、沪深300）
   - 美股隔夜表现对A股的影响
   - 北向资金动向
   - 行业板块轮动
   - 用户持仓的关联板块

4. **给出建议时注明**
   - 这是基于公开数据的分析
   - 不构成投资建议
   - 最终决策需要用户自行判断

## 典型对话示例

用户: "今天市场怎么样？我该加仓还是减仓？"

Claude 应该:
1. 读取今日报告
2. 分析市场数据
3. 结合用户持仓给出客观分析
4. 提供多种情景下的操作思路
5. 提醒风险因素

## 文件结构

```
invest/
├── run.py              # 主入口
├── config.yaml         # 配置文件
├── CLAUDE.md          # 本文件
├── src/
│   ├── market.py      # 市场数据采集（指数、资金流向）
│   ├── portfolio.py   # 持仓管理（支付宝账单导入）
│   ├── valuation.py   # 估值计算（历史净值、份额估算）
│   ├── news.py        # 新闻收集（财联社、新闻联播、宏观数据）
│   └── report.py      # 报告生成
├── data/
│   ├── portfolio.json # 持仓数据
│   └── data_*.json    # 历史原始数据
└── reports/
    └── report_*.md    # 历史报告
```

## 注意事项

- 数据采集依赖网络，可能因接口限制偶尔失败
- 美股数据有延迟（非实时）
- 基金估值为盘中估算，与实际净值可能有偏差
- 政策信息需要人工关注，脚本暂不自动抓取

## 依赖安装

```bash
cd /Users/mt/IdeaProjects/invest
source .venv/bin/activate
pip install akshare yfinance pyyaml pandas
```
