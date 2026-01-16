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
    load_manual_portfolio,
    load_portfolio,
    calculate_portfolio_value,
    parse_alipay_fund_bill,
    extract_fund_positions,
    save_portfolio,
)
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


def run_portfolio_analysis(config: dict, portfolio_file: str = None) -> dict:
    """执行持仓分析"""
    print("📁 正在分析持仓...")

    # 优先从文件加载，否则从配置加载
    if portfolio_file:
        positions = load_portfolio(portfolio_file)
    else:
        # 尝试加载已保存的持仓
        default_portfolio = ROOT_DIR / "data" / "portfolio.json"
        if default_portfolio.exists():
            positions = load_portfolio(str(default_portfolio))
        else:
            positions = load_manual_portfolio(config)

    if not positions:
        print("  ⚠ 未找到持仓数据")
        return {}

    print(f"  ✓ 持仓基金: {len(positions)} 只")

    # 计算持仓价值
    portfolio_value = calculate_portfolio_value(positions)
    print(f"  ✓ 总市值: ¥{portfolio_value['total_value']:,.2f}")

    return portfolio_value


def import_alipay_bill(bill_path: str, output_path: str = None):
    """导入支付宝账单"""
    print(f"📄 正在导入支付宝账单: {bill_path}")

    records = parse_alipay_fund_bill(bill_path)
    if not records:
        print("  ⚠ 未能解析账单数据")
        return

    print(f"  ✓ 解析到 {len(records)} 条记录")

    positions = extract_fund_positions(records)
    print(f"  ✓ 提取到 {len(positions)} 只基金持仓")

    # 保存持仓
    output = output_path or str(ROOT_DIR / "data" / "portfolio.json")
    save_portfolio(positions, output)


def main():
    parser = argparse.ArgumentParser(
        description="投资助手 - 每日市场监控与分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py                    # 生成今日完整报告
  python run.py --quick            # 只看指数，跳过资金流向
  python run.py --import-bill xxx.csv  # 导入支付宝账单
  python run.py --no-portfolio     # 不分析持仓
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
        help='快速模式: 只获取指数数据'
    )
    parser.add_argument(
        '--no-portfolio',
        action='store_true',
        help='跳过持仓分析'
    )
    parser.add_argument(
        '--import-bill',
        metavar='FILE',
        help='导入支付宝基金账单 CSV 文件'
    )
    parser.add_argument(
        '--portfolio-file',
        metavar='FILE',
        help='指定持仓数据文件'
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
        import_alipay_bill(args.import_bill)
        return

    # 加载配置
    config = load_config(args.config)

    print("=" * 50)
    print("🚀 投资助手 - 每日市场监控")
    print("=" * 50)

    # 市场扫描
    market_data = run_market_scan(config, include_flow=not args.quick)

    # 持仓分析
    portfolio_data = {}
    if not args.no_portfolio:
        portfolio_data = run_portfolio_analysis(config, args.portfolio_file)

    # 生成报告
    print("\n📝 正在生成报告...")
    report = generate_daily_report(
        indices_data=market_data['indices'],
        north_flow=market_data.get('north_flow'),
        sector_flow=market_data.get('sector_flow'),
        portfolio_data=portfolio_data,
        output_dir=args.output
    )

    # 保存原始数据
    raw_data = {
        'indices': market_data['indices'],
        'north_flow': market_data.get('north_flow'),
        'sector_flow': market_data.get('sector_flow'),
        'portfolio': portfolio_data
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
