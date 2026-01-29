# NewsTrace 使用示例

## 示例1: 基础新闻审计

```python
from newstrace import NewsTraceEngine

# 初始化引擎
engine = NewsTraceEngine(config_path="config.yaml")

# 待审计的新闻
news = {
    "title": "重磅!消费税改革方案出台,白酒板块暴涨在即!",
    "content": "据财政部消息,新一轮消费税改革方案正式发布...",
    "source": "某财经自媒体",
    "timestamp": "2026-01-20 09:35:00"
}

# 执行审计
result = engine.audit_news(news)

# 查看结果
print(f"逻辑评分: {result['audit_result']['score']}/100")
print(f"风险等级: {result['audit_result']['risk_level']}")
print(f"警告信息: {result['audit_result']['warnings']}")
print(f"推荐标的: {[t['name'] for t in result['recommended_tickers']]}")
```

**输出示例**:

```
逻辑评分: 45/100
风险等级: High
警告信息: ['标题使用了"暴涨"等情绪化词汇', '缺乏具体政策细节', '来源可信度较低']
推荐标的: ['贵州茅台', '五粮液', '泸州老窖']
```

---

## 示例2: 开启7天追踪

```python
# 基于审计结果开启追踪
tracking_id = engine.start_tracking(
    news_id=result['news_id'],
    tickers=result['recommended_tickers'],
    duration_days=7
)

print(f"追踪任务已启动,ID: {tracking_id}")
print(f"预计结案时间: {result['expected_close_date']}")

# 查看当前追踪状态
status = engine.get_tracking_status(tracking_id)
print(f"当前天数: T+{status['current_day']}")
print(f"贵州茅台涨幅: {status['tickers']['600519.SH']['pnl']}")
```

**输出示例**:

```
追踪任务已启动,ID: NT20260120093500001
预计结案时间: 2026-01-27 15:30:00
当前天数: T+3
贵州茅台涨幅: +2.15%
```

---

## 示例3: 批量处理新闻流

```python
import asyncio

async def process_news_stream():
    """实时处理新闻流"""
    async for news in engine.subscribe_news_feed():
        # 异步审计
        result = await engine.audit_news_async(news)
        
        # 高风险新闻发送告警
        if result['audit_result']['risk_level'] == 'High':
            await engine.send_alert(
                channel="wechat_work",
                message=f"⚠️ 高风险新闻: {news['title']}\n"
                        f"风险评分: {result['audit_result']['score']}\n"
                        f"警告: {', '.join(result['audit_result']['warnings'])}"
            )
        
        # 中低风险新闻开启追踪
        else:
            await engine.start_tracking_async(
                news_id=result['news_id'],
                tickers=result['recommended_tickers']
            )

# 运行
asyncio.run(process_news_stream())
```

---

## 示例4: 信源公信力分析

```python
# 查询过去30天的信源排名
ranking = engine.get_source_ranking(days=30)

for source in ranking[:5]:  # 前5名
    print(f"\n信源: {source['name']}")
    print(f"  评级: {source['grade']}")
    print(f"  平均收益: {source['avg_return']}")
    print(f"  辟谣率: {source['rumor_rate']}")
    print(f"  推荐准确率: {source['accuracy']}")
    print(f"  建议: {source['recommendation']}")
```

**输出示例**:

```
信源: 财联社
  评级: A
  平均收益: +3.2%
  辟谣率: 12%
  推荐准确率: 68%
  建议: 高可信度信源

信源: 证券时报
  评级: A-
  平均收益: +2.8%
  辟谣率: 15%
  推荐准确率: 64%
  建议: 可信度较高

信源: 某自媒体
  评级: D
  平均收益: -1.8%
  辟谣率: 45%
  推荐准确率: 35%
  建议: 建议过滤
```

---

## 示例5: 历史回测查询

```python
# 查询某条新闻的完整追踪结果
report = engine.get_tracking_report("NT20260120093500001")

print(f"新闻标题: {report['news']['title']}")
print(f"发布时间: {report['news']['timestamp']}")
print(f"初始评分: {report['audit']['score']}/100")
print(f"\n追踪结果:")

for ticker in report['tracking_results']:
    print(f"\n{ticker['name']} ({ticker['code']})")
    print(f"  T0价格: ¥{ticker['t0_price']}")
    print(f"  T+7价格: ¥{ticker['t7_price']}")
    print(f"  涨跌幅: {ticker['pnl']}")
    print(f"  波动率: {ticker['volatility']}")
    
    # 显示每日价格走势
    print(f"  价格走势:")
    for day, price in ticker['daily_prices'].items():
        print(f"    {day}: ¥{price}")
```

**输出示例**:

```
新闻标题: 重磅!消费税改革方案出台,白酒板块暴涨在即!
发布时间: 2026-01-20 09:35:00
初始评分: 45/100

追踪结果:

贵州茅台 (600519.SH)
  T0价格: ¥1850.00
  T+7价格: ¥1925.00
  涨跌幅: +4.05%
  波动率: 1.2%
  价格走势:
    T+1: ¥1865.50
    T+2: ¥1842.30
    T+3: ¥1888.00
    T+4: ¥1901.20
    T+5: ¥1895.60
    T+6: ¥1910.00
    T+7: ¥1925.00
```

