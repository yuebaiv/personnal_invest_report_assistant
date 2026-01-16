"""
基金估值模块

计算方法优先级：
1. 使用基金实际净值计算（最准确）
2. 对于无法获取净值的基金，使用指数估算（有误差）
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import akshare as ak
import pandas as pd
import yaml

# 缓存
_index_history_cache = {}
_fund_nav_cache = {}


def get_fund_nav_history(fund_code: str, days: int = 60) -> pd.DataFrame:
    """
    获取基金历史净值数据
    返回 DataFrame: date, nav (单位净值)
    """
    cache_key = f"nav_{fund_code}"
    if cache_key in _fund_nav_cache:
        return _fund_nav_cache[cache_key]

    try:
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        if df is not None and not df.empty:
            df.columns = ['date', 'nav', 'pct_change']
            df['date'] = pd.to_datetime(df['date'])
            df['nav'] = df['nav'].astype(float)
            df = df[['date', 'nav']].sort_values('date')
            # 只保留最近days天
            cutoff = datetime.now() - timedelta(days=days)
            df = df[df['date'] >= cutoff]
            _fund_nav_cache[cache_key] = df
            return df
    except Exception as e:
        print(f"  获取基金 {fund_code} 净值历史失败: {e}")

    return pd.DataFrame()


def get_nav_on_date(nav_df: pd.DataFrame, target_date: datetime) -> Optional[float]:
    """获取指定日期的净值，如果当天没有则取最近的前一个交易日"""
    if nav_df.empty:
        return None

    df = nav_df[nav_df['date'] <= target_date].sort_values('date', ascending=False)
    if not df.empty:
        return float(df.iloc[0]['nav'])

    # 没有更早的数据，取最早的一条
    df = nav_df.sort_values('date', ascending=True)
    if not df.empty:
        return float(df.iloc[0]['nav'])

    return None


def get_fund_current_nav(fund_code: str) -> dict:
    """获取基金当前净值"""
    try:
        df = ak.fund_open_fund_rank_em(symbol="全部")
        row = df[df['基金代码'] == fund_code]
        if not row.empty:
            row = row.iloc[0]
            return {
                'nav': float(row.get('单位净值', 0)),
                'nav_date': str(row.get('日期', '')),
                'day_change_pct': float(row.get('日增长率', 0)) if pd.notna(row.get('日增长率')) else None
            }
    except Exception as e:
        print(f"  获取基金 {fund_code} 当前净值失败: {e}")
    return {'nav': None}


def load_fund_index_mapping() -> dict:
    """加载基金-指数映射配置"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('fund_index_mapping', {})
    except Exception:
        return {}


def get_a_share_index_history(index_code: str, days: int = 60, include_volume: bool = False) -> pd.DataFrame:
    """
    获取A股指数历史数据

    Args:
        index_code: 指数代码
        days: 历史天数
        include_volume: 是否包含成交额数据

    Returns:
        DataFrame: date, close, [amount]
    """
    cache_key = f"a_{index_code}_{include_volume}"
    if cache_key in _index_history_cache:
        return _index_history_cache[cache_key]

    try:
        df = ak.index_zh_a_hist(symbol=index_code, period="daily",
                                start_date=(datetime.now() - timedelta(days=days)).strftime("%Y%m%d"),
                                end_date=datetime.now().strftime("%Y%m%d"))
        if df is not None and not df.empty:
            df['date'] = pd.to_datetime(df['日期'])
            df['close'] = df['收盘'].astype(float)

            if include_volume:
                df['amount'] = df['成交额'].astype(float)
                df = df[['date', 'close', 'amount']].sort_values('date')
            else:
                df = df[['date', 'close']].sort_values('date')

            _index_history_cache[cache_key] = df
            return df
    except Exception as e:
        print(f"  获取A股指数 {index_code} 历史失败: {e}")

    return pd.DataFrame()


