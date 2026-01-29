"""
NewsTrace Core Engine: Adaptive Weight Strategy
Version: 2.0
Description: Implements Reflexivity (反身性) by adjusting audit weights based on market feedback.
"""
import numpy as np
from dataclasses import dataclass
from typing import List, Dict
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# --- Data Structures ---

@dataclass
class MarketFeedback:
    """
    输入数据对象：连接 '语义审计' 与 '事后回溯'
    """
    news_id: str
    ai_audit_score: float        # 原始逻辑评分 (0-100)
    detected_features: List[str] # AI提取的特征 (e.g., "hype_language", "policy_demand")
    actual_return_t3: float      # 市场真实反馈 (T+3 PnL)
    market_regime: str           # 市场状态 (Bull/Bear/Neutral)

class DynamicConfig:
    """
    配置对象：系统的'长期记忆'
    """
    def __init__(self):
        # 初始权重：对应原文档中的静态逻辑
        # 随着进化，这些值会偏离初始设定
        self.weights = {
            "hype_language": -20.0,   # 初始：标题党扣分
            "policy_demand": 15.0,    # 初始：强政策加分
            "uncertainty": -30.0,     # 初始：不确定性扣分
            "logical_rigor": 25.0,    # 初始：逻辑严谨加分
            "data_support": 20.0      # 初始：数据支撑加分
        }
        self.learning_rate = 0.1      # 进化速率
        self.update_history = []      # 更新历史记录
        
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "weights": self.weights.copy(),
            "learning_rate": self.learning_rate,
            "last_update": datetime.now().isoformat() if self.update_history else None
        }
    
    def from_dict(self, data: Dict):
        """从字典加载配置"""
        if "weights" in data:
            self.weights = data["weights"]
        if "learning_rate" in data:
            self.learning_rate = data["learning_rate"]

# --- Core Evolution Logic ---

