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
from collections import defaultdict

import akshare as ak
import pandas as pd


# 基金名称到代码的缓存
_fund_code_cache = {}

# 常见基金名称映射（支付宝名称 -> 标准名称/代码）
FUND_NAME_MAPPING = {
    # 摩根系列
    "摩根纳斯达克100指数(QDII)C": "017641",
    "摩根标普500指数(QDII)C": "017639",
    # 易方达系列
    "易方达科创50联接C": "011609",
    "易方达沪深300ETF联接C": "007339",
    # 广发系列
    "广发纳斯达克100ETF联接(QDII)C": "006480",
    # 招商系列
    "招商纳斯达克100ETF联接(QDII)C": "019547",
    # 南方系列
    "南方纳斯达克100指数(QDII)C": "022453",
    # 宝盈系列
    "宝盈纳斯达克100指数(QDII)C": "021966",
    # 天弘系列
    "天弘标普500(QDII-FOF)C": "017243",
    # 博道系列
    "博道中证A500指数增强C": "022746",
}

# 全局基金列表缓存
_all_funds_df = None


def _get_all_funds() -> pd.DataFrame:
    """获取并缓存所有基金列表"""
    global _all_funds_df
    if _all_funds_df is None:
        try:
            _all_funds_df = ak.fund_open_fund_rank_em(symbol="全部")
        except Exception:
            _all_funds_df = pd.DataFrame()
    return _all_funds_df


def search_fund_code(fund_name: str) -> Optional[str]:
    """
    根据基金名称搜索基金代码
    """
    if fund_name in _fund_code_cache:
        return _fund_code_cache[fund_name]

    # 先查映射表
    if fund_name in FUND_NAME_MAPPING:
        code = FUND_NAME_MAPPING[fund_name]
        _fund_code_cache[fund_name] = code
        return code

    try:
        df = _get_all_funds()
        if df.empty:
            return None

        # 精确匹配
        matches = df[df['基金简称'] == fund_name]
        if not matches.empty:
            code = matches.iloc[0]['基金代码']
            _fund_code_cache[fund_name] = code
            return code

        # 去掉括号内容和后缀再匹配
        clean_name = re.sub(r'\(.*?\)', '', fund_name)  # 去掉括号
        clean_name = re.sub(r'[A-Z]$', '', clean_name)  # 去掉末尾字母

        if clean_name != fund_name:
            matches = df[df['基金简称'].str.contains(clean_name, na=False, regex=False)]
            if not matches.empty:
                # 优先选择C类份额
                c_matches = matches[matches['基金简称'].str.endswith('C')]
                if not c_matches.empty:
                    code = c_matches.iloc[0]['基金代码']
                else:
                    code = matches.iloc[0]['基金代码']
                _fund_code_cache[fund_name] = code
                return code

        # 提取关键词匹配
        keywords = []
        if '纳斯达克' in fund_name:
            keywords.append('纳斯达克')
        if '标普500' in fund_name or '标普' in fund_name:
            keywords.append('标普')
        if '科创50' in fund_name:
            keywords.append('科创50')
        if '沪深300' in fund_name:
            keywords.append('沪深300')
        if 'A500' in fund_name or 'a500' in fund_name.lower():
            keywords.append('A500')

        # 提取基金公司名称
        companies = ['摩根', '易方达', '广发', '招商', '南方', '宝盈', '天弘', '博道', '华夏', '嘉实']
        company = None
        for c in companies:
            if c in fund_name:
                company = c
                break

        if keywords and company:
            for kw in keywords:
                matches = df[
                    df['基金简称'].str.contains(company, na=False, regex=False) &
                    df['基金简称'].str.contains(kw, na=False, regex=False)
                ]
                if not matches.empty:
                    # 优先C类
                    c_matches = matches[matches['基金简称'].str.endswith('C')]
                    if not c_matches.empty:
                        code = c_matches.iloc[0]['基金代码']
                    else:
                        code = matches.iloc[0]['基金代码']
                    _fund_code_cache[fund_name] = code
                    return code

    except Exception as e:
        print(f"  搜索基金代码失败 [{fund_name}]: {e}")

    return None


