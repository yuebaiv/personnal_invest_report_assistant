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

    # LLM 分析摘要（如果有）
    llm_analysis = news_data.get('llm_analysis', {})
    if llm_analysis and 'error' not in llm_analysis:
        overall_sentiment = llm_analysis.get('overall_sentiment', 0)
        market_summary = llm_analysis.get('market_summary', '')
        hot_sectors = llm_analysis.get('hot_sectors', [])
        resonance = llm_analysis.get('resonance', [])

        # 情绪指标
        if overall_sentiment != 0 or market_summary:
            lines.append("### AI 市场情绪分析\n")
            if overall_sentiment > 0.3:
                emoji = "🟢"
                desc = "偏多"
            elif overall_sentiment < -0.3:
                emoji = "🔴"
                desc = "偏空"
            else:
                emoji = "🟡"
                desc = "中性"
            lines.append(f"- 整体情绪: {emoji} **{desc}** ({overall_sentiment:+.2f})")

            if market_summary:
                lines.append(f"- 今日概况: {market_summary}")

            if hot_sectors:
                lines.append(f"- 热点板块: **{', '.join(hot_sectors[:5])}**")

            # 逻辑共振分析
            if resonance:
                lines.append("\n**行业逻辑共振分析:**\n")
                lines.append("| 行业 | 类型 | 分析 |")
                lines.append("|------|------|------|")
                for r in resonance[:5]:
                    sector = r.get('sector', '')
                    res_type = r.get('type', '')
                    conclusion = r.get('conclusion', '')
                    # 类型图标
                    if res_type == '逻辑共振':
                        type_icon = "🟢 逻辑共振"
                    elif res_type == '资金驱动':
                        type_icon = "🟡 资金驱动"
                    elif res_type == '利空不跌':
                        type_icon = "⚡ 利空不跌"
                    else:
                        type_icon = res_type or "待分析"
                    lines.append(f"| {sector} | {type_icon} | {conclusion} |")

            lines.append("")

    # 政策信号（来自新闻联播分析）
    cctv_analysis = news_data.get('cctv_analysis', {})
    if cctv_analysis and 'error' not in cctv_analysis:
        policy_signals = cctv_analysis.get('policy_signals', [])
        if policy_signals:
            lines.append("### 政策信号\n")
            for signal in policy_signals[:5]:
                direction = signal.get('direction', '')
                sector = signal.get('sector', '')
                reasoning = signal.get('reasoning', '')
                if direction == '利好':
                    emoji = "🟢"
                elif direction == '利空':
                    emoji = "🔴"
                else:
                    emoji = "🟡"
                lines.append(f"- {emoji} **{sector}**: {direction} - {reasoning}")
            lines.append("")

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
        for item in important_news[:10]:
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

    if len(lines) <= 1:
        return ""

    return "\n".join(lines)


def format_trend_signal(signal: str) -> str:
    """格式化趋势信号为emoji"""
    signal_map = {
        '多头': '📈 多头',
        '偏多': '📈 偏多',
        '空头': '📉 空头',
        '偏空': '📉 偏空',
        '震荡': '↔️ 震荡',
    }
    return signal_map.get(signal, signal)


def format_ma_position(price: float, ma: float) -> str:
    """格式化均线位置"""
    if ma is None:
        return "N/A"
    if price > ma:
        return f"↑{ma:.0f}"
    else:
        return f"↓{ma:.0f}"


def format_smart_signal(smart_signal: dict) -> str:
    """格式化智能信号为emoji"""
    if not smart_signal:
        return "N/A"

    action = smart_signal.get('action', 'unknown')
    action_cn = smart_signal.get('action_cn', '未知')

    signal_map = {
        'buy': '🟢 买入',
        'hold': '🟢 持有',
        'watch': '🟡 观望',
        'reduce': '🟠 减仓',
        'sell': '🔴 卖出',
    }
    return signal_map.get(action, f"⚪ {action_cn}")


