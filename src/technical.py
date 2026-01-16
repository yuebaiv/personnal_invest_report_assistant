"""
技术分析模块

提供趋势分析、估值分位、持仓风险等功能
"""

import math
from datetime import datetime, timedelta
from typing import Optional

import akshare as ak
import pandas as pd

from src.valuation import (
    get_a_share_index_history,
    get_us_index_history,
    get_fund_nav_history,
)

# 缓存
_north_flow_history_cache = {}
_valuation_history_cache = {}


# =============================================================================
# RSI 指标计算
# =============================================================================

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """
    计算RSI指标 (相对强弱指数)

    Args:
        df: 包含 date, close 列的 DataFrame
        period: RSI周期，默认14

    Returns:
        RSI值 (0-100)
    """
    if df.empty or len(df) < period + 1:
        return None

    df = df.sort_values('date', ascending=True).reset_index(drop=True)

    # 计算价格变化
    delta = df['close'].diff()

    # 分离涨跌
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)

    # 计算平均涨跌幅 (使用指数移动平均)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    # 计算RS和RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # 返回最新RSI值
    latest_rsi = rsi.iloc[-1]
    if pd.isna(latest_rsi):
        return None

    return round(float(latest_rsi), 1)


def analyze_rsi_signal(rsi_value: float) -> dict:
    """
    分析RSI信号

    Args:
        rsi_value: RSI值

    Returns:
        {
            'rsi': RSI值,
            'signal': 'overbought' / 'oversold' / 'normal',
            'signal_cn': 中文信号,
            'description': 描述
        }
    """
    if rsi_value is None:
        return {'rsi': None, 'signal': 'unknown', 'signal_cn': '未知'}

    if rsi_value >= 80:
        signal = 'very_overbought'
        signal_cn = '严重超买'
        description = '短期涨幅过大，注意回调风险'
    elif rsi_value >= 70:
        signal = 'overbought'
        signal_cn = '超买'
        description = '动能较强，但接近超买区'
    elif rsi_value <= 20:
        signal = 'very_oversold'
        signal_cn = '严重超卖'
        description = '短期跌幅过大，可能反弹'
    elif rsi_value <= 30:
        signal = 'oversold'
        signal_cn = '超卖'
        description = '动能较弱，但可能企稳'
    else:
        signal = 'normal'
        signal_cn = '正常'
        description = '动能正常'

    return {
        'rsi': rsi_value,
        'signal': signal,
        'signal_cn': signal_cn,
        'description': description
    }


# =============================================================================
# 第一阶段：趋势与动量
# =============================================================================

def calculate_period_change(df: pd.DataFrame, periods: list = None) -> dict:
    """
    计算多周期涨跌幅

    Args:
        df: 包含 date, close 列的 DataFrame
        periods: 周期列表，默认 [5, 10, 20, 30]

    Returns:
        {'5d': 涨跌幅, '10d': 涨跌幅, ...}
    """
    if periods is None:
        periods = [5, 10, 20, 30]

    if df.empty or len(df) < 2:
        return {}

    df = df.sort_values('date', ascending=False).reset_index(drop=True)
    current_price = float(df.iloc[0]['close'])

    result = {}
    for period in periods:
        if len(df) > period:
            past_price = float(df.iloc[period]['close'])
            change_pct = (current_price - past_price) / past_price * 100
            result[f'{period}d'] = round(change_pct, 2)
        else:
            result[f'{period}d'] = None

    return result


def calculate_moving_averages(df: pd.DataFrame, windows: list = None) -> dict:
    """
    计算均线

    Args:
        df: 包含 date, close 列的 DataFrame
        windows: 均线周期列表，默认 [5, 10, 20, 60]

    Returns:
        {'ma5': 均线值, 'ma10': 均线值, ...}
    """
    if windows is None:
        windows = [5, 10, 20, 60]

    if df.empty:
        return {}

    df = df.sort_values('date', ascending=True).reset_index(drop=True)

    result = {}
    for window in windows:
        if len(df) >= window:
            ma_value = df['close'].tail(window).mean()
            result[f'ma{window}'] = round(float(ma_value), 2)
        else:
            result[f'ma{window}'] = None

    return result


