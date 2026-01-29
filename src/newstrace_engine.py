"""
NewsTrace - 金融新闻智能审计与回溯系统
主引擎类
"""
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import yaml

from .news_fetcher import NewsFetcher
from .audit_engine import AuditEngine
from .tracking_scheduler import TrackingScheduler
from .source_rating import SourceRating
from .database import Database

logger = logging.getLogger(__name__)


class NewsTraceEngine:
    """NewsTrace核心引擎"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        初始化NewsTrace引擎
        
        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        self.db = Database(self.config['database'])
        self.news_fetcher = NewsFetcher(self.config['data_source'])
        self.audit_engine = AuditEngine(self.config['llm'])
        self.tracking_scheduler = TrackingScheduler(
            self.db, 
            self.config['tracking']
        )
        self.source_rating = SourceRating(self.db)
        
        logger.info("NewsTrace引擎初始化完成")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 如果配置被嵌套在 'newstrace' 下，则将其展开
        if config and 'newstrace' in config:
            return config['newstrace']
        return config
    
    def audit_news(self, news: Dict) -> Dict:
        """
        审计单条新闻
        
        Args:
            news: 新闻字典 {title, content, source, timestamp}
            
        Returns:
            审计结果字典
        """
        logger.info(f"开始审计新闻: {news['title']}")
        
        # 生成新闻ID
        news_id = self._generate_news_id(news)
        news['news_id'] = news_id
        
        # 保存新闻到数据库
        self.db.save_news(news)
        
        # AI审计
        audit_result = self.audit_engine.audit(news)
        audit_result['news_id'] = news_id
        
        # 保存审计结果
        self.db.save_audit_result(audit_result)
        
        # 保存推荐标的
        for ticker in audit_result['recommended_tickers']:
            ticker['news_id'] = news_id
            self.db.save_recommended_ticker(ticker)
        
        logger.info(f"审计完成: 评分={audit_result['audit_result']['score']}, "
                   f"风险={audit_result['audit_result']['risk_level']}")
        
        return audit_result
    
    def start_tracking(
        self, 
        news_id: str, 
        tickers: List[Dict],
        duration_days: int = 7
    ) -> str:
        """
        开启追踪任务
        
        Args:
            news_id: 新闻ID
            tickers: 标的列表
            duration_days: 追踪天数
            
        Returns:
            追踪任务ID
        """
        logger.info(f"开启追踪任务: news_id={news_id}, 标的数={len(tickers)}")
        
        tracking_id = self.tracking_scheduler.create_tracking(
            news_id=news_id,
            tickers=tickers,
            duration_days=duration_days
        )
        
        return tracking_id
    
    async def start_tracking_async(
        self, 
        news_id: str, 
        tickers: List[Dict],
        duration_days: int = 7
    ) -> str:
        """异步开启追踪任务"""
        return self.start_tracking(news_id, tickers, duration_days)
    
    def get_tracking_status(self, tracking_id: str) -> Dict:
        """
        获取追踪任务状态
        
        Args:
            tracking_id: 追踪任务ID
            
        Returns:
            状态字典
        """
        return self.tracking_scheduler.get_status(tracking_id)
    
    def get_tracking_report(self, news_id: str) -> Dict:
        """
        获取完整追踪报告
        
        Args:
            news_id: 新闻ID
            
        Returns:
            报告字典
        """
        # 获取新闻信息
        news = self.db.get_news(news_id)
        
        # 获取审计结果
        audit = self.db.get_audit_result(news_id)
        
        # 获取追踪结果
        tracking_results = self.tracking_scheduler.get_tracking_results(news_id)
        
        return {
            'news': news,
            'audit': audit,
            'tracking_results': tracking_results
        }
    
    def update_tracking_prices(self):
        """更新所有活跃追踪任务的价格"""
        logger.info("开始更新追踪价格...")
        self.tracking_scheduler.update_all_prices()
        logger.info("价格更新完成")
    
    def update_all_trackings(self):
        """更新所有追踪任务(包括检查结案)"""
        self.update_tracking_prices()
        self.tracking_scheduler.check_and_close_completed()
    
    def get_source_ranking(self, days: int = 30) -> List[Dict]:
        """
        获取信源排名
        
        Args:
            days: 统计天数
            
        Returns:
            排名列表
        """
        return self.source_rating.get_ranking(days)
    
    def fetch_news(self, sources: Optional[List[str]] = None) -> List[Dict]:
        """
        获取最新新闻
        
        Args:
            sources: 指定信源列表，None表示所有
            
        Returns:
            新闻列表
        """
        return self.news_fetcher.fetch(sources)
    
    def get_latest_news(self, limit: int = 10) -> List[Dict]:
        """
        从数据库获取最新新闻及其审计结果
        
        Args:
            limit: 数量限制
            
        Returns:
            新闻列表(包含审计结果)
        """
        return self.db.get_latest_news_with_audit(limit)
    
    def get_active_trackings(self) -> List[Dict]:
        """获取所有活跃的追踪任务"""
        return self.tracking_scheduler.get_active_trackings()
    
    def generate_daily_report(self) -> Dict:
        """生成每日报告"""
        today = datetime.now().date()
        
        # 统计今日新闻
        news_count = self.db.count_news_by_date(today)
        
        # 统计风险分布
        risk_distribution = self.db.get_risk_distribution(today)
        
        # 获取高风险新闻
        high_risk_news = self.db.get_high_risk_news(today)
        
        # 获取今日结案的追踪任务
        closed_trackings = self.db.get_closed_trackings(today)
        
        return {
            'date': today.isoformat(),
            'news_count': news_count,
            'risk_distribution': risk_distribution,
            'high_risk_news': high_risk_news,
            'closed_trackings': closed_trackings
        }
    
    def generate_weekly_report(self) -> Dict:
        """生成周报"""
        # 更新信源评级
        self.source_rating.update_all_ratings()
        
        # 获取排名
        ranking = self.get_source_ranking(days=7)
        
        # 统计本周数据
        week_start = datetime.now().date() - timedelta(days=7)
        total_news = self.db.count_news_since(week_start)
        total_trackings = self.db.count_trackings_since(week_start)
        
        return {
            'week_start': week_start.isoformat(),
            'total_news': total_news,
            'total_trackings': total_trackings,
            'source_ranking': ranking
        }
    
    def send_report(self, report: Dict, channels: List[str]):
        """
        发送报告
        
        Args:
            report: 报告字典
            channels: 发送渠道列表 ['email', 'wechat_work', 'dingtalk']
        """
        # TODO: 实现报告发送逻辑
        logger.info(f"发送报告到: {', '.join(channels)}")
        pass
    
    async def send_alert(self, channel: str, message: str):
        """
        发送告警
        
        Args:
            channel: 告警渠道
            message: 告警消息
        """
        # TODO: 实现告警发送逻辑
        logger.warning(f"[{channel}] {message}")
        pass
    
    def _generate_news_id(self, news: Dict) -> str:
        """生成新闻ID"""
        timestamp = news.get('timestamp', datetime.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        
        return f"NT{timestamp.strftime('%Y%m%d%H%M%S')}{hash(news['title']) % 1000:03d}"
    
    def switch_data_source(self, provider: str):
        """切换数据源"""
        self.news_fetcher.switch_provider(provider)
        logger.info(f"数据源已切换至: {provider}")
    
    def normalize_news_format(self, news: Dict) -> Dict:
        """标准化新闻格式"""
        return self.news_fetcher.normalize(news)
    
    async def subscribe_news_feed(self):
        """订阅新闻流(异步生成器)"""
        while True:
            news_list = self.fetch_news()
            for news in news_list:
                yield news
            
            # 等待一段时间再获取
            import asyncio
            await asyncio.sleep(self.config.get('fetch_interval', 3600))
