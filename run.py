#!/usr/bin/env python3
"""
投资助手主入口
每日运行此脚本获取市场数据并生成报告
"""

import argparse
import sys
from pathlib import Path

import yaml

# 添加项目根目录到 Python 路径
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from src.market import (
    collect_all_indices,
    get_north_flow_today,
    get_sector_flow,
)
from src.portfolio import (
    load_portfolio,
    build_portfolio_from_alipay,
)
from src.valuation import calculate_portfolio_valuation
from src.news import collect_daily_news
from src.report import generate_daily_report, save_raw_data


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def run_market_scan(config: dict, include_flow: bool = True) -> dict:
    """执行市场扫描"""
    print("📊 正在获取市场数据...")

    # 获取指数数据
    indices_data = collect_all_indices(config)
    print(f"  ✓ A股指数: {len(indices_data['a_share'])} 个")
    print(f"  ✓ 美股指数: {len(indices_data['us_stock'])} 个")

    result = {'indices': indices_data}

    if include_flow:
        # 获取北向资金
        print("💰 正在获取资金流向...")
        north_flow = get_north_flow_today()
        if 'error' not in north_flow:
            print(f"  ✓ 北向资金: {north_flow.get('net_inflow', 0):.2f}亿")
        result['north_flow'] = north_flow

        # 获取行业资金流向
        sector_flow = get_sector_flow()
        if sector_flow and 'error' not in sector_flow[0]:
            print(f"  ✓ 行业板块: {len(sector_flow)} 个")
        result['sector_flow'] = sector_flow

    return result


def run_portfolio_analysis(with_valuation: bool = True, indices_data: dict = None) -> dict:
    """执行持仓分析"""
    print("📁 正在分析持仓...")

    # 加载持仓数据
    default_portfolio = ROOT_DIR / "data" / "portfolio.json"
    if not default_portfolio.exists():
        print("  ⚠ 未找到持仓数据，请先导入支付宝账单")
        print("    使用: python run.py --import-bill <账单文件.csv>")
        return {}

    portfolio = load_portfolio(str(default_portfolio))

    if not portfolio or 'funds' not in portfolio or not portfolio['funds']:
        print("  ⚠ 持仓数据为空")
        return {}

    fund_count = len(portfolio['funds'])
    net_invested = portfolio.get('summary', {}).get('net_invested', 0)

    print(f"  ✓ 持仓基金: {fund_count} 只")
    print(f"  ✓ 净投入: ¥{net_invested:,.2f}")

    if with_valuation:
        # 计算估值（包含历史净值查询，可能较慢）
        # 传入指数数据用于估算今日涨跌
        valuation = calculate_portfolio_valuation(str(default_portfolio), indices_data)

        if 'error' not in valuation:
            summary = valuation.get('summary', {})
            total_profit = summary.get('total_profit', 0)
            total_profit_pct = summary.get('total_profit_pct', 0)

            profit_icon = "📈" if total_profit >= 0 else "📉"
            print(f"  {profit_icon} 估算盈亏: ¥{total_profit:,.2f} ({total_profit_pct:+.2f}%)")

            # 显示今日估算
            today_est_profit = summary.get('today_estimated_profit')
            today_est_pct = summary.get('today_estimated_pct')
            if today_est_profit is not None:
                today_icon = "📈" if today_est_profit >= 0 else "📉"
                print(f"  {today_icon} 今日估算: ¥{today_est_profit:,.2f} ({today_est_pct:+.2f}%)")

            return valuation

    # 简单模式，不计算估值
    return {
        'funds': list(portfolio['funds'].values()),
        'summary': portfolio.get('summary', {}),
    }


def run_news_collection() -> dict:
    """收集新闻资讯"""
    return collect_daily_news()


def main():
    parser = argparse.ArgumentParser(
        description="投资助手 - 每日市场监控与分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py                        # 生成完整报告（含估值和新闻）
  python run.py --quick                # 快速模式（只看指数）
  python run.py --no-news              # 跳过新闻收集
  python run.py --no-valuation         # 跳过估值计算
  python run.py --import-bill xxx.csv  # 导入支付宝账单生成持仓
        """
    )

    parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='配置文件路径 (默认: config.yaml)'
    )
    parser.add_argument(
        '--quick', '-q',
        action='store_true',
        help='快速模式: 只获取指数数据，跳过资金流向、新闻和估值'
    )
    parser.add_argument(
        '--no-portfolio',
        action='store_true',
        help='跳过持仓分析'
    )
    parser.add_argument(
        '--no-valuation',
        action='store_true',
        help='跳过估值计算（加快速度）'
    )
    parser.add_argument(
        '--no-news',
        action='store_true',
        help='跳过新闻收集'
    )
    parser.add_argument(
        '--import-bill',
        metavar='FILE',
        help='导入支付宝基金账单 CSV 文件'
    )
    parser.add_argument(
        '--output', '-o',
        default='reports',
        help='报告输出目录 (默认: reports)'
    )
    parser.add_argument(
        '--print-only',
        action='store_true',
        help='只打印报告，不保存文件'
    )

    args = parser.parse_args()

    # 导入账单模式
    if args.import_bill:
        print("=" * 50)
        print("🚀 导入支付宝账单")
        print("=" * 50)
        build_portfolio_from_alipay(args.import_bill)
        print("\n" + "=" * 50)
        print("✅ 导入完成！现在可以运行 python run.py 生成报告")
        print("=" * 50)
        return

    # 加载配置
    config = load_config(args.config)

    print("=" * 50)
    print("🚀 投资助手 - 每日市场监控")
    print("=" * 50)

    # 市场扫描
    include_flow = not args.quick
    market_data = run_market_scan(config, include_flow=include_flow)

    # 持仓分析
    portfolio_data = {}
    if not args.no_portfolio:
        with_valuation = not args.quick and not args.no_valuation
        # 传入指数数据用于估算今日涨跌
        portfolio_data = run_portfolio_analysis(
            with_valuation=with_valuation,
            indices_data=market_data.get('indices')
        )

    # 新闻收集
    news_data = {}
    if not args.quick and not args.no_news:
        news_data = run_news_collection()

    # 生成报告
    print("\n📝 正在生成报告...")
    report = generate_daily_report(
        indices_data=market_data['indices'],
        north_flow=market_data.get('north_flow'),
        sector_flow=market_data.get('sector_flow'),
        portfolio_data=portfolio_data,
        news_data=news_data,
        output_dir=args.output
    )

    # 保存原始数据
    raw_data = {
        'indices': market_data['indices'],
        'north_flow': market_data.get('north_flow'),
        'sector_flow': market_data.get('sector_flow'),
        'portfolio': portfolio_data,
        'news': news_data
    }
    save_raw_data(raw_data)

    if args.print_only:
        print("\n" + "=" * 50)
        print(report)

    print("\n" + "=" * 50)
    print("✅ 完成！可以开始与 Claude 讨论今日投资策略")
    print("=" * 50)


if __name__ == "__main__":
    main()