def check_sell_signal(price: float, mas: dict, ma_key: str = 'ma10') -> dict:
    """
    检查卖出信号（跌破均线）

    Args:
        price: 当前价格
        mas: 均线数据
        ma_key: 用于判断的均线，默认 ma10

    Returns:
        {
            'should_sell': True/False,
            'ma_value': 均线值,
            'distance_pct': 距离均线百分比（负数表示在均线下方）
        }
    """
    ma_value = mas.get(ma_key)
    if not ma_value or not price:
        return {'should_sell': False, 'ma_value': None, 'distance_pct': None}

    distance_pct = (price - ma_value) / ma_value * 100

    return {
        'should_sell': price < ma_value,
        'ma_value': ma_value,
        'distance_pct': round(distance_pct, 2)
    }


def determine_trend_signal(price: float, mas: dict, changes: dict) -> dict:
    """
    综合判断趋势信号

    Args:
        price: 当前价格
        mas: 均线数据 {'ma5': ..., 'ma20': ...}
        changes: 涨跌幅数据 {'5d': ..., '10d': ...}

    Returns:
        {
            'signal': '多头' / '空头' / '震荡',
            'strength': 1-5 (强度),
            'description': 描述
        }
    """
    if not mas or not price:
        return {'signal': '未知', 'strength': 0, 'description': '数据不足'}

    ma5 = mas.get('ma5')
    ma10 = mas.get('ma10')
    ma20 = mas.get('ma20')
    ma60 = mas.get('ma60')

    change_5d = changes.get('5d', 0) or 0
    change_10d = changes.get('10d', 0) or 0
    change_20d = changes.get('20d', 0) or 0

    # 计算多头/空头得分
    bull_score = 0
    bear_score = 0

    # 价格与均线位置
    if ma5 and price > ma5:
        bull_score += 1
    elif ma5 and price < ma5:
        bear_score += 1

    if ma20 and price > ma20:
        bull_score += 1
    elif ma20 and price < ma20:
        bear_score += 1

    if ma60 and price > ma60:
        bull_score += 1
    elif ma60 and price < ma60:
        bear_score += 1

    # 均线排列
    if ma5 and ma10 and ma20:
        if ma5 > ma10 > ma20:
            bull_score += 2  # 多头排列
        elif ma5 < ma10 < ma20:
            bear_score += 2  # 空头排列

    # 涨跌趋势
    if change_5d > 0 and change_10d > 0:
        bull_score += 1
    elif change_5d < 0 and change_10d < 0:
        bear_score += 1

    # 判断信号
    total_score = bull_score - bear_score

    if total_score >= 3:
        signal = '多头'
        strength = min(5, total_score)
        description = '均线多头排列，价格强势'
    elif total_score <= -3:
        signal = '空头'
        strength = min(5, abs(total_score))
        description = '均线空头排列，价格弱势'
    elif total_score > 0:
        signal = '偏多'
        strength = total_score
        description = '趋势偏多，但力度有限'
    elif total_score < 0:
        signal = '偏空'
        strength = abs(total_score)
        description = '趋势偏空，注意风险'
    else:
        signal = '震荡'
        strength = 1
        description = '多空交织，方向不明'

    return {
        'signal': signal,
        'strength': strength,
        'description': description,
        'bull_score': bull_score,
        'bear_score': bear_score
    }


def analyze_index_trend(code: str, name: str, price: float, market: str = 'a_share', days: int = 90) -> dict:
    """
    分析单个指数的趋势

    Args:
        code: 指数代码
        name: 指数名称
        price: 当前价格
        market: 'a_share' 或 'us'
        days: 历史数据天数

    Returns:
        {
            'code': 代码,
            'name': 名称,
            'price': 当前价格,
            'changes': 多周期涨跌幅,
            'mas': 均线数据,
            'trend': 趋势信号,
            'sell_signal': 卖出信号
        }
    """
    # 获取历史数据
    if market == 'us':
        df = get_us_index_history(code, days=days)
    else:
        df = get_a_share_index_history(code, days=days)

    if df.empty:
        return {
            'code': code,
            'name': name,
            'price': price,
            'error': '无法获取历史数据'
        }

    # 计算技术指标
    changes = calculate_period_change(df, [5, 10, 20, 30])
    mas = calculate_moving_averages(df, [5, 10, 20, 60])
    trend = determine_trend_signal(price, mas, changes)

    # 检查卖出信号（基于MA10）
    sell_signal = check_sell_signal(price, mas, 'ma10')

    # 计算RSI
    rsi_value = calculate_rsi(df, period=14)
    rsi_analysis = analyze_rsi_signal(rsi_value)

    return {
        'code': code,
        'name': name,
        'price': price,
        'changes': changes,
        'mas': mas,
        'trend': trend,
        'sell_signal': sell_signal,
        'rsi': rsi_analysis
    }