def generate_trend_section(technical_data: dict) -> str:
    """生成趋势分析部分"""
    if not technical_data:
        return ""

    lines = ["## 趋势分析\n"]

    # 指数趋势
    trend_list = technical_data.get('trend', [])
    if trend_list:
        # 检查是否有需要关注的信号
        attention_items = []
        for item in trend_list:
            if 'error' in item:
                continue
            smart_signal = item.get('smart_signal', {})
            action = smart_signal.get('action', '')
            if action in ['sell', 'reduce']:
                attention_items.append({
                    'name': item.get('name'),
                    'action_cn': smart_signal.get('action_cn'),
                    'suggestion': smart_signal.get('suggestion'),
                    'reasons': smart_signal.get('reasons', [])
                })

        # 显示需要关注的项目
        if attention_items:
            lines.append("### ⚠️ 需要关注\n")
            for att in attention_items:
                reasons_str = '、'.join(att['reasons'][:3]) if att['reasons'] else ''
                lines.append(f"- **{att['name']}**: {att['action_cn']} - {att['suggestion']}")
                if reasons_str:
                    lines.append(f"  - 原因: {reasons_str}")
            lines.append("")

        lines.append("### 指数趋势\n")
        lines.append("| 指数 | 现价 | MA10位置 | MA20斜率 | RSI | 趋势 | 建议 |")
        lines.append("|------|------|----------|---------|-----|------|------|")

        for item in trend_list:
            if 'error' in item:
                continue

            name = item.get('name', '')
            price = item.get('price', 0)
            mas = item.get('mas', {})
            trend = item.get('trend', {})
            smart_signal = item.get('smart_signal', {})
            rsi_data = item.get('rsi', {})
            ma20_slope = item.get('ma20_slope')
            days_below = item.get('days_below_ma10', 0)

            # MA10位置
            ma10 = mas.get('ma10')
            if ma10:
                distance = (price - ma10) / ma10 * 100
                if distance < -2:
                    ma10_str = f"🔴 {distance:.1f}%"
                elif distance < 0:
                    ma10_str = f"🟡 {distance:.1f}%"
                elif distance > 3:
                    ma10_str = f"🟡 +{distance:.1f}%"
                else:
                    ma10_str = f"🟢 +{distance:.1f}%"
                if days_below > 0:
                    ma10_str += f"({days_below}日)"
            else:
                ma10_str = "N/A"

            # MA20斜率
            if ma20_slope is not None:
                if ma20_slope > 0.5:
                    slope_str = f"📈 +{ma20_slope:.1f}%"
                elif ma20_slope > 0:
                    slope_str = f"↗️ +{ma20_slope:.1f}%"
                elif ma20_slope > -0.5:
                    slope_str = f"↘️ {ma20_slope:.1f}%"
                else:
                    slope_str = f"📉 {ma20_slope:.1f}%"
            else:
                slope_str = "N/A"

            trend_str = format_trend_signal(trend.get('signal', ''))

            # RSI显示
            rsi_val = rsi_data.get('rsi')
            if rsi_val is not None:
                rsi_signal = rsi_data.get('signal', 'normal')
                if rsi_signal in ['very_overbought', 'overbought']:
                    rsi_str = f"🔴 {rsi_val:.0f}"
                elif rsi_signal in ['very_oversold', 'oversold']:
                    rsi_str = f"🟢 {rsi_val:.0f}"
                else:
                    rsi_str = f"{rsi_val:.0f}"
            else:
                rsi_str = "N/A"

            # 智能信号
            signal_str = format_smart_signal(smart_signal)

            lines.append(f"| {name} | {price:.2f} | {ma10_str} | {slope_str} | {rsi_str} | {trend_str} | {signal_str} |")

        lines.append("\n> 建议说明：综合MA位置、MA20斜率、成交量、RSI、市场广度等多因素判断\n")

        # 显示智能信号详情
        lines.append("### 信号详情\n")
        for item in trend_list:
            if 'error' in item:
                continue
            smart_signal = item.get('smart_signal', {})
            if not smart_signal:
                continue

            name = item.get('name', '')
            action_cn = smart_signal.get('action_cn', '')
            suggestion = smart_signal.get('suggestion', '')
            reasons = smart_signal.get('reasons', [])
            scores = smart_signal.get('scores', {})

            score_str = f"(多:{scores.get('buy_score', 0)} 空:{scores.get('sell_score', 0)} 净:{scores.get('net_score', 0)})"
            reasons_str = '、'.join(reasons[:4]) if reasons else '无特殊因素'

            lines.append(f"- **{name}**: {action_cn} {score_str}")
            lines.append(f"  - {suggestion}")
            lines.append(f"  - 依据: {reasons_str}")

        lines.append("")

    # 北向资金趋势
    north = technical_data.get('north_flow', {})
    if north and 'error' not in north:
        lines.append("### 北向资金趋势\n")

        recent_5d = north.get('recent_5d')
        recent_10d = north.get('recent_10d')
        avg_5d = north.get('avg_5d')
        consecutive = north.get('consecutive', {})

        if recent_5d is not None:
            direction = "+" if recent_5d > 0 else ""
            lines.append(f"- 近5日累计: **{direction}{recent_5d}亿** (日均{avg_5d:+.1f}亿)")

        if recent_10d is not None:
            direction = "+" if recent_10d > 0 else ""
            lines.append(f"- 近10日累计: **{direction}{recent_10d}亿**")

        if consecutive.get('direction'):
            lines.append(f"- 连续{consecutive['direction']}: **{consecutive['days']}天**")

        lines.append("")

    # 成交额对比
    volume_list = technical_data.get('volume', [])
    if volume_list:
        lines.append("### 成交额对比\n")
        lines.append("| 指数 | 今日 | 5日均值 | 比例 |")
        lines.append("|------|------|---------|------|")

        for item in volume_list:
            name = item.get('name', '')
            today = item.get('today_amount', 0)
            avg_5d = item.get('avg_5d', 0)
            ratio = item.get('ratio', 100)

            today_str = format_amount(today / 100000000)
            avg_str = format_amount(avg_5d / 100000000)

            # 根据比例添加标识
            ratio_icon = ""
            if ratio >= 120:
                ratio_icon = "🔥"
            elif ratio <= 80:
                ratio_icon = "❄️"

            lines.append(f"| {name} | {today_str} | {avg_str} | {ratio:.0f}%{ratio_icon} |")

        lines.append("")

    return "\n".join(lines)