def parse_alipay_bill(file_path: str) -> list[dict]:
    """
    解析支付宝交易明细 CSV 文件

    返回投资理财类交易记录列表
    """
    records = []

    # 尝试不同编码
    content = None
    for encoding in ['utf-8', 'gbk', 'gb18030', 'utf-8-sig']:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        raise ValueError(f"无法读取文件: {file_path}")

    lines = content.strip().split('\n')

    # 解析CSV头
    reader = csv.DictReader(lines)

    for row in reader:
        # 跳过空行
        if not row.get('交易时间') or not row.get('交易分类'):
            continue

        # 只保留投资理财类
        if row.get('交易分类') != '投资理财':
            continue

        records.append(row)

    return records


def parse_fund_transaction(description: str) -> dict:
    """
    解析商品说明字段，提取基金名称和操作类型

    示例输入: "蚂蚁财富-博道中证A500指数增强C-买入"
    返回: {"fund_name": "博道中证A500指数增强C", "action": "买入"}
    """
    # 移除"蚂蚁财富-"前缀
    desc = description.replace('蚂蚁财富-', '')

    # 提取操作类型
    action = None
    for op in ['买入', '卖出', '赎回', '分红', '定投']:
        if op in desc:
            action = op
            desc = desc.replace(f'-{op}', '').replace(op, '')
            break

    return {
        "fund_name": desc.strip(),
        "action": action
    }


def aggregate_transactions(records: list[dict]) -> dict:
    """
    汇总交易记录，按基金计算总投入/赎回金额

    返回: {基金名称: {"buy": 买入总额, "sell": 卖出总额, "transactions": [...]}}
    """
    funds = defaultdict(lambda: {
        "buy": 0.0,
        "sell": 0.0,
        "transactions": []
    })

    for record in records:
        desc = record.get('商品说明', '')
        parsed = parse_fund_transaction(desc)

        fund_name = parsed['fund_name']
        action = parsed['action']

        if not fund_name:
            continue

        # 解析金额
        amount_str = record.get('金额', '0')
        try:
            amount = float(re.sub(r'[^\d.]', '', amount_str))
        except ValueError:
            amount = 0.0

        # 记录交易
        funds[fund_name]['transactions'].append({
            'date': record.get('交易时间', ''),
            'action': action,
            'amount': amount,
            'status': record.get('交易状态', '')
        })

        # 汇总金额
        if action in ['买入', '定投']:
            funds[fund_name]['buy'] += amount
        elif action in ['卖出', '赎回']:
            funds[fund_name]['sell'] += amount

    return dict(funds)


