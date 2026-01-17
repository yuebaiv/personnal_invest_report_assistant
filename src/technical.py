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
    检查卖出信号（跌破均线）- 基础版本，保持向后兼容

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


def calculate_ma_slope(df: pd.DataFrame, ma_period: int = 20, lookback: int = 5) -> Optional[float]:
    """
    计算均线斜率（判断趋势方向）

    Args:
        df: 价格数据
        ma_period: 均线周期
        lookback: 计算斜率的回看天数

    Returns:
        斜率百分比（正数向上，负数向下）
    """
    if df.empty or len(df) < ma_period + lookback:
        return None

    df = df.sort_values('date', ascending=True).reset_index(drop=True)

    # 计算MA序列
    ma_series = df['close'].rolling(window=ma_period).mean()

    if len(ma_series) < lookback + 1:
        return None

    # 取最近的MA值和lookback天前的MA值
    current_ma = ma_series.iloc[-1]
    past_ma = ma_series.iloc[-lookback - 1]

    if pd.isna(current_ma) or pd.isna(past_ma) or past_ma == 0:
        return None

    slope_pct = (current_ma - past_ma) / past_ma * 100
    return round(slope_pct, 2)


def count_days_below_ma(df: pd.DataFrame, ma_period: int = 10) -> int:
    """
    统计最近连续在MA下方的天数

    Args:
        df: 价格数据
        ma_period: 均线周期

    Returns:
        连续天数（0表示当前在MA上方）
    """
    if df.empty or len(df) < ma_period:
        return 0

    df = df.sort_values('date', ascending=True).reset_index(drop=True)

    # 计算MA
    df['ma'] = df['close'].rolling(window=ma_period).mean()

    # 从最新往前数连续在MA下方的天数
    count = 0
    for i in range(len(df) - 1, -1, -1):
        if pd.isna(df.iloc[i]['ma']):
            break
        if df.iloc[i]['close'] < df.iloc[i]['ma']:
            count += 1
        else:
            break

    return count