def generate_valuation_section(technical_data: dict) -> str:
    """生成估值分析部分"""
    valuation_list = technical_data.get('valuation', [])
    if not valuation_list:
        return ""

    lines = ["## 估值分析\n"]
    lines.append("| 指数 | PE | PE分位(3年) | PB | PB分位(3年) | 水平 |")
    lines.append("|------|-----|------------|-----|------------|------|")

    for item in valuation_list:
        name = item.get('name', '')
        pe = item.get('pe')
        pb = item.get('pb')
        pe_pct = item.get('pe_percentile')
        pb_pct = item.get('pb_percentile')
        level = item.get('level', '')

        pe_str = f"{pe:.1f}" if pe else "N/A"
        pb_str = f"{pb:.2f}" if pb else "N/A"
        pe_pct_str = f"{pe_pct:.0f}%" if pe_pct is not None else "N/A"
        pb_pct_str = f"{pb_pct:.0f}%" if pb_pct is not None else "N/A"

        # 估值水平emoji
        level_map = {
            '低估': '🟢 低估',
            '中等': '🟡 中等',
            '高估': '🔴 高估',
        }
        level_str = level_map.get(level, level)

        lines.append(f"| {name} | {pe_str} | {pe_pct_str} | {pb_str} | {pb_pct_str} | {level_str} |")

    lines.append("")
    return "\n".join(lines)


