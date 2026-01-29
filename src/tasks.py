"""
Celery定时任务
"""
from celery import Celery
from celery.schedules import crontab
import os
import logging

logger = logging.getLogger(__name__)

# 初始化Celery
app = Celery(
    'newstrace',
    broker=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:6379/0",
    backend=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:6379/0"
)

# Celery配置
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
)


@app.task(bind=True, max_retries=3)
def fetch_news_task(self):
    """每小时采集新闻"""
    try:
        from src.newstrace_engine import NewsTraceEngine
        engine = NewsTraceEngine()
        news_list = engine.fetch_news()
        
        # 自动审计新闻
        for news in news_list:
            audit_news_task.delay(news)
        
        logger.info(f"成功采集 {len(news_list)} 条新闻")
        return len(news_list)
    except Exception as exc:
        logger.error(f"新闻采集失败: {exc}")
        raise self.retry(exc=exc, countdown=300)  # 5分钟后重试


@app.task(bind=True, max_retries=3)
def audit_news_task(self, news):
    """审计单条新闻"""
    try:
        from src.newstrace_engine import NewsTraceEngine
        engine = NewsTraceEngine()
        result = engine.audit_news(news)
        
        # 如果有推荐标的,自动开启追踪
        if result.get('recommended_tickers'):
            start_tracking_task.delay(
                result['news_id'],
                result['recommended_tickers']
            )
        
        return result
    except Exception as exc:
        logger.error(f"新闻审计失败: {exc}")
        raise self.retry(exc=exc, countdown=60)


@app.task(bind=True, max_retries=3)
def start_tracking_task(self, news_id, tickers):
    """开启追踪任务"""
    try:
        from src.newstrace_engine import NewsTraceEngine
        engine = NewsTraceEngine()
        tracking_id = engine.start_tracking(news_id, tickers)
        logger.info(f"开启追踪任务: {tracking_id}")
        return tracking_id
    except Exception as exc:
        logger.error(f"开启追踪失败: {exc}")
        raise self.retry(exc=exc, countdown=60)


@app.task
def update_tracking_prices_task():
    """每日15:30更新追踪价格"""
    try:
        from src.newstrace_engine import NewsTraceEngine
        engine = NewsTraceEngine()
        engine.update_tracking_prices()
        logger.info("价格更新完成")
    except Exception as exc:
        logger.error(f"价格更新失败: {exc}")


@app.task
def check_and_close_trackings_task():
    """每日检查并结案追踪任务"""
    try:
        from src.newstrace_engine import NewsTraceEngine
        engine = NewsTraceEngine()
        engine.update_all_trackings()
        logger.info("追踪任务检查完成")
    except Exception as exc:
        logger.error(f"追踪任务检查失败: {exc}")


@app.task
def update_source_ratings_task():
    """每周更新信源评级"""
    try:
        from src.newstrace_engine import NewsTraceEngine
        engine = NewsTraceEngine()
        engine.source_rating.update_all_ratings()
        logger.info("信源评级更新完成")
    except Exception as exc:
        logger.error(f"信源评级更新失败: {exc}")


@app.task
def generate_daily_report_task():
    """每日生成报告"""
    try:
        from src.newstrace_engine import NewsTraceEngine
        engine = NewsTraceEngine()
        report = engine.generate_daily_report()
        # 可以在这里发送报告
        logger.info("每日报告生成完成")
        return report
    except Exception as exc:
        logger.error(f"报告生成失败: {exc}")


# 定时任务配置
app.conf.beat_schedule = {
    # 每小时采集新闻
    'fetch-news-hourly': {
        'task': 'src.tasks.fetch_news_task',
        'schedule': 3600.0,
    },
    # 每日15:30更新价格
    'update-prices-daily': {
        'task': 'src.tasks.update_tracking_prices_task',
        'schedule': crontab(hour=15, minute=30),
    },
    # 每日16:00检查结案
    'check-trackings-daily': {
        'task': 'src.tasks.check_and_close_trackings_task',
        'schedule': crontab(hour=16, minute=0),
    },
    # 每周日凌晨更新评级
    'update-ratings-weekly': {
        'task': 'src.tasks.update_source_ratings_task',
        'schedule': crontab(day_of_week=0, hour=0, minute=0),
    },
    # 每日18:00生成报告
    'generate-report-daily': {
        'task': 'src.tasks.generate_daily_report_task',
        'schedule': crontab(hour=18, minute=0),
    },
}