def generate_smart_signal(
    price: float,
    mas: dict,
    changes: dict,
    rsi: float = None,
    volume_ratio: float = None,
    ma20_slope: float = None,
    days_below_ma10: int = 0,
    market_breadth: dict = None
) -> dict:
    """
    生成智能交易信号（综合多维度判断）

    Args:
        price: 当前价格
        mas: 均线数据 {'ma5', 'ma10', 'ma20', 'ma60'}
        changes: 涨跌幅数据
        rsi: RSI值
        volume_ratio: 成交量相对5日均量的比例 (100 = 持平)
        ma20_slope: MA20斜率 (正数向上)
        days_below_ma10: 连续在MA10下方的天数
        market_breadth: 市场广度数据 {'rise_ratio': 涨跌比}

    Returns:
        {
            'action': 'buy' / 'hold' / 'watch' / 'reduce' / 'sell',
            'action_cn': 中文动作,
            'confidence': 1-5 (信心度),
            'reasons': [原因列表],
            'suggestion': 操作建议
        }
    """
    if not mas or not price:
        return {
            'action': 'unknown',
            'action_cn': '未知',
            'confidence': 0,
            'reasons': ['数据不足'],
            'suggestion': '等待数据'
        }

    ma5 = mas.get('ma5')
    ma10 = mas.get('ma10')
    ma20 = mas.get('ma20')
    ma60 = mas.get('ma60')

    reasons = []
    buy_score = 0   # 买入分数
    sell_score = 0  # 卖出分数

    # ========== 1. 均线位置分析 ==========

    # MA10 位置（核心短期指标）
    if ma10:
        distance_ma10 = (price - ma10) / ma10 * 100

        if distance_ma10 < -2:
            # 跌破MA10超过2%，较强卖出信号
            sell_score += 3
            reasons.append(f'跌破MA10超2%({distance_ma10:.1f}%)')
        elif distance_ma10 < -1:
            # 跌破MA10 1-2%，中等卖出信号
            sell_score += 2
            reasons.append(f'跌破MA10({distance_ma10:.1f}%)')
        elif distance_ma10 < 0:
            # 微幅跌破MA10，观望
            sell_score += 1
            reasons.append(f'微幅跌破MA10({distance_ma10:.1f}%)')
        elif distance_ma10 > 3:
            # 距离MA10过远，短期有回调风险
            sell_score += 1
            reasons.append(f'距MA10较远({distance_ma10:.1f}%)')

    # MA20 位置（中期趋势）
    if ma20:
        distance_ma20 = (price - ma20) / ma20 * 100

        if price > ma20:
            buy_score += 2
            reasons.append('站稳MA20')
        elif distance_ma20 < -2:
            sell_score += 2
            reasons.append(f'跌破MA20({distance_ma20:.1f}%)')

    # MA60 位置（长期趋势）
    if ma60:
        if price > ma60:
            buy_score += 1
            reasons.append('在MA60上方')
        else:
            sell_score += 1

    # ========== 2. MA20斜率分析（大趋势方向） ==========

    if ma20_slope is not None:
        if ma20_slope > 0.5:
            buy_score += 2
            reasons.append(f'MA20向上({ma20_slope:.1f}%)')
        elif ma20_slope > 0:
            buy_score += 1
        elif ma20_slope < -0.5:
            sell_score += 2
            reasons.append(f'MA20向下({ma20_slope:.1f}%)')
        elif ma20_slope < 0:
            sell_score += 1

    # ========== 3. 连续破位天数确认 ==========

    if days_below_ma10 >= 3:
        sell_score += 2
        reasons.append(f'连续{days_below_ma10}日破MA10')
    elif days_below_ma10 == 2:
        sell_score += 1
        reasons.append('连续2日破MA10')
    elif days_below_ma10 == 1:
        # 仅1天，可能是回踩
        pass

    # ========== 4. 成交量确认 ==========

    if volume_ratio is not None:
        if price < ma10 if ma10 else False:
            # 破位情况下看量
            if volume_ratio > 120:
                sell_score += 2
                reasons.append('放量下跌')
            elif volume_ratio < 80:
                buy_score += 1
                reasons.append('缩量回踩')

    # ========== 5. RSI分析 ==========

    if rsi is not None:
        if rsi > 80:
            sell_score += 2
            reasons.append(f'RSI严重超买({rsi:.0f})')
        elif rsi > 70:
            sell_score += 1
            reasons.append(f'RSI超买({rsi:.0f})')
        elif rsi < 20:
            buy_score += 2
            reasons.append(f'RSI严重超卖({rsi:.0f})')
        elif rsi < 30:
            buy_score += 1
            reasons.append(f'RSI超卖({rsi:.0f})')
        elif 40 <= rsi <= 60:
            # 中性区域，回踩企稳
            if ma10 and price < ma10:
                buy_score += 1
                reasons.append(f'RSI中性企稳({rsi:.0f})')

    # ========== 6. 市场广度修正 ==========

    if market_breadth:
        rise_ratio = market_breadth.get('rise_ratio', 1)
        if rise_ratio > 1.2:
            # 多数股票上涨，指数跌可能是权重拖累
            buy_score += 1
            reasons.append(f'市场广度强(涨跌比{rise_ratio:.2f})')
        elif rise_ratio < 0.8:
            sell_score += 1
            reasons.append(f'市场广度弱(涨跌比{rise_ratio:.2f})')

    # ========== 7. 特殊情况：MA10下方但MA20上方且斜率向上 ==========

    if ma10 and ma20 and ma20_slope is not None:
        if price < ma10 and price > ma20 and ma20_slope > 0:
            # 典型的牛市回踩
            buy_score += 2
            sell_score -= 1
            reasons.append('牛市回踩MA10')

    # ========== 综合判断 ==========

    net_score = buy_score - sell_score

    if net_score >= 4:
        action = 'buy'
        action_cn = '买入'
        suggestion = '趋势向好，可逢低布局'
    elif net_score >= 2:
        action = 'hold'
        action_cn = '持有'
        suggestion = '维持仓位，等待方向明确'
    elif net_score >= 0:
        action = 'watch'
        action_cn = '观望'
        suggestion = '短期震荡，暂不操作'
    elif net_score >= -2:
        action = 'reduce'
        action_cn = '减仓'
        suggestion = '趋势转弱，可适当减仓'
    else:
        action = 'sell'
        action_cn = '卖出'
        suggestion = '趋势走坏，建议离场'

    # 信心度
    confidence = min(5, max(1, abs(net_score)))

    return {
        'action': action,
        'action_cn': action_cn,
        'confidence': confidence,
        'reasons': reasons[:5],  # 最多5条原因
        'suggestion': suggestion,
        'scores': {
            'buy_score': buy_score,
            'sell_score': sell_score,
            'net_score': net_score
        }
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


def analyze_index_trend(
    code: str,
    name: str,
    price: float,
    market: str = 'a_share',
    days: int = 90,
    volume_ratio: float = None,
    market_breadth: dict = None
) -> dict:
    """
    分析单个指数的趋势

    Args:
        code: 指数代码
        name: 指数名称
        price: 当前价格
        market: 'a_share' 或 'us'
        days: 历史数据天数
        volume_ratio: 成交量相对5日均量的比例
        market_breadth: 市场广度数据（仅A股有效）

    Returns:
        {
            'code': 代码,
            'name': 名称,
            'price': 当前价格,
            'changes': 多周期涨跌幅,
            'mas': 均线数据,
            'trend': 趋势信号,
            'sell_signal': 卖出信号（旧版，保持兼容）,
            'smart_signal': 智能信号（新版）,
            'rsi': RSI分析
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

    # 检查卖出信号（基于MA10）- 旧版保持兼容
    sell_signal = check_sell_signal(price, mas, 'ma10')

    # 计算RSI
    rsi_value = calculate_rsi(df, period=14)
    rsi_analysis = analyze_rsi_signal(rsi_value)

    # 计算MA20斜率
    ma20_slope = calculate_ma_slope(df, ma_period=20, lookback=5)

    # 统计连续破MA10天数
    days_below_ma10 = count_days_below_ma(df, ma_period=10)

    # 生成智能信号（新版）
    smart_signal = generate_smart_signal(
        price=price,
        mas=mas,
        changes=changes,
        rsi=rsi_value,
        volume_ratio=volume_ratio,
        ma20_slope=ma20_slope,
        days_below_ma10=days_below_ma10,
        market_breadth=market_breadth if market == 'a_share' else None  # 只对A股使用广度数据
    )

    return {
        'code': code,
        'name': name,
        'price': price,
        'changes': changes,
        'mas': mas,
        'ma20_slope': ma20_slope,
        'days_below_ma10': days_below_ma10,
        'trend': trend,
        'sell_signal': sell_signal,
        'smart_signal': smart_signal,
        'rsi': rsi_analysis
    }


def analyze_all_indices(
    indices_data: dict,
    config: dict = None,
    volume_data: list = None,
    market_breadth: dict = None
) -> list:
    """
    批量分析所有指数趋势

    Args:
        indices_data: 市场数据 {'a_share': [...], 'us_stock': [...]}
        config: 配置文件（未使用，保留扩展性）
        volume_data: 成交量分析数据列表
        market_breadth: 市场广度数据

    Returns:
        分析结果列表
    """
    results = []

    # 构建成交量比例映射
    volume_map = {}
    if volume_data:
        for v in volume_data:
            volume_map[v.get('code')] = v.get('ratio')

    # 分析 A 股指数
    for idx in indices_data.get('a_share', []):
        if 'error' in idx:
            continue
        code = idx.get('code')
        analysis = analyze_index_trend(
            code=code,
            name=idx.get('name'),
            price=idx.get('price'),
            market='a_share',
            volume_ratio=volume_map.get(code),
            market_breadth=market_breadth
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

# 指数代码到乐咕API支持的指数名称映射
# 注：akshare stock_index_pe_lg/pb_lg 只支持有限指数
INDEX_CODE_TO_NAME = {
    '000300': '沪深300',
    '000016': '上证50',
    '000905': '中证500',
    '000852': '中证1000',
    # 科创50(000688)、中证A500(000510)、创业板指(399006)等暂不支持
}

# PE/PB 数据缓存
_pe_data_cache = {}
_pb_data_cache = {}


def _get_pe_data(index_name: str) -> pd.DataFrame:
    """获取指数PE数据（带缓存）"""
    if index_name in _pe_data_cache:
        return _pe_data_cache[index_name]

    try:
        df = ak.stock_index_pe_lg(symbol=index_name)
        if df is not None and not df.empty:
            _pe_data_cache[index_name] = df
            return df
    except Exception:
        pass
    return pd.DataFrame()


def _get_pb_data(index_name: str) -> pd.DataFrame:
    """获取指数PB数据（带缓存）"""
    if index_name in _pb_data_cache:
        return _pb_data_cache[index_name]

    try:
        df = ak.stock_index_pb_lg(symbol=index_name)
        if df is not None and not df.empty:
            _pb_data_cache[index_name] = df
            return df
    except Exception:
        pass
    return pd.DataFrame()


def get_index_valuation(code: str) -> dict:
    """
    获取指数当前估值 (PE/PB)

    Args:
        code: 指数代码

    Returns:
        {'pe': PE值, 'pb': PB值}
    """
    # 获取指数名称
    index_name = INDEX_CODE_TO_NAME.get(code)
    if not index_name:
        return {'pe': None, 'pb': None}

    pe = None
    pb = None

    # 获取PE
    df_pe = _get_pe_data(index_name)
    if not df_pe.empty:
        try:
            # 使用滚动市盈率（TTM）
            pe = float(df_pe.iloc[-1]['滚动市盈率'])
        except Exception:
            pass

    # 获取PB
    df_pb = _get_pb_data(index_name)
    if not df_pb.empty:
        try:
            pb = float(df_pb.iloc[-1]['市净率'])
        except Exception:
            pass

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

    # 获取指数名称
    index_name = INDEX_CODE_TO_NAME.get(code)
    if not index_name:
        return {'pe_history': [], 'pb_history': []}

    result = {'pe_history': [], 'pb_history': []}
    cutoff = datetime.now() - timedelta(days=years * 365)

    # 获取PE历史
    df_pe = _get_pe_data(index_name)
    if not df_pe.empty:
        try:
            df_pe = df_pe.copy()
            df_pe['日期'] = pd.to_datetime(df_pe['日期'])
            df_pe = df_pe[df_pe['日期'] >= cutoff]
            result['pe_history'] = df_pe['滚动市盈率'].dropna().tolist()
        except Exception:
            pass

    # 获取PB历史
    df_pb = _get_pb_data(index_name)
    if not df_pb.empty:
        try:
            df_pb = df_pb.copy()
            df_pb['日期'] = pd.to_datetime(df_pb['日期'])
            df_pb = df_pb[df_pb['日期'] >= cutoff]
            result['pb_history'] = df_pb['市净率'].dropna().tolist()
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

def run_technical_analysis(
    indices_data: dict,
    portfolio_data: dict = None,
    config: dict = None,
    market_breadth: dict = None,
    sentiment_data: dict = None
) -> dict:
    """
    运行完整的技术分析

    Args:
        indices_data: 市场数据
        portfolio_data: 持仓数据（可选）
        config: 配置（可选）
        market_breadth: 市场广度数据（可选，来自sentiment分析）
        sentiment_data: 完整情绪分析数据（可选）

    Returns:
        {
            'trend': 指数趋势分析,
            'north_flow': 北向资金趋势,
            'volume': 成交额分析,
            'valuation': 估值分位分析,
            'risk': 持仓风险分析,
            'recommendations': 情境化投资建议
        }
    """
    print("📈 正在进行技术分析...")

    result = {}

    # 2. 北向资金趋势（先分析，因为不依赖其他）
    print("  分析北向资金趋势...")
    result['north_flow'] = analyze_north_flow_trend()

    # 3. 成交额分析（先分析，供趋势分析使用）
    print("  分析成交额变化...")
    result['volume'] = analyze_volume_trend(indices_data)

    # 1. 指数趋势分析（使用成交量和市场广度数据）
    print("  分析指数趋势...")
    result['trend'] = analyze_all_indices(
        indices_data,
        config,
        volume_data=result['volume'],
        market_breadth=market_breadth
    )

    # 4. 估值分位（可能较慢）
    print("  分析指数估值...")
    result['valuation'] = analyze_all_valuations(indices_data)

    # 5. 持仓风险分析（如果有持仓数据）
    if portfolio_data and portfolio_data.get('funds'):
        print("  分析持仓风险...")
        result['risk'] = analyze_portfolio_risk(portfolio_data)

    # 6. 生成情境化投资建议
    print("  生成投资建议...")
    result['recommendations'] = generate_all_recommendations(
        trend_data=result['trend'],
        valuation_data=result['valuation'],
        portfolio_data=portfolio_data,
        sentiment_data=sentiment_data,
        config=config
    )

    # 打印建议摘要
    for rec in result['recommendations'][:3]:
        action = rec.get('action_cn', '')
        name = rec.get('index_name', '')
        context = rec.get('context', '')
        print(f"    {name}: {action} ({context})")

    return result


# =============================================================================
# 情境化投资建议引擎
# =============================================================================

def calculate_position_weight(portfolio_data: dict, index_code: str, fund_index_mapping: dict = None) -> dict:
    """
    计算指数相关持仓权重

    Args:
        portfolio_data: 持仓数据
        index_code: 指数代码
        fund_index_mapping: 基金-指数映射配置

    Returns:
        {
            'weight': 持仓占比 (0-100%),
            'amount': 持仓金额,
            'related_funds': 相关基金列表
        }
    """
    if not portfolio_data or 'funds' not in portfolio_data:
        return {'weight': 0, 'amount': 0, 'related_funds': []}

    funds_data = portfolio_data.get('funds', {})
    summary = portfolio_data.get('summary', {})
    total_invested = summary.get('net_invested', 0) or summary.get('total_invested', 0)

    if total_invested <= 0:
        return {'weight': 0, 'amount': 0, 'related_funds': []}

    # funds_data 可能是 dict 或 list
    if isinstance(funds_data, dict):
        funds = list(funds_data.values())
    else:
        funds = funds_data

    # 指数代码映射关系（包含关键词匹配）
    index_mapping = {
        '000300': ['000300', 'hs300', '沪深300'],
        '000905': ['000905', 'zz500', '中证500'],
        '000510': ['000510', 'zza500', '中证a500', 'a500'],
        '000688': ['000688', 'kc50', '科创50', '科创'],
        '399006': ['399006', 'cyb', '创业板'],
        '^GSPC': ['^GSPC', 'sp500', '标普500', '标普'],
        '^NDX': ['^NDX', 'nasdaq100', '纳斯达克100', '纳指100'],
        '^IXIC': ['^IXIC', 'nasdaq', '纳斯达克', '纳指'],
        '^DJI': ['^DJI', 'dow', '道琼斯'],
    }

    related_codes = index_mapping.get(index_code, [index_code])

    related_funds = []
    related_amount = 0

    for fund in funds:
        if not isinstance(fund, dict):
            continue
        fund_name = fund.get('name', '').lower()
        fund_code = fund.get('code', '')
        net_invested = fund.get('net_invested', 0) or fund.get('amount', 0)

        # 检查基金是否跟踪该指数
        is_related = False

        # 通过配置映射
        if fund_index_mapping and fund_code in fund_index_mapping:
            mapped_index = fund_index_mapping[fund_code].get('index_code', '')
            if mapped_index in related_codes or mapped_index == index_code:
                is_related = True

        # 通过名称匹配
        if not is_related:
            for code_keyword in related_codes:
                if code_keyword.lower() in fund_name:
                    is_related = True
                    break

        if is_related:
            related_funds.append({
                'code': fund_code,
                'name': fund.get('name'),
                'amount': net_invested
            })
            related_amount += net_invested

    weight = (related_amount / total_invested * 100) if total_invested > 0 else 0

    return {
        'weight': round(weight, 1),
        'amount': round(related_amount, 2),
        'related_funds': related_funds
    }


def estimate_max_drawdown_risk(
    current_price: float,
    mas: dict,
    valuation_percentile: float = None,
    historical_volatility: float = None
) -> dict:
    """
    估算潜在最大回撤风险

    Args:
        current_price: 当前价格
        mas: 均线数据
        valuation_percentile: 估值分位 (0-100)
        historical_volatility: 历史波动率

    Returns:
        {
            'estimated_drawdown': 预估回撤幅度 (%),
            'support_levels': [支撑位列表],
            'risk_level': '低' / '中' / '高'
        }
    """
    ma20 = mas.get('ma20')
    ma60 = mas.get('ma60')

    support_levels = []
    if ma20:
        support_levels.append({'level': 'MA20', 'price': ma20, 'distance': round((current_price - ma20) / current_price * 100, 1)})
    if ma60:
        support_levels.append({'level': 'MA60', 'price': ma60, 'distance': round((current_price - ma60) / current_price * 100, 1)})

    # 估算回撤幅度
    base_drawdown = 5  # 基础回撤

    # 估值因素
    if valuation_percentile is not None:
        if valuation_percentile > 80:
            base_drawdown += 8
        elif valuation_percentile > 60:
            base_drawdown += 4
        elif valuation_percentile < 30:
            base_drawdown -= 2

    # 距离均线因素
    if ma20 and current_price > ma20:
        distance = (current_price - ma20) / ma20 * 100
        if distance > 10:
            base_drawdown += 5
        elif distance > 5:
            base_drawdown += 2

    # 波动率因素
    if historical_volatility:
        if historical_volatility > 25:
            base_drawdown += 3
        elif historical_volatility < 15:
            base_drawdown -= 2

    # 风险等级
    if base_drawdown >= 15:
        risk_level = '高'
    elif base_drawdown >= 8:
        risk_level = '中'
    else:
        risk_level = '低'

    return {
        'estimated_drawdown': round(base_drawdown, 1),
        'support_levels': support_levels,
        'risk_level': risk_level
    }


def generate_contextual_recommendation(
    index_code: str,
    index_name: str,
    trend_data: dict,
    valuation_data: dict = None,
    position_data: dict = None,
    risk_data: dict = None,
    sentiment_data: dict = None
) -> dict:
    """
    生成情境化投资建议

    Args:
        index_code: 指数代码
        index_name: 指数名称
        trend_data: 趋势分析数据
        valuation_data: 估值分析数据
        position_data: 持仓权重数据
        risk_data: 风险分析数据
        sentiment_data: 市场情绪数据

    Returns:
        {
            'action': 建议动作,
            'action_cn': 中文动作,
            'confidence': 信心度 (1-5),
            'context': 情境描述,
            'reasoning': 推理过程,
            'risk_warning': 风险提示,
            'position_advice': 仓位建议
        }
    """
    # 提取各维度数据
    smart_signal = trend_data.get('smart_signal', {})
    mas = trend_data.get('mas', {})
    price = trend_data.get('price', 0)
    ma20_slope = trend_data.get('ma20_slope')
    rsi = trend_data.get('rsi', {}).get('rsi')

    # 估值分位
    val_percentile = None
    val_level = '未知'
    if valuation_data:
        pe_pct = valuation_data.get('pe_percentile')
        pb_pct = valuation_data.get('pb_percentile')
        if pe_pct is not None and pb_pct is not None:
            val_percentile = (pe_pct + pb_pct) / 2
        elif pe_pct is not None:
            val_percentile = pe_pct
        elif pb_pct is not None:
            val_percentile = pb_pct
        val_level = valuation_data.get('level', '未知')

    # 持仓权重
    position_weight = position_data.get('weight', 0) if position_data else 0

    # 构建情境矩阵
    # 趋势: 强/中/弱
    net_score = smart_signal.get('scores', {}).get('net_score', 0)
    if net_score >= 3:
        trend_strength = 'strong'
        trend_cn = '强势'
    elif net_score >= 0:
        trend_strength = 'medium'
        trend_cn = '中性'
    else:
        trend_strength = 'weak'
        trend_cn = '弱势'

    # 估值: 低/中/高
    if val_percentile is not None:
        if val_percentile <= 30:
            valuation_level = 'low'
            val_cn = '低估'
        elif val_percentile >= 70:
            valuation_level = 'high'
            val_cn = '高估'
        else:
            valuation_level = 'medium'
            val_cn = '适中'
    else:
        valuation_level = 'unknown'
        val_cn = '未知'

    # 仓位: 重/中/轻/空
    if position_weight >= 30:
        position_level = 'heavy'
        pos_cn = '重仓'
    elif position_weight >= 15:
        position_level = 'medium'
        pos_cn = '中仓'
    elif position_weight > 0:
        position_level = 'light'
        pos_cn = '轻仓'
    else:
        position_level = 'empty'
        pos_cn = '空仓'

    # ========== 情境化决策矩阵 ==========

    reasoning = []
    risk_warnings = []

    # 情境1: 趋势强 + 低估 + 轻仓/空仓 → 积极买入
    if trend_strength == 'strong' and valuation_level == 'low' and position_level in ['light', 'empty']:
        action = 'strong_buy'
        action_cn = '积极买入'
        confidence = 5
        context = '黄金买点'
        reasoning.append(f'趋势{trend_cn}，估值{val_cn}({val_percentile:.0f}%分位)')
        reasoning.append(f'当前{pos_cn}，有充足加仓空间')
        position_advice = '建议分2-3次建仓至目标仓位'

    # 情境2: 趋势强 + 低估 + 重仓 → 持有
    elif trend_strength == 'strong' and valuation_level == 'low' and position_level == 'heavy':
        action = 'hold'
        action_cn = '坚定持有'
        confidence = 4
        context = '最佳持仓期'
        reasoning.append(f'趋势{trend_cn}，估值{val_cn}')
        reasoning.append(f'已{pos_cn}，继续持有享受上涨')
        position_advice = '无需操作，等待趋势走坏再考虑减仓'

    # 情境3: 趋势强 + 高估 + 重仓 → 逐步止盈
    elif trend_strength == 'strong' and valuation_level == 'high' and position_level in ['heavy', 'medium']:
        action = 'take_profit'
        action_cn = '逐步止盈'
        confidence = 4
        context = '高位风险'
        reasoning.append(f'趋势仍{trend_cn}，但估值已{val_cn}({val_percentile:.0f}%分位)')
        reasoning.append(f'当前{pos_cn}，建议逐步兑现利润')
        risk_warnings.append(f'估值处于历史{val_percentile:.0f}%分位，回撤风险增大')
        position_advice = '建议减仓1/3，锁定部分利润'

    # 情境4: 趋势强 + 高估 + 轻仓/空仓 → 小仓试探
    elif trend_strength == 'strong' and valuation_level == 'high' and position_level in ['light', 'empty']:
        action = 'small_position'
        action_cn = '小仓试探'
        confidence = 2
        context = '高位追涨'
        reasoning.append(f'趋势{trend_cn}，但估值{val_cn}({val_percentile:.0f}%分位)')
        reasoning.append(f'当前{pos_cn}，可小仓参与，但不宜重仓')
        risk_warnings.append('追涨高估值资产风险较大')
        position_advice = '仅用10-15%仓位试探，严格止损'

    # 情境5: 趋势弱 + 低估 → 分批布局
    elif trend_strength == 'weak' and valuation_level == 'low':
        action = 'accumulate'
        action_cn = '分批布局'
        confidence = 3
        context = '逢低布局'
        reasoning.append(f'短期趋势{trend_cn}，但估值{val_cn}({val_percentile:.0f}%分位)')
        reasoning.append('价值投资角度具有吸引力')
        risk_warnings.append('短期可能继续下跌，需有耐心')
        position_advice = '建议定投或分3-5次逐步建仓'

    # 情境6: 趋势弱 + 高估 + 重仓 → 减仓避险
    elif trend_strength == 'weak' and valuation_level == 'high' and position_level in ['heavy', 'medium']:
        action = 'reduce'
        action_cn = '减仓避险'
        confidence = 5
        context = '高风险区'
        reasoning.append(f'趋势{trend_cn}且估值{val_cn}({val_percentile:.0f}%分位)')
        reasoning.append(f'当前{pos_cn}，风险敞口过大')
        risk_warnings.append('双杀风险：估值回归+趋势下行')
        position_advice = '建议减仓50%以上，控制回撤'

    # 情境7: 趋势弱 + 高估 + 轻仓/空仓 → 观望
    elif trend_strength == 'weak' and valuation_level == 'high' and position_level in ['light', 'empty']:
        action = 'wait'
        action_cn = '耐心等待'
        confidence = 4
        context = '等待机会'
        reasoning.append(f'趋势{trend_cn}，估值{val_cn}')
        reasoning.append(f'当前{pos_cn}是正确选择，继续等待')
        position_advice = '保持观望，等待估值或趋势改善'

    # 情境8: 趋势中性 → 根据估值和仓位微调
    else:
        if valuation_level == 'low' and position_level in ['light', 'empty']:
            action = 'buy_dip'
            action_cn = '逢低买入'
            confidence = 3
            context = '震荡布局'
            reasoning.append(f'趋势{trend_cn}，但估值{val_cn}')
            position_advice = '可在回调时小幅加仓'
        elif valuation_level == 'high' and position_level in ['heavy', 'medium']:
            action = 'trim'
            action_cn = '适度减仓'
            confidence = 3
            context = '高位震荡'
            reasoning.append(f'趋势{trend_cn}，估值偏高')
            risk_warnings.append('震荡市高估值容易向下突破')
            position_advice = '可减仓20-30%降低风险'
        else:
            action = 'hold'
            action_cn = '持有观望'
            confidence = 2
            context = '方向不明'
            reasoning.append(f'趋势{trend_cn}，估值{val_cn}，仓位{pos_cn}')
            position_advice = '维持现状，等待方向明确'

    # RSI 修正
    if rsi:
        if rsi > 75:
            risk_warnings.append(f'RSI={rsi:.0f}，短期超买严重')
            if action in ['strong_buy', 'buy_dip']:
                action = 'wait'
                action_cn = '等待回调'
                reasoning.append('RSI超买，等待回调再入场')
        elif rsi < 25:
            reasoning.append(f'RSI={rsi:.0f}，短期超卖，反弹概率大')

    # 市场情绪修正
    if sentiment_data:
        summary = sentiment_data.get('summary', {})
        sentiment_score = summary.get('score', 0)
        if sentiment_score < -30:
            risk_warnings.append('市场情绪悲观，注意系统性风险')
        elif sentiment_score > 30:
            reasoning.append('市场情绪乐观')

    # 估算风险
    risk_estimate = estimate_max_drawdown_risk(price, mas, val_percentile)

    return {
        'index_code': index_code,
        'index_name': index_name,
        'action': action,
        'action_cn': action_cn,
        'confidence': confidence,
        'context': context,
        'reasoning': reasoning,
        'risk_warning': risk_warnings,
        'position_advice': position_advice,
        'metrics': {
            'trend': trend_cn,
            'valuation': f'{val_cn}({val_percentile:.0f}%)' if val_percentile else val_cn,
            'position': pos_cn,
            'estimated_drawdown': f"{risk_estimate['estimated_drawdown']}%",
            'risk_level': risk_estimate['risk_level']
        }
    }


def get_holding_indices(portfolio_data: dict, fund_index_mapping: dict) -> dict:
    """
    从持仓数据中提取实际持有的指数

    支持两种数据结构:
    1. 原始portfolio.json: {'funds': {name: {code, net_invested, ...}}}
    2. 估值结果: {'funds': [{code, name, total_invested, market_value, ...}]}

    Returns:
        {index_code: {'name': 指数名, 'amount': 金额, 'funds': [相关基金]}}
    """
    if not portfolio_data or 'funds' not in portfolio_data:
        return {}

    funds_data = portfolio_data.get('funds', {})
    if isinstance(funds_data, dict):
        funds = list(funds_data.values())
    else:
        funds = funds_data

    # 按指数汇总
    index_holdings = {}

    for fund in funds:
        if not isinstance(fund, dict):
            continue

        fund_code = fund.get('code', '')
        fund_name = fund.get('name', '')
        # 支持多种字段名: net_invested (原始), market_value (估值), total_invested
        net_invested = (
            fund.get('net_invested')
            or fund.get('market_value')
            or fund.get('total_invested')
            or fund.get('amount')
            or 0
        )

        if net_invested <= 0:
            continue

        # 通过配置映射获取跟踪指数
        if fund_code in fund_index_mapping:
            mapping = fund_index_mapping[fund_code]
            index_code = mapping.get('index_code', '')
            index_name = mapping.get('index_name', '')

            if index_code:
                if index_code not in index_holdings:
                    index_holdings[index_code] = {
                        'name': index_name,
                        'amount': 0,
                        'funds': []
                    }
                index_holdings[index_code]['amount'] += net_invested
                index_holdings[index_code]['funds'].append({
                    'code': fund_code,
                    'name': fund_name,
                    'amount': net_invested
                })

    return index_holdings


def generate_all_recommendations(
    trend_data: list,
    valuation_data: list,
    portfolio_data: dict = None,
    sentiment_data: dict = None,
    config: dict = None
) -> list:
    """
    为实际持仓的指数生成情境化建议

    Args:
        trend_data: 趋势分析结果列表
        valuation_data: 估值分析结果列表
        portfolio_data: 持仓数据
        sentiment_data: 市场情绪数据
        config: 配置文件

    Returns:
        建议列表（只包含实际持仓的指数）
    """
    # 构建估值映射
    val_map = {}
    for v in valuation_data or []:
        val_map[v.get('code')] = v

    # 构建趋势映射
    trend_map = {}
    for t in trend_data or []:
        if 'error' not in t:
            trend_map[t.get('code')] = t

    # 获取基金-指数映射
    fund_index_mapping = config.get('fund_index_mapping', {}) if config else {}

    # 获取实际持仓的指数
    holding_indices = get_holding_indices(portfolio_data, fund_index_mapping)

    if not holding_indices:
        # 如果没有持仓数据，返回所有跟踪指数的建议（兼容旧逻辑）
        recommendations = []
        for trend in trend_data:
            if 'error' in trend:
                continue
            code = trend.get('code')
            name = trend.get('name')
            valuation = val_map.get(code)
            position = calculate_position_weight(portfolio_data, code, fund_index_mapping)
            rec = generate_contextual_recommendation(
                index_code=code,
                index_name=name,
                trend_data=trend,
                valuation_data=valuation,
                position_data=position,
                sentiment_data=sentiment_data
            )
            recommendations.append(rec)
        return recommendations

    recommendations = []
    summary = portfolio_data.get('summary', {})
    total_invested = summary.get('net_invested') or summary.get('total_invested') or 0

    for index_code, holding_info in holding_indices.items():
        index_name = holding_info['name']
        index_amount = holding_info['amount']
        related_funds = holding_info['funds']

        # 获取趋势数据
        trend = trend_map.get(index_code)
        if not trend:
            # 没有趋势数据时使用空数据
            trend = {'code': index_code, 'name': index_name, 'trend': {}, 'smart_signal': {}}

        # 获取估值数据
        valuation = val_map.get(index_code)

        # 构建持仓权重数据
        weight = (index_amount / total_invested * 100) if total_invested > 0 else 0
        position = {
            'weight': round(weight, 1),
            'amount': round(index_amount, 2),
            'related_funds': related_funds
        }

        # 生成建议
        rec = generate_contextual_recommendation(
            index_code=index_code,
            index_name=index_name,
            trend_data=trend,
            valuation_data=valuation,
            position_data=position,
            sentiment_data=sentiment_data
        )

        recommendations.append(rec)

    # 按持仓金额降序排列
    recommendations.sort(key=lambda x: x.get('position_weight', 0), reverse=True)

    return recommendations


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
