import random
import time
import logging
from collections import deque

logger = logging.getLogger(__name__)

class AdaptiveRateLimiter:
    """自适应速率限制器"""
    
    def __init__(self, min_interval=15, max_interval=45):
        """
        初始化流控器
        
        Args:
            min_interval: 最小等待间隔(秒)
            max_interval: 最大等待间隔(秒)
        """
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.recent_failures = deque(maxlen=10)
    
    def wait(self):
        """动态调整等待时间并执行休眠"""
        # 如果最近失败率高,增加等待时间
        failure_rate = sum(self.recent_failures) / len(self.recent_failures) if self.recent_failures else 0
        
        if failure_rate > 0.3:  # 30%失败率
            interval = self.max_interval
            logger.warning(f"检测到高失败率({failure_rate:.1%}), 触发熔断保护, 等待 {interval} 秒")
        else:
            interval = random.uniform(self.min_interval, self.max_interval)
            logger.debug(f"流控等待: {interval:.1f} 秒")
        
        time.sleep(interval)
    
    def record_result(self, success: bool):
        """记录请求结果"""
        self.recent_failures.append(0 if success else 1)
        if not success:
            logger.warning("记录到一次采集失败")
