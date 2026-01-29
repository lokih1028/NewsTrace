"""
NewsTrace 2.0 核心功能验证脚本
不依赖 pytest,直接运行测试
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategy_updater import StrategyUpdater, MarketFeedback, DynamicConfig


def test_strategy_updater():
    """测试策略更新器"""
    print("\n" + "="*60)
    print("测试 1: 策略更新器基础功能")
    print("="*60)
    
    updater = StrategyUpdater()
    
    # 测试初始权重
    print(f"\n✓ 初始权重配置:")
    for feature, weight in updater.config.weights.items():
        print(f"  {feature}: {weight:+.1f}")
    
    # 测试奖励计算
    print(f"\n✓ 测试奖励计算:")
    
    # 正向情况: AI 给高分,市场也涨
    feedback_positive = MarketFeedback(
        news_id="test001",
        ai_audit_score=80,
        detected_features=["policy_demand"],
        actual_return_t3=0.05,
        market_regime="Bull"
    )
    reward_positive = updater.calculate_reward(feedback_positive)
    print(f"  正向情况 (AI:80, 市场:+5%): 奖励 = {reward_positive:+.2f}")
    assert reward_positive > 0, "正向情况应该获得正奖励"
    
    # 负向情况: AI 给高分,市场跌
    feedback_negative = MarketFeedback(
        news_id="test002",
        ai_audit_score=80,
        detected_features=["hype_language"],
        actual_return_t3=-0.05,
        market_regime="Bear"
    )
    reward_negative = updater.calculate_reward(feedback_negative)
    print(f"  负向情况 (AI:80, 市场:-5%): 奖励 = {reward_negative:+.2f}")
    assert reward_negative < 0, "负向情况应该获得负奖励"
    
    print("\n✅ 奖励计算测试通过!")
    
    return True


def test_evolution_bull_market():
    """测试牛市进化"""
    print("\n" + "="*60)
    print("测试 2: 牛市场景权重进化")
    print("="*60)
    
    updater = StrategyUpdater()
    
    initial_hype_weight = updater.config.weights["hype_language"]
    print(f"\n初始 hype_language 权重: {initial_hype_weight:+.1f}")
    
    # 模拟牛市中"标题党"新闻大涨
    feedbacks = [
        MarketFeedback(
            news_id=f"test{i}",
            ai_audit_score=30,  # AI 给了低分(因为是标题党)
            detected_features=["hype_language"],
            actual_return_t3=0.05,  # 但市场大涨
            market_regime="Bull"
        )
        for i in range(10)
    ]
    
    print(f"模拟 {len(feedbacks)} 个样本: AI低分但市场大涨")
    
    updater.evolve(feedbacks)
    
    new_hype_weight = updater.config.weights["hype_language"]
    delta = new_hype_weight - initial_hype_weight
    
    print(f"进化后 hype_language 权重: {new_hype_weight:+.1f}")
    print(f"权重变化: {delta:+.1f}")
    
    assert new_hype_weight > initial_hype_weight, \
        "牛市中标题党有效,权重应该上升"
    
    print("\n✅ 牛市进化测试通过!")
    
    return True


def test_evolution_bear_market():
    """测试熊市进化"""
    print("\n" + "="*60)
    print("测试 3: 熊市场景权重进化")
    print("="*60)
    
    updater = StrategyUpdater()
    
    initial_hype_weight = updater.config.weights["hype_language"]
    print(f"\n初始 hype_language 权重: {initial_hype_weight:+.1f}")
    
    # 模拟熊市中"标题党"新闻大跌
    feedbacks = [
        MarketFeedback(
            news_id=f"test{i}",
            ai_audit_score=30,  # AI 给了低分
            detected_features=["hype_language"],
            actual_return_t3=-0.05,  # 市场也大跌
            market_regime="Bear"
        )
        for i in range(10)
    ]
    
    print(f"模拟 {len(feedbacks)} 个样本: AI低分且市场大跌")
    
    updater.evolve(feedbacks)
    
    new_hype_weight = updater.config.weights["hype_language"]
    delta = new_hype_weight - initial_hype_weight
    
    print(f"进化后 hype_language 权重: {new_hype_weight:+.1f}")
    print(f"权重变化: {delta:+.1f}")
    
    # 熊市中 AI 判断正确,权重变化应该较小
    assert abs(delta) < 5, "熊市中 AI 判断正确,权重变化应该较小"
    
    print("\n✅ 熊市进化测试通过!")
    
    return True


def test_prompt_generation():
    """测试动态 Prompt 生成"""
    print("\n" + "="*60)
    print("测试 4: 动态 Prompt 生成")
    print("="*60)
    
    updater = StrategyUpdater()
    
    # 修改权重配置
    updater.config.weights["hype_language"] = 5.0  # 从负变正
    updater.config.weights["policy_demand"] = 25.0  # 超过阈值
    
    instruction = updater.generate_new_prompt_instruction()
    
    print(f"\n生成的动态指令:")
    print("-" * 60)
    print(instruction)
    print("-" * 60)
    
    assert "动态审计指令" in instruction
    assert len(instruction) > 100, "指令应该包含足够的内容"
    
    print("\n✅ Prompt 生成测试通过!")
    
    return True


def test_weight_bounds():
    """测试权重边界"""
    print("\n" + "="*60)
    print("测试 5: 权重边界限制")
    print("="*60)
    
    updater = StrategyUpdater()
    
    # 模拟极端情况
    extreme_feedbacks = [
        MarketFeedback(
            news_id=f"test{i}",
            ai_audit_score=10,
            detected_features=["hype_language"],
            actual_return_t3=0.10,  # 极端大涨
            market_regime="Bull"
        )
        for i in range(50)
    ]
    
    print(f"\n模拟 {len(extreme_feedbacks)} 个极端样本")
    
    updater.evolve(extreme_feedbacks)
    
    print(f"\n进化后权重:")
    for feature, weight in updater.config.weights.items():
        print(f"  {feature}: {weight:+.1f}")
        assert -50 <= weight <= 50, f"权重 {weight} 超出范围 [-50, 50]"
    
    print("\n✅ 权重边界测试通过!")
    
    return True


def test_evolution_summary():
    """测试进化摘要"""
    print("\n" + "="*60)
    print("测试 6: 进化摘要功能")
    print("="*60)
    
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
    
    print(f"\n进化摘要:")
    print(f"  当前权重数量: {len(summary['current_weights'])}")
    print(f"  总更新次数: {summary['total_updates']}")
    print(f"  学习率: {summary['learning_rate']}")
    
    assert "current_weights" in summary
    assert "total_updates" in summary
    assert summary["total_updates"] > 0
    
    print("\n✅ 进化摘要测试通过!")
    
    return True


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("NewsTrace 2.0 核心功能验证")
    print("="*60)
    
    tests = [
        ("策略更新器基础功能", test_strategy_updater),
        ("牛市场景权重进化", test_evolution_bull_market),
        ("熊市场景权重进化", test_evolution_bear_market),
        ("动态 Prompt 生成", test_prompt_generation),
        ("权重边界限制", test_weight_bounds),
        ("进化摘要功能", test_evolution_summary),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"\n❌ 测试失败: {name}")
            print(f"   错误: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ 测试异常: {name}")
            print(f"   错误: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"总计: {len(tests)} 个测试")
    print(f"✅ 通过: {passed} 个")
    print(f"❌ 失败: {failed} 个")
    
    if failed == 0:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
