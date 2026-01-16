"""
财经新闻和政策信息收集模块
"""

from datetime import datetime, timedelta
from typing import Optional
import akshare as ak
import pandas as pd


def get_cctv_news() -> list[dict]:
    """
    获取新闻联播文字稿 - 重大政策风向标

    返回最近的新闻联播内容摘要
    """
    try:
        df = ak.news_cctv(date=datetime.now().strftime("%Y%m%d"))
        if df is not None and not df.empty:
            news_list = []
            for _, row in df.head(10).iterrows():
                news_list.append({
                    'title': row.get('title', ''),
                    'content': row.get('content', '')[:200] + '...' if len(str(row.get('content', ''))) > 200 else row.get('content', ''),
                    'source': '新闻联播',
                    'date': datetime.now().strftime("%Y-%m-%d")
                })
            return news_list
    except Exception as e:
        print(f"  获取新闻联播失败: {e}")
    return []


def get_eastmoney_news() -> list[dict]:
    """
    获取东方财富财经要闻

    返回今日重要财经新闻
    """
    try:
        df = ak.stock_info_global_em()
        if df is not None and not df.empty:
            news_list = []
            for _, row in df.head(15).iterrows():
                title = row.get('标题', '')
                if not title:
                    continue
                news_list.append({
                    'title': title,
                    'summary': row.get('摘要', ''),
                    'time': str(row.get('发布时间', '')),
                    'source': '东方财富',
                })
            return news_list
    except Exception as e:
        print(f"  获取东方财富新闻失败: {e}")
    return []


def get_cls_telegraph() -> list[dict]:
    """
    获取财联社电报 - 快讯消息

    返回最新财经快讯
    """
    try:
        df = ak.stock_info_global_cls()
        if df is not None and not df.empty:
            news_list = []
            for _, row in df.head(20).iterrows():
                title = row.get('标题', '')
                content = row.get('内容', '')
                if not title and not content:
                    continue

                # 组合日期和时间
                pub_date = str(row.get('发布日期', ''))
                pub_time = str(row.get('发布时间', ''))
                time_str = f"{pub_date} {pub_time}".strip()

                news_list.append({
                    'title': title if title else content[:50] + '...' if len(content) > 50 else content,
                    'content': content[:150] + '...' if len(str(content)) > 150 else content,
                    'time': time_str,
                    'source': '财联社',
                })
            return news_list
    except Exception as e:
        print(f"  获取财联社电报失败: {e}")
    return []


def get_jin10_news() -> list[dict]:
    """
    获取金十数据快讯

    返回金融市场实时资讯
    """
    try:
        df = ak.js_news(timestamp=datetime.now().strftime("%Y%m%d%H%M%S"))
        if df is not None and not df.empty:
            news_list = []
            for _, row in df.head(15).iterrows():
                content = row.get('content', '')
                if content:
                    news_list.append({
                        'content': content[:200] + '...' if len(content) > 200 else content,
                        'time': row.get('time', ''),
                        'source': '金十数据',
                    })
            return news_list
    except Exception as e:
        print(f"  获取金十数据失败: {e}")
    return []


def get_macro_china_news() -> list[dict]:
    """
    获取中国宏观经济数据发布

    返回最近的宏观数据（使用年度数据接口，数据更新更及时）
    """
    import math
    news_list = []

    # GDP (使用年度数据接口)
    try:
        gdp = ak.macro_china_gdp_yearly()
        if gdp is not None and not gdp.empty:
            # 找最近一条有效数据
            valid_gdp = gdp[gdp['今值'].notna()]
            if not valid_gdp.empty:
                latest = valid_gdp.iloc[-1]
                value = latest.get('今值', 'N/A')
                date = str(latest.get('日期', 'N/A'))
                news_list.append({
                    'title': f"GDP同比: {value}%",
                    'content': f"发布日期: {date}",
                    'source': '宏观数据',
                    'type': 'GDP'
                })
    except Exception as e:
        print(f"  获取GDP数据失败: {e}")

    # CPI (使用年度数据接口)
    try:
        cpi = ak.macro_china_cpi_yearly()
        if cpi is not None and not cpi.empty:
            valid_cpi = cpi[cpi['今值'].notna()]
            if not valid_cpi.empty:
                latest = valid_cpi.iloc[-1]
                value = latest.get('今值', 'N/A')
                date = str(latest.get('日期', 'N/A'))
                news_list.append({
                    'title': f"CPI同比: {value}%",
                    'content': f"发布日期: {date}",
                    'source': '宏观数据',
                    'type': 'CPI'
                })
    except Exception as e:
        print(f"  获取CPI数据失败: {e}")

    # PMI (使用年度数据接口)
    try:
        pmi = ak.macro_china_pmi_yearly()
        if pmi is not None and not pmi.empty:
            valid_pmi = pmi[pmi['今值'].notna()]
            if not valid_pmi.empty:
                latest = valid_pmi.iloc[-1]
                value = latest.get('今值', 'N/A')
                date = str(latest.get('日期', 'N/A'))
                # PMI > 50 表示扩张
                status = "扩张" if float(value) > 50 else "收缩"
                news_list.append({
                    'title': f"制造业PMI: {value} ({status})",
                    'content': f"发布日期: {date}",
                    'source': '宏观数据',
                    'type': 'PMI'
                })
    except Exception as e:
        print(f"  获取PMI数据失败: {e}")

    return news_list