def analyze_all_indices(indices_data: dict, config: dict = None) -> list:
    """
    批量分析所有指数趋势

    Args:
        indices_data: 市场数据 {'a_share': [...], 'us_stock': [...]}
        config: 配置文件（未使用，保留扩展性）

    Returns:
        分析结果列表
    """
    results = []

    # 分析 A 股指数
    for idx in indices_data.get('a_share', []):
        if 'error' in idx:
            continue
        analysis = analyze_index_trend(
            code=idx.get('code'),
            name=idx.get('name'),
            price=idx.get('price'),
            market='a_share'
        )
        results.append(analysis)

    # 分析美股指数
    for idx in indices_data.get('us_stock', []):
        if 'error' in idx:
            continue
        analysis = analyze_index_trend(
            code=idx.get('code'),
            name=idx.get('name'),
            price=idx.get('price'),
            market='us'
        )
        results.append(analysis)

    return results


# =============================================================================
# 北向资金趋势分析
# =============================================================================

def get_north_flow_history(days: int = 30) -> pd.DataFrame:
    """
    获取北向资金历史数据

    Args:
        days: 获取天数

    Returns:
        DataFrame: date, net_inflow (亿元)
    """
    cache_key = f"north_{days}"
    if cache_key in _north_flow_history_cache:
        return _north_flow_history_cache[cache_key]

    try:
        df = ak.stock_hsgt_hist_em(symbol="北向资金")
        if df is not None and not df.empty:
            df = df.rename(columns={
                '日期': 'date',
                '当日成交净买额': 'net_inflow'
            })
            df['date'] = pd.to_datetime(df['date'])
            df = df[['date', 'net_inflow']].dropna()
            df = df.sort_values('date', ascending=False).head(days)
            _north_flow_history_cache[cache_key] = df
            return df
    except Exception as e:
        print(f"  获取北向资金历史失败: {e}")

    return pd.DataFrame()


def count_consecutive_flow_days(df: pd.DataFrame) -> dict:
    """
    统计连续流入/流出天数

    Args:
        df: 北向资金历史数据

    Returns:
        {'direction': '流入'/'流出', 'days': 天数}
    """
    if df.empty:
        return {'direction': None, 'days': 0}

    df = df.sort_values('date', ascending=False).reset_index(drop=True)

    # 第一天的方向
    first_flow = df.iloc[0]['net_inflow']
    if first_flow > 0:
        direction = '流入'
        count = 0
        for _, row in df.iterrows():
            if row['net_inflow'] > 0:
                count += 1
            else:
                break
    else:
        direction = '流出'
        count = 0
        for _, row in df.iterrows():
            if row['net_inflow'] < 0:
                count += 1
            else:
                break

    return {'direction': direction, 'days': count}


def analyze_north_flow_trend(days: int = 30) -> dict:
    """
    分析北向资金趋势

    Returns:
        {
            'recent_5d': 近5日累计,
            'recent_10d': 近10日累计,
            'avg_5d': 5日日均,
            'consecutive': {'direction': '流入'/'流出', 'days': 天数},
            'history': 历史数据列表
        }
    """
    df = get_north_flow_history(days)

    if df.empty:
        return {'error': '无法获取北向资金历史数据'}

    df = df.sort_values('date', ascending=False).reset_index(drop=True)

    result = {}

    # 近5日累计
    if len(df) >= 5:
        result['recent_5d'] = round(float(df.head(5)['net_inflow'].sum()), 2)
        result['avg_5d'] = round(float(df.head(5)['net_inflow'].mean()), 2)

    # 近10日累计
    if len(df) >= 10:
        result['recent_10d'] = round(float(df.head(10)['net_inflow'].sum()), 2)

    # 近20日累计
    if len(df) >= 20:
        result['recent_20d'] = round(float(df.head(20)['net_inflow'].sum()), 2)

    # 连续流入/流出
    result['consecutive'] = count_consecutive_flow_days(df)

    # 历史数据（最近10天）
    result['history'] = df.head(10).to_dict('records')

    return result


# =============================================================================
# 成交额分析
# =============================================================================