def get_us_index_history(index_code: str, days: int = 60) -> pd.DataFrame:
    """获取美股指数历史数据"""
    cache_key = f"us_{index_code}"
    if cache_key in _index_history_cache:
        return _index_history_cache[cache_key]

    try:
        import yfinance as yf
        ticker = yf.Ticker(index_code)
        df = ticker.history(period=f"{days}d")
        if df is not None and not df.empty:
            df = df.reset_index()
            df['date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
            df['close'] = df['Close'].astype(float)
            df = df[['date', 'close']].sort_values('date')
            _index_history_cache[cache_key] = df
            return df
    except Exception as e:
        print(f"  获取美股指数 {index_code} 历史失败: {e}")

    return pd.DataFrame()


def get_index_history(index_code: str, market: str = "a_share") -> pd.DataFrame:
    """获取指数历史数据"""
    if market == "us":
        return get_us_index_history(index_code)
    else:
        return get_a_share_index_history(index_code)


def get_index_value_on_date(index_df: pd.DataFrame, target_date: datetime) -> Optional[float]:
    """获取指定日期的指数收盘价，如果当天没有则取前一个交易日"""
    if index_df.empty:
        return None

    # 查找该日期或之前最近的数据
    df = index_df[index_df['date'] <= target_date].sort_values('date', ascending=False)

    if not df.empty:
        return float(df.iloc[0]['close'])

    # 如果没有更早的，取最早的一条
    df = index_df.sort_values('date', ascending=True)
    if not df.empty:
        return float(df.iloc[0]['close'])

    return None


def parse_order_date(order_time_str: str) -> Optional[datetime]:
    """解析下单时间字符串"""
    try:
        if '/' in order_time_str:
            return datetime.strptime(order_time_str.split()[0], '%Y/%m/%d')
        else:
            return datetime.strptime(order_time_str.split()[0], '%Y-%m-%d')
    except Exception:
        return None


def parse_order_datetime(order_time_str: str) -> Optional[datetime]:
    """解析下单时间（包含时分）"""
    try:
        if '/' in order_time_str:
            return datetime.strptime(order_time_str, '%Y/%m/%d %H:%M')
        else:
            return datetime.strptime(order_time_str, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return parse_order_date(order_time_str)


def get_nav_confirm_date(order_time: datetime, nav_df: pd.DataFrame) -> Optional[datetime]:
    """
    根据下单时间计算净值确认日期
    - 交易日15:00前下单 → 当日净值
    - 交易日15:00后或非交易日 → 下一交易日净值
    """
    order_date = order_time.date()
    order_hour = order_time.hour

    # 获取所有交易日（有净值的日期）
    trading_days = set(nav_df['date'].dt.date)

    is_trading_day = order_date in trading_days

    if is_trading_day and order_hour < 15:
        return datetime.combine(order_date, datetime.min.time())
    else:
        # 找下一个交易日
        future_days = sorted([d for d in trading_days if d > order_date])
        if future_days:
            return datetime.combine(future_days[0], datetime.min.time())
    return None


def calculate_fund_valuation_by_nav(fund_data: dict) -> dict:
    """
    使用基金实际净值计算估值（最准确）

    逻辑：
    - 获取每笔买入的确认净值
    - 份额 = 金额 / 确认净值
    - 市值 = 总份额 × 当前净值
    """
    fund_code = fund_data.get('code')
    fund_name = fund_data.get('name', '')
    total_invested = fund_data.get('net_invested', 0)

    result = {
        'name': fund_name,
        'code': fund_code,
        'total_invested': total_invested,
        'calc_method': 'nav',
    }

    if not fund_code:
        return None  # 无法用净值计算，返回None让调用者使用备选方法

    # 获取当前净值
    current = get_fund_current_nav(fund_code)
    current_nav = current.get('nav')
    if not current_nav or current_nav <= 0:
        return None

    result['current_nav'] = current_nav
    result['nav_date'] = current.get('nav_date')
    result['day_change_pct'] = current.get('day_change_pct')

    # 获取历史净值
    nav_history = get_fund_nav_history(fund_code)
    if nav_history.empty:
        return None

    # 逐笔计算份额
    buy_transactions = fund_data.get('buy_transactions', [])
    if not buy_transactions:
        return None

    total_shares = 0.0
    total_cost = 0.0
    uncalculated_amount = 0.0  # 无法计算的金额（视为未买入，盈亏为0）
    calc_details = []

    for tx in buy_transactions:
        tx_date_str = tx.get('date', '')
        tx_amount = tx.get('amount', 0)

        if tx_amount <= 0:
            continue

        tx_time = parse_order_datetime(tx_date_str)
        if not tx_time:
            # 无法解析时间，按不涨不跌计入
            uncalculated_amount += tx_amount
            calc_details.append({
                'order_time': tx_date_str,
                'amount': tx_amount,
                'note': '时间解析失败，按原金额计入'
            })
            continue

        # 计算净值确认日期
        confirm_date = get_nav_confirm_date(tx_time, nav_history)
        if not confirm_date:
            # 净值还没更新（当天买入），按不涨不跌计入
            uncalculated_amount += tx_amount
            calc_details.append({
                'order_time': tx_date_str,
                'amount': tx_amount,
                'note': '净值待更新，按原金额计入'
            })
            continue

        # 获取确认日的净值
        buy_nav = get_nav_on_date(nav_history, confirm_date)
        if not buy_nav or buy_nav <= 0:
            # 无法获取净值，按不涨不跌计入
            uncalculated_amount += tx_amount
            calc_details.append({
                'order_time': tx_date_str,
                'confirm_date': confirm_date.strftime('%Y-%m-%d'),
                'amount': tx_amount,
                'note': '无法获取确认净值，按原金额计入'
            })
            continue

        # 计算份额
        shares = tx_amount / buy_nav
        total_shares += shares
        total_cost += tx_amount

        calc_details.append({
            'order_time': tx_date_str,
            'confirm_date': confirm_date.strftime('%Y-%m-%d'),
            'amount': tx_amount,
            'nav': round(buy_nav, 4),
            'shares': round(shares, 2)
        })

    if total_shares <= 0 and uncalculated_amount <= 0:
        return None

    # 计算市值和盈亏
    # 可计算部分：份额 × 当前净值
    calculated_market_value = total_shares * current_nav if total_shares > 0 else 0
    # 不可计算部分：按原金额计入（盈亏为0）
    market_value = calculated_market_value + uncalculated_amount
    # 盈亏只来自可计算部分
    profit = calculated_market_value - total_cost
    # 盈亏比例基于总投入
    total_actual_cost = total_cost + uncalculated_amount
    profit_pct = (profit / total_actual_cost * 100) if total_actual_cost > 0 else 0

    result['total_shares'] = round(total_shares, 2)
    result['avg_cost'] = round(total_cost / total_shares, 4) if total_shares > 0 else 0
    result['market_value'] = round(market_value, 2)
    result['profit'] = round(profit, 2)
    result['profit_pct'] = round(profit_pct, 2)
    result['calc_details'] = calc_details
    if uncalculated_amount > 0:
        result['uncalculated_amount'] = uncalculated_amount

    return result


def calculate_fund_valuation_by_index(fund_data: dict, fund_index_mapping: dict) -> dict:
    """
    基于指数涨跌计算基金估值

    逻辑：
    - 每笔投入的市值 = 金额 × (1 + 从买入日到今日的指数涨跌幅 × 跟踪系数)
    - 总市值 = 所有投入市值之和
    """
    fund_code = fund_data.get('code')
    fund_name = fund_data.get('name', '')
    total_invested = fund_data.get('net_invested', 0)

    result = {
        'name': fund_name,
        'code': fund_code,
        'total_invested': total_invested,
    }

    if not fund_code:
        result['market_value'] = total_invested
        result['profit'] = 0
        result['profit_pct'] = 0
        result['error'] = '缺少基金代码'
        return result

    # 获取基金对应的指数配置
    mapping = fund_index_mapping.get(fund_code)
    if not mapping:
        result['market_value'] = total_invested
        result['profit'] = 0
        result['profit_pct'] = 0
        result['error'] = '未配置跟踪指数'
        return result

    index_code = mapping.get('index_code')
    index_name = mapping.get('index_name', '')
    tracking_ratio = mapping.get('tracking_ratio', 0.95)
    market = mapping.get('market', 'a_share')

    result['tracking_index'] = index_name
    result['tracking_ratio'] = tracking_ratio

    # 获取指数历史数据
    index_history = get_index_history(index_code, market)
    if index_history.empty:
        result['market_value'] = total_invested
        result['profit'] = 0
        result['profit_pct'] = 0
        result['error'] = f'无法获取指数 {index_code} 历史数据'
        return result

    # 获取今日指数收盘价
    today_value = get_index_value_on_date(index_history, datetime.now())
    if not today_value:
        result['market_value'] = total_invested
        result['profit'] = 0
        result['profit_pct'] = 0
        result['error'] = '无法获取今日指数'
        return result

    result['index_today'] = today_value

    # 逐笔计算市值
    buy_transactions = fund_data.get('buy_transactions', [])

    total_market_value = 0.0
    calc_details = []

    for tx in buy_transactions:
        tx_date_str = tx.get('date', '')
        tx_amount = tx.get('amount', 0)

        if tx_amount <= 0:
            continue

        tx_date = parse_order_date(tx_date_str)
        if not tx_date:
            # 无法解析日期，假设盈亏为0
            total_market_value += tx_amount
            calc_details.append({
                'date': tx_date_str,
                'amount': tx_amount,
                'market_value': tx_amount,
                'change_pct': 0,
                'note': '日期解析失败'
            })
            continue

        # 获取买入日的指数值
        buy_value = get_index_value_on_date(index_history, tx_date)

        if not buy_value:
            # 无法获取买入日指数，假设盈亏为0
            total_market_value += tx_amount
            calc_details.append({
                'date': tx_date_str,
                'amount': tx_amount,
                'market_value': tx_amount,
                'change_pct': 0,
                'note': '无法获取买入日指数'
            })
            continue

        # 计算涨跌幅
        index_change_pct = (today_value - buy_value) / buy_value
        # 基金涨跌 = 指数涨跌 × 跟踪系数（增强型基金可能>1）
        fund_change_pct = index_change_pct * tracking_ratio
        # 当前市值
        market_value = tx_amount * (1 + fund_change_pct)

        total_market_value += market_value
        calc_details.append({
            'date': tx_date_str,
            'amount': tx_amount,
            'index_buy': round(buy_value, 2),
            'index_today': round(today_value, 2),
            'index_change_pct': round(index_change_pct * 100, 2),
            'fund_change_pct': round(fund_change_pct * 100, 2),
            'market_value': round(market_value, 2)
        })

    # 计算汇总
    profit = total_market_value - total_invested
    profit_pct = (profit / total_invested * 100) if total_invested > 0 else 0

    result['market_value'] = round(total_market_value, 2)
    result['profit'] = round(profit, 2)
    result['profit_pct'] = round(profit_pct, 2)
    result['calc_details'] = calc_details

    return result


def estimate_today_change(fund_code: str, indices_data: dict, fund_index_mapping: dict = None) -> dict:
    """
    根据跟踪指数估算基金今日涨跌

    Args:
        fund_code: 基金代码
        indices_data: 当日指数数据 {'a_share': [...], 'us_stock': [...]}
        fund_index_mapping: 基金-指数映射配置

    Returns:
        {
            'estimated_change_pct': 估算涨跌幅,
            'index_name': 跟踪指数名称,
            'index_change_pct': 指数实际涨跌,
            'tracking_ratio': 跟踪系数,
        }
    """
    if fund_index_mapping is None:
        fund_index_mapping = load_fund_index_mapping()

    mapping = fund_index_mapping.get(fund_code)
    if not mapping:
        return {'error': '未配置跟踪指数', 'estimated_change_pct': None}

    index_code = mapping.get('index_code')
    index_name = mapping.get('index_name', '')
    tracking_ratio = mapping.get('tracking_ratio', 0.95)
    market = mapping.get('market', 'a_share')

    # 从指数数据中查找对应指数
    index_change_pct = None

    if market == 'us':
        # 美股指数
        for idx in indices_data.get('us_stock', []):
            if idx.get('code') == index_code:
                index_change_pct = idx.get('change_pct')
                break
        # 如果是纳斯达克100 (^NDX)，用纳斯达克综合 (^IXIC) 近似
        if index_change_pct is None and index_code == '^NDX':
            for idx in indices_data.get('us_stock', []):
                if idx.get('code') == '^IXIC':
                    index_change_pct = idx.get('change_pct')
                    index_name = '纳斯达克(近似)'
                    break
    else:
        # A股指数
        for idx in indices_data.get('a_share', []):
            if idx.get('code') == index_code:
                index_change_pct = idx.get('change_pct')
                break

    if index_change_pct is None:
        return {
            'error': f'未找到指数 {index_code} 数据',
            'estimated_change_pct': None,
            'index_name': index_name
        }

    # 估算基金涨跌 = 指数涨跌 × 跟踪系数
    estimated_change_pct = index_change_pct * tracking_ratio

    return {
        'estimated_change_pct': round(estimated_change_pct, 2),
        'index_name': index_name,
        'index_code': index_code,
        'index_change_pct': index_change_pct,
        'tracking_ratio': tracking_ratio,
        'is_estimated': True
    }


def calculate_portfolio_valuation(portfolio_path: str = None, indices_data: dict = None) -> dict:
    """
    计算整个持仓的估值

    Args:
        portfolio_path: 持仓文件路径
        indices_data: 当日指数数据，用于估算今日涨跌

    返回: {
        'funds': [每只基金的估值详情],
        'summary': {
            'total_invested': 总投入,
            'total_market_value': 总市值,
            'total_profit': 总盈亏,
            'total_profit_pct': 总盈亏比例,
            'today_estimated_profit': 今日估算盈亏,
            'today_estimated_pct': 今日估算涨跌幅
        },
        'updated_at': 更新时间
    }
    """
    if portfolio_path is None:
        portfolio_path = Path(__file__).parent.parent / "data" / "portfolio.json"

    try:
        with open(portfolio_path, 'r', encoding='utf-8') as f:
            portfolio = json.load(f)
    except FileNotFoundError:
        return {'error': '未找到持仓文件'}

    funds_data = portfolio.get('funds', {})

    if not funds_data:
        return {'error': '持仓为空'}

    print("📊 计算持仓估值...")

    # 加载基金-指数映射
    fund_index_mapping = load_fund_index_mapping()

    results = []
    total_invested = 0
    total_market_value = 0
    total_today_estimated_profit = 0
    has_today_estimate = False

    for fund_name, fund_data in funds_data.items():
        print(f"  计算 {fund_name[:15]}...")

        fund_code = fund_data.get('code', '')
        mapping = fund_index_mapping.get(fund_code, {})
        is_qdii = mapping.get('market') == 'us'  # 美股QDII基金

        if is_qdii:
            # QDII基金：用指数估算（净值更新延迟，用指数更准确）
            valuation = calculate_fund_valuation_by_index(fund_data, fund_index_mapping)
        else:
            # A股基金：优先用净值计算
            valuation = calculate_fund_valuation_by_nav(fund_data)
            if valuation is None:
                valuation = calculate_fund_valuation_by_index(fund_data, fund_index_mapping)

        # 计算今日估算涨跌（如果有指数数据）
        if indices_data and valuation.get('code'):
            today_est = estimate_today_change(
                valuation['code'],
                indices_data,
                fund_index_mapping
            )
            valuation['today_estimated_pct'] = today_est.get('estimated_change_pct')
            if 'tracking_index' not in valuation:
                valuation['tracking_index'] = today_est.get('index_name')

            # 计算今日估算盈亏金额
            if valuation.get('today_estimated_pct') is not None and valuation.get('market_value'):
                market_value = valuation['market_value']
                est_pct = valuation['today_estimated_pct']
                today_profit = market_value * est_pct / 100
                valuation['today_estimated_profit'] = round(today_profit, 2)
                total_today_estimated_profit += today_profit
                has_today_estimate = True

        results.append(valuation)

        total_invested += valuation.get('total_invested', 0)
        total_market_value += valuation.get('market_value', valuation.get('total_invested', 0))

    # 按市值排序
    results.sort(key=lambda x: x.get('market_value', 0), reverse=True)

    total_profit = total_market_value - total_invested
    total_profit_pct = (total_profit / total_invested * 100) if total_invested > 0 else 0

    # 今日估算涨跌幅（基于当前市值）
    today_estimated_pct = (total_today_estimated_profit / total_market_value * 100) if total_market_value > 0 and has_today_estimate else None

    summary = {
        'total_invested': round(total_invested, 2),
        'total_market_value': round(total_market_value, 2),
        'total_profit': round(total_profit, 2),
        'total_profit_pct': round(total_profit_pct, 2),
        'fund_count': len(results)
    }

    # 只有在有今日估算数据时才添加
    if has_today_estimate:
        summary['today_estimated_profit'] = round(total_today_estimated_profit, 2)
        summary['today_estimated_pct'] = round(today_estimated_pct, 2) if today_estimated_pct else None

    return {
        'funds': results,
        'summary': summary,
        'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


if __name__ == "__main__":
    result = calculate_portfolio_valuation()

    if 'error' in result:
        print(f"错误: {result['error']}")
    else:
        print("\n=== 持仓估值 ===")
        print(f"总投入: ¥{result['summary']['total_invested']:,.2f}")
        print(f"估算市值: ¥{result['summary']['total_market_value']:,.2f}")
        print(f"浮动盈亏: ¥{result['summary']['total_profit']:,.2f} ({result['summary']['total_profit_pct']:+.2f}%)")

        print("\n=== 持仓明细 ===")
        for fund in result['funds']:
            name = fund['name'][:18]
            mv = fund.get('market_value', fund.get('total_invested', 0))
            profit_pct = fund.get('profit_pct', 0)
            print(f"{name}: ¥{mv:,.2f} ({profit_pct:+.2f}%)")