def get_us_economic_calendar() -> list[dict]:
    """
    获取美国经济日历 - 重要经济数据发布

    返回近期美国经济数据
    """
    import math
    news_list = []

    try:
        df = ak.macro_usa_cpi_monthly()
        if df is not None and not df.empty:
            # 找最近一条有效数据
            valid_df = df[df['今值'].notna()]
            if not valid_df.empty:
                latest = valid_df.iloc[-1]
                value = latest.get('今值', 'N/A')
                prev = latest.get('前值', 'N/A')
                date = str(latest.get('日期', 'N/A'))
                news_list.append({
                    'title': f"美国CPI月率: {value}%",
                    'content': f"前值: {prev}% | 发布: {date}",
                    'source': '美国经济数据',
                    'type': 'US_CPI'
                })
    except Exception as e:
        print(f"  获取美国CPI数据失败: {e}")

    return news_list


def filter_important_news(news_list: list[dict], keywords: list[str] = None) -> list[dict]:
    """
    筛选重要新闻

    keywords: 关键词列表，包含这些词的新闻会被标记为重要
    """
    if keywords is None:
        keywords = [
            # 政策相关
            '央行', '降息', '降准', '加息', 'LPR', '货币政策', '财政政策',
            '证监会', '发改委', '国务院', '政治局',
            # 市场相关
            '北向资金', '外资', '主力资金', '融资', '融券',
            # 行业相关
            '芯片', '半导体', '新能源', '人工智能', 'AI', '光伏', '锂电',
            # 美国相关
            '美联储', 'Fed', '美股', '纳斯达克', '标普',
            # 重大事件
            '暴跌', '暴涨', '熔断', '黑天鹅', '利好', '利空',
        ]

    important = []
    normal = []

    for news in news_list:
        text = str(news.get('title', '')) + str(news.get('content', ''))
        is_important = any(kw in text for kw in keywords)

        if is_important:
            news['important'] = True
            important.append(news)
        else:
            news['important'] = False
            normal.append(news)

    # 重要新闻在前
    return important + normal


def collect_daily_news() -> dict:
    """
    收集每日财经新闻汇总

    返回: {
        'cctv': 新闻联播,
        'telegraph': 财联社/金十快讯,
        'macro': 宏观数据,
        'all_news': 所有新闻合并并按重要性排序,
        'important_count': 重要新闻数量,
        'updated_at': 更新时间
    }
    """
    print("📰 收集财经新闻...")

    result = {
        'cctv': [],
        'telegraph': [],
        'eastmoney': [],
        'macro': [],
        'all_news': [],
        'important_count': 0,
        'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # 新闻联播
    print("  获取新闻联播...")
    result['cctv'] = get_cctv_news()

    # 财联社快讯
    print("  获取财联社快讯...")
    result['telegraph'] = get_cls_telegraph()

    # 东方财富要闻
    print("  获取东方财富要闻...")
    result['eastmoney'] = get_eastmoney_news()

    # 宏观数据
    print("  获取宏观经济数据...")
    result['macro'] = get_macro_china_news()
    result['macro'].extend(get_us_economic_calendar())

    # 合并所有新闻
    all_news = []
    all_news.extend(result['cctv'])
    all_news.extend(result['telegraph'])
    all_news.extend(result['eastmoney'])

    # 筛选重要新闻
    result['all_news'] = filter_important_news(all_news)
    result['important_count'] = sum(1 for n in result['all_news'] if n.get('important'))

    print(f"  ✓ 共获取 {len(result['all_news'])} 条新闻，其中重要 {result['important_count']} 条")

    return result


def format_news_for_report(news_data: dict, max_items: int = 10) -> str:
    """
    将新闻数据格式化为报告文本
    """
    lines = ["## 今日要闻\n"]

    # 宏观数据
    if news_data.get('macro'):
        lines.append("### 宏观数据\n")
        for item in news_data['macro']:
            lines.append(f"- **{item.get('title', '')}** {item.get('content', '')}")
        lines.append("")

    # 重要新闻
    important_news = [n for n in news_data.get('all_news', []) if n.get('important')]
    if important_news:
        lines.append("### 重要资讯\n")
        for item in important_news[:max_items]:
            title = item.get('title', item.get('content', ''))[:60]
            source = item.get('source', '')
            time = item.get('time', '')
            lines.append(f"- [{source}] {title}")
            if time:
                lines.append(f"  - 时间: {time}")
        lines.append("")

    # 新闻联播摘要
    if news_data.get('cctv'):
        lines.append("### 新闻联播要点\n")
        for item in news_data['cctv'][:3]:
            title = item.get('title', '')
            if title:
                lines.append(f"- {title}")
        lines.append("")

    if not important_news and not news_data.get('macro') and not news_data.get('cctv'):
        lines.append("暂无重要新闻\n")

    return "\n".join(lines)


if __name__ == "__main__":
    news_data = collect_daily_news()

    print("\n" + "=" * 50)
    print(format_news_for_report(news_data))
