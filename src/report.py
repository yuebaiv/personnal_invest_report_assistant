"""
报告生成模块
生成每日市场分析报告 (Markdown 格式)
"""

import json
from datetime import datetime
from pathlib import Path


def format_change(value: float, with_sign: bool = True) -> str:
    """格式化涨跌幅"""
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%" if with_sign else f"{value:.2f}%"


def format_amount(value: float) -> str:
    """格式化金额（亿为单位）"""
    if value is None:
        return "N/A"
    if abs(value) >= 10000:
        return f"{value/10000:.2f}万亿"
    return f"{value:.2f}亿"


def generate_market_section(indices_data: dict) -> str:
    """生成市场指数部分"""
    lines = ["## 市场指数\n"]

    # A股指数
    lines.append("### A股指数\n")
    lines.append("| 指数 | 点位 | 涨跌幅 | 成交额 |")
    lines.append("|------|------|--------|--------|")

    for idx in indices_data.get('a_share', []):
        if 'error' in idx:
            lines.append(f"| {idx['name']} | - | 获取失败 | - |")
        else:
            amount = format_amount(idx.get('amount', 0) / 100000000) if idx.get('amount') else "-"
            lines.append(
                f"| {idx['name']} | {idx.get('price', 'N/A'):.2f} | "
                f"{format_change(idx.get('change_pct'))} | {amount} |"
            )

    # 美股指数
    lines.append("\n### 美股指数\n")
    lines.append("| 指数 | 点位 | 涨跌幅 |")
    lines.append("|------|------|--------|")

    for idx in indices_data.get('us_stock', []):
        if 'error' in idx:
            lines.append(f"| {idx['name']} | - | 获取失败 |")
        else:
            lines.append(
                f"| {idx['name']} | {idx.get('price', 'N/A'):.2f} | "
                f"{format_change(idx.get('change_pct'))} |"
            )

    return "\n".join(lines)


def generate_flow_section(north_flow: dict, sector_flow: list) -> str:
    """生成资金流向部分"""
    lines = ["## 资金流向\n"]

    # 北向资金
    lines.append("### 北向资金\n")
    if 'error' in north_flow:
        lines.append(f"数据获取失败: {north_flow['error']}\n")
    else:
        net = north_flow.get('net_inflow', 0)
        direction = "流入" if net > 0 else "流出"
        lines.append(f"- 今日净{direction}: **{abs(net):.2f}亿**\n")

    # 行业板块
    if sector_flow and not any('error' in s for s in sector_flow):
        lines.append("### 行业板块资金流向\n")

        inflows = [s for s in sector_flow if s.get('type') == 'inflow']
        outflows = [s for s in sector_flow if s.get('type') == 'outflow']

        if inflows:
            lines.append("**主力净流入 TOP:**\n")
            for s in inflows[:5]:
                lines.append(f"- {s['name']}: {format_change(s.get('change_pct'))} (净流入 {format_amount(s.get('net_flow', 0))})")

        if outflows:
            lines.append("\n**主力净流出 TOP:**\n")
            for s in outflows[:5]:
                lines.append(f"- {s['name']}: {format_change(s.get('change_pct'))} (净流出 {format_amount(abs(s.get('net_flow', 0)))})")

    return "\n".join(lines)


def generate_portfolio_section(portfolio_data: dict) -> str:
    """生成持仓分析部分"""
    if not portfolio_data or not portfolio_data.get('details'):
        return "## 持仓分析\n\n暂无持仓数据，请在 config.yaml 中配置或导入支付宝账单。\n"

    lines = ["## 持仓分析\n"]

    # 总览
    lines.append("### 总览\n")
    lines.append(f"- 总市值: **¥{portfolio_data['total_value']:,.2f}**")
    lines.append(f"- 总成本: ¥{portfolio_data['total_cost']:,.2f}")
    lines.append(f"- 总盈亏: **{format_change(portfolio_data['total_profit_pct'])}** (¥{portfolio_data['total_profit']:,.2f})\n")

    # 明细
    lines.append("### 持仓明细\n")
    lines.append("| 基金 | 今日涨跌 | 持有市值 | 盈亏 |")
    lines.append("|------|----------|----------|------|")

    for fund in portfolio_data['details']:
        lines.append(
            f"| {fund['name'] or fund['code']} | {format_change(fund.get('day_change_pct'))} | "
            f"¥{fund['value']:,.2f} | {format_change(fund.get('profit_pct'))} |"
        )

    return "\n".join(lines)


def generate_analysis_prompt(indices_data: dict, north_flow: dict, portfolio_data: dict) -> str:
    """生成给 Claude 的分析提示"""
    lines = ["## 分析要点\n"]
    lines.append("基于以上数据，请帮我分析：\n")
    lines.append("1. **市场情绪**: 今日市场整体表现如何？有什么特点？")
    lines.append("2. **资金动向**: 北向资金和行业资金流向反映了什么？")
    lines.append("3. **持仓建议**: 结合市场情况，我的持仓应该如何操作？")
    lines.append("4. **风险提示**: 需要关注哪些风险因素？\n")

    return "\n".join(lines)


def generate_daily_report(
    indices_data: dict,
    north_flow: dict = None,
    sector_flow: list = None,
    portfolio_data: dict = None,
    output_dir: str = "reports"
) -> str:
    """生成完整的每日报告"""

    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# 每日投资报告 - {today}\n",
        f"> 生成时间: {now}\n",
        "---\n",
    ]

    # 市场指数
    lines.append(generate_market_section(indices_data))
    lines.append("\n---\n")

    # 资金流向
    if north_flow or sector_flow:
        lines.append(generate_flow_section(north_flow or {}, sector_flow or []))
        lines.append("\n---\n")

    # 持仓分析
    if portfolio_data:
        lines.append(generate_portfolio_section(portfolio_data))
        lines.append("\n---\n")

    # 分析提示
    lines.append(generate_analysis_prompt(indices_data, north_flow or {}, portfolio_data or {}))

    report = "\n".join(lines)

    # 保存报告
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filename = f"report_{today}.md"
    filepath = output_path / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"报告已保存到: {filepath}")

    return report


def save_raw_data(data: dict, output_dir: str = "data") -> str:
    """保存原始数据为 JSON"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"data_{today}.json"
    filepath = output_path / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    return str(filepath)