class StrategyUpdater:
    """
    策略更新器：实现基于市场反馈的权重自适应调整
    """
    def __init__(self, config: DynamicConfig = None):
        self.config = config or DynamicConfig()
        logger.info(f"StrategyUpdater initialized with weights: {self.config.weights}")
    
    def calculate_reward(self, feedback: MarketFeedback) -> float:
        """
        计算 'Regret' (遗憾值)：AI 判断与市场走势的偏差
        
        Args:
            feedback: 市场反馈数据
            
        Returns:
            奖励值：正值表示判断正确，负值表示误判
        """
        # 归一化 AI 分数 (-1 ~ 1)
        normalized_score = (feedback.ai_audit_score - 50) / 50 
        
        # 奖励函数：方向一致(Score同号PnL)为正，反之为负
        # 乘以100是为了放大信号
        reward = normalized_score * feedback.actual_return_t3 * 100
        
        logger.debug(f"News {feedback.news_id}: AI Score={feedback.ai_audit_score}, "
                    f"T+3 Return={feedback.actual_return_t3:.2%}, Reward={reward:.2f}")
        
        return reward
    
    def evolve(self, batch_feedback: List[MarketFeedback]):
        """
        执行进化：基于贝叶斯推断调整权重
        
        Args:
            batch_feedback: 批量市场反馈数据
        """
        if not batch_feedback:
            logger.warning("No feedback data provided for evolution")
            return
        
        weight_deltas = {k: 0.0 for k in self.config.weights.keys()}
        feature_counts = {k: 0 for k in self.config.weights.keys()}
        
        for feedback in batch_feedback:
            # 如果 AI 误判 (例如：给了低分但股价大涨)，需要修正导致误判的特征权重
            for feature in feedback.detected_features:
                if feature in self.config.weights:
                    feature_counts[feature] += 1
                    correction_signal = 0
                    
                    # 案例1：牛市中，市场奖励"标题党"，AI却在惩罚它
                    # Action: 减少惩罚，甚至转为奖励
                    if feedback.actual_return_t3 > 0.02:  # 大涨 (>2%)
                        # 如果AI给了低分但市场大涨，说明该特征应该加分
                        if feedback.ai_audit_score < 50:
                            correction_signal = 5.0
                        else:
                            correction_signal = 2.0
                            
                    elif feedback.actual_return_t3 < -0.02:  # 大跌 (<-2%)
                        # 如果AI给了高分但市场大跌，说明该特征应该扣分
                        if feedback.ai_audit_score > 50:
                            correction_signal = -5.0
                        else:
                            correction_signal = -2.0
                    
                    # 根据市场状态调整修正信号
                    if feedback.market_regime == "Bull":
                        correction_signal *= 1.2  # 牛市中放大信号
                    elif feedback.market_regime == "Bear":
                        correction_signal *= 0.8  # 熊市中保守调整
                    
                    weight_deltas[feature] += correction_signal
        
        # 应用梯度更新
        update_log = []
        for feature, delta in weight_deltas.items():
            if feature_counts[feature] > 0:
                avg_delta = delta / feature_counts[feature]
                old_w = self.config.weights[feature]
                new_w = old_w + (avg_delta * self.config.learning_rate)
                
                # 限制权重范围 [-50, 50]
                new_w = max(-50.0, min(50.0, new_w))
                
                self.config.weights[feature] = round(new_w, 2)
                
                # 记录日志，用于 "红黑榜" 的深度分析
                if abs(new_w - old_w) > 0.1:  # 只记录有意义的变化
                    change_info = {
                        "feature": feature,
                        "old_weight": old_w,
                        "new_weight": new_w,
                        "delta": round(new_w - old_w, 2),
                        "sample_count": feature_counts[feature],
                        "timestamp": datetime.now().isoformat()
                    }
                    update_log.append(change_info)
                    logger.info(f"Weight updated: {feature} {old_w:.2f} -> {new_w:.2f} "
                              f"(Δ={new_w - old_w:.2f}, n={feature_counts[feature]})")
        
        self.config.update_history.append({
            "timestamp": datetime.now().isoformat(),
            "batch_size": len(batch_feedback),
            "updates": update_log
        })
        
        logger.info(f"Evolution completed: {len(update_log)} weights updated from {len(batch_feedback)} feedbacks")
    
    def generate_new_prompt_instruction(self) -> str:
        """
        Prompt 工程自动化：将数学参数转化为自然语言指令
        
        Returns:
            动态审计指令文本
        """
        instructions = ["### 动态审计指令 (基于 T+3 回测):"]
        w = self.config.weights
        
        # 标题党/夸大表达
        if w["hype_language"] > -5:
            instructions.append("- ⚠️ 市场处于情绪亢奋期：暂停对'夸大表达'的降权，将其视为动量因子。")
        elif w["hype_language"] < -30:
            instructions.append("- 🚫 高度警惕夸大表达：市场对标题党惩罚严厉，大幅降权。")
        
        # 政策强度
        if w["policy_demand"] > 20:
            instructions.append("- ✅ 强语态偏好：对于'要求/必须'类词汇，给予额外加权。")
        elif w["policy_demand"] < 5:
            instructions.append("- ⚠️ 政策疲劳：市场对政策类新闻反应钝化，降低权重。")
        
        # 不确定性
        if w["uncertainty"] > -15:
            instructions.append("- 📊 容忍不确定性：市场接受'可能/或将'等模糊表达，适度放宽。")
        elif w["uncertainty"] < -40:
            instructions.append("- ⛔ 零容忍不确定性：严格惩罚模糊表达，要求明确性。")
        
        # 逻辑严谨性
        if w["logical_rigor"] > 30:
            instructions.append("- 🎯 逻辑为王：市场高度奖励逻辑严密的分析，大幅加分。")
        
        # 数据支撑
        if w["data_support"] > 25:
            instructions.append("- 📈 数据驱动：有具体数据支撑的新闻获得显著加权。")
        
        instructions.append(f"\n**当前权重配置** (更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')})")
        instructions.append("```")
        for feature, weight in w.items():
            emoji = "📈" if weight > 0 else "📉"
            instructions.append(f"{emoji} {feature}: {weight:+.1f}")
        instructions.append("```")
        
        return "\n".join(instructions)
    
    def get_evolution_summary(self) -> Dict:
        """
        获取进化摘要信息
        
        Returns:
            包含权重、历史等信息的字典
        """
        return {
            "current_weights": self.config.weights.copy(),
            "learning_rate": self.config.learning_rate,
            "total_updates": len(self.config.update_history),
            "last_update": self.config.update_history[-1] if self.config.update_history else None
        }
    
    def save_to_database(self, db):
        """
        将权重更新保存到数据库
        
        Args:
            db: 数据库实例
        """
        if not self.config.update_history:
            logger.warning("No updates to save")
            return
        
        last_update = self.config.update_history[-1]
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            for update in last_update["updates"]:
                cursor.execute("""
                    INSERT INTO strategy_evolution_log 
                    (feature_name, old_weight, new_weight, trigger_reason, update_date)
                    VALUES (%s, %s, %s, %s, CURRENT_DATE)
                """, (
                    update["feature"],
                    update["old_weight"],
                    update["new_weight"],
                    f"Market feedback from {last_update['batch_size']} samples"
                ))
            
            conn.commit()
            logger.info(f"Saved {len(last_update['updates'])} weight updates to database")
    
    def load_from_database(self, db):
        """
        从数据库加载最新权重
        
        Args:
            db: 数据库实例
        """
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取每个特征的最新权重
            cursor.execute("""
                SELECT DISTINCT ON (feature_name) 
                    feature_name, new_weight
                FROM strategy_evolution_log
                ORDER BY feature_name, update_date DESC, log_id DESC
            """)
            
            rows = cursor.fetchall()
            
            if rows:
                for row in rows:
                    feature_name, new_weight = row
                    if feature_name in self.config.weights:
                        self.config.weights[feature_name] = float(new_weight)
                
                logger.info(f"Loaded {len(rows)} weights from database")
            else:
                logger.info("No historical weights found, using defaults")
