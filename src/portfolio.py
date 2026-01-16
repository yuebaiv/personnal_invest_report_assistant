"""
持仓管理模块
支持从支付宝账单导入基金持仓数据
"""

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
import akshare as ak


def parse_alipay_fund_bill(file_path: str) -> list[dict]:
    """
    解析支付宝基金账单 CSV 文件

    支付宝账单导出方式：
    1. 打开支付宝 -> 我的 -> 账单
    2. 点击右上角"..." -> 开具交易流水证明/账单下载
    3. 选择时间范围，下载 CSV 文件

    或者从基金详情页：
    1. 支付宝 -> 理财 -> 基金 -> 持有
    2. 点击某只基金 -> 交易记录 -> 可以看到明细
    """
    records = []

    try:
        # 尝试不同编码
        for encoding in ['utf-8', 'gbk', 'gb18030']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        # 支付宝账单格式可能有多种，这里处理常见格式
        lines = content.strip().split('\n')

        # 跳过头部信息，找到数据行
        data_start = 0
        for i, line in enumerate(lines):
            if '交易时间' in line or '基金名称' in line or '交易类型' in line:
                data_start = i
                break

        if data_start == 0:
            # 尝试直接解析为 CSV
            reader = csv.DictReader(lines)
            for row in reader:
                records.append(row)
        else:
            # 解析找到的数据
            header = lines[data_start].split(',')
            header = [h.strip().strip('"') for h in header]

            for line in lines[data_start + 1:]:
                if not line.strip():
                    continue
                values = line.split(',')
                values = [v.strip().strip('"') for v in values]
                if len(values) == len(header):
                    records.append(dict(zip(header, values)))

    except Exception as e:
        print(f"解析账单失败: {e}")

    return records


def extract_fund_positions(records: list[dict]) -> dict:
    """
    从交易记录中计算当前持仓
    返回: {基金代码: {name, shares, cost, ...}}
    """
    positions = {}

    for record in records:
        # 尝试提取基金代码和名称
        fund_code = record.get('基金代码', record.get('fund_code', ''))
        fund_name = record.get('基金名称', record.get('fund_name', ''))
        trade_type = record.get('交易类型', record.get('type', ''))
        amount = record.get('金额', record.get('amount', '0'))
        shares = record.get('份额', record.get('shares', '0'))

        if not fund_code:
            continue

        # 清理数值
        try:
            amount = float(re.sub(r'[^\d.-]', '', str(amount)))
            shares = float(re.sub(r'[^\d.-]', '', str(shares)))
        except ValueError:
            continue

        if fund_code not in positions:
            positions[fund_code] = {
                'name': fund_name,
                'shares': 0,
                'cost': 0,
                'transactions': []
            }

        # 根据交易类型更新持仓
        if '买入' in trade_type or '申购' in trade_type:
            positions[fund_code]['shares'] += shares
            positions[fund_code]['cost'] += abs(amount)
        elif '卖出' in trade_type or '赎回' in trade_type:
            positions[fund_code]['shares'] -= shares
            positions[fund_code]['cost'] -= abs(amount)

        positions[fund_code]['transactions'].append({
            'type': trade_type,
            'amount': amount,
            'shares': shares,
            'date': record.get('交易时间', record.get('date', ''))
        })

    # 过滤掉已清仓的基金
    positions = {k: v for k, v in positions.items() if v['shares'] > 0}

    return positions


def load_manual_portfolio(config: dict) -> dict:
    """从配置文件加载手动维护的持仓"""
    portfolio = config.get('portfolio', {})
    positions = {}

    for code, shares in portfolio.items():
        if shares and shares > 0:
            positions[code] = {
                'shares': float(shares),
                'cost': 0,  # 手动维护的不记录成本
                'name': ''
            }

    return positions


def save_portfolio(positions: dict, output_path: str):
    """保存持仓数据到 JSON 文件"""
    data = {
        'positions': positions,
        'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"持仓数据已保存到: {output_path}")


def load_portfolio(input_path: str) -> dict:
    """从 JSON 文件加载持仓数据"""
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('positions', {})
    except FileNotFoundError:
        return {}


def get_fund_info(fund_code: str) -> dict:
    """获取基金基本信息"""
    try:
        # 尝试获取基金信息
        df = ak.fund_individual_basic_info_xq(symbol=fund_code)
        if df is not None and not df.empty:
            info = {}
            for _, row in df.iterrows():
                info[row['item']] = row['value']
            return {
                'code': fund_code,
                'name': info.get('基金简称', ''),
                'type': info.get('基金类型', ''),
                'manager': info.get('基金经理', ''),
                'size': info.get('资产规模', ''),
            }
    except Exception:
        pass

    try:
        # 备用方案
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="基金概况")
        if df is not None:
            return {
                'code': fund_code,
                'name': str(df.get('基金简称', [''])[0]) if isinstance(df.get('基金简称'), list) else '',
            }
    except Exception:
        pass

    return {'code': fund_code, 'error': '无法获取基金信息'}


def calculate_portfolio_value(positions: dict) -> dict:
    """计算持仓市值和收益"""
    from src.market import get_fund_realtime_estimate

    total_value = 0
    total_cost = 0
    details = []

    for code, pos in positions.items():
        estimate = get_fund_realtime_estimate(code)

        nav = estimate.get('estimate_nav') or estimate.get('price', 0)
        shares = pos.get('shares', 0)
        cost = pos.get('cost', 0)

        if nav and shares:
            value = nav * shares
            profit = value - cost if cost else 0
            profit_pct = (profit / cost * 100) if cost else 0

            total_value += value
            total_cost += cost

            details.append({
                'code': code,
                'name': pos.get('name', estimate.get('name', '')),
                'shares': shares,
                'nav': nav,
                'value': round(value, 2),
                'cost': round(cost, 2),
                'profit': round(profit, 2),
                'profit_pct': round(profit_pct, 2),
                'day_change_pct': estimate.get('change_pct') or estimate.get('estimate_change_pct', 0)
            })

    return {
        'total_value': round(total_value, 2),
        'total_cost': round(total_cost, 2),
        'total_profit': round(total_value - total_cost, 2),
        'total_profit_pct': round((total_value - total_cost) / total_cost * 100, 2) if total_cost else 0,
        'details': details,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


if __name__ == "__main__":
    # 测试
    import yaml

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # 加载手动维护的持仓
    positions = load_manual_portfolio(config)
    print(f"持仓基金数量: {len(positions)}")

    for code, pos in positions.items():
        print(f"  {code}: {pos['shares']} 份")