def get_index_volume_history(code: str, days: int = 30) -> pd.DataFrame:
    """
    获取指数成交额历史数据

    Args:
        code: 指数代码
        days: 天数

    Returns:
        DataFrame: date, amount (成交额，元)
    """
    try:
        df = ak.index_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=(datetime.now() - timedelta(days=days)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d")
        )
        if df is not None and not df.empty:
            df['date'] = pd.to_datetime(df['日期'])
            df['amount'] = df['成交额'].astype(float)
            return df[['date', 'amount']].sort_values('date')
    except Exception as e:
        print(f"  获取指数 {code} 成交额历史失败: {e}")

    return pd.DataFrame()


def analyze_volume_trend(indices_data: dict) -> list:
    """
    分析成交额变化趋势

    Args:
        indices_data: 市场数据

    Returns:
        成交额分析结果列表
    """
    results = []

    for idx in indices_data.get('a_share', []):
        if 'error' in idx:
            continue

        code = idx.get('code')
        name = idx.get('name')
        today_amount = idx.get('amount', 0)

        if not today_amount:
            continue

        # 获取历史成交额
        df = get_index_volume_history(code, days=30)
        if df.empty or len(df) < 5:
            continue

        df = df.sort_values('date', ascending=False)

        # 计算5日均值（不含今日）
        avg_5d = df.iloc[1:6]['amount'].mean() if len(df) > 5 else df['amount'].mean()

        # 计算比例
        ratio = today_amount / avg_5d * 100 if avg_5d > 0 else 100

        results.append({
            'code': code,
            'name': name,
            'today_amount': today_amount,
            'avg_5d': round(avg_5d, 0),
            'ratio': round(ratio, 1)
        })

    return results


# =============================================================================
# 第二阶段：估值分位
# =============================================================================

def get_index_valuation(code: str) -> dict:
    """
    获取指数当前估值 (PE/PB)

    Args:
        code: 指数代码

    Returns:
        {'pe': PE值, 'pb': PB值}
    """
    try:
        # 尝试获取指数估值数据
        df = ak.index_value_hist_funddb(symbol=code, indicator="市盈率")
        if df is not None and not df.empty:
            df = df.sort_values('日期', ascending=False)
            pe = float(df.iloc[0]['市盈率'])
        else:
            pe = None
    except Exception:
        pe = None

    try:
        df = ak.index_value_hist_funddb(symbol=code, indicator="市净率")
        if df is not None and not df.empty:
            df = df.sort_values('日期', ascending=False)
            pb = float(df.iloc[0]['市净率'])
        else:
            pb = None
    except Exception:
        pb = None

    return {'pe': pe, 'pb': pb}


def get_index_valuation_history(code: str, years: int = 3) -> dict:
    """
    获取指数历史估值数据

    Args:
        code: 指数代码
        years: 历史年数

    Returns:
        {'pe_history': [...], 'pb_history': [...]}
    """
    cache_key = f"val_{code}_{years}"
    if cache_key in _valuation_history_cache:
        return _valuation_history_cache[cache_key]

    result = {'pe_history': [], 'pb_history': []}

    try:
        df = ak.index_value_hist_funddb(symbol=code, indicator="市盈率")
        if df is not None and not df.empty:
            df['日期'] = pd.to_datetime(df['日期'])
            cutoff = datetime.now() - timedelta(days=years * 365)
            df = df[df['日期'] >= cutoff]
            result['pe_history'] = df['市盈率'].dropna().tolist()
    except Exception:
        pass

    try:
        df = ak.index_value_hist_funddb(symbol=code, indicator="市净率")
        if df is not None and not df.empty:
            df['日期'] = pd.to_datetime(df['日期'])
            cutoff = datetime.now() - timedelta(days=years * 365)
            df = df[df['日期'] >= cutoff]
            result['pb_history'] = df['市净率'].dropna().tolist()
    except Exception:
        pass

    if result['pe_history'] or result['pb_history']:
        _valuation_history_cache[cache_key] = result

    return result


