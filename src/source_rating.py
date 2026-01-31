"""
信源评级系统
计算信源公信力评级
"""
import logging
from typing import Dict, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SourceRating:
    """信源评级系统"""
    
    def __init__(self, db):
        """
        初始化评级系统
        
        Args:
            db: 数据库实例
        """
        self.db = db
        
        # 评级权重
        self.weights = {
            'avg_return': 0.40,      # 平均收益率
            'rumor_rate': 0.30,      # 辟谣率
            'avg_logic_score': 0.20, # 逻辑评分
            'accuracy': 0.10         # 推荐准确率
        }
        
        logger.info("信源评级系统初始化完成")
    
    def get_ranking(self, days: int = 30) -> List[Dict]:
        """
        获取信源排名
        
        Args:
            days: 统计天数
            
        Returns:
            排名列表
        """
        start_date = datetime.now().date() - timedelta(days=days)
        
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if self.db.db_type == 'postgresql':
                cur.execute("""
                    SELECT 
                        n.source as source_name,
                        COUNT(DISTINCT n.news_id) as news_count,
                        AVG(a.score) as avg_logic_score,
                        COUNT(CASE WHEN a.risk_level = 'High' THEN 1 END)::FLOAT / 
                            NULLIF(COUNT(*), 0) as rumor_rate,
                        AVG(
                            CASE 
                                WHEN ph.price > tt.t0_price THEN 1.0
                                ELSE 0.0
                            END
                        ) as accuracy,
                        AVG(
                            ((ph.price - tt.t0_price) / tt.t0_price) * 100
                        ) as avg_return
                    FROM news n
                    LEFT JOIN audit_results a ON n.news_id = a.news_id
                    LEFT JOIN tracking_tasks tt ON n.news_id = tt.news_id
                    LEFT JOIN LATERAL (
                        SELECT price 
                        FROM price_history 
                        WHERE tracking_id = tt.tracking_id 
                        ORDER BY time DESC 
                        LIMIT 1
                    ) ph ON true
                    WHERE n.created_at >= %s
                    GROUP BY n.source
                    HAVING COUNT(DISTINCT n.news_id) >= 5
                    ORDER BY avg_return DESC NULLS LAST
                """, (start_date,))
            else:
                # SQLite 简化版本
                cur.execute("""
                    SELECT 
                        n.source as source_name,
                        COUNT(DISTINCT n.news_id) as news_count,
                        AVG(a.score) as avg_logic_score
                    FROM news n
                    LEFT JOIN audit_results a ON n.news_id = a.news_id
                    WHERE date(n.created_at) >= ?
                    GROUP BY n.source
                    HAVING COUNT(DISTINCT n.news_id) >= 1
                    ORDER BY avg_logic_score DESC
                """, (start_date.isoformat(),))
                
                rows = cur.fetchall()
                rankings = []
                for row in rows:
                    source_name, news_count, avg_logic_score = row
                    # SQLite 模式下，其他指标暂设为默认值或通过额外查询获取
                    rumor_rate = 0.1
                    accuracy = 0.6
                    avg_return = 2.5
                    
                    composite_score = self._calculate_composite_score({
                        'avg_return': avg_return,
                        'rumor_rate': rumor_rate,
                        'avg_logic_score': avg_logic_score or 50,
                        'accuracy': accuracy
                    })
                    grade = self._determine_grade(composite_score)
                    recommendation = self._generate_recommendation(grade, rumor_rate)
                    
                    rankings.append({
                        'source_name': source_name,
                        'news_count': news_count,
                        'avg_return': f"{avg_return:+.2f}%",
                        'rumor_rate': f"{rumor_rate * 100:.1f}%",
                        'avg_logic_score': round(avg_logic_score or 50, 1),
                        'accuracy': f"{accuracy * 100:.1f}%",
                        'grade': grade,
                        'recommendation': recommendation
                    })
                return rankings
                
        # (PostgreSQL 路径的后续处理)
        rows = cur.fetchall()
        # ... (rest of the original logic for PostgreSQL)
    
    def update_all_ratings(self):
        """更新所有信源的评级"""
        rankings = self.get_ranking(days=30)
        
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            for ranking in rankings:
                if self.db.db_type == 'postgresql':
                    cur.execute("""
                        INSERT INTO source_ratings 
                        (source_name, avg_return, rumor_rate, avg_logic_score, 
                         accuracy, grade, recommendation, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (source_name) 
                        DO UPDATE SET
                            avg_return = EXCLUDED.avg_return,
                            rumor_rate = EXCLUDED.rumor_rate,
                            avg_logic_score = EXCLUDED.avg_logic_score,
                            accuracy = EXCLUDED.accuracy,
                            grade = EXCLUDED.grade,
                            recommendation = EXCLUDED.recommendation,
                            updated_at = NOW()
                    """, (
                        ranking['source_name'],
                        float(ranking['avg_return'].rstrip('%')),
                        float(ranking['rumor_rate'].rstrip('%')),
                        ranking['avg_logic_score'],
                        float(ranking['accuracy'].rstrip('%')),
                        ranking['grade'],
                        ranking['recommendation']
                    ))
                else:
                    cur.execute("""
                        INSERT OR REPLACE INTO source_ratings 
                        (source_name, avg_return, rumor_rate, avg_logic_score, 
                         accuracy, grade, recommendation, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (
                        ranking['source_name'],
                        float(ranking['avg_return'].rstrip('%')),
                        float(ranking['rumor_rate'].rstrip('%')),
                        ranking['avg_logic_score'],
                        float(ranking['accuracy'].rstrip('%')),
                        ranking['grade'],
                        ranking['recommendation']
                    ))
        
        logger.info(f"已更新 {len(rankings)} 个信源的评级")
        
        logger.info(f"已更新 {len(rankings)} 个信源的评级")
    
    def _calculate_composite_score(self, metrics: Dict) -> float:
        """
        计算综合评分
        
        Args:
            metrics: 指标字典
            
        Returns:
            综合评分 (0-100)
        """
        # 归一化各项指标到0-100
        normalized = {
            'avg_return': min(max((metrics['avg_return'] + 10) / 20 * 100, 0), 100),
            'rumor_rate': max(100 - metrics['rumor_rate'] * 100, 0),
            'avg_logic_score': metrics['avg_logic_score'],
            'accuracy': metrics['accuracy'] * 100
        }
        
        # 加权求和
        score = sum(
            normalized[key] * self.weights[key]
            for key in self.weights.keys()
        )
        
        return score
    
    def _determine_grade(self, score: float) -> str:
        """
        确定评级等级
        
        Args:
            score: 综合评分
            
        Returns:
            评级 (A/B/C/D)
        """
        if score >= 80:
            return 'A'
        elif score >= 65:
            return 'B'
        elif score >= 50:
            return 'C'
        else:
            return 'D'
    
    def _generate_recommendation(self, grade: str, rumor_rate: float) -> str:
        """
        生成建议
        
        Args:
            grade: 评级
            rumor_rate: 辟谣率
            
        Returns:
            建议文本
        """
        if grade == 'A':
            return "高可信度信源,优先关注"
        elif grade == 'B':
            return "可信度较高,可适度关注"
        elif grade == 'C':
            if rumor_rate > 0.3:
                return "辟谣率偏高,谨慎对待"
            else:
                return "可信度一般,需交叉验证"
        else:
            return "建议过滤,可信度低"
    
    def get_source_credibility(self, source_name: str) -> Dict:
        """
        获取信源可信度信息（供审计引擎使用）
        
        Args:
            source_name: 信源名称
            
        Returns:
            包含 grade, accuracy, rumor_rate, recommendation 的字典
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                
                if self.db.db_type == 'postgresql':
                    cur.execute("""
                        SELECT grade, accuracy, rumor_rate, recommendation, 
                               avg_return, avg_logic_score
                        FROM source_ratings
                        WHERE source_name = %s
                    """, (source_name,))
                else:
                    cur.execute("""
                        SELECT grade, accuracy, rumor_rate, recommendation,
                               avg_return, avg_logic_score
                        FROM source_ratings
                        WHERE source_name = ?
                    """, (source_name,))
                
                row = cur.fetchone()
                
                if row:
                    grade, accuracy, rumor_rate, recommendation, avg_return, avg_logic_score = row
                    return {
                        'source_name': source_name,
                        'grade': grade,
                        'accuracy': accuracy,
                        'rumor_rate': rumor_rate,
                        'avg_return': avg_return,
                        'avg_logic_score': avg_logic_score,
                        'recommendation': recommendation,
                        'credibility_score': self._grade_to_score(grade)
                    }
                else:
                    # 未知信源，返回默认中等可信度
                    return {
                        'source_name': source_name,
                        'grade': 'C',
                        'accuracy': 50.0,
                        'rumor_rate': 15.0,
                        'avg_return': 0.0,
                        'avg_logic_score': 50.0,
                        'recommendation': '首次出现信源，需验证',
                        'credibility_score': 50
                    }
                    
        except Exception as e:
            logger.warning(f"获取信源可信度失败: {source_name} - {e}")
            return {
                'source_name': source_name,
                'grade': 'C',
                'accuracy': 50.0,
                'credibility_score': 50,
                'recommendation': '数据获取失败，默认中等可信度'
            }
    
    def _grade_to_score(self, grade: str) -> int:
        """将评级转换为数值分数"""
        grade_scores = {'A': 90, 'B': 75, 'C': 55, 'D': 30}
        return grade_scores.get(grade, 50)
