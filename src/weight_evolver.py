"""
权重进化器 (Weight Evolver)
实现审计权重的自动化进化

触发条件（混合方案）:
1. T+3完成新闻数 >= min_samples AND 准确率 < accuracy_threshold
2. 或 每周日02:00 强制执行
"""
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class WeightEvolver:
    """审计权重进化器"""
    
    def __init__(self, db, config: Dict):
        """
        初始化权重进化器
        
        Args:
            db: 数据库实例
            config: 进化配置
        """
        self.db = db
        self.config = config.get('weight_evolution', {})
        
        # 进化参数
        self.min_samples = self.config.get('min_samples', 30)
        self.accuracy_threshold = self.config.get('accuracy_threshold', 0.55)
        self.max_weight_change = self.config.get('max_weight_change', 0.15)
        self.decay_factor = self.config.get('decay_factor', 0.9)
        self.enabled = self.config.get('enabled', True)
        
        # 默认权重
        self.default_weights = {
            'hype_language': -0.3,      # 夸大语言惩罚
            'policy_demand': 0.15,       # 政策需求奖励
            'logical_rigor': 0.25,       # 逻辑严密奖励
            'data_support': 0.2,         # 数据支撑奖励
            'uncertainty': -0.15,        # 不确定性惩罚
            'source_credibility': 0.15   # 信源可信度奖励
        }
        
        logger.info(f"权重进化器初始化完成: min_samples={self.min_samples}, "
                   f"accuracy_threshold={self.accuracy_threshold}")
    
    def should_evolve(self) -> tuple:
        """
        检查是否应该触发进化
        
        Returns:
            (should_evolve: bool, reason: str)
        """
        if not self.enabled:
            return False, "权重进化已禁用"
        
        # 获取待进化样本
        samples = self._get_evolution_samples()
        sample_count = len(samples)
        
        if sample_count < self.min_samples:
            return False, f"样本不足: {sample_count}/{self.min_samples}"
        
        # 计算当前准确率
        current_accuracy = self._calculate_accuracy(samples)
        
        if current_accuracy < self.accuracy_threshold:
            return True, f"准确率低于阈值: {current_accuracy:.2%} < {self.accuracy_threshold:.0%}"
        
        # 检查是否周日凌晨（保底机制）
        now = datetime.now()
        if now.weekday() == 6 and now.hour == 2:  # 周日02点
            return True, "周日定时进化"
        
        return False, f"无需进化: 准确率={current_accuracy:.2%}, 样本={sample_count}"
    
    def evolve(self, current_weights: Dict = None) -> Dict:
        """
        执行权重进化
        
        Args:
            current_weights: 当前权重（可选）
            
        Returns:
            进化后的新权重
        """
        if current_weights is None:
            current_weights = self._load_current_weights()
        
        # 获取进化样本
        samples = self._get_evolution_samples()
        
        if len(samples) < self.min_samples:
            logger.warning(f"样本不足，跳过进化: {len(samples)}/{self.min_samples}")
            return current_weights
        
        # 分析特征与收益的相关性
        feature_performance = self._analyze_feature_performance(samples)
        
        # 计算新权重
        new_weights = {}
        for feature, old_weight in current_weights.items():
            if feature in feature_performance:
                perf = feature_performance[feature]
                
                # 计算调整量（正相关增加权重，负相关减少）
                adjustment = perf['correlation'] * self.max_weight_change
                
                # 应用衰减因子，避免过度调整
                new_weight = old_weight * self.decay_factor + adjustment
                
                # 限制权重范围
                new_weight = max(-0.5, min(0.5, new_weight))
                new_weights[feature] = round(new_weight, 4)
            else:
                new_weights[feature] = old_weight
        
        # 保存新权重
        self._save_weights(new_weights)
        
        # 记录进化日志
        self._log_evolution(current_weights, new_weights, len(samples))
        
        # 标记样本为已使用
        self._mark_samples_evolved(samples)
        
        logger.info(f"权重进化完成: 样本数={len(samples)}")
        return new_weights
    
    def _get_evolution_samples(self) -> List[Dict]:
        """获取待进化的样本（T+3已完成且未用于进化的记录）"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                if self.db.db_type == 'postgresql':
                    cursor.execute("""
                        SELECT 
                            mt.news_id,
                            mt.ticker,
                            mt.price_t0,
                            mt.price_t3,
                            n.ai_audit_result,
                            mt.market_regime
                        FROM market_tracking mt
                        JOIN news n ON mt.news_id = n.news_id
                        WHERE mt.t3_timestamp IS NOT NULL
                        AND mt.price_t3 IS NOT NULL
                        AND (mt.evolved IS NULL OR mt.evolved = false)
                        ORDER BY mt.t3_timestamp DESC
                        LIMIT 200
                    """)
                else:
                    cursor.execute("""
                        SELECT 
                            mt.news_id,
                            mt.ticker,
                            mt.price_t0,
                            mt.price_t3,
                            n.ai_audit_result,
                            mt.market_regime
                        FROM market_tracking mt
                        JOIN news n ON mt.news_id = n.news_id
                        WHERE mt.t3_timestamp IS NOT NULL
                        AND mt.price_t3 IS NOT NULL
                        LIMIT 200
                    """)
                
                rows = cursor.fetchall()
                
                samples = []
                for row in rows:
                    news_id, ticker, t0, t3, audit_result, regime = row
                    
                    if t0 and t3 and audit_result:
                        t3_return = (t3 - t0) / t0
                        
                        # 解析审计结果
                        if isinstance(audit_result, str):
                            audit_result = json.loads(audit_result)
                        
                        samples.append({
                            'news_id': news_id,
                            'ticker': ticker,
                            'ai_score': audit_result.get('score', 50),
                            'detected_features': audit_result.get('detected_features', []),
                            'actual_return_t3': t3_return,
                            'market_regime': regime
                        })
                
                return samples
                
        except Exception as e:
            logger.error(f"获取进化样本失败: {e}")
            return []
    
    def _calculate_accuracy(self, samples: List[Dict]) -> float:
        """计算预测准确率"""
        if not samples:
            return 0.5
        
        correct = 0
        for sample in samples:
            # AI评分>60预测上涨，<=60预测下跌/横盘
            predicted_up = sample['ai_score'] > 60
            actual_up = sample['actual_return_t3'] > 0.01
            
            if predicted_up == actual_up:
                correct += 1
        
        return correct / len(samples)
    
    def _analyze_feature_performance(self, samples: List[Dict]) -> Dict:
        """分析特征与收益的相关性"""
        feature_returns = {}
        
        for sample in samples:
            for feature in sample['detected_features']:
                if feature not in feature_returns:
                    feature_returns[feature] = []
                feature_returns[feature].append(sample['actual_return_t3'])
        
        # 计算每个特征的平均收益和相关性
        performance = {}
        for feature, returns in feature_returns.items():
            if len(returns) >= 5:  # 至少5个样本
                avg_return = sum(returns) / len(returns)
                # 简化相关性：正收益特征正相关，负收益负相关
                correlation = 1.0 if avg_return > 0.02 else (-1.0 if avg_return < -0.02 else 0)
                
                performance[feature] = {
                    'avg_return': avg_return,
                    'sample_count': len(returns),
                    'correlation': correlation
                }
        
        return performance
    
    def _load_current_weights(self) -> Dict:
        """加载当前权重"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                if self.db.db_type == 'postgresql':
                    cursor.execute("""
                        SELECT weights FROM weight_evolution_log
                        ORDER BY evolved_at DESC LIMIT 1
                    """)
                else:
                    cursor.execute("""
                        SELECT weights FROM weight_evolution_log
                        ORDER BY evolved_at DESC LIMIT 1
                    """)
                
                row = cursor.fetchone()
                if row:
                    weights = row[0]
                    if isinstance(weights, str):
                        return json.loads(weights)
                    return weights
                    
        except Exception as e:
            logger.debug(f"加载权重失败，使用默认值: {e}")
        
        return self.default_weights.copy()
    
    def _save_weights(self, weights: Dict):
        """保存新权重到数据库"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                weights_json = json.dumps(weights)
                
                if self.db.db_type == 'postgresql':
                    cursor.execute("""
                        INSERT INTO weight_evolution_log (weights, evolved_at)
                        VALUES (%s, NOW())
                    """, (weights_json,))
                else:
                    cursor.execute("""
                        INSERT INTO weight_evolution_log (weights, evolved_at)
                        VALUES (?, datetime('now'))
                    """, (weights_json,))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"保存权重失败: {e}")
    
    def _log_evolution(self, old_weights: Dict, new_weights: Dict, sample_count: int):
        """记录进化日志"""
        changes = []
        for key in new_weights:
            old_val = old_weights.get(key, 0)
            new_val = new_weights[key]
            if abs(new_val - old_val) > 0.001:
                changes.append(f"{key}: {old_val:.3f} → {new_val:.3f}")
        
        if changes:
            logger.info(f"权重进化详情 (样本={sample_count}):\n" + "\n".join(changes))
        else:
            logger.info(f"权重无变化 (样本={sample_count})")
    
    def _mark_samples_evolved(self, samples: List[Dict]):
        """标记样本为已用于进化"""
        try:
            news_ids = [s['news_id'] for s in samples]
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                if self.db.db_type == 'postgresql':
                    cursor.execute("""
                        UPDATE market_tracking 
                        SET evolved = true
                        WHERE news_id = ANY(%s)
                    """, (news_ids,))
                else:
                    # SQLite 需要逐个更新或使用 IN 子句
                    placeholders = ','.join('?' * len(news_ids))
                    cursor.execute(f"""
                        UPDATE market_tracking 
                        SET evolved = 1
                        WHERE news_id IN ({placeholders})
                    """, news_ids)
                
                conn.commit()
                
        except Exception as e:
            logger.debug(f"标记样本失败（可忽略）: {e}")
    
    def get_current_weights(self) -> Dict:
        """获取当前权重（供外部调用）"""
        return self._load_current_weights()
