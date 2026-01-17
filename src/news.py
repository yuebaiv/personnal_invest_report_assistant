"""
财经新闻和政策信息收集模块
支持 LLM 语义化新闻分析
"""

from datetime import datetime, timedelta
from typing import Optional
import json
import akshare as ak
import pandas as pd

# LLM API 配置
LLM_API_KEY = "24bW7BzhYaf5O"
LLM_BASE_URL = "https://ai.liaobots.work/v1"
LLM_MODEL = "gpt-4o"


def llm_analyze_news(news_list: list[dict], sector_flow: list[dict] = None) -> dict:
    """
    使用 LLM 对新闻进行语义化分析

    返回:
    {
        'analyzed_news': [
            {
                'title': 新闻标题,
                'importance': 0-10 重要性评分,
                'sentiment': -1到1 情感倾向,
                'sectors': ['半导体', '消费电子'],  # 受影响板块
                'reason': '评分理由'
            }
        ],
        'overall_sentiment': 整体市场情绪 (-1到1),
        'hot_sectors': ['板块1', '板块2'],  # 今日热点板块
        'resonance': [  # 新闻与资金共振
            {'sector': '半导体', 'news_sentiment': 0.8, 'capital_flow': 142.79, 'resonance': True}
        ]
    }
    """
    try:
        from openai import OpenAI
    except ImportError:
        print("  ⚠ 未安装 openai 库，跳过 LLM 分析")
        return {'error': 'openai not installed'}

    if not news_list:
        return {'analyzed_news': [], 'overall_sentiment': 0, 'hot_sectors': [], 'resonance': []}

    # 准备新闻文本
    news_texts = []
    for i, news in enumerate(news_list[:20]):  # 最多分析20条
        title = news.get('title', news.get('content', ''))[:100]
        source = news.get('source', '')
        news_texts.append(f"{i+1}. [{source}] {title}")

    news_block = "\n".join(news_texts)

    # 准备资金流向信息（用于共振分析）
    flow_info = ""
    top_inflow_sectors = []
    top_outflow_sectors = []
    if sector_flow:
        # 分离流入和流出
        inflow_texts = []
        outflow_texts = []
        for sector in sector_flow:
            name = sector.get('name', '')
            net_flow = sector.get('net_flow', sector.get('net_inflow', 0))
            sector_type = sector.get('type', '')
            if sector_type == 'inflow' or net_flow > 0:
                inflow_texts.append(f"- {name}: +{abs(net_flow):.2f}亿")
                top_inflow_sectors.append(name)
            else:
                outflow_texts.append(f"- {name}: -{abs(net_flow):.2f}亿")
                top_outflow_sectors.append(name)

        flow_info = "\n\n📊 今日行业资金流向:"
        if inflow_texts:
            flow_info += f"\n主力净流入:\n" + "\n".join(inflow_texts[:5])
        if outflow_texts:
            flow_info += f"\n\n主力净流出:\n" + "\n".join(outflow_texts[:5])

    # 构建共振分析要求
    resonance_instruction = ""
    if top_inflow_sectors:
        resonance_instruction = f"""

🔍 共振分析任务:
请对比今日资金流入前五的行业（{', '.join(top_inflow_sectors[:5])}）与今日要闻:
1. 若新闻中有关于这些行业的重大利好，标注为"逻辑共振"（趋势更持久）
2. 若行业资金大涨但无相关新闻支撑，标注为"资金驱动"（易回调）
3. 若新闻利空但资金仍流入，标注为"利空不跌"（主力托底）"""

    prompt = f"""作为资深投资经理，请分析以下财经新闻，返回 JSON 格式结果。

今日新闻列表:
{news_block}
{flow_info}
{resonance_instruction}

请返回严格的 JSON 格式（不要有其他文字）:
{{
    "analyzed_news": [
        {{
            "index": 1,
            "importance": 8,
            "sentiment": 0.5,
            "sectors": ["半导体", "消费电子"],
            "reason": "简短理由"
        }}
    ],
    "overall_sentiment": 0.3,
    "hot_sectors": ["半导体", "新能源"],
    "resonance": [
        {{
            "sector": "半导体",
            "news_sentiment": 0.8,
            "capital_flow": 142.79,
            "type": "逻辑共振",
            "conclusion": "逻辑共振：新闻利好(AI芯片需求)+资金流入142亿，趋势较持久"
        }},
        {{
            "sector": "软件开发",
            "news_sentiment": 0,
            "capital_flow": -90.73,
            "type": "资金驱动",
            "conclusion": "资金驱动：无明显新闻支撑但资金大幅流出，谨慎观望"
        }}
    ],
    "market_summary": "一句话总结今日市场情绪和操作建议"
}}

评分标准:
- importance (0-10): 0=礼仪性新闻, 5=行业一般消息, 8=重大政策, 10=影响全市场
- sentiment (-1到1): -1=极大利空, 0=中性, 1=极大利好
- sectors: 只填写直接受影响的A股板块名称
- resonance: 必须针对资金流入/流出前5的行业逐一分析，标注为逻辑共振、资金驱动或利空不跌"""

    try:
        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是专业的A股投资分析师，擅长从新闻中提取投资信号。只返回JSON，不要其他文字。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )

        result_text = response.choices[0].message.content.strip()

        # 尝试解析 JSON
        # 处理可能的 markdown 代码块
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()

        result = json.loads(result_text)

        # 将分析结果合并回原新闻列表
        analyzed_map = {item['index']: item for item in result.get('analyzed_news', [])}
        for i, news in enumerate(news_list[:20]):
            if i + 1 in analyzed_map:
                analysis = analyzed_map[i + 1]
                news['llm_importance'] = analysis.get('importance', 5)
                news['llm_sentiment'] = analysis.get('sentiment', 0)
                news['llm_sectors'] = analysis.get('sectors', [])
                news['llm_reason'] = analysis.get('reason', '')

        return {
            'analyzed_news': news_list[:20],
            'overall_sentiment': result.get('overall_sentiment', 0),
            'hot_sectors': result.get('hot_sectors', []),
            'resonance': result.get('resonance', []),
            'market_summary': result.get('market_summary', '')
        }

    except json.JSONDecodeError as e:
        print(f"  ⚠ LLM 返回格式错误: {e}")
        return {'error': f'JSON parse error: {e}'}
    except Exception as e:
        print(f"  ⚠ LLM 分析失败: {e}")
        return {'error': str(e)}


