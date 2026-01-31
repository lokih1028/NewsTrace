"""
LLM 响应缓存管理器
使用 Redis 缓存 LLM 审计结果,避免重复 API 调用
"""
import hashlib
import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    logger.warning("Redis 未安装,将使用内存缓存")


class LLMCache:
    """LLM 响应缓存器"""
    
    def __init__(self, redis_url: str = None, ttl_days: int = 7):
        """
        初始化缓存管理器
        
        Args:
            redis_url: Redis 连接 URL
            ttl_days: 缓存过期时间(天)
        """
        self.ttl = ttl_days * 86400  # 转换为秒
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client = None
        self.memory_cache = {}  # 内存缓存降级
        
        self._init_redis()
        
        logger.info(f"LLM 缓存初始化完成, TTL={ttl_days}天, 模式={'Redis' if self.redis_client else '内存'}")
    
    def _init_redis(self):
        """初始化 Redis 连接"""
        if not HAS_REDIS:
            return
        
        try:
            self.redis_client = redis.from_url(self.redis_url)
            self.redis_client.ping()
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.warning(f"Redis 连接失败,降级为内存缓存: {e}")
            self.redis_client = None
    
    def _get_cache_key(self, news_title: str, news_content: str = "") -> str:
        """生成缓存键（包含时间维度）"""
        import datetime
        # 使用日期+小时作为时间盐，同一天同一小时内的相同新闻才命中缓存
        # 这样可以保证不同时间段对同一新闻产生不同的分析结果
        time_salt = datetime.datetime.now().strftime("%Y%m%d%H")
        content_hash = hashlib.md5(
            f"{news_title}:{news_content[:200]}:{time_salt}".encode()
        ).hexdigest()
        return f"llm:audit:{content_hash}"
    
    def get(self, news_title: str, news_content: str = "") -> Optional[Dict]:
        """
        获取缓存的审计结果
        
        Args:
            news_title: 新闻标题
            news_content: 新闻内容
            
        Returns:
            缓存的审计结果,未命中返回 None
        """
        key = self._get_cache_key(news_title, news_content)
        
        try:
            if self.redis_client:
                cached = self.redis_client.get(key)
                if cached:
                    logger.debug(f"缓存命中: {key}")
                    return json.loads(cached)
            else:
                if key in self.memory_cache:
                    logger.debug(f"内存缓存命中: {key}")
                    return self.memory_cache[key]
        except Exception as e:
            logger.error(f"获取缓存失败: {e}")
        
        return None
    
    def set(self, news_title: str, news_content: str, result: Dict):
        """
        缓存审计结果
        
        Args:
            news_title: 新闻标题
            news_content: 新闻内容
            result: 审计结果
        """
        key = self._get_cache_key(news_title, news_content)
        
        try:
            if self.redis_client:
                self.redis_client.setex(key, self.ttl, json.dumps(result, ensure_ascii=False))
                logger.debug(f"缓存写入: {key}")
            else:
                self.memory_cache[key] = result
                # 内存缓存限制大小
                if len(self.memory_cache) > 1000:
                    # 删除最早的条目
                    oldest_key = next(iter(self.memory_cache))
                    del self.memory_cache[oldest_key]
        except Exception as e:
            logger.error(f"写入缓存失败: {e}")
    
    def clear(self, pattern: str = "llm:audit:*"):
        """清除缓存"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                    logger.info(f"清除 {len(keys)} 条缓存")
            else:
                self.memory_cache.clear()
                logger.info("内存缓存已清空")
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
    
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys("llm:audit:*")
                info = self.redis_client.info("memory")
                return {
                    "type": "redis",
                    "entries": len(keys),
                    "memory_used": info.get("used_memory_human", "unknown")
                }
            else:
                return {
                    "type": "memory",
                    "entries": len(self.memory_cache),
                    "memory_used": "N/A"
                }
        except Exception as e:
            return {"error": str(e)}
