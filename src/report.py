"""
报告生成模块
生成每日市场分析报告 (Markdown 格式)
"""

import json
import math
from datetime import datetime
from pathlib import Path


def is_nan(value) -> bool:
    """检查值是否为 NaN"""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def format_change(value: float, with_sign: bool = True) -> str:
    """格式化涨跌幅"""
    if is_nan(value):
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%" if with_sign else f"{value:.2f}%"


def format_amount(value: float, unit: str = "亿") -> str:
    """
    格式化金额

    value: 金额数值
    unit: 输入单位
      - "亿": 输入已经是亿元
      - "万": 输入是万元
      - "元": 输入是元
    """
    if is_nan(value):
        return "N/A"

    # 统一转换为亿元
    if unit == "万":
        value = value / 10000  # 万元转亿元
    elif unit == "元":
        value = value / 100000000  # 元转亿元

    if abs(value) >= 10000:
        return f"{value/10000:.2f}万亿"
    elif abs(value) >= 1:
        return f"{value:.2f}亿"
    else:
        return f"{value*10000:.0f}万"


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
        lines.append(f"- 数据获取失败: {north_flow['error']}\n")
    else:
        net = north_flow.get('net_inflow', 0)
        if is_nan(net):
            lines.append("- 今日数据暂无\n")
        elif net == 0:
            # 0 可能表示数据尚未更新
            lines.append("- 今日数据更新中...\n")
        else:
            direction = "流入" if net > 0 else "流出"
            lines.append(f"- 今日净{direction}: **{abs(net):.2f}亿**\n")
            # 显示沪深港通明细
            detail = north_flow.get('detail')
            if detail:
                hu = detail.get('沪股通', 0)
                shen = detail.get('深股通', 0)
                lines.append(f"  - 沪股通: {hu:+.2f}亿 | 深股通: {shen:+.2f}亿\n")

    # 行业板块
    if sector_flow and not any('error' in s for s in sector_flow):
        lines.append("### 行业板块资金流向\n")

        inflows = [s for s in sector_flow if s.get('type') == 'inflow']
        outflows = [s for s in sector_flow if s.get('type') == 'outflow']

        if inflows:
            lines.append("**主力净流入 TOP:**\n")
            for s in inflows[:5]:
                # 行业资金流数据单位是元
                lines.append(f"- {s['name']}: {format_change(s.get('change_pct'))} (净流入 {format_amount(s.get('net_flow', 0), '元')})")

        if outflows:
            lines.append("\n**主力净流出 TOP:**\n")
            for s in outflows[:5]:
                lines.append(f"- {s['name']}: {format_change(s.get('change_pct'))} (净流出 {format_amount(abs(s.get('net_flow', 0)), '元')})")

    return "\n".join(lines)


def generate_portfolio_section(portfolio_data: dict) -> str:
    """生成持仓分析部分（支持估值数据和今日估算）"""
    if not portfolio_data:
        return "## 持仓分析\n\n暂无持仓数据，请先导入支付宝账单:\n```\npython run.py --import-bill <账单文件.csv>\n```\n"

    funds = portfolio_data.get('funds', [])
    summary = portfolio_data.get('summary', {})

    if not funds:
        return "## 持仓分析\n\n暂无持仓数据。\n"

    lines = ["## 持仓分析\n"]

    # 总览 - 根据是否有估值数据显示不同内容
    lines.append("### 总览\n")

    has_valuation = 'total_market_value' in summary
    has_today_estimate = 'today_estimated_profit' in summary

    if has_valuation:
        total_invested = summary.get('total_invested', 0)
        total_market_value = summary.get('total_market_value', 0)
        total_profit = summary.get('total_profit', 0)
        total_profit_pct = summary.get('total_profit_pct', 0)

        lines.append(f"- 总投入: ¥{total_invested:,.2f}")
        lines.append(f"- 估算市值: **¥{total_market_value:,.2f}**")
        profit_color = "📈" if total_profit >= 0 else "📉"
        lines.append(f"- 累计盈亏: {profit_color} **¥{total_profit:,.2f}** ({format_change(total_profit_pct)})")

        # 显示今日估算盈亏（基于指数）
        if has_today_estimate:
            today_profit = summary.get('today_estimated_profit', 0)
            today_pct = summary.get('today_estimated_pct', 0)
            today_color = "📈" if today_profit >= 0 else "📉"
            lines.append(f"- 今日估算: {today_color} **¥{today_profit:,.2f}** ({format_change(today_pct)}) *")

        lines.append(f"- 持有基金: {summary.get('fund_count', len(funds))} 只\n")

        if has_today_estimate:
            lines.append("> \\* 今日估算基于跟踪指数实时涨跌推算，实际以基金公司公布净值为准\n")
    else:
        lines.append(f"- 净投入: **¥{summary.get('net_invested', 0):,.2f}**")
        lines.append(f"- 总投入: ¥{summary.get('total_invested', 0):,.2f}")
        lines.append(f"- 总赎回: ¥{summary.get('total_redeemed', 0):,.2f}")
        lines.append(f"- 持有基金: {summary.get('fund_count', len(funds))} 只\n")
        lines.append("> 注: 市值和盈亏为估算值，基于历史净值推算份额\n")

    # 明细
    lines.append("### 持仓明细\n")

    if has_valuation:
        # 检查是否有今日估算数据
        if has_today_estimate:
            lines.append("| 基金名称 | 估算市值 | 累计盈亏 | 今日估算 | 跟踪指数 |")
            lines.append("|----------|----------|----------|----------|----------|")
        else:
            lines.append("| 基金名称 | 估算市值 | 累计盈亏 | 净值涨跌 |")
            lines.append("|----------|----------|----------|----------|")

        for fund in funds:
            name = fund.get('name', '')
            display_name = name[:16] + '...' if len(name) > 16 else name

            market_value = fund.get('market_value', fund.get('total_invested', 0))
            profit_pct = fund.get('profit_pct', 0)

            profit_str = f"{format_change(profit_pct)}" if profit_pct != 0 else "-"

            if has_today_estimate:
                # 今日估算涨跌
                today_est = fund.get('today_estimated_pct')
                today_str = f"**{format_change(today_est)}**" if today_est is not None else "N/A"
                tracking_idx = fund.get('tracking_index', '-')

                lines.append(
                    f"| {display_name} | ¥{market_value:,.2f} | {profit_str} | {today_str} | {tracking_idx} |"
                )
            else:
                day_change = fund.get('day_change_pct')
                day_str = format_change(day_change) if day_change is not None else "N/A"

                lines.append(
                    f"| {display_name} | ¥{market_value:,.2f} | {profit_str} | {day_str} |"
                )
    else:
        lines.append("| 基金名称 | 代码 | 净投入 | 今日涨跌 |")
        lines.append("|----------|------|--------|----------|")

        for fund in funds:
            name = fund.get('name', '')
            code = fund.get('code', 'N/A')
            net_invested = fund.get('net_invested', 0)
            day_change = fund.get('day_change_pct')

            display_name = name[:20] + '...' if len(name) > 20 else name

            lines.append(
                f"| {display_name} | {code or 'N/A'} | "
                f"¥{net_invested:,.2f} | {format_change(day_change) if day_change is not None else 'N/A'} |"
            )

    return "\n".join(lines)