def generate_sentiment_section(sentiment_data: dict) -> str:
    """生成市场情绪分析部分"""
    if not sentiment_data:
        return ""

    lines = ["## 市场情绪\n"]

    # 融资余额
    margin = sentiment_data.get('margin', {})
    if margin and 'error' not in margin:
        lines.append("### 融资余额\n")
        current = margin.get('current', 0) or 0
        change_1d = margin.get('change_1d', 0) or 0
        change_5d = margin.get('change_5d')
        change_10d = margin.get('change_10d')
        avg_5d = margin.get('avg_5d')
        trend = margin.get('trend', '')

        # 检查是否有有效数据（融资余额应该在万亿级别）
        if current and current > 100:  # 100亿以上才算有效数据
            # current 单位是亿元，转换为万亿显示
            current_wan_yi = current / 10000
            lines.append(f"- 两市融资余额: **{current_wan_yi:.2f}万亿** (较昨日 {change_1d:+.1f}亿)")
        else:
            # 数据未更新或获取失败
            lines.append("- 两市融资余额: **数据未更新**")
        if change_5d is not None:
            lines.append(f"- 5日变化: **{change_5d:+.0f}亿** (日均{avg_5d:+.1f}亿)")
        if change_10d is not None:
            lines.append(f"- 10日变化: **{change_10d:+.0f}亿**")

        # 情绪判断
        if trend == '增加':
            lines.append("- 情绪判断: 📈 杠杆资金持续流入\n")
        elif trend == '减少':
            lines.append("- 情绪判断: 📉 杠杆资金持续流出\n")
        else:
            lines.append("- 情绪判断: ↔️ 杠杆资金变化不大\n")

    # 市场广度
    breadth = sentiment_data.get('breadth', {})
    if breadth and 'error' not in breadth:
        breadth_data = breadth.get('breadth', {})
        new_high_low = breadth.get('new_high_low', {})

        if breadth_data and 'error' not in breadth_data:
            lines.append("### 市场广度\n")
            lines.append("| 指标 | 今日 | 信号 |")
            lines.append("|------|------|------|")

            rise = breadth_data.get('rise_count', 0)
            fall = breadth_data.get('fall_count', 0)
            ratio = breadth_data.get('rise_ratio', 0)
            limit_up = breadth_data.get('limit_up', 0)
            limit_down = breadth_data.get('limit_down', 0)

            # 涨跌比信号
            if ratio > 1.5:
                ratio_signal = "🟢 强势"
            elif ratio > 1.0:
                ratio_signal = "🟢 偏多"
            elif ratio > 0.67:
                ratio_signal = "🟡 中性"
            else:
                ratio_signal = "🔴 偏空"

            lines.append(f"| 上涨家数 | {rise} | - |")
            lines.append(f"| 下跌家数 | {fall} | - |")
            lines.append(f"| 涨跌比 | {ratio:.2f} | {ratio_signal} |")
            lines.append(f"| 涨停 | {limit_up} | - |")
            lines.append(f"| 跌停 | {limit_down} | - |")

            # 创新高低
            if new_high_low and 'error' not in new_high_low:
                h20 = new_high_low.get('high_20d', 0)
                l20 = new_high_low.get('low_20d', 0)
                net = new_high_low.get('net_high_low', 0)

                if net > 50:
                    net_signal = "🟢 活跃"
                elif net < -50:
                    net_signal = "🔴 低迷"
                else:
                    net_signal = "🟡 中性"

                lines.append(f"| 20日新高 | {h20} | - |")
                lines.append(f"| 20日新低 | {l20} | - |")
                lines.append(f"| 净新高 | {net} | {net_signal} |")

            lines.append("")

    # 无风险利率与股债性价比
    bond_yield = sentiment_data.get('bond_yield', {})
    equity_bond = sentiment_data.get('equity_bond', {})

    if (bond_yield and 'error' not in bond_yield) or (equity_bond and 'error' not in equity_bond):
        lines.append("### 无风险利率\n")

        if bond_yield and 'error' not in bond_yield:
            cn_10y = bond_yield.get('cn_10y', 0)
            us_10y = bond_yield.get('us_10y')
            spread = bond_yield.get('spread')
            lines.append(f"- 中国10年国债收益率: **{cn_10y:.2f}%**")
            if us_10y is not None and not is_nan(us_10y):
                lines.append(f"- 美国10年国债收益率: **{us_10y:.2f}%**")
            if spread is not None and not is_nan(spread):
                lines.append(f"- 中美利差: **{spread*100:.0f}bp**")

        if equity_bond and 'error' not in equity_bond:
            ratio = equity_bond.get('ratio', 0)
            signal_cn = equity_bond.get('signal_cn', '')
            pe = equity_bond.get('pe', 0)
            pe_percentile = equity_bond.get('pe_percentile')

            if ratio > 1.5:
                ratio_icon = "🟢"
            elif ratio > 1.0:
                ratio_icon = "🟡"
            else:
                ratio_icon = "🔴"

            lines.append(f"- 股债性价比(沪深300): {ratio_icon} **{ratio:.2f}** ({signal_cn})")
            if pe:
                lines.append(f"  - 沪深300 PE: {pe:.1f}")

            # 当股债性价比高但估值也高时，添加解释
            if ratio > 1.5 and pe_percentile and pe_percentile > 70:
                lines.append("")
                lines.append(f"> ⚠️ **特殊情境说明**: 受无风险利率大幅下行影响(10年国债{cn_10y:.2f}%)，股票资产相对价值凸显(股债比{ratio:.2f})，但绝对估值已处于近三年{pe_percentile:.0f}%分位。建议关注利率拐点风险。")

        lines.append("")

    # 全球联动
    vix = sentiment_data.get('vix', {})
    usd = sentiment_data.get('usd', {})

    has_global = (vix and 'error' not in vix) or (usd and 'usd_index' in usd)
    if has_global:
        lines.append("### 全球联动\n")
        lines.append("| 指标 | 数值 | 变化 | 信号 |")
        lines.append("|------|------|------|------|")

        # VIX
        if vix and 'error' not in vix:
            vix_val = vix.get('vix', 0)
            vix_change = vix.get('change', 0)
            vix_level = vix.get('level_cn', '')

            if vix.get('signal') == 'bullish':
                vix_icon = "🟢"
            elif vix.get('signal') in ['bearish', 'very_bearish']:
                vix_icon = "🔴"
            else:
                vix_icon = "🟡"

            lines.append(f"| VIX恐慌指数 | {vix_val:.1f} | {vix_change:+.1f} | {vix_icon} {vix_level} |")

        # 美元指数
        if usd and 'usd_index' in usd:
            usd_index = usd.get('usd_index', {})
            if usd_index and 'error' not in usd_index:
                usd_val = usd_index.get('value', 0)
                usd_change = usd_index.get('change_pct', 0)

                if usd_change > 0.5:
                    usd_icon = "🔴"  # 美元强对A股不利
                    usd_signal = "美元走强"
                elif usd_change < -0.5:
                    usd_icon = "🟢"
                    usd_signal = "美元走弱"
                else:
                    usd_icon = "🟡"
                    usd_signal = "中性"

                lines.append(f"| 美元指数 | {usd_val:.1f} | {usd_change:+.1f}% | {usd_icon} {usd_signal} |")

            # 离岸人民币
            usd_cnh = usd.get('usd_cnh', {})
            if usd_cnh and 'error' not in usd_cnh:
                cnh_val = usd_cnh.get('value', 0)
                cnh_change = usd_cnh.get('change_pct', 0)

                if cnh_change > 0.3:
                    cnh_icon = "🔴"
                    cnh_signal = "贬值"
                elif cnh_change < -0.3:
                    cnh_icon = "🟢"
                    cnh_signal = "升值"
                else:
                    cnh_icon = "🟡"
                    cnh_signal = "稳定"

                lines.append(f"| 离岸人民币 | {cnh_val:.4f} | {cnh_change:+.2f}% | {cnh_icon} {cnh_signal} |")

        lines.append("")

    # 综合判断
    summary = sentiment_data.get('summary', {})
    if summary:
        score = summary.get('score', 0)
        signal_cn = summary.get('signal_cn', '')
        description = summary.get('description', '')

        lines.append("### 情绪综合判断\n")

        if score >= 20:
            score_icon = "📈"
        elif score <= -20:
            score_icon = "📉"
        else:
            score_icon = "↔️"

        lines.append(f"- 综合得分: {score_icon} **{score}** ({signal_cn})")
        if description:
            lines.append(f"- 主要因素: {description}")
        lines.append("")

    return "\n".join(lines)


