"""
NewsTrace 2.0 集成测试
测试各模块之间的协作
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategy_updater import StrategyUpdater, MarketFeedback, DynamicConfig


def test_integration_workflow():
    """测试完整工作流集成"""
    print("\n" + "="*60)
    print("集成测试: 完整权重进化工作流")
    print("="*60)
    
    # 步骤 1: 初始化策略更新器
    print("\n步骤 1: 初始化策略更新器")
    updater = StrategyUpdater()
    print(f"✓ 初始化完成,学习率: {updater.config.learning_rate}")
    
    # 步骤 2: 模拟 T+3 市场反馈数据
    print("\n步骤 2: 模拟 T+3 市场反馈数据")
    
    # 场景 1: 牛市中的混合表现
    feedbacks = [
        # 标题党新闻,AI 低分但市场涨
        MarketFeedback(
            news_id="NEWS001",
            ai_audit_score=35,
            detected_features=["hype_language"],
            actual_return_t3=0.04,
            market_regime="Bull"
        ),
        # 政策新闻,AI 高分且市场涨
        MarketFeedback(
            news_id="NEWS002",
            ai_audit_score=75,
            detected_features=["policy_demand", "logical_rigor"],
            actual_return_t3=0.06,
            market_regime="Bull"
        ),
        # 不确定性新闻,AI 低分且市场跌
        MarketFeedback(
            news_id="NEWS003",
            ai_audit_score=40,
            detected_features=["uncertainty"],
            actual_return_t3=-0.02,
            market_regime="Bull"
        ),
        # 数据支撑新闻,AI 高分且市场涨
        MarketFeedback(
            news_id="NEWS004",
            ai_audit_score=80,
            detected_features=["data_support", "logical_rigor"],
            actual_return_t3=0.05,
            market_regime="Bull"
        ),
    ]
    
    print(f"✓ 生成 {len(feedbacks)} 个市场反馈样本")
    for fb in feedbacks:
        print(f"  - {fb.news_id}: AI={fb.ai_audit_score}, "
              f"T+3={fb.actual_return_t3:+.2%}, "
              f"特征={fb.detected_features}")
    
    # 步骤 3: 记录初始权重
    print("\n步骤 3: 记录初始权重")
    initial_weights = updater.config.weights.copy()
    for feature, weight in initial_weights.items():
        print(f"  {feature}: {weight:+.1f}")
    
    # 步骤 4: 执行权重进化
    print("\n步骤 4: 执行权重进化")
    updater.evolve(feedbacks)
    print("✓ 进化完成")
    
    # 步骤 5: 分析权重变化
    print("\n步骤 5: 分析权重变化")
    new_weights = updater.config.weights
    
    changes = []
    for feature in initial_weights.keys():
        old_w = initial_weights[feature]
        new_w = new_weights[feature]
        delta = new_w - old_w
        
        if abs(delta) > 0.01:
            changes.append((feature, old_w, new_w, delta))
            direction = "↑" if delta > 0 else "↓"
            print(f"  {direction} {feature}: {old_w:+.1f} → {new_w:+.1f} (Δ{delta:+.1f})")
    
    assert len(changes) > 0, "应该有权重发生变化"
    print(f"\n✓ 共有 {len(changes)} 个特征权重发生变化")
    
    # 步骤 6: 生成新的 Prompt 指令
    print("\n步骤 6: 生成新的 Prompt 指令")
    new_instruction = updater.generate_new_prompt_instruction()
    print("✓ 动态指令生成成功")
    print("-" * 60)
    print(new_instruction[:300] + "...")
    print("-" * 60)
    
    # 步骤 7: 获取进化摘要
    print("\n步骤 7: 获取进化摘要")
    summary = updater.get_evolution_summary()
    print(f"✓ 总更新次数: {summary['total_updates']}")
    print(f"✓ 最后更新时间: {summary['last_update']['timestamp'][:19]}")
    print(f"✓ 本次更新样本数: {summary['last_update']['batch_size']}")
    
    # 验证
    assert summary['total_updates'] > 0
    assert summary['last_update']['batch_size'] == len(feedbacks)
    
    print("\n✅ 完整工作流集成测试通过!")
    
    return True


def test_multi_iteration_evolution():
    """测试多次迭代进化"""
    print("\n" + "="*60)
    print("集成测试: 多次迭代权重进化")
    print("="*60)
    
    updater = StrategyUpdater()
    
    print(f"\n初始 hype_language 权重: {updater.config.weights['hype_language']:+.1f}")
    
    # 模拟 3 天的进化
    for day in range(1, 4):
        print(f"\n--- 第 {day} 天 ---")
        
        # 每天 5 个样本
        feedbacks = [
            MarketFeedback(
                news_id=f"DAY{day}_NEWS{i}",
                ai_audit_score=30 + i * 5,
                detected_features=["hype_language"],
                actual_return_t3=0.03 + i * 0.01,
                market_regime="Bull"
            )
            for i in range(5)
        ]
        
        updater.evolve(feedbacks)
        
        current_weight = updater.config.weights['hype_language']
        print(f"进化后 hype_language 权重: {current_weight:+.1f}")
    
    final_weight = updater.config.weights['hype_language']
    initial_weight = -20.0
    total_change = final_weight - initial_weight
    
    print(f"\n总权重变化: {initial_weight:+.1f} → {final_weight:+.1f} (Δ{total_change:+.1f})")
    print(f"总更新次数: {updater.get_evolution_summary()['total_updates']}")
    
    assert updater.get_evolution_summary()['total_updates'] == 3
    
    print("\n✅ 多次迭代进化测试通过!")
    
    return True


def test_mixed_market_regimes():
    """测试混合市场状态"""
    print("\n" + "="*60)
    print("集成测试: 混合市场状态下的权重调整")
    print("="*60)
    
    updater = StrategyUpdater()
    
    # 混合牛市和熊市样本
    feedbacks = [
        # 牛市样本
        MarketFeedback(
            news_id="BULL1",
            ai_audit_score=40,
            detected_features=["hype_language"],
            actual_return_t3=0.05,
            market_regime="Bull"
        ),
        MarketFeedback(
            news_id="BULL2",
            ai_audit_score=35,
            detected_features=["hype_language"],
            actual_return_t3=0.04,
            market_regime="Bull"
        ),
        # 熊市样本
        MarketFeedback(
            news_id="BEAR1",
            ai_audit_score=40,
            detected_features=["hype_language"],
            actual_return_t3=-0.03,
            market_regime="Bear"
        ),
        MarketFeedback(
            news_id="BEAR2",
            ai_audit_score=35,
            detected_features=["hype_language"],
            actual_return_t3=-0.04,
            market_regime="Bear"
        ),
    ]
    
    print(f"\n样本分布:")
    print(f"  牛市样本: 2 个 (标题党大涨)")
    print(f"  熊市样本: 2 个 (标题党大跌)")
    
    initial_weight = updater.config.weights['hype_language']
    print(f"\n初始权重: {initial_weight:+.1f}")
    
    updater.evolve(feedbacks)
    
    final_weight = updater.config.weights['hype_language']
    print(f"进化后权重: {final_weight:+.1f}")
    
    # 混合市场下,权重变化应该相互抵消,变化较小
    delta = abs(final_weight - initial_weight)
    print(f"权重变化幅度: {delta:.1f}")
    
    assert delta < 2.0, "混合市场下权重变化应该较小"
    
    print("\n✅ 混合市场状态测试通过!")
    
    return True


def main():
    """运行所有集成测试"""
    print("\n" + "="*60)
    print("NewsTrace 2.0 集成测试")
    print("="*60)
    
    tests = [
        ("完整权重进化工作流", test_integration_workflow),
        ("多次迭代权重进化", test_multi_iteration_evolution),
        ("混合市场状态权重调整", test_mixed_market_regimes),
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
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print("集成测试总结")
    print("="*60)
    print(f"总计: {len(tests)} 个测试")
    print(f"✅ 通过: {passed} 个")
    print(f"❌ 失败: {failed} 个")
    
    if failed == 0:
        print("\n🎉 所有集成测试通过!")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