def format_news_time(time_str: str) -> str:
    """格式化新闻时间，提取时分部分"""
    if not time_str:
        return ""
    # 尝试提取时间部分 (HH:MM 或 HH:MM:SS)
    import re
    match = re.search(r'(\d{1,2}:\d{2})(:\d{2})?', time_str)
    if match:
        return match.group(1)
    return time_str[:16] if len(time_str) > 16 else time_str


def generate_news_section(news_data: dict) -> str:
    """生成新闻资讯部分"""
    if not news_data:
        return ""

    lines = ["## 今日要闻\n"]

    # 宏观数据
    macro = news_data.get('macro', [])
    if macro:
        lines.append("### 宏观经济数据\n")
        for item in macro:
            title = item.get('title', '')
            content = item.get('content', '')
            lines.append(f"- **{title}** ({content})")
        lines.append("")

    # 重要新闻
    all_news = news_data.get('all_news', [])
    important_news = [n for n in all_news if n.get('important')]

    if important_news:
        lines.append("### 重要资讯\n")
        for item in important_news[:15]:  # 增加到15条
            title = item.get('title', item.get('content', ''))
            if len(title) > 55:
                title = title[:55] + '...'
            source = item.get('source', '')
            time_str = format_news_time(item.get('time', ''))
            if time_str:
                lines.append(f"- [{source} {time_str}] {title}")
            else:
                lines.append(f"- [{source}] {title}")
        lines.append("")

    # 其他财经新闻（非重要但可能有参考价值）
    other_news = [n for n in all_news if not n.get('important')]
    if other_news:
        lines.append("### 其他财经快讯\n")
        for item in other_news[:15]:  # 显示15条普通新闻
            title = item.get('title', item.get('content', ''))
            if len(title) > 55:
                title = title[:55] + '...'
            source = item.get('source', '')
            time_str = format_news_time(item.get('time', ''))
            if time_str:
                lines.append(f"- [{source} {time_str}] {title}")
            else:
                lines.append(f"- [{source}] {title}")
        lines.append("")

    # 新闻联播
    cctv = news_data.get('cctv', [])
    if cctv:
        lines.append("### 新闻联播要点\n")
        for item in cctv[:3]:
            title = item.get('title', '')
            if title:
                lines.append(f"- {title}")
        lines.append("")

    if not macro and not important_news and not cctv:
        return ""

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
    news_data: dict = None,
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

    # 今日要闻
    if news_data:
        news_section = generate_news_section(news_data)
        if news_section:
            lines.append(news_section)
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


def clean_nan_values(obj):
    """
    递归清理数据中的 NaN 值，转换为 None
    确保 JSON 序列化有效
    """
    if isinstance(obj, dict):
        return {k: clean_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan_values(item) for item in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return None
    else:
        return obj


def save_raw_data(data: dict, output_dir: str = "data") -> str:
    """保存原始数据为 JSON"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"data_{today}.json"
    filepath = output_path / filename

    # 清理 NaN 值
    clean_data = clean_nan_values(data)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=2, default=str)

    return str(filepath)