def generate_risk_section(technical_data: dict) -> str:
    """生成持仓风险分析部分"""
    risk_data = technical_data.get('risk', {})
    if not risk_data or 'error' in risk_data:
        return ""

    funds = risk_data.get('funds', [])
    summary = risk_data.get('summary', {})

    if not funds:
        return ""

    lines = ["## 持仓风险分析\n"]

    # 汇总信息
    if summary:
        avg_dd = summary.get('avg_drawdown')
        max_dd_fund = summary.get('max_drawdown_fund')
        max_dd = summary.get('max_drawdown')
        avg_vol = summary.get('avg_volatility')

        if avg_dd is not None:
            lines.append(f"- 持仓平均回撤: **{avg_dd:.1f}%**")
        if max_dd_fund and max_dd is not None:
            lines.append(f"- 最大回撤基金: {max_dd_fund} (**{max_dd:.1f}%**)")
        if avg_vol is not None:
            lines.append(f"- 平均年化波动率: **{avg_vol:.1f}%**")
        lines.append("")

    # 明细表格
    lines.append("| 基金名称 | 30日最大回撤 | 回撤区间 | 年化波动率 |")
    lines.append("|----------|-------------|----------|----------|")

    for fund in funds:
        if 'error' in fund:
            continue

        name = fund.get('name', '')
        display_name = name[:16] + '...' if len(name) > 16 else name

        dd = fund.get('max_drawdown')
        period = fund.get('drawdown_period', '-')
        vol = fund.get('volatility')

        dd_str = f"{dd:.1f}%" if dd is not None else "N/A"
        vol_str = f"{vol:.1f}%" if vol is not None else "N/A"

        lines.append(f"| {display_name} | {dd_str} | {period} | {vol_str} |")

    lines.append("")
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


