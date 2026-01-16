"""
市场情绪模块

提供融资融券、涨跌家数、国债收益率、VIX、美元指数等市场情绪指标
"""

import math
from datetime import datetime, timedelta
from typing import Optional

import akshare as ak
import pandas as pd
import yfinance as yf


# 缓存
_margin_history_cache = {}
_bond_yield_cache = {}
_usd_index_cache = {}


# =============================================================================
# P0 核心指标：融资融券
# =============================================================================

def get_margin_balance() -> dict:
    """
    获取两融余额（融资余额 + 融券余额）

    Returns:
        {
            'date': 日期,
            'margin_balance': 融资余额(亿元),
            'margin_change': 较昨日变化(亿元),
            'short_balance': 融券余额(亿元),
            'total_balance': 两融余额(亿元),
            'timestamp': 获取时间
        }
    """
    try:
        # 获取沪市融资融券数据
        df_sse = ak.stock_margin_sse(start_date="2024-01-01")
        if df_sse is not None and not df_sse.empty:
            # 排序获取最新数据
            df_sse = df_sse.sort_values('信用交易日期', ascending=False)
            latest = df_sse.iloc[0]
            prev = df_sse.iloc[1] if len(df_sse) > 1 else None

            # 融资余额(元转亿元)
            sse_margin = float(latest.get('融资余额(元)', 0)) / 100000000
            sse_prev = float(prev.get('融资余额(元)', 0)) / 100000000 if prev is not None else 0

            # 获取深市融资融券数据
            df_szse = ak.stock_margin_szse(start_date="2024-01-01")
            szse_margin = 0
            szse_prev = 0
            if df_szse is not None and not df_szse.empty:
                df_szse = df_szse.sort_values('交易日期', ascending=False)
                szse_latest = df_szse.iloc[0]
                szse_margin = float(szse_latest.get('融资余额(元)', 0)) / 100000000
                if len(df_szse) > 1:
                    szse_prev = float(df_szse.iloc[1].get('融资余额(元)', 0)) / 100000000

            total_margin = sse_margin + szse_margin
            total_prev = sse_prev + szse_prev
            margin_change = total_margin - total_prev

            return {
                'date': str(latest.get('信用交易日期', '')),
                'margin_balance': round(total_margin, 2),
                'margin_change': round(margin_change, 2),
                'sse_margin': round(sse_margin, 2),
                'szse_margin': round(szse_margin, 2),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
    except Exception as e:
        pass

    # 备用方案：使用汇总数据
    try:
        df = ak.stock_margin_account_info()
        if df is not None and not df.empty:
            df = df.sort_values('日期', ascending=False)
            latest = df.iloc[0]
            prev = df.iloc[1] if len(df) > 1 else None

            margin = float(latest.get('融资余额', 0))
            prev_margin = float(prev.get('融资余额', 0)) if prev is not None else 0

            return {
                'date': str(latest.get('日期', '')),
                'margin_balance': round(margin / 100000000, 2),
                'margin_change': round((margin - prev_margin) / 100000000, 2),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
    except Exception as e:
        return {'error': f'获取融资余额失败: {str(e)}'}

    return {'error': '无法获取融资余额数据'}


def get_margin_balance_history(days: int = 30) -> pd.DataFrame:
    """
    获取历史融资余额

    Args:
        days: 历史天数

    Returns:
        DataFrame: date, margin_balance (亿元)
    """
    cache_key = f"margin_{days}"
    if cache_key in _margin_history_cache:
        return _margin_history_cache[cache_key]

    try:
        # 计算开始日期
        start_date = (datetime.now() - timedelta(days=days + 30)).strftime("%Y-%m-%d")

        # 获取沪市数据
        df_sse = ak.stock_margin_sse(start_date=start_date.replace("-", ""))
        if df_sse is not None and not df_sse.empty:
            df_sse = df_sse.rename(columns={
                '信用交易日期': 'date',
                '融资余额(元)': 'sse_margin'
            })
            df_sse['date'] = pd.to_datetime(df_sse['date'])
            df_sse['sse_margin'] = df_sse['sse_margin'].astype(float) / 100000000

            # 获取深市数据
            df_szse = ak.stock_margin_szse(start_date=start_date.replace("-", ""))
            if df_szse is not None and not df_szse.empty:
                df_szse = df_szse.rename(columns={
                    '交易日期': 'date',
                    '融资余额(元)': 'szse_margin'
                })
                df_szse['date'] = pd.to_datetime(df_szse['date'])
                df_szse['szse_margin'] = df_szse['szse_margin'].astype(float) / 100000000

                # 合并
                df = df_sse.merge(df_szse[['date', 'szse_margin']], on='date', how='outer')
                df = df.fillna(0)
                df['margin_balance'] = df['sse_margin'] + df['szse_margin']
            else:
                df = df_sse.copy()
                df['margin_balance'] = df['sse_margin']

            df = df[['date', 'margin_balance']].sort_values('date', ascending=False).head(days)
            _margin_history_cache[cache_key] = df
            return df
    except Exception as e:
        print(f"  获取融资余额历史失败: {e}")

    return pd.DataFrame()


def analyze_margin_trend() -> dict:
    """
    分析融资余额趋势

    Returns:
        {
            'current': 当前融资余额,
            'change_1d': 日变化,
            'change_5d': 5日变化,
            'change_10d': 10日变化,
            'avg_5d': 5日日均变化,
            'trend': '增加' / '减少' / '持平'
        }
    """
    current = get_margin_balance()
    if 'error' in current:
        return current

    df = get_margin_balance_history(30)
    if df.empty:
        return {
            'current': current.get('margin_balance'),
            'change_1d': current.get('margin_change'),
            'error': '历史数据不足'
        }

    df = df.sort_values('date', ascending=False).reset_index(drop=True)

    result = {
        'current': current.get('margin_balance'),
        'change_1d': current.get('margin_change'),
        'date': current.get('date'),
    }

    # 计算5日、10日累计变化
    if len(df) >= 5:
        change_5d = float(df.iloc[0]['margin_balance']) - float(df.iloc[4]['margin_balance'])
        result['change_5d'] = round(change_5d, 2)
        result['avg_5d'] = round(change_5d / 5, 2)

    if len(df) >= 10:
        change_10d = float(df.iloc[0]['margin_balance']) - float(df.iloc[9]['margin_balance'])
        result['change_10d'] = round(change_10d, 2)

    # 判断趋势
    change_5d = result.get('change_5d', 0)
    if change_5d > 50:  # 5日增加超50亿
        result['trend'] = '增加'
        result['signal'] = 'bullish'
    elif change_5d < -50:
        result['trend'] = '减少'
        result['signal'] = 'bearish'
    else:
        result['trend'] = '持平'
        result['signal'] = 'neutral'

    return result


# =============================================================================
# P0 核心指标：涨跌家数 / 创新高低
# =============================================================================

def get_market_breadth() -> dict:
    """
    获取市场涨跌家数

    Returns:
        {
            'rise_count': 上涨家数,
            'fall_count': 下跌家数,
            'flat_count': 平盘家数,
            'rise_ratio': 涨跌比 (>1偏多),
            'limit_up': 涨停家数,
            'limit_down': 跌停家数,
            'timestamp': 获取时间
        }
    """
    try:
        # 获取A股实时行情
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            # 涨跌幅
            change_col = '涨跌幅'
            if change_col in df.columns:
                rise_count = len(df[df[change_col] > 0])
                fall_count = len(df[df[change_col] < 0])
                flat_count = len(df[df[change_col] == 0])

                # 涨跌停
                limit_up = len(df[df[change_col] >= 9.9])
                limit_down = len(df[df[change_col] <= -9.9])

                rise_ratio = rise_count / fall_count if fall_count > 0 else float('inf')

                return {
                    'rise_count': rise_count,
                    'fall_count': fall_count,
                    'flat_count': flat_count,
                    'total_count': len(df),
                    'rise_ratio': round(rise_ratio, 2),
                    'limit_up': limit_up,
                    'limit_down': limit_down,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
    except Exception as e:
        return {'error': f'获取涨跌家数失败: {str(e)}'}

    return {'error': '无法获取涨跌家数数据'}


def get_new_high_low_stats() -> dict:
    """
    获取创新高/新低统计

    Returns:
        {
            'high_20d': 20日新高家数,
            'low_20d': 20日新低家数,
            'high_60d': 60日新高家数,
            'low_60d': 60日新低家数,
            'net_high_low': 净新高(新高-新低),
            'timestamp': 获取时间
        }
    """
    try:
        # 获取创新高统计
        df_high = ak.stock_a_high_low_statistics(symbol="创新高")
        df_low = ak.stock_a_high_low_statistics(symbol="创新低")

        result = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if df_high is not None and not df_high.empty:
            # 找最新日期数据
            df_high = df_high.sort_values('trade_date', ascending=False)
            latest = df_high.iloc[0]
            result['high_20d'] = int(latest.get('high20', 0))
            result['high_60d'] = int(latest.get('high60', 0))

        if df_low is not None and not df_low.empty:
            df_low = df_low.sort_values('trade_date', ascending=False)
            latest = df_low.iloc[0]
            result['low_20d'] = int(latest.get('low20', 0))
            result['low_60d'] = int(latest.get('low60', 0))

        # 计算净新高
        h20 = result.get('high_20d', 0)
        l20 = result.get('low_20d', 0)
        result['net_high_low'] = h20 - l20

        return result
    except Exception as e:
        return {'error': f'获取创新高低统计失败: {str(e)}'}


def analyze_breadth_signal() -> dict:
    """
    分析市场广度信号

    Returns:
        {
            'breadth': 涨跌数据,
            'new_high_low': 创新高低数据,
            'signal': 'bullish' / 'bearish' / 'neutral',
            'description': 信号描述
        }
    """
    breadth = get_market_breadth()
    new_high_low = get_new_high_low_stats()

    result = {
        'breadth': breadth,
        'new_high_low': new_high_low,
    }

    # 综合判断信号
    score = 0
    descriptions = []

    # 涨跌比信号
    if 'rise_ratio' in breadth:
        ratio = breadth['rise_ratio']
        if ratio > 1.5:
            score += 2
            descriptions.append('涨跌比强势')
        elif ratio > 1.0:
            score += 1
            descriptions.append('上涨家数占优')
        elif ratio < 0.67:
            score -= 2
            descriptions.append('涨跌比弱势')
        elif ratio < 1.0:
            score -= 1
            descriptions.append('下跌家数占优')

    # 涨跌停信号
    if 'limit_up' in breadth and 'limit_down' in breadth:
        if breadth['limit_up'] > breadth['limit_down'] * 2:
            score += 1
            descriptions.append('涨停多于跌停')
        elif breadth['limit_down'] > breadth['limit_up'] * 2:
            score -= 1
            descriptions.append('跌停多于涨停')

    # 创新高低信号
    if 'net_high_low' in new_high_low:
        net = new_high_low['net_high_low']
        if net > 50:
            score += 1
            descriptions.append('净新高较多')
        elif net < -50:
            score -= 1
            descriptions.append('净新低较多')

    # 判断信号
    if score >= 2:
        result['signal'] = 'bullish'
        result['signal_cn'] = '看多'
    elif score <= -2:
        result['signal'] = 'bearish'
        result['signal_cn'] = '看空'
    else:
        result['signal'] = 'neutral'
        result['signal_cn'] = '中性'

    result['score'] = score
    result['description'] = '，'.join(descriptions) if descriptions else '市场情绪中性'

    return result


# =============================================================================
# P0 核心指标：国债收益率
# =============================================================================

def get_bond_yield() -> dict:
    """
    获取国债收益率

    Returns:
        {
            'cn_10y': 中国10年国债收益率,
            'us_10y': 美国10年国债收益率,
            'spread': 中美利差,
            'timestamp': 获取时间
        }
    """
    try:
        df = ak.bond_zh_us_rate()
        if df is not None and not df.empty:
            # 排序获取最新数据
            df = df.sort_values('日期', ascending=False)
            latest = df.iloc[0]

            cn_10y = float(latest.get('中国国债收益率10年', 0))
            us_10y = float(latest.get('美国国债收益率10年', 0))

            return {
                'date': str(latest.get('日期', '')),
                'cn_10y': round(cn_10y, 3),
                'us_10y': round(us_10y, 3),
                'spread': round(cn_10y - us_10y, 3),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
    except Exception as e:
        return {'error': f'获取国债收益率失败: {str(e)}'}

    return {'error': '无法获取国债收益率数据'}


def get_bond_yield_history(days: int = 30) -> pd.DataFrame:
    """
    获取国债收益率历史

    Args:
        days: 历史天数

    Returns:
        DataFrame: date, cn_10y, us_10y
    """
    cache_key = f"bond_{days}"
    if cache_key in _bond_yield_cache:
        return _bond_yield_cache[cache_key]

    try:
        df = ak.bond_zh_us_rate()
        if df is not None and not df.empty:
            df = df.rename(columns={
                '日期': 'date',
                '中国国债收益率10年': 'cn_10y',
                '美国国债收益率10年': 'us_10y'
            })
            df['date'] = pd.to_datetime(df['date'])
            df = df[['date', 'cn_10y', 'us_10y']].dropna()
            df = df.sort_values('date', ascending=False).head(days)
            _bond_yield_cache[cache_key] = df
            return df
    except Exception as e:
        print(f"  获取国债收益率历史失败: {e}")

    return pd.DataFrame()


def calculate_equity_bond_ratio(pe: float = None, index_code: str = '000300') -> dict:
    """
    计算股债性价比 (风险溢价)

    公式: 1/PE - 国债收益率
    或: 股息率 / 国债收益率

    Args:
        pe: PE值(可选，不提供则获取沪深300)
        index_code: 指数代码

    Returns:
        {
            'equity_yield': 股票收益率(1/PE),
            'bond_yield': 国债收益率,
            'risk_premium': 风险溢价(bp),
            'ratio': 股债性价比,
            'signal': 信号判断
        }
    """
    bond = get_bond_yield()
    if 'error' in bond:
        return bond

    cn_10y = bond.get('cn_10y', 0)

    # 获取PE
    if pe is None:
        try:
            from src.technical import get_index_valuation
            val = get_index_valuation(index_code)
            pe = val.get('pe')
        except Exception:
            pass

    if not pe or pe <= 0:
        return {
            'bond_yield': cn_10y,
            'error': '无法获取PE数据'
        }

    equity_yield = 100 / pe  # 股票收益率 = 1/PE (百分比)
    risk_premium = equity_yield - cn_10y  # 风险溢价
    ratio = equity_yield / cn_10y if cn_10y > 0 else 0  # 股债比

    # 信号判断
    if ratio > 2.0:
        signal = 'very_bullish'
        signal_cn = '极具吸引力'
    elif ratio > 1.5:
        signal = 'bullish'
        signal_cn = '有吸引力'
    elif ratio > 1.0:
        signal = 'neutral'
        signal_cn = '中性'
    else:
        signal = 'bearish'
        signal_cn = '股票较贵'

    return {
        'pe': round(pe, 2),
        'equity_yield': round(equity_yield, 2),
        'bond_yield': cn_10y,
        'risk_premium': round(risk_premium * 100, 0),  # 转为bp
        'ratio': round(ratio, 2),
        'signal': signal,
        'signal_cn': signal_cn
    }


# =============================================================================
# P1 全球联动：VIX恐慌指数
# =============================================================================

def get_vix_index() -> dict:
    """
    获取VIX恐慌指数

    Returns:
        {
            'vix': VIX值,
            'change': 变化,
            'change_pct': 变化百分比,
            'timestamp': 获取时间
        }
    """
    try:
        ticker = yf.Ticker("^VIX")
        hist = ticker.history(period="5d")

        if hist.empty:
            return {'error': '无法获取VIX数据'}

        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else hist.iloc[0]

        vix = float(latest['Close'])
        prev_vix = float(prev['Close'])
        change = vix - prev_vix
        change_pct = (change / prev_vix) * 100 if prev_vix > 0 else 0

        return {
            'vix': round(vix, 2),
            'prev_vix': round(prev_vix, 2),
            'change': round(change, 2),
            'change_pct': round(change_pct, 2),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {'error': f'获取VIX失败: {str(e)}'}


def analyze_vix_signal(vix: float = None) -> dict:
    """
    分析VIX信号

    Args:
        vix: VIX值(可选，不提供则获取实时)

    Returns:
        {
            'vix': VIX值,
            'level': '低' / '中' / '高' / '极高',
            'signal': 'bullish' / 'neutral' / 'bearish',
            'description': 描述
        }
    """
    if vix is None:
        vix_data = get_vix_index()
        if 'error' in vix_data:
            return vix_data
        vix = vix_data.get('vix', 0)

    # VIX水平判断
    if vix < 15:
        level = '低'
        level_cn = '低波动'
        signal = 'bullish'
        description = '市场情绪乐观，波动率低'
    elif vix < 20:
        level = '中'
        level_cn = '正常'
        signal = 'neutral'
        description = '市场情绪正常'
    elif vix < 30:
        level = '高'
        level_cn = '偏高'
        signal = 'bearish'
        description = '市场存在担忧情绪'
    else:
        level = '极高'
        level_cn = '恐慌'
        signal = 'very_bearish'
        description = '市场恐慌，风险偏好极低'

    return {
        'vix': vix,
        'level': level,
        'level_cn': level_cn,
        'signal': signal,
        'description': description
    }


# =============================================================================
# P1 全球联动：美元指数
# =============================================================================

def get_usd_index() -> dict:
    """
    获取美元指数

    Returns:
        {
            'value': 美元指数,
            'change': 变化,
            'change_pct': 变化百分比,
            'timestamp': 获取时间
        }
    """
    try:
        # 使用yfinance获取美元指数
        ticker = yf.Ticker("DX-Y.NYB")
        hist = ticker.history(period="5d")

        if hist.empty:
            # 备用方案：通过akshare
            df = ak.currency_boc_safe()
            if df is not None and not df.empty:
                # 找美元
                usd_row = df[df['货币名称'].str.contains('美元')]
                if not usd_row.empty:
                    return {
                        'value': float(usd_row.iloc[0].get('中行折算价', 0)),
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'source': 'boc'
                    }
            return {'error': '无法获取美元指数'}

        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else hist.iloc[0]

        value = float(latest['Close'])
        prev_value = float(prev['Close'])
        change = value - prev_value
        change_pct = (change / prev_value) * 100 if prev_value > 0 else 0

        return {
            'value': round(value, 2),
            'prev_value': round(prev_value, 2),
            'change': round(change, 2),
            'change_pct': round(change_pct, 2),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {'error': f'获取美元指数失败: {str(e)}'}


def get_usd_cnh() -> dict:
    """
    获取离岸人民币汇率

    Returns:
        {
            'value': 汇率,
            'change_pct': 变化百分比,
            'timestamp': 获取时间
        }
    """
    try:
        ticker = yf.Ticker("CNH=X")
        hist = ticker.history(period="5d")

        if hist.empty:
            return {'error': '无法获取离岸人民币数据'}

        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else hist.iloc[0]

        value = float(latest['Close'])
        prev_value = float(prev['Close'])
        change_pct = ((value - prev_value) / prev_value) * 100 if prev_value > 0 else 0

        return {
            'value': round(value, 4),
            'prev_value': round(prev_value, 4),
            'change_pct': round(change_pct, 2),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {'error': f'获取离岸人民币失败: {str(e)}'}


def analyze_usd_trend() -> dict:
    """
    分析美元趋势及对A股影响

    Returns:
        {
            'usd_index': 美元指数数据,
            'usd_cnh': 离岸人民币数据,
            'signal': 信号,
            'impact': 对A股影响
        }
    """
    usd_index = get_usd_index()
    usd_cnh = get_usd_cnh()

    result = {
        'usd_index': usd_index,
        'usd_cnh': usd_cnh,
    }

    # 分析信号
    descriptions = []
    impact_score = 0  # 正数利好A股，负数利空

    # 美元指数判断
    if 'change_pct' in usd_index:
        usd_change = usd_index['change_pct']
        if usd_change > 0.5:
            descriptions.append('美元走强')
            impact_score -= 1
        elif usd_change < -0.5:
            descriptions.append('美元走弱')
            impact_score += 1

    # 人民币判断
    if 'change_pct' in usd_cnh:
        cnh_change = usd_cnh['change_pct']
        if cnh_change > 0.3:  # 人民币贬值
            descriptions.append('人民币贬值')
            impact_score -= 1
        elif cnh_change < -0.3:  # 人民币升值
            descriptions.append('人民币升值')
            impact_score += 1

    # 判断影响
    if impact_score > 0:
        result['impact'] = 'positive'
        result['impact_cn'] = '利好'
    elif impact_score < 0:
        result['impact'] = 'negative'
        result['impact_cn'] = '利空'
    else:
        result['impact'] = 'neutral'
        result['impact_cn'] = '中性'

    result['description'] = '，'.join(descriptions) if descriptions else '汇率稳定'

    return result


# =============================================================================
# 综合情绪分析
# =============================================================================

def run_sentiment_analysis() -> dict:
    """
    运行完整的情绪分析

    Returns:
        {
            'margin': 融资余额分析,
            'breadth': 市场广度分析,
            'bond_yield': 国债收益率,
            'equity_bond': 股债性价比,
            'vix': VIX分析,
            'usd': 美元分析,
            'summary': 综合判断
        }
    """
    print("📊 正在分析市场情绪...")

    result = {}

    # P0: 融资余额
    print("  分析融资余额...")
    result['margin'] = analyze_margin_trend()

    # P0: 市场广度
    print("  分析涨跌家数...")
    result['breadth'] = analyze_breadth_signal()

    # P0: 国债收益率
    print("  获取国债收益率...")
    result['bond_yield'] = get_bond_yield()

    # P0: 股债性价比
    print("  计算股债性价比...")
    result['equity_bond'] = calculate_equity_bond_ratio()

    # P1: VIX
    print("  获取VIX指数...")
    vix_data = get_vix_index()
    result['vix'] = analyze_vix_signal(vix_data.get('vix') if 'vix' in vix_data else None)
    if 'change' in vix_data:
        result['vix']['change'] = vix_data['change']
        result['vix']['change_pct'] = vix_data['change_pct']

    # P1: 美元
    print("  分析美元趋势...")
    result['usd'] = analyze_usd_trend()

    # 综合判断
    result['summary'] = generate_sentiment_summary(result)

    return result


def generate_sentiment_summary(data: dict) -> dict:
    """
    生成情绪综合判断

    Args:
        data: 各项情绪数据

    Returns:
        {
            'score': 综合得分 (-100 ~ +100),
            'signal': 信号,
            'description': 描述
        }
    """
    score = 0
    weights = {
        'margin': 25,      # 融资余额权重
        'breadth': 30,     # 市场广度权重
        'equity_bond': 20, # 股债性价比权重
        'vix': 15,         # VIX权重
        'usd': 10,         # 美元权重
    }

    descriptions = []

    # 融资余额信号
    margin = data.get('margin', {})
    if margin.get('signal') == 'bullish':
        score += weights['margin']
        descriptions.append('杠杆资金流入')
    elif margin.get('signal') == 'bearish':
        score -= weights['margin']
        descriptions.append('杠杆资金流出')

    # 市场广度信号
    breadth = data.get('breadth', {})
    if breadth.get('signal') == 'bullish':
        score += weights['breadth']
        descriptions.append('市场广度强')
    elif breadth.get('signal') == 'bearish':
        score -= weights['breadth']
        descriptions.append('市场广度弱')

    # 股债性价比信号
    eq_bond = data.get('equity_bond', {})
    if eq_bond.get('signal') in ['bullish', 'very_bullish']:
        score += weights['equity_bond']
        descriptions.append('股债性价比高')
    elif eq_bond.get('signal') == 'bearish':
        score -= weights['equity_bond']
        descriptions.append('股债性价比低')

    # VIX信号
    vix = data.get('vix', {})
    if vix.get('signal') == 'bullish':
        score += weights['vix']
    elif vix.get('signal') in ['bearish', 'very_bearish']:
        score -= weights['vix']
        descriptions.append('VIX偏高')

    # 美元信号
    usd = data.get('usd', {})
    if usd.get('impact') == 'positive':
        score += weights['usd']
    elif usd.get('impact') == 'negative':
        score -= weights['usd']
        descriptions.append('汇率承压')

    # 判断综合信号
    if score >= 40:
        signal = 'very_bullish'
        signal_cn = '非常乐观'
    elif score >= 20:
        signal = 'bullish'
        signal_cn = '偏乐观'
    elif score > -20:
        signal = 'neutral'
        signal_cn = '中性'
    elif score > -40:
        signal = 'bearish'
        signal_cn = '偏悲观'
    else:
        signal = 'very_bearish'
        signal_cn = '非常悲观'

    return {
        'score': score,
        'signal': signal,
        'signal_cn': signal_cn,
        'description': '，'.join(descriptions) if descriptions else '市场情绪中性'
    }


if __name__ == "__main__":
    # 测试
    print("=== 融资余额 ===")
    margin = get_margin_balance()
    print(f"融资余额: {margin}")

    print("\n=== 涨跌家数 ===")
    breadth = get_market_breadth()
    print(f"涨跌家数: {breadth}")

    print("\n=== 国债收益率 ===")
    bond = get_bond_yield()
    print(f"国债收益率: {bond}")

    print("\n=== VIX ===")
    vix = get_vix_index()
    print(f"VIX: {vix}")

    print("\n=== 美元指数 ===")
    usd = get_usd_index()
    print(f"美元指数: {usd}")

    print("\n=== 完整情绪分析 ===")
    sentiment = run_sentiment_analysis()
    print(f"综合评分: {sentiment['summary']['score']}")
    print(f"信号: {sentiment['summary']['signal_cn']}")
