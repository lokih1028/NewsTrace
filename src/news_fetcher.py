"""
新闻采集器
支持Tushare、AkShare等数据源
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class NewsFetcher:
    """新闻采集器"""
    
    def __init__(self, config: Dict):
        """
        初始化采集器
        
        Args:
            config: 数据源配置
        """
        self.config = config
        self.provider = config.get('provider', 'tushare')
        self.api_key = config.get('api_key')
        
        # 初始化API客户端
        self._init_client()
        
        logger.info(f"新闻采集器初始化完成: provider={self.provider}")
    
    def _init_client(self):
        """初始化API客户端"""
        if self.provider == 'tushare':
            try:
                import tushare as ts
                ts.set_token(self.api_key)
                self.client = ts.pro_api()
                logger.info("Tushare客户端初始化成功")
            except ImportError:
                logger.error("Tushare未安装,请运行: pip install tushare")
                self.client = None
            except Exception as e:
                logger.error(f"Tushare初始化失败: {e}")
                self.client = None
                
        elif self.provider == 'akshare':
            try:
                import akshare as ak
                self.client = ak
                logger.info("AkShare客户端初始化成功")
            except ImportError:
                logger.error("AkShare未安装,请运行: pip install akshare")
                self.client = None
        else:
            logger.warning(f"未知的数据源: {self.provider}")
            self.client = None
    
    def fetch(self, sources: Optional[List[str]] = None) -> List[Dict]:
        """
        获取最新新闻
        
        Args:
            sources: 指定信源列表
            
        Returns:
            新闻列表
        """
        if self.client is None:
            logger.error("API客户端未初始化")
            return []
        
        try:
            if self.provider == 'tushare':
                return self._fetch_from_tushare(sources)
            elif self.provider == 'akshare':
                return self._fetch_from_akshare(sources)
            else:
                return []
        except Exception as e:
            logger.error(f"获取新闻失败: {e}")
            return []
    
    def fetch_with_fallback(self) -> List[Dict]:
        """
        多源容错采集:按优先级尝试不同数据源
        """
        sources = [
            {'name': 'tushare', 'method': self._fetch_from_tushare},
            {'name': 'akshare', 'method': self._fetch_from_akshare},
        ]
        
        # 如果配置了其他源,可以在这里添加
        
        for source in sources:
            try:
                logger.info(f"正在尝试从 {source['name']} 获取新闻...")
                news_list = source['method'](None)
                if news_list:
                    logger.info(f"✅ 从 {source['name']} 成功获取到 {len(news_list)} 条新闻")
                    return news_list
            except Exception as e:
                logger.warning(f"⚠️ 从 {source['name']} 获取失败: {e}")
                continue
        
        logger.error("❌ 所有数据源均获取失败")
        return []

    def _fetch_from_tushare(self, sources: Optional[List[str]]) -> List[Dict]:
        """从Tushare获取新闻"""
        if self.provider != 'tushare' or not self.client:
            # 临时切换或初始化
            self.switch_provider('tushare')
            
        try:
            # 获取财经新闻
            df = self.client.news(
                src='sina',  # 新浪财经
                start_date='',
                end_date='',
                limit=50
            )
            
            news_list = []
            for _, row in df.iterrows():
                news = {
                    'title': row['title'],
                    'content': row.get('content', ''),
                    'source': row.get('src', 'Tushare'),
                    'timestamp': row['datetime'],
                    'url': row.get('url', ''),
                    'docid': row.get('id', '')
                }
                news_list.append(news)
            
            return news_list
            
        except Exception as e:
            logger.error(f"Tushare获取新闻失败: {e}")
            return []

    def _fetch_from_akshare(self, sources: Optional[List[str]]) -> List[Dict]:
        """从AkShare获取新闻"""
        if self.provider != 'akshare' or not self.client:
            self.switch_provider('akshare')
            
        try:
            # 获取东方财富快讯
            df = self.client.stock_news_em()
            
            news_list = []
            for _, row in df.iterrows():
                news = {
                    'title': row['新闻标题'],
                    'content': row.get('新闻内容', ''),
                    'source': '东方财富',
                    'timestamp': row['发布时间'],
                    'url': row.get('新闻链接', ''),
                    'docid': row.get('新闻链接', '') # 使用链接作为ID
                }
                news_list.append(news)
            
            return news_list[:50]
            
        except Exception as e:
            logger.error(f"AkShare获取新闻失败: {e}")
            return []
    
    def fetch_from_rss(self, rss_url: str) -> List[Dict]:
        """
        从RSS源获取新闻
        
        Args:
            rss_url: RSS地址
            
        Returns:
            新闻列表
        """
        try:
            import feedparser
            
            feed = feedparser.parse(rss_url)
            news_list = []
            
            for entry in feed.entries[:50]:
                news = {
                    'title': entry.title,
                    'content': entry.get('summary', ''),
                    'source': feed.feed.get('title', 'RSS'),
                    'timestamp': entry.get('published', datetime.now().isoformat()),
                    'url': entry.get('link', '')
                }
                news_list.append(news)
            
            logger.info(f"从RSS获取到 {len(news_list)} 条新闻")
            return news_list
            
        except ImportError:
            logger.error("feedparser未安装,请运行: pip install feedparser")
            return []
        except Exception as e:
            logger.error(f"RSS获取新闻失败: {e}")
            return []
    
    def normalize(self, news: Dict) -> Dict:
        """
        标准化新闻格式
        
        Args:
            news: 原始新闻字典
            
        Returns:
            标准化后的新闻字典
        """
        # 确保必需字段存在
        normalized = {
            'title': news.get('title', ''),
            'content': news.get('content', ''),
            'source': news.get('source', 'Unknown'),
            'timestamp': news.get('timestamp', datetime.now().isoformat()),
            'url': news.get('url', '')
        }
        
        # 标准化时间格式
        if isinstance(normalized['timestamp'], str):
            try:
                # 尝试解析时间字符串
                dt = datetime.fromisoformat(normalized['timestamp'].replace('Z', '+00:00'))
                normalized['timestamp'] = dt.isoformat()
            except:
                normalized['timestamp'] = datetime.now().isoformat()
        
        return normalized
    
    def switch_provider(self, provider: str):
        """
        切换数据源
        
        Args:
            provider: 数据源名称 (tushare/akshare)
        """
        self.provider = provider
        self._init_client()
        logger.info(f"数据源已切换至: {provider}")
    
    def enqueue_to_redis(self, news_list: List[Dict], redis_client):
        """
        将新闻入队到Redis
        
        Args:
            news_list: 新闻列表
            redis_client: Redis客户端
        """
        import json
        
        for news in news_list:
            try:
                redis_client.lpush(
                    'newstrace:news_queue',
                    json.dumps(news, ensure_ascii=False)
                )
            except Exception as e:
                logger.error(f"新闻入队失败: {e}")
        
        logger.info(f"已将 {len(news_list)} 条新闻入队")