def generate_recommendations_section(technical_data: dict) -> str:
    """生成情境化投资建议部分"""
    recommendations = technical_data.get('recommendations', [])

    if not recommendations:
        return ""

    lines = ["## 📋 投资建议\n"]
    lines.append("> 基于趋势、估值、持仓的多维度情境化分析\n")

    # 建议汇总表格
    lines.append("### 建议汇总\n")
    lines.append("| 指数 | 建议 | 情境 | 信心 | 趋势 | 估值 | 仓位 | 风险 |")
    lines.append("|------|------|------|------|------|------|------|------|")

    # 动作对应的图标
    action_icons = {
        'strong_buy': '🟢🟢',
        'buy_dip': '🟢',
        'accumulate': '🟢',
        'small_position': '🟡',
        'hold': '⚪',
        'wait': '⚪',
        'trim': '🟡',
        'take_profit': '🟠',
        'reduce': '🔴',
        'sell': '🔴🔴'
    }

    for rec in recommendations:
        name = rec.get('index_name', '')[:8]
        action = rec.get('action', '')
        action_cn = rec.get('action_cn', '')
        context = rec.get('context', '')
        confidence = rec.get('confidence', 0)
        metrics = rec.get('metrics', {})

        icon = action_icons.get(action, '⚪')
        confidence_bar = '●' * confidence + '○' * (5 - confidence)

        trend = metrics.get('trend', '-')
        valuation = metrics.get('valuation', '-')
        position = metrics.get('position', '-')
        risk = metrics.get('risk_level', '-')

        # 风险等级颜色
        risk_icon = '🟢' if risk == '低' else ('🟡' if risk == '中' else '🔴')

        lines.append(f"| {name} | {icon} {action_cn} | {context} | {confidence_bar} | {trend} | {valuation} | {position} | {risk_icon}{risk} |")

    lines.append("")

    # 详细建议（只显示需要关注的）
    important_recs = [r for r in recommendations if r.get('action') in
                      ['strong_buy', 'take_profit', 'reduce', 'sell', 'accumulate']]

    if important_recs:
        lines.append("### 重点关注\n")

        for rec in important_recs:
            name = rec.get('index_name', '')
            action_cn = rec.get('action_cn', '')
            context = rec.get('context', '')
            reasoning = rec.get('reasoning', [])
            risk_warnings = rec.get('risk_warning', [])
            position_advice = rec.get('position_advice', '')
            metrics = rec.get('metrics', {})

            action = rec.get('action', '')
            icon = action_icons.get(action, '⚪')

            lines.append(f"#### {icon} {name} - {action_cn}\n")
            lines.append(f"**情境**: {context}\n")

            if reasoning:
                lines.append("**分析**:")
                for r in reasoning:
                    lines.append(f"- {r}")
                lines.append("")

            if risk_warnings:
                lines.append("**风险提示**:")
                for w in risk_warnings:
                    lines.append(f"- ⚠️ {w}")
                lines.append("")

            if position_advice:
                lines.append(f"**操作建议**: {position_advice}\n")

            # 关键指标
            est_dd = metrics.get('estimated_drawdown', '')
            if est_dd:
                lines.append(f"> 预估最大回撤: {est_dd}\n")

    return "\n".join(lines)


def generate_daily_report(
    indices_data: dict,
    north_flow: dict = None,
    sector_flow: list = None,
    portfolio_data: dict = None,
    news_data: dict = None,
    technical_data: dict = None,
    sentiment_data: dict = None,
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

    # 趋势分析
    if technical_data:
        trend_section = generate_trend_section(technical_data)
        if trend_section:
            lines.append(trend_section)
            lines.append("\n---\n")

    # 情境化投资建议（核心新增功能）
    if technical_data:
        rec_section = generate_recommendations_section(technical_data)
        if rec_section:
            lines.append(rec_section)
            lines.append("\n---\n")

    # 估值分析
    if technical_data:
        valuation_section = generate_valuation_section(technical_data)
        if valuation_section:
            lines.append(valuation_section)
            lines.append("\n---\n")

    # 市场情绪分析（新增）
    if sentiment_data:
        sentiment_section = generate_sentiment_section(sentiment_data)
        if sentiment_section:
            lines.append(sentiment_section)
            lines.append("\n---\n")

    # 资金流向
    if north_flow or sector_flow:
        lines.append(generate_flow_section(north_flow or {}, sector_flow or []))
        lines.append("\n---\n")

    # 持仓分析
    if portfolio_data:
        lines.append(generate_portfolio_section(portfolio_data))
        lines.append("\n---\n")

    # 持仓风险分析（新增）
    if technical_data:
        risk_section = generate_risk_section(technical_data)
        if risk_section:
            lines.append(risk_section)
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