---

## 示例6: 自定义审计规则

```python
# 添加自定义语义检测规则
engine.add_semantic_rule(
    name="政策解读夸大",
    pattern=r"(重磅|震撼|暴涨|暴跌|必涨|必跌)",
    risk_level="High",
    warning_message="标题使用了过度煽动性词汇"
)

# 添加行业特定规则
engine.add_industry_rule(
    industry="白酒",
    keywords=["消费税", "税率", "政策"],
    related_tickers=["600519.SH", "000858.SZ", "000568.SZ"],
    logic_template="消费税政策直接影响{industry}行业利润预期"
)

# 使用自定义规则审计
result = engine.audit_news(news, use_custom_rules=True)
```

---

## 示例7: Dashboard集成

```python
import streamlit as st

# Streamlit Dashboard
st.title("NewsTrace 金融情报监控台")

# 实时新闻流
st.header("实时新闻审计")
news_stream = engine.get_latest_news(limit=10)

for news in news_stream:
    with st.expander(f"{news['title']} - {news['source']}"):
        col1, col2, col3 = st.columns(3)
        
        col1.metric("逻辑评分", f"{news['audit']['score']}/100")
        col2.metric("风险等级", news['audit']['risk_level'])
        col3.metric("推荐标的数", len(news['tickers']))
        
        if news['audit']['warnings']:
            st.warning("⚠️ " + "\n".join(news['audit']['warnings']))
        
        st.write("**推荐标的:**")
        for ticker in news['tickers']:
            st.write(f"- {ticker['name']} ({ticker['code']}): {ticker['logic']}")

# 信源排名
st.header("信源公信力排名")
ranking = engine.get_source_ranking(days=30)
st.dataframe(ranking)

# 追踪中的任务
st.header("进行中的追踪任务")
active_trackings = engine.get_active_trackings()
st.write(f"当前追踪中: {len(active_trackings)} 个任务")
```

---

## 示例8: 定时任务配置

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# 每日15:30更新追踪价格
scheduler.add_job(
    func=engine.update_tracking_prices,
    trigger='cron',
    hour=15,
    minute=30,
    timezone='Asia/Shanghai'
)

# 每周一生成信源报告
scheduler.add_job(
    func=engine.generate_weekly_report,
    trigger='cron',
    day_of_week='mon',
    hour=9,
    minute=0
)

# 每小时检查新闻流
scheduler.add_job(
    func=engine.fetch_latest_news,
    trigger='interval',
    hours=1
)

scheduler.start()
```

---

## 完整工作流示例

```python
from newstrace import NewsTraceEngine
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化
engine = NewsTraceEngine(config_path="config.yaml")

def main_workflow():
    """完整的NewsTrace工作流"""
    
    # 1. 获取最新新闻
    logger.info("获取最新财经新闻...")
    news_list = engine.fetch_news(sources=["财联社", "证券时报", "新浪财经"])
    
    # 2. 批量审计
    logger.info(f"开始审计 {len(news_list)} 条新闻...")
    audit_results = []
    
    for news in news_list:
        result = engine.audit_news(news)
        audit_results.append(result)
        
        # 记录高风险新闻
        if result['audit_result']['risk_level'] == 'High':
            logger.warning(f"发现高风险新闻: {news['title']}")
    
    # 3. 过滤并开启追踪
    logger.info("开启追踪任务...")
    for result in audit_results:
        # 只追踪中低风险新闻
        if result['audit_result']['risk_level'] in ['Medium', 'Low']:
            engine.start_tracking(
                news_id=result['news_id'],
                tickers=result['recommended_tickers']
            )
    
    # 4. 更新现有追踪
    logger.info("更新追踪价格...")
    engine.update_all_trackings()
    
    # 5. 生成报告
    logger.info("生成每日报告...")
    report = engine.generate_daily_report()
    engine.send_report(report, channels=["email", "wechat_work"])
    
    logger.info("工作流完成!")

if __name__ == "__main__":
    main_workflow()
```

---

## 错误处理示例

```python
from newstrace.exceptions import (
    NewsTraceAPIError,
    InvalidNewsFormatError,
    TrackingNotFoundError
)

try:
    result = engine.audit_news(news)
except InvalidNewsFormatError as e:
    logger.error(f"新闻格式错误: {e}")
    # 尝试修复格式
    news = engine.normalize_news_format(news)
    result = engine.audit_news(news)
    
except NewsTraceAPIError as e:
    logger.error(f"API调用失败: {e}")
    # 使用备用数据源
    engine.switch_data_source("akshare")
    result = engine.audit_news(news)
    
except TrackingNotFoundError as e:
    logger.error(f"追踪任务不存在: {e}")
    # 重新创建追踪
    engine.start_tracking(news_id, tickers)
```