def calculate_percentile(current: float, history: list) -> Optional[float]:
    """
    计算当前值在历史数据中的分位数

    Args:
        current: 当前值
        history: 历史数据列表

    Returns:
        分位数 (0-100)
    """
    if not history or current is None:
        return None

    history = [x for x in history if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if not history:
        return None

    count_below = sum(1 for x in history if x < current)
    percentile = count_below / len(history) * 100

    return round(percentile, 1)


def analyze_index_valuation(code: str, name: str, years: int = 3) -> dict:
    """
    完整的指数估值分析

    Args:
        code: 指数代码
        name: 指数名称
        years: 历史年数

    Returns:
        {
            'code': 代码,
            'name': 名称,
            'pe': 当前PE,
            'pb': 当前PB,
            'pe_percentile': PE分位,
            'pb_percentile': PB分位,
            'level': '低估' / '中等' / '高估'
        }
    """
    # 获取当前估值
    current = get_index_valuation(code)
    pe = current.get('pe')
    pb = current.get('pb')

    # 获取历史估值
    history = get_index_valuation_history(code, years)

    # 计算分位
    pe_percentile = calculate_percentile(pe, history.get('pe_history', []))
    pb_percentile = calculate_percentile(pb, history.get('pb_history', []))

    # 判断估值水平
    avg_percentile = None
    if pe_percentile is not None and pb_percentile is not None:
        avg_percentile = (pe_percentile + pb_percentile) / 2
    elif pe_percentile is not None:
        avg_percentile = pe_percentile
    elif pb_percentile is not None:
        avg_percentile = pb_percentile

    if avg_percentile is not None:
        if avg_percentile <= 30:
            level = '低估'
        elif avg_percentile >= 70:
            level = '高估'
        else:
            level = '中等'
    else:
        level = '未知'

    return {
        'code': code,
        'name': name,
        'pe': round(pe, 2) if pe else None,
        'pb': round(pb, 2) if pb else None,
        'pe_percentile': pe_percentile,
        'pb_percentile': pb_percentile,
        'level': level
    }


def analyze_all_valuations(indices_data: dict) -> list:
    """
    批量分析指数估值

    Args:
        indices_data: 市场数据

    Returns:
        估值分析结果列表
    """
    results = []

    # 只分析A股主要指数（美股指数通常没有估值数据）
    for idx in indices_data.get('a_share', []):
        if 'error' in idx:
            continue

        code = idx.get('code')
        name = idx.get('name')

        # 只分析主要宽基指数
        if code in ['000300', '000905', '000688', '000510', '399006']:
            try:
                analysis = analyze_index_valuation(code, name)
                if analysis.get('pe') or analysis.get('pb'):
                    results.append(analysis)
            except Exception as e:
                print(f"  分析 {name} 估值失败: {e}")

    return results


# =============================================================================
# 第三阶段：持仓风险分析
# =============================================================================

def calculate_max_drawdown(nav_series: pd.Series) -> dict:
    """
    计算最大回撤

    Args:
        nav_series: 净值序列 (index=date, values=nav)

    Returns:
        {
            'max_drawdown': 最大回撤比例,
            'peak_date': 高点日期,
            'trough_date': 低点日期
        }
    """
    if nav_series.empty or len(nav_series) < 2:
        return {'max_drawdown': None}

    # 计算累计最高点
    cummax = nav_series.cummax()
    # 计算回撤
    drawdown = (nav_series - cummax) / cummax

    # 找最大回撤
    max_drawdown = drawdown.min()
    trough_idx = drawdown.idxmin()

    # 找高点（最大回撤前的最高点）
    peak_idx = nav_series[:trough_idx].idxmax()

    return {
        'max_drawdown': round(float(max_drawdown) * 100, 2),
        'peak_date': peak_idx.strftime('%m/%d') if hasattr(peak_idx, 'strftime') else str(peak_idx),
        'trough_date': trough_idx.strftime('%m/%d') if hasattr(trough_idx, 'strftime') else str(trough_idx)
    }


def calculate_volatility(returns: pd.Series, annualize: bool = True) -> Optional[float]:
    """
    计算波动率

    Args:
        returns: 日收益率序列
        annualize: 是否年化

    Returns:
        波动率 (百分比)
    """
    if returns.empty or len(returns) < 2:
        return None

    std = returns.std()

    if annualize:
        # 年化 (假设252个交易日)
        std = std * (252 ** 0.5)

    return round(float(std) * 100, 2)


def analyze_fund_risk(fund_code: str, fund_name: str, days: int = 30) -> dict:
    """
    分析单只基金的风险指标

    Args:
        fund_code: 基金代码
        fund_name: 基金名称
        days: 分析天数

    Returns:
        {
            'code': 代码,
            'name': 名称,
            'max_drawdown': 最大回撤,
            'volatility': 波动率,
            'drawdown_period': 回撤区间
        }
    """
    # 获取基金净值历史
    df = get_fund_nav_history(fund_code, days=days + 30)  # 多取一些确保数据够

    if df.empty or len(df) < days // 2:
        return {
            'code': fund_code,
            'name': fund_name,
            'error': '历史数据不足'
        }

    df = df.sort_values('date').tail(days)
    df = df.set_index('date')

    nav_series = df['nav']

    # 计算收益率
    returns = nav_series.pct_change().dropna()

    # 计算最大回撤
    drawdown = calculate_max_drawdown(nav_series)

    # 计算波动率
    volatility = calculate_volatility(returns, annualize=True)

    result = {
        'code': fund_code,
        'name': fund_name,
        'max_drawdown': drawdown.get('max_drawdown'),
        'volatility': volatility,
    }

    if drawdown.get('peak_date') and drawdown.get('trough_date'):
        result['drawdown_period'] = f"{drawdown['peak_date']}-{drawdown['trough_date']}"

    return result


def analyze_portfolio_risk(portfolio_data: dict, days: int = 30) -> dict:
    """
    分析整个持仓的风险

    Args:
        portfolio_data: 持仓数据 (估值结果)
        days: 分析天数

    Returns:
        {
            'funds': [各基金风险分析],
            'summary': {
                'avg_drawdown': 平均回撤,
                'max_drawdown_fund': 最大回撤基金,
                'avg_volatility': 平均波动率
            }
        }
    """
    funds = portfolio_data.get('funds', [])

    if not funds:
        return {'error': '持仓为空'}

    results = []
    total_drawdown = 0
    total_volatility = 0
    valid_count = 0
    max_drawdown = 0
    max_drawdown_fund = None

    for fund in funds:
        code = fund.get('code')
        name = fund.get('name', '')

        if not code:
            continue

        analysis = analyze_fund_risk(code, name, days)
        results.append(analysis)

        dd = analysis.get('max_drawdown')
        vol = analysis.get('volatility')

        if dd is not None:
            total_drawdown += abs(dd)
            valid_count += 1
            if abs(dd) > abs(max_drawdown):
                max_drawdown = dd
                max_drawdown_fund = name

        if vol is not None:
            total_volatility += vol

    summary = {}
    if valid_count > 0:
        summary['avg_drawdown'] = round(total_drawdown / valid_count, 2)
        summary['avg_volatility'] = round(total_volatility / valid_count, 2)
    if max_drawdown_fund:
        summary['max_drawdown_fund'] = max_drawdown_fund
        summary['max_drawdown'] = max_drawdown

    return {
        'funds': results,
        'summary': summary
    }


# =============================================================================
# 综合技术分析入口
# =============================================================================

def run_technical_analysis(indices_data: dict, portfolio_data: dict = None, config: dict = None) -> dict:
    """
    运行完整的技术分析

    Args:
        indices_data: 市场数据
        portfolio_data: 持仓数据（可选）
        config: 配置（可选）

    Returns:
        {
            'trend': 指数趋势分析,
            'north_flow': 北向资金趋势,
            'volume': 成交额分析,
            'valuation': 估值分位分析,
            'risk': 持仓风险分析
        }
    """
    print("📈 正在进行技术分析...")

    result = {}

    # 1. 指数趋势分析
    print("  分析指数趋势...")
    result['trend'] = analyze_all_indices(indices_data, config)

    # 2. 北向资金趋势
    print("  分析北向资金趋势...")
    result['north_flow'] = analyze_north_flow_trend()

    # 3. 成交额分析
    print("  分析成交额变化...")
    result['volume'] = analyze_volume_trend(indices_data)

    # 4. 估值分位（可能较慢）
    print("  分析指数估值...")
    result['valuation'] = analyze_all_valuations(indices_data)

    # 5. 持仓风险分析（如果有持仓数据）
    if portfolio_data and portfolio_data.get('funds'):
        print("  分析持仓风险...")
        result['risk'] = analyze_portfolio_risk(portfolio_data)

    return result


if __name__ == "__main__":
    # 测试
    import yaml

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    from src.market import collect_all_indices

    indices_data = collect_all_indices(config)

    print("\n=== 趋势分析测试 ===")
    trend_results = analyze_all_indices(indices_data)
    for r in trend_results:
        if 'error' not in r:
            print(f"{r['name']}: {r['trend']['signal']} "
                  f"(5日:{r['changes'].get('5d')}%, MA5:{r['mas'].get('ma5')})")

    print("\n=== 北向资金趋势 ===")
    north = analyze_north_flow_trend()
    if 'error' not in north:
        print(f"近5日累计: {north.get('recent_5d')}亿")
        print(f"连续{north['consecutive']['direction']}: {north['consecutive']['days']}天")
