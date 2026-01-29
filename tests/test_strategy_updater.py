"""
测试策略更新器
"""
import pytest
from src.strategy_updater import StrategyUpdater, MarketFeedback, DynamicConfig


class TestStrategyUpdater:
    """测试策略更新器"""
    
    def test_calculate_reward_positive(self):
        """测试奖励计算 - 正向情况"""
        updater = StrategyUpdater()
        
        # AI 给了高分(80),市场也涨了(+5%)
        feedback = MarketFeedback(
            news_id="test001",
            ai_audit_score=80,
            detected_features=["policy_demand"],
            actual_return_t3=0.05,
            market_regime="Bull"
        )
        
        reward = updater.calculate_reward(feedback)
        
        # (80-50)/50 * 0.05 * 100 = 0.6 * 5 = 3.0
        assert reward > 0, "AI判断正确应该获得正奖励"
    
    def test_calculate_reward_negative(self):
        """测试奖励计算 - 负向情况"""
        updater = StrategyUpdater()
        
        # AI 给了高分(80),但市场跌了(-5%)
        feedback = MarketFeedback(
            news_id="test002",
            ai_audit_score=80,
            detected_features=["hype_language"],
            actual_return_t3=-0.05,
            market_regime="Bear"
        )
        
        reward = updater.calculate_reward(feedback)
        
        # (80-50)/50 * (-0.05) * 100 = 0.6 * (-5) = -3.0
        assert reward < 0, "AI误判应该获得负奖励"
    
    def test_evolve_bull_market(self):
        """测试进化 - 牛市场景"""
        updater = StrategyUpdater()
        
        # 记录初始权重
        initial_hype_weight = updater.config.weights["hype_language"]
        
        # 模拟牛市中"标题党"新闻大涨的情况
        feedbacks = [
            MarketFeedback(
                news_id=f"test{i}",
                ai_audit_score=30,  # AI给了低分(因为是标题党)
                detected_features=["hype_language"],
                actual_return_t3=0.05,  # 但市场大涨
                market_regime="Bull"
            )
            for i in range(10)
        ]
        
        # 执行进化
        updater.evolve(feedbacks)
        
        # 验证: hype_language 的惩罚应该减少(权重上升)
        new_hype_weight = updater.config.weights["hype_language"]
        assert new_hype_weight > initial_hype_weight, \
            "牛市中标题党有效,权重应该上升"
    
    def test_evolve_bear_market(self):
        """测试进化 - 熊市场景"""
        updater = StrategyUpdater()
        
        initial_hype_weight = updater.config.weights["hype_language"]
        
        # 模拟熊市中"标题党"新闻大跌的情况
        feedbacks = [
            MarketFeedback(
                news_id=f"test{i}",
                ai_audit_score=30,  # AI给了低分
                detected_features=["hype_language"],
                actual_return_t3=-0.05,  # 市场也大跌
                market_regime="Bear"
            )
            for i in range(10)
        ]
        
        updater.evolve(feedbacks)
        
        # 验证: hype_language 的惩罚应该保持或增加
        new_hype_weight = updater.config.weights["hype_language"]
        # 在熊市中,AI判断正确,权重变化应该较小或更负
        assert new_hype_weight <= initial_hype_weight + 1, \
            "熊市中标题党无效,权重不应大幅上升"
    
    def test_generate_prompt_instruction(self):
        """测试动态 Prompt 生成"""
        updater = StrategyUpdater()
        
        # 修改权重配置
        updater.config.weights["hype_language"] = 5.0  # 从负变正
        updater.config.weights["policy_demand"] = 25.0  # 超过阈值
        
        instruction = updater.generate_new_prompt_instruction()
        
        # 验证指令包含预期内容
        assert "动态审计指令" in instruction
        assert "市场处于情绪亢奋期" in instruction or "暂停对'夸大表达'的降权" in instruction
        assert "强语态偏好" in instruction
    
    def test_weight_bounds(self):
        """测试权重边界限制"""
        updater = StrategyUpdater()
        
        # 模拟极端情况,尝试让权重超出范围
        extreme_feedbacks = [
            MarketFeedback(
                news_id=f"test{i}",
                ai_audit_score=10,
                detected_features=["hype_language"],
                actual_return_t3=0.10,  # 极端大涨
                market_regime="Bull"
            )
            for i in range(100)  # 大量样本
        ]
        
        updater.evolve(extreme_feedbacks)
        
        # 验证权重在合理范围内
        for weight in updater.config.weights.values():
            assert -50 <= weight <= 50, f"权重 {weight} 超出范围 [-50, 50]"
    
    def test_evolution_summary(self):
        """测试进化摘要"""
        updater = StrategyUpdater()
        
        feedbacks = [
            MarketFeedback(
                news_id="test001",
                ai_audit_score=70,
                detected_features=["policy_demand"],
                actual_return_t3=0.03,
                market_regime="Bull"
            )
        ]
        
        updater.evolve(feedbacks)
        
        summary = updater.get_evolution_summary()
        
        assert "current_weights" in summary
        assert "total_updates" in summary
        assert summary["total_updates"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
