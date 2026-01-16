"""
市场数据采集模块
获取A股指数、美股指数、北向资金等数据
"""

import akshare as ak
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd


def get_a_share_index(code: str, name: str) -> dict:
    """获取A股指数实时数据"""
    try:
        # 先尝试东方财富数据源
        df = ak.stock_zh_index_spot_em()
        row = df[df['代码'] == code]

        if not row.empty:
            row = row.iloc[0]
            return {
                "code": code,
                "name": name,
                "price": float(row['最新价']),
                "change": float(row['涨跌额']),
                "change_pct": float(row['涨跌幅']),
                "volume": float(row.get('成交量', 0)),
                "amount": float(row.get('成交额', 0)),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        # 如果东财没有，尝试新浪数据源 (深证系列指数)
        df_sina = ak.stock_zh_index_spot_sina()
        # 新浪代码格式: sh000001 或 sz399001
        sina_code = f"sz{code}" if code.startswith('399') else f"sh{code}"
        row = df_sina[df_sina['代码'] == sina_code]

        if not row.empty:
            row = row.iloc[0]
            return {
                "code": code,
                "name": name,
                "price": float(row['最新价']),
                "change": float(row['涨跌额']),
                "change_pct": float(row['涨跌幅']),
                "volume": float(row.get('成交量', 0)),
                "amount": float(row.get('成交额', 0)),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        return {"code": code, "name": name, "error": "未找到数据"}
    except Exception as e:
        return {"code": code, "name": name, "error": str(e)}


def get_us_index(code: str, name: str) -> dict:
    """获取美股指数数据"""
    try:
        ticker = yf.Ticker(code)
        hist = ticker.history(period="2d")

        if hist.empty:
            return {"code": code, "name": name, "error": "未找到数据"}

        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else hist.iloc[0]

        price = float(latest['Close'])
        prev_close = float(prev['Close'])
        change = price - prev_close
        change_pct = (change / prev_close) * 100

        return {
            "code": code,
            "name": name,
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume": int(latest['Volume']),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {"code": code, "name": name, "error": str(e)}


def get_north_flow() -> dict:
    """获取北向资金流向"""
    try:
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北向")
        if df.empty:
            return {"error": "未找到北向资金数据"}

        # 获取最近的数据
        latest = df.iloc[-1]

        return {
            "date": str(latest.get('日期', '')),
            "net_inflow": float(latest.get('收盘', 0)),  # 净流入(亿)
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {"error": str(e)}


def get_north_flow_today() -> dict:
    """获取今日北向资金实时流入"""
    import math

    # 方法1: 尝试获取今日资金流向汇总（最可靠）
    try:
        df = ak.stock_hsgt_fund_flow_summary_em()
        if df is not None and not df.empty:
            # 筛选北向资金（沪股通+深股通）
            north_df = df[df['资金方向'] == '北向']
            if not north_df.empty:
                # 汇总沪股通和深股通的成交净买额
                total_net = north_df['成交净买额'].sum()
                if not math.isnan(total_net):
                    trade_date = str(north_df.iloc[0].get('交易日', ''))
                    return {
                        "date": trade_date,
                        "net_inflow": round(float(total_net), 2),  # 单位：亿元
                        "detail": {
                            "沪股通": float(north_df[north_df['板块'] == '沪股通']['成交净买额'].iloc[0]) if len(north_df[north_df['板块'] == '沪股通']) > 0 else 0,
                            "深股通": float(north_df[north_df['板块'] == '深股通']['成交净买额'].iloc[0]) if len(north_df[north_df['板块'] == '深股通']) > 0 else 0,
                        },
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
    except Exception as e:
        print(f"  获取北向资金汇总失败: {e}")

    # 方法2: 尝试获取分钟级数据的最新值
    try:
        df = ak.stock_hsgt_fund_min_em(symbol="北向资金")
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            net_inflow = latest.get('北向资金', 0)
            if not math.isnan(net_inflow) and net_inflow != 0:
                return {
                    "date": str(latest.get('日期', '')),
                    "net_inflow": round(float(net_inflow), 2),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
    except Exception:
        pass

    # 方法3: 回退到历史数据
    try:
        df = ak.stock_hsgt_hist_em(symbol="北向资金")
        if df is not None and not df.empty:
            # 找最近一条有效数据
            valid_df = df[df['当日成交净买额'].notna()]
            if not valid_df.empty:
                latest = valid_df.iloc[-1]
                net_inflow = latest.get('当日成交净买额', 0)
                return {
                    "date": str(latest.get('日期', '')),
                    "net_inflow": round(float(net_inflow), 2),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "note": "历史数据，非实时"
                }
    except Exception:
        pass

    return {"error": "无法获取北向资金数据"}


def get_sector_flow() -> list[dict]:
    """获取行业板块资金流向"""
    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
        if df.empty:
            return []

        # 取前10和后5
        top_inflow = df.head(10)
        top_outflow = df.tail(5)

        results = []
        for _, row in top_inflow.iterrows():
            results.append({
                "name": row.get('名称', ''),
                "change_pct": float(row.get('今日涨跌幅', 0)),
                "net_flow": float(row.get('今日主力净流入-净额', 0)),
                "type": "inflow"
            })

        for _, row in top_outflow.iterrows():
            results.append({
                "name": row.get('名称', ''),
                "change_pct": float(row.get('今日涨跌幅', 0)),
                "net_flow": float(row.get('今日主力净流入-净额', 0)),
                "type": "outflow"
            })

        return results
    except Exception as e:
        return [{"error": str(e)}]


def get_fund_estimate(fund_code: str) -> dict:
    """获取基金实时估值"""
    try:
        df = ak.fund_etf_fund_info_em(fund=fund_code)
        if df is None or df.empty:
            # 尝试场外基金
            df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
            if df is None or df.empty:
                return {"code": fund_code, "error": "未找到基金数据"}

        latest = df.iloc[-1]
        return {
            "code": fund_code,
            "nav": float(latest.get('单位净值', latest.get('累计净值', 0))),
            "date": str(latest.get('净值日期', '')),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {"code": fund_code, "error": str(e)}


def get_fund_realtime_estimate(fund_code: str) -> dict:
    """获取基金盘中实时估值（净值估算）"""
    try:
        # 获取基金实时估值
        df = ak.fund_etf_spot_em()
        row = df[df['代码'] == fund_code]

        if row.empty:
            # 尝试场外基金估值
            df = ak.fund_open_fund_rank_em(symbol="全部")
            row = df[df['基金代码'] == fund_code]

            if row.empty:
                return {"code": fund_code, "error": "未找到实时估值"}

            row = row.iloc[0]
            return {
                "code": fund_code,
                "name": row.get('基金简称', ''),
                "estimate_nav": float(row.get('日增长估值', 0)),
                "estimate_change_pct": float(row.get('日增长率', 0)),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        row = row.iloc[0]
        return {
            "code": fund_code,
            "name": row.get('名称', ''),
            "price": float(row.get('最新价', 0)),
            "change_pct": float(row.get('涨跌幅', 0)),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {"code": fund_code, "error": str(e)}


def collect_all_indices(config: dict) -> dict:
    """采集所有配置的指数数据"""
    results = {
        "a_share": [],
        "us_stock": [],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # A股指数
    for idx in config.get('indices', {}).get('a_share', []):
        data = get_a_share_index(idx['code'], idx['name'])
        results['a_share'].append(data)

    # 美股指数
    for idx in config.get('indices', {}).get('us_stock', []):
        data = get_us_index(idx['code'], idx['name'])
        results['us_stock'].append(data)

    return results


if __name__ == "__main__":
    # 测试
    import yaml

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    print("=== A股指数 ===")
    for idx in config['indices']['a_share']:
        data = get_a_share_index(idx['code'], idx['name'])
        print(f"{data['name']}: {data.get('price', 'N/A')} ({data.get('change_pct', 'N/A')}%)")

    print("\n=== 美股指数 ===")
    for idx in config['indices']['us_stock']:
        data = get_us_index(idx['code'], idx['name'])
        print(f"{data['name']}: {data.get('price', 'N/A')} ({data.get('change_pct', 'N/A')}%)")