def build_portfolio_from_alipay(file_path: str, output_path: str = None) -> dict:
    """
    从支付宝账单构建持仓数据

    返回并保存持仓信息
    """
    print(f"📄 解析支付宝账单: {file_path}")

    # 解析账单
    records = parse_alipay_bill(file_path)
    print(f"  找到 {len(records)} 条投资理财记录")

    # 汇总交易
    aggregated = aggregate_transactions(records)
    print(f"  涉及 {len(aggregated)} 只基金")

    # 构建持仓
    portfolio = {
        "funds": {},
        "summary": {
            "total_invested": 0.0,
            "total_redeemed": 0.0,
            "fund_count": 0
        },
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": file_path
    }

    print("\n🔍 查找基金代码...")

    for fund_name, data in aggregated.items():
        net_invested = data['buy'] - data['sell']

        # 跳过已清仓的基金
        if net_invested <= 0:
            print(f"  ⏭ {fund_name}: 已清仓，跳过")
            continue

        # 查找基金代码
        fund_code = search_fund_code(fund_name)

        # 保存每笔买入交易明细（用于精确计算份额）
        buy_transactions = [
            {"date": tx['date'], "amount": tx['amount']}
            for tx in data['transactions']
            if tx['action'] in ['买入', '定投'] and tx['amount'] > 0
        ]

        portfolio['funds'][fund_name] = {
            "code": fund_code,
            "name": fund_name,
            "total_invested": round(data['buy'], 2),
            "total_redeemed": round(data['sell'], 2),
            "net_invested": round(net_invested, 2),
            "transaction_count": len(data['transactions']),
            "first_buy": data['transactions'][-1]['date'] if data['transactions'] else None,
            "last_buy": data['transactions'][0]['date'] if data['transactions'] else None,
            "buy_transactions": buy_transactions,  # 新增：每笔买入明细
        }

        status = "✓" if fund_code else "⚠ 未找到代码"
        print(f"  {status} {fund_name}: ¥{net_invested:.2f} (代码: {fund_code or 'N/A'})")

        portfolio['summary']['total_invested'] += data['buy']
        portfolio['summary']['total_redeemed'] += data['sell']
        portfolio['summary']['fund_count'] += 1

    portfolio['summary']['total_invested'] = round(portfolio['summary']['total_invested'], 2)
    portfolio['summary']['total_redeemed'] = round(portfolio['summary']['total_redeemed'], 2)
    portfolio['summary']['net_invested'] = round(
        portfolio['summary']['total_invested'] - portfolio['summary']['total_redeemed'], 2
    )

    # 保存持仓文件
    if output_path is None:
        output_path = Path(__file__).parent.parent / "data" / "portfolio.json"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)

    print(f"\n💾 持仓数据已保存: {output_path}")
    print(f"   总投入: ¥{portfolio['summary']['total_invested']:,.2f}")
    print(f"   总赎回: ¥{portfolio['summary']['total_redeemed']:,.2f}")
    print(f"   净投入: ¥{portfolio['summary']['net_invested']:,.2f}")
    print(f"   持有基金: {portfolio['summary']['fund_count']} 只")

    return portfolio


def load_portfolio(file_path: str = None) -> dict:
    """加载持仓数据"""
    if file_path is None:
        file_path = Path(__file__).parent.parent / "data" / "portfolio.json"

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def get_portfolio_with_estimates(portfolio: dict) -> dict:
    """
    获取持仓的实时估值

    注意：由于没有份额数据，只能显示投入金额，无法计算实际市值
    """
    if not portfolio or 'funds' not in portfolio:
        return portfolio

    result = {
        "funds": [],
        "summary": portfolio.get('summary', {}),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    for fund_name, fund_data in portfolio['funds'].items():
        fund_code = fund_data.get('code')

        fund_info = {
            "name": fund_name,
            "code": fund_code,
            "net_invested": fund_data.get('net_invested', 0),
            "estimate": None,
            "day_change_pct": None
        }

        # 尝试获取实时估值
        if fund_code:
            try:
                df = ak.fund_open_fund_rank_em(symbol="全部")
                row = df[df['基金代码'] == fund_code]
                if not row.empty:
                    row = row.iloc[0]
                    fund_info['estimate'] = {
                        'nav': float(row.get('单位净值', 0)),
                        'nav_date': str(row.get('日期', '')),
                        'day_change_pct': float(row.get('日增长率', 0))
                    }
                    fund_info['day_change_pct'] = fund_info['estimate']['day_change_pct']
            except Exception:
                pass

        result['funds'].append(fund_info)

    # 按净投入金额排序
    result['funds'].sort(key=lambda x: x['net_invested'], reverse=True)

    return result


# 保留旧函数的兼容性
def load_manual_portfolio(config: dict) -> dict:
    """从配置文件加载手动维护的持仓（兼容旧接口）"""
    portfolio = config.get('portfolio') or {}
    positions = {}

    for code, shares in portfolio.items():
        if shares and shares > 0:
            positions[code] = {
                'shares': float(shares),
                'cost': 0,
                'name': ''
            }

    return positions


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        bill_path = sys.argv[1]
        build_portfolio_from_alipay(bill_path)
    else:
        print("用法: python portfolio.py <支付宝账单CSV文件>")
