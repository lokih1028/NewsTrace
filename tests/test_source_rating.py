"""
信源评级测试
"""
import pytest
from src.source_rating import SourceRating


class TestSourceRating:
    """信源评级测试类"""
    
    def test_calculate_composite_score(self):
        """测试综合评分计算"""
        # 创建一个模拟的数据库对象
        class MockDB:
            pass
        
        rating = SourceRating(MockDB())
        
        metrics = {
            'avg_return': 5.0,
            'rumor_rate': 0.1,
            'avg_logic_score': 80.0,
            'accuracy': 0.7
        }
        
        score = rating._calculate_composite_score(metrics)
        
        # 验证评分在合理范围内
        assert 0 <= score <= 100
        assert score > 50  # 这些指标应该得到较高分数
    
    def test_determine_grade(self):
        """测试评级确定"""
        class MockDB:
            pass
        
        rating = SourceRating(MockDB())
        
        assert rating._determine_grade(85) == 'A'
        assert rating._determine_grade(70) == 'B'
        assert rating._determine_grade(55) == 'C'
        assert rating._determine_grade(40) == 'D'
    
    def test_generate_recommendation(self):
        """测试建议生成"""
        class MockDB:
            pass
        
        rating = SourceRating(MockDB())
        
        # A级信源
        rec_a = rating._generate_recommendation('A', 0.1)
        assert '高可信度' in rec_a
        
        # B级信源
        rec_b = rating._generate_recommendation('B', 0.2)
        assert '可信度较高' in rec_b
        
        # C级信源 - 高辟谣率
        rec_c_high = rating._generate_recommendation('C', 0.35)
        assert '辟谣率偏高' in rec_c_high
        
        # C级信源 - 低辟谣率
        rec_c_low = rating._generate_recommendation('C', 0.2)
        assert '交叉验证' in rec_c_low
        
        # D级信源
        rec_d = rating._generate_recommendation('D', 0.4)
        assert '建议过滤' in rec_d
