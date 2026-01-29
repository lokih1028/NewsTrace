"""
LLM 成本跟踪器
记录 Token 消耗并提供成本统计
"""
import logging
import os
from datetime import datetime, date
from typing import Dict, Optional
import json

logger = logging.getLogger(__name__)

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    logger.warning("tiktoken 未安装,Token 计数将使用估算")


class CostTracker:
    """LLM 成本跟踪器"""
    
    # 定价 (per 1M tokens, USD)
    PRICING = {
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
    }
    
    def __init__(self, db=None, model: str = "gpt-4o"):
        """
        初始化成本跟踪器
        
        Args:
            db: 数据库实例 (可选)
            model: 默认模型名称
        """
        self.db = db
        self.model = model
        self.encoding = None
        
        # 内存统计
        self.session_stats = {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
            "start_time": datetime.now()
        }
        
        if HAS_TIKTOKEN:
            try:
                self.encoding = tiktoken.encoding_for_model("gpt-4o")
            except Exception:
                self.encoding = tiktoken.get_encoding("cl100k_base")
        
        logger.info(f"成本跟踪器初始化完成, 模型={model}, tiktoken={'启用' if self.encoding else '禁用'}")
    
    def count_tokens(self, text: str) -> int:
        """计算文本的 Token 数量"""
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            # 粗略估算: 1 token ≈ 4 字符 (英文) 或 2 字符 (中文)
            return max(len(text) // 2, 1)
    
    def record_call(
        self,
        prompt: str,
        response: str,
        model: str = None,
        cached: bool = False
    ) -> Dict:
        """
        记录一次 LLM 调用
        
        Args:
            prompt: 输入提示词
            response: LLM 响应
            model: 使用的模型
            cached: 是否来自缓存
            
        Returns:
            调用统计信息
        """
        model = model or self.model
        
        input_tokens = self.count_tokens(prompt)
        output_tokens = self.count_tokens(response)
        
        # 计算成本
        pricing = self.PRICING.get(model, self.PRICING["gpt-4o"])
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
        
        # 如果是缓存命中,成本为 0
        if cached:
            cost = 0.0
        
        # 更新会话统计
        self.session_stats["calls"] += 1
        self.session_stats["input_tokens"] += input_tokens
        self.session_stats["output_tokens"] += output_tokens
        self.session_stats["total_cost"] += cost
        
        call_info = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
            "cached": cached
        }
        
        # 持久化到数据库
        if self.db:
            self._save_to_db(call_info)
        
        logger.debug(
            f"LLM 调用记录: model={model}, "
            f"tokens={input_tokens}+{output_tokens}, "
            f"cost=${cost:.6f}, cached={cached}"
        )
        
        return call_info
    
    def _save_to_db(self, call_info: Dict):
        """保存调用记录到数据库"""
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                if self.db.db_type == 'postgresql':
                    cur.execute("""
                        INSERT INTO llm_cost_log 
                        (timestamp, model, input_tokens, output_tokens, cost_usd, cached)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        call_info["timestamp"],
                        call_info["model"],
                        call_info["input_tokens"],
                        call_info["output_tokens"],
                        call_info["cost_usd"],
                        call_info["cached"]
                    ))
                else:
                    cur.execute("""
                        INSERT INTO llm_cost_log 
                        (timestamp, model, input_tokens, output_tokens, cost_usd, cached)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        call_info["timestamp"],
                        call_info["model"],
                        call_info["input_tokens"],
                        call_info["output_tokens"],
                        call_info["cost_usd"],
                        call_info["cached"]
                    ))
        except Exception as e:
            logger.error(f"保存成本记录失败: {e}")
    
    def get_session_stats(self) -> Dict:
        """获取当前会话统计"""
        duration = (datetime.now() - self.session_stats["start_time"]).total_seconds()
        return {
            **self.session_stats,
            "duration_seconds": round(duration, 2),
            "avg_cost_per_call": round(
                self.session_stats["total_cost"] / max(self.session_stats["calls"], 1), 6
            )
        }
    
    def get_daily_stats(self, target_date: date = None) -> Dict:
        """获取指定日期的成本统计"""
        if not self.db:
            return self.get_session_stats()
        
        target_date = target_date or date.today()
        
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                if self.db.db_type == 'postgresql':
                    cur.execute("""
                        SELECT 
                            COUNT(*) as calls,
                            SUM(input_tokens) as input_tokens,
                            SUM(output_tokens) as output_tokens,
                            SUM(cost_usd) as total_cost,
                            SUM(CASE WHEN cached THEN 1 ELSE 0 END) as cache_hits
                        FROM llm_cost_log
                        WHERE DATE(timestamp) = %s
                    """, (target_date,))
                else:
                    cur.execute("""
                        SELECT 
                            COUNT(*) as calls,
                            SUM(input_tokens) as input_tokens,
                            SUM(output_tokens) as output_tokens,
                            SUM(cost_usd) as total_cost,
                            SUM(CASE WHEN cached THEN 1 ELSE 0 END) as cache_hits
                        FROM llm_cost_log
                        WHERE date(timestamp) = ?
                    """, (target_date.isoformat(),))
                
                row = cur.fetchone()
                if row:
                    return {
                        "date": target_date.isoformat(),
                        "calls": row[0] or 0,
                        "input_tokens": row[1] or 0,
                        "output_tokens": row[2] or 0,
                        "total_cost_usd": round(row[3] or 0, 4),
                        "cache_hits": row[4] or 0,
                        "cache_hit_rate": round((row[4] or 0) / max(row[0] or 1, 1) * 100, 2)
                    }
        except Exception as e:
            logger.error(f"获取日统计失败: {e}")
        
        return {}
    
    def get_monthly_projection(self) -> Dict:
        """根据当前使用情况预估月成本"""
        stats = self.get_session_stats()
        
        if stats["calls"] == 0:
            return {"projected_monthly_cost": 0}
        
        duration_hours = stats["duration_seconds"] / 3600
        if duration_hours < 0.1:
            return {"projected_monthly_cost": "insufficient_data"}
        
        hourly_cost = stats["total_cost"] / duration_hours
        # 假设每天运行 8 小时,每月 22 个工作日
        monthly_projection = hourly_cost * 8 * 22
        
        return {
            "hourly_cost": round(hourly_cost, 4),
            "projected_monthly_cost": round(monthly_projection, 2),
            "assumptions": "8 hours/day, 22 working days/month"
        }
    
    def format_summary(self) -> str:
        """格式化输出统计摘要"""
        stats = self.get_session_stats()
        projection = self.get_monthly_projection()
        
        return f"""
📊 LLM 成本统计摘要
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
调用次数: {stats['calls']}
输入 Token: {stats['input_tokens']:,}
输出 Token: {stats['output_tokens']:,}
总成本: ${stats['total_cost']:.4f}
平均每次: ${stats['avg_cost_per_call']:.6f}
预估月成本: ${projection.get('projected_monthly_cost', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