def llm_analyze_cctv_news(cctv_news: list[dict]) -> dict:
    """
    专门针对新闻联播的政策导向分析

    返回:
    {
        'policy_signals': [
            {'topic': '产业政策', 'direction': '利好', 'sectors': ['新能源'], 'term': '中长期'}
        ],
        'key_meetings': ['国务院常务会议', '中央政治局会议'],
        'investment_hints': '投资启示'
    }
    """
    try:
        from openai import OpenAI
    except ImportError:
        return {'error': 'openai not installed'}

    if not cctv_news:
        return {'policy_signals': [], 'key_meetings': [], 'investment_hints': ''}

    # 合并新闻联播内容
    cctv_texts = []
    for news in cctv_news[:5]:
        title = news.get('title', '')
        content = news.get('content', '')[:300]
        cctv_texts.append(f"标题: {title}\n摘要: {content}")

    cctv_block = "\n\n".join(cctv_texts)

    prompt = f"""作为政策分析师，请解读今日《新闻联播》的投资信号。

新闻联播内容:
{cctv_block}

请返回严格的 JSON 格式:
{{
    "policy_signals": [
        {{
            "topic": "政策主题",
            "direction": "利好/利空/中性",
            "sectors": ["受益板块1", "受益板块2"],
            "term": "短期/中期/长期",
            "reason": "简要分析"
        }}
    ],
    "key_meetings": ["提到的重要会议名称"],
    "investment_hints": "一句话投资启示"
}}

重点关注:
- 国务院常务会议、中央政治局、深化改革等关键词
- 产业政策导向（如新能源、半导体、消费）
- 忽略外交礼仪、体育文化等非经济新闻"""

    try:
        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是专业的宏观政策分析师。只返回JSON，不要其他文字。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )

        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()

        return json.loads(result_text)

    except Exception as e:
        print(f"  ⚠ 新闻联播分析失败: {e}")
        return {'error': str(e)}


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

    返回最近的宏观数据（优先使用月度/季度数据接口）
    """
    news_list = []

    # GDP (季度数据，每季首月15号左右发布)
    try:
        # 尝试获取季度GDP数据
        gdp = ak.macro_china_gdp()
        if gdp is not None and not gdp.empty:
            # 确保按日期排序取最新数据
            date_col = '日期' if '日期' in gdp.columns else '季度' if '季度' in gdp.columns else None
            if date_col:
                gdp = gdp.sort_values(date_col, ascending=True)
            latest = gdp.iloc[-1]
            value = latest.get('今值', latest.get('国内生产总值-同比增长', 'N/A'))
            date = str(latest.get('日期', latest.get('季度', 'N/A')))
            news_list.append({
                'title': f"GDP同比: {value}%",
                'content': f"数据期: {date}",
                'source': '宏观数据',
                'type': 'GDP'
            })
    except Exception as e:
        # 降级到年度数据
        try:
            gdp = ak.macro_china_gdp_yearly()
            if gdp is not None and not gdp.empty:
                # 确保按日期排序
                if '日期' in gdp.columns:
                    gdp = gdp.sort_values('日期', ascending=True)
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
        except Exception as e2:
            print(f"  获取GDP数据失败: {e2}")

    # CPI (月度数据，每月10号左右发布)
    try:
        cpi = ak.macro_china_cpi()
        if cpi is not None and not cpi.empty:
            # 确保按日期排序
            date_col = '日期' if '日期' in cpi.columns else '月份' if '月份' in cpi.columns else None
            if date_col:
                cpi = cpi.sort_values(date_col, ascending=True)
            latest = cpi.iloc[-1]
            value = latest.get('今值', latest.get('全国-同比增长', 'N/A'))
            date = str(latest.get('日期', latest.get('月份', 'N/A')))
            news_list.append({
                'title': f"CPI同比: {value}%",
                'content': f"数据期: {date}",
                'source': '宏观数据',
                'type': 'CPI'
            })
    except Exception as e:
        # 降级到年度数据
        try:
            cpi = ak.macro_china_cpi_yearly()
            if cpi is not None and not cpi.empty:
                # 确保按日期排序
                if '日期' in cpi.columns:
                    cpi = cpi.sort_values('日期', ascending=True)
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
        except Exception as e2:
            print(f"  获取CPI数据失败: {e2}")

    # PPI (月度数据)
    try:
        ppi = ak.macro_china_ppi()
        if ppi is not None and not ppi.empty:
            # 确保按日期排序
            date_col = '日期' if '日期' in ppi.columns else '月份' if '月份' in ppi.columns else None
            if date_col:
                ppi = ppi.sort_values(date_col, ascending=True)
            latest = ppi.iloc[-1]
            value = latest.get('今值', latest.get('工业品出厂价格指数-同比增长', 'N/A'))
            date = str(latest.get('日期', latest.get('月份', 'N/A')))
            news_list.append({
                'title': f"PPI同比: {value}%",
                'content': f"数据期: {date}",
                'source': '宏观数据',
                'type': 'PPI'
            })
    except Exception as e:
        pass  # PPI 非必须

    # PMI (月度数据，每月最后一天发布)
    try:
        pmi = ak.macro_china_pmi()
        if pmi is not None and not pmi.empty:
            # 确保按日期排序
            date_col = '日期' if '日期' in pmi.columns else '月份' if '月份' in pmi.columns else None
            if date_col:
                pmi = pmi.sort_values(date_col, ascending=True)
            latest = pmi.iloc[-1]
            value = latest.get('今值', latest.get('制造业-指数', 'N/A'))
            date = str(latest.get('日期', latest.get('月份', 'N/A')))
            try:
                status = "扩张" if float(value) > 50 else "收缩"
            except:
                status = ""
            news_list.append({
                'title': f"制造业PMI: {value}" + (f" ({status})" if status else ""),
                'content': f"数据期: {date}",
                'source': '宏观数据',
                'type': 'PMI'
            })
    except Exception as e:
        # 降级到年度数据
        try:
            pmi = ak.macro_china_pmi_yearly()
            if pmi is not None and not pmi.empty:
                # 确保按日期排序
                if '日期' in pmi.columns:
                    pmi = pmi.sort_values('日期', ascending=True)
                valid_pmi = pmi[pmi['今值'].notna()]
                if not valid_pmi.empty:
                    latest = valid_pmi.iloc[-1]
                    value = latest.get('今值', 'N/A')
                    date = str(latest.get('日期', 'N/A'))
                    status = "扩张" if float(value) > 50 else "收缩"
                    news_list.append({
                        'title': f"制造业PMI: {value} ({status})",
                        'content': f"发布日期: {date}",
                        'source': '宏观数据',
                        'type': 'PMI'
                    })
        except Exception as e2:
            print(f"  获取PMI数据失败: {e2}")

    # 社融数据 (月度)
    try:
        sf = ak.macro_china_shrzgm()
        if sf is not None and not sf.empty:
            # 确保按日期排序
            date_col = '月份' if '月份' in sf.columns else '日期' if '日期' in sf.columns else None
            if date_col:
                sf = sf.sort_values(date_col, ascending=True)
            latest = sf.iloc[-1]
            value = latest.get('社会融资规模增量', 'N/A')
            date = str(latest.get('月份', 'N/A'))
            news_list.append({
                'title': f"社融增量: {value}亿",
                'content': f"数据期: {date}",
                'source': '宏观数据',
                'type': 'SHRZGM'
            })
    except Exception as e:
        pass  # 社融非必须

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


def collect_daily_news(sector_flow: list[dict] = None, use_llm: bool = True) -> dict:
    """
    收集每日财经新闻汇总

    参数:
        sector_flow: 行业资金流向数据，用于 LLM 共振分析
        use_llm: 是否使用 LLM 进行语义分析

    返回: {
        'cctv': 新闻联播,
        'telegraph': 财联社/金十快讯,
        'macro': 宏观数据,
        'all_news': 所有新闻合并并按重要性排序,
        'important_count': 重要新闻数量,
        'llm_analysis': LLM 分析结果,
        'cctv_analysis': 新闻联播政策分析,
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
        'llm_analysis': {},
        'cctv_analysis': {},
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

    # 筛选重要新闻（关键词初筛）
    result['all_news'] = filter_important_news(all_news)
    result['important_count'] = sum(1 for n in result['all_news'] if n.get('important'))

    print(f"  ✓ 共获取 {len(result['all_news'])} 条新闻，其中重要 {result['important_count']} 条")

    # LLM 语义分析
    if use_llm:
        print("  🤖 使用 LLM 分析新闻情绪...")

        # 分析一般新闻
        llm_result = llm_analyze_news(result['all_news'], sector_flow)
        if 'error' not in llm_result:
            result['llm_analysis'] = llm_result
            # 按 LLM 重要性重新排序
            result['all_news'] = sorted(
                result['all_news'],
                key=lambda x: x.get('llm_importance', 0),
                reverse=True
            )
            print(f"  ✓ LLM 分析完成，整体情绪: {llm_result.get('overall_sentiment', 0):+.2f}")

            # 显示共振信息
            resonance = llm_result.get('resonance', [])
            if resonance:
                for r in resonance[:3]:
                    print(f"    📊 {r.get('conclusion', '')}")
        else:
            print(f"  ⚠ LLM 分析跳过: {llm_result.get('error', '')}")

        # 分析新闻联播政策导向
        if result['cctv']:
            print("  🏛️ 分析新闻联播政策信号...")
            cctv_result = llm_analyze_cctv_news(result['cctv'])
            if 'error' not in cctv_result:
                result['cctv_analysis'] = cctv_result
                hints = cctv_result.get('investment_hints', '')
                if hints:
                    print(f"  ✓ 政策启示: {hints}")

    return result


def format_news_for_report(news_data: dict, max_items: int = 10) -> str:
    """
    将新闻数据格式化为报告文本（支持 LLM 分析结果）
    """
    lines = ["## 今日要闻\n"]

    # LLM 市场情绪总结
    llm_analysis = news_data.get('llm_analysis', {})
    if llm_analysis and 'error' not in llm_analysis:
        overall = llm_analysis.get('overall_sentiment', 0)
        summary = llm_analysis.get('market_summary', '')

        # 情绪图标
        if overall > 0.3:
            emoji = "🟢"
            mood = "偏多"
        elif overall < -0.3:
            emoji = "🔴"
            mood = "偏空"
        else:
            emoji = "🟡"
            mood = "中性"

        lines.append("### 📊 AI 市场情绪分析\n")
        lines.append(f"- 整体情绪: {emoji} **{mood}** ({overall:+.2f})")
        if summary:
            lines.append(f"- 今日总结: {summary}")

        # 热点板块
        hot_sectors = llm_analysis.get('hot_sectors', [])
        if hot_sectors:
            lines.append(f"- 热点板块: **{', '.join(hot_sectors[:5])}**")

        # 新闻与资金共振
        resonance = llm_analysis.get('resonance', [])
        if resonance:
            lines.append("\n**逻辑共振:**\n")
            for r in resonance[:3]:
                conclusion = r.get('conclusion', '')
                if conclusion:
                    lines.append(f"- {conclusion}")
        lines.append("")

    # 新闻联播政策分析
    cctv_analysis = news_data.get('cctv_analysis', {})
    if cctv_analysis and 'error' not in cctv_analysis:
        policy_signals = cctv_analysis.get('policy_signals', [])
        hints = cctv_analysis.get('investment_hints', '')

        if policy_signals or hints:
            lines.append("### 🏛️ 政策信号\n")

            for signal in policy_signals[:3]:
                topic = signal.get('topic', '')
                direction = signal.get('direction', '')
                sectors = signal.get('sectors', [])
                term = signal.get('term', '')

                direction_emoji = "🟢" if direction == "利好" else ("🔴" if direction == "利空" else "🟡")
                sectors_str = f"→ {', '.join(sectors)}" if sectors else ""
                lines.append(f"- {direction_emoji} **{topic}** ({term}) {sectors_str}")

            if hints:
                lines.append(f"\n> 💡 {hints}")
            lines.append("")

    # 宏观数据
    if news_data.get('macro'):
        lines.append("### 📈 宏观数据\n")
        for item in news_data['macro']:
            lines.append(f"- **{item.get('title', '')}** {item.get('content', '')}")
        lines.append("")

    # 重要新闻（按 LLM 重要性排序）
    all_news = news_data.get('all_news', [])

    # 如果有 LLM 分析，按重要性筛选
    if llm_analysis and 'error' not in llm_analysis:
        high_importance = [n for n in all_news if n.get('llm_importance', 0) >= 6]
        if high_importance:
            lines.append("### 📰 高价值资讯\n")
            lines.append("| 来源 | 新闻 | 重要性 | 情绪 | 相关板块 |")
            lines.append("|------|------|--------|------|----------|")

            for item in high_importance[:max_items]:
                title = item.get('title', item.get('content', ''))[:40]
                source = item.get('source', '')
                importance = item.get('llm_importance', 0)
                sentiment = item.get('llm_sentiment', 0)
                sectors = item.get('llm_sectors', [])

                # 情绪图标
                sent_emoji = "🟢" if sentiment > 0.2 else ("🔴" if sentiment < -0.2 else "🟡")
                sectors_str = ', '.join(sectors[:2]) if sectors else "-"

                lines.append(f"| {source} | {title} | {importance}/10 | {sent_emoji} {sentiment:+.1f} | {sectors_str} |")
            lines.append("")
    else:
        # 无 LLM 时，使用关键词筛选
        important_news = [n for n in all_news if n.get('important')]
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

    # 新闻联播摘要（无 LLM 分析时显示）
    if news_data.get('cctv') and not cctv_analysis:
        lines.append("### 新闻联播要点\n")
        for item in news_data['cctv'][:3]:
            title = item.get('title', '')
            if title:
                lines.append(f"- {title}")
        lines.append("")

    if not all_news and not news_data.get('macro') and not news_data.get('cctv'):
        lines.append("暂无重要新闻\n")

    return "\n".join(lines)


if __name__ == "__main__":
    news_data = collect_daily_news()

    print("\n" + "=" * 50)
    print(format_news_for_report(news_data))
