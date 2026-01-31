#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NewsTrace GitHub Actions 运行入口
零成本部署专用脚本
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def setup_environment():
    """配置运行环境"""
    # 确保数据目录存在
    Path("data").mkdir(exist_ok=True)
    Path("data/reports").mkdir(exist_ok=True)
    
    # 设置数据库路径 (SQLite)
    os.environ.setdefault("DATABASE_URL", "sqlite:///data/newstrace.db")
    
    # 检测 LLM 配置
    if os.getenv("GEMINI_API_KEY"):
        os.environ.setdefault("LLM_PROVIDER", "gemini")
        logger.info("✅ 使用 Gemini (免费) 作为 LLM 提供商")
    elif os.getenv("OPENAI_API_KEY"):
        os.environ.setdefault("LLM_PROVIDER", "openai")
        logger.info("✅ 使用 OpenAI 作为 LLM 提供商")
    else:
        logger.warning("⚠️ 未检测到 LLM API Key")
    
    logger.info(f"✅ 环境配置完成, 数据目录: {Path('data').absolute()}")


def get_watch_keywords():
    """获取关注关键词"""
    keywords_str = os.getenv("WATCH_KEYWORDS", "黄金,茅台,英伟达,央行,GDP")
    return [k.strip() for k in keywords_str.split(",") if k.strip()]


def run_audit_mode():
    """运行审计模式"""
    logger.info("📰 开始新闻采集与审计...")
    
    from src.news_fetcher import NewsFetcher
    from src.audit_engine import AuditEngine
    from src.multi_channel_notifier import MultiChannelNotifier
    from src.semantic_dedup import SemanticDeduplicator
    
    # 初始化组件
    fetcher = NewsFetcher({"provider": "akshare"})
    deduplicator = SemanticDeduplicator(similarity_threshold=0.6)
    
    # 根据环境变量选择 LLM
    provider = os.getenv("LLM_PROVIDER", "gemini")
    audit_config = {
        "provider": provider,
        "model": os.getenv("LLM_MODEL", "gemini-3-flash-preview" if provider == "gemini" else "gpt-4o"),
        "api_key": os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    }
    
    if provider == "openai" and os.getenv("OPENAI_BASE_URL"):
        audit_config["base_url"] = os.getenv("OPENAI_BASE_URL")
    
    auditor = AuditEngine(audit_config)
    notifier = MultiChannelNotifier()
    
    # 🆕 语义去重与事件聚合
    event_groups = deduplicator.group_by_event(news_list)
    logger.info(f"🔄 事件聚合: 原始新闻 {original_count} 条, 识别出 {len(event_groups)} 个独立事件")
    
    # 审计每个事件的代表性新闻
    results = []
    high_risk_news = []
    
    for event_id, news_group in event_groups.items():
        # 选取代表性新闻
        representative_news = deduplicator.get_representative(news_group)
        try:
            result = auditor.audit(representative_news)
            result['_news_title'] = representative_news.get('title', '未知标题')
            # 记录该事件包含的新闻数量
            result['_event_count'] = len(news_group)
            result['_other_titles'] = [n.get('title') for n in news_group if n != representative_news]
            results.append(result)
            
            audit_result = result.get("audit_result", {})
            risk_level = audit_result.get("risk_level", "Medium")
            
            if risk_level in ["High", "high", "critical", "Critical"]:
                high_risk_news.append({
                    "title": representative_news.get("title"),
                    "risk_level": risk_level,
                    "score": audit_result.get("score", 50),
                    "news_category": audit_result.get("news_category", "neutral"),
                    "core_thesis": audit_result.get("core_thesis") or audit_result.get("one_sentence_conclusion", "N/A"),
                    "event_count": len(news_group)
                })
        except Exception as e:
            logger.error(f"审计失败: {e}")
    
    logger.info(f"✅ 审计完成, 识别独立事件: {len(results)} 个, 高风险预警: {len(high_risk_news)} 条")
    
    # 生成报告（传入去重统计信息）
    dedup_stats = {
        "original": original_count,
        "unique": len(results),
        "duplicates": original_count - len(results)
    }
    report = generate_daily_report(results, high_risk_news, dedup_stats)
    
    # 推送日报
    if notifier.is_available():
        notifier.send(f"📊 NewsTrace 日报 {datetime.now().strftime('%Y-%m-%d')}", report)
        if high_risk_news:
            logger.info(f"📤 已推送通知: {len(high_risk_news)} 条高风险新闻")
        else:
            logger.info("📤 已推送日报 (今日无高风险新闻)")
    
    # 保存报告
    report_path = f"data/reports/daily_{datetime.now().strftime('%Y%m%d')}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info(f"📝 报告已保存: {report_path}")
    
    return results


def run_tracking_mode():
    """运行追踪模式"""
    logger.info("📈 开始追踪更新...")
    
    # TODO: 实现追踪逻辑
    logger.info("✅ 追踪更新完成")


def get_historical_stats():
    """获取历史统计数据"""
    try:
        from src.database import Database
        db = Database()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # 获取最近 50 条已完成追踪的记录
            cursor.execute("""
                SELECT 
                    n.ai_audit_result,
                    mt.price_t0,
                    mt.price_t3
                FROM market_tracking mt
                JOIN news n ON mt.news_id = n.news_id
                WHERE mt.price_t3 IS NOT NULL
                ORDER BY mt.t3_timestamp DESC
                LIMIT 50
            """)
            rows = cursor.fetchall()
            if not rows:
                return None
                
            correct = 0
            for row in rows:
                audit_result, t0, t3 = row
                if isinstance(audit_result, str):
                    audit_result = json.loads(audit_result)
                
                # 简单逻辑：看多且涨，看空且跌
                category = audit_result.get("news_category", "neutral")
                if t0 and t3:
                    ret = (t3 - t0) / t0
                    if category == "bullish" and ret > 0.005: correct += 1
                    elif category == "bearish" and ret < -0.005: correct += 1
                    elif category == "neutral" and abs(ret) <= 0.005: correct += 1
            
            return {
                "accuracy": correct / len(rows),
                "sample_count": len(rows)
            }
    except Exception:
        return None


def generate_daily_report(results, high_risk_news, dedup_stats=None):
    """生成每日报告"""
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    stats = get_historical_stats()
    
    # 统计分类
    category_counts = {"bullish": 0, "bearish": 0, "neutral": 0}
    for r in results:
        cat = r.get("audit_result", {}).get("news_category", "neutral")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    report_lines = [
        f"# 📊 NewsTrace 每日分析报告",
        f"",
        f"**日期**: {current_time}",
        f"",
        f"---",
        f"",
        f"## 📰 分析概览",
        f"",
    ]
    
    if dedup_stats:
        report_lines.extend([
            f"- 采集原始新闻: `{dedup_stats['original']}` 条",
            f"- 识别独立事件: `{dedup_stats['unique']}` 个",
            f"- 语义去重过滤: `{dedup_stats['duplicates']}` 条 (重复率: {dedup_stats['duplicates']/dedup_stats['original']:.1%})",
            f"- 投资情绪分布: 🟢利好 `{category_counts['bullish']}` | 🔴利空 `{category_counts['bearish']}` | ⚪中性 `{category_counts['neutral']}`",
        ])
    
    if stats:
        report_lines.append(f"- **系统置信度**: `{(stats['accuracy']*100):.1f}%` (基于最近 {stats['sample_count']} 条历史回测)")
    
    report_lines.append("")
    
    if high_risk_news:
        report_lines.extend([
            f"## ⚠️ 核心审计预警 (Top 5)",
            f""
        ])
        
        for i, news in enumerate(high_risk_news[:5], 1):
            emoji = "🔴" if news["risk_level"] in ["critical", "Critical"] else "🟠"
            cat_emoji = "📈" if news["news_category"] == "bullish" else "📉" if news["news_category"] == "bearish" else "⚖️"
            group_suffix = f" (由 {news['event_count']} 篇报道聚合)" if news['event_count'] > 1 else ""
            
            report_lines.extend([
                f"### {emoji} {i}. {news['title']}{group_suffix}",
                f"",
                f"- **态势**: `{news['news_category']}` {cat_emoji} | **逻辑评分**: `{news['score']}`",
                f"- **核心论点**: {news.get('core_thesis', 'N/A')}",
                f""
            ])
    else:
        report_lines.extend([
            f"## ✅ 安全状态",
            f"",
            f"本次分析未发现高风险预警事件，市场处于低合谋或低风险震荡状态。",
            f""
        ])
    
    # 📋 所有新闻摘要
    report_lines.extend([
        f"## 📋 情报库摘要 (事件聚合)",
        f""
    ])
    
    for i, result in enumerate(results[:25], 1):
        audit_result = result.get("audit_result", {})
        risk_level = audit_result.get("risk_level", "Medium")
        score = audit_result.get("score", 50)
        category = audit_result.get("news_category", "neutral")
        title = result.get("_news_title", "未知标题")
        event_count = result.get("_event_count", 1)
        conclusion = audit_result.get("one_sentence_conclusion", "")
        
        # 风险/方向图标
        risk_emoji = "🔴" if risk_level in ["High", "high", "Critical", "critical"] else "🟡"
        cat_tag = "[利好]" if category == "bullish" else "[利空]" if category == "bearish" else "[中性]"
        dup_tag = f" (+{event_count-1}篇重复)" if event_count > 1 else ""
        
        report_lines.append(f"{i}. {risk_emoji} **{cat_tag} {title}**{dup_tag}")
        report_lines.append(f"   - 风险: `{risk_level}` | 评分: `{score}`")
        if conclusion:
            report_lines.append(f"   - 💡 {conclusion}")
    
    report_lines.extend([
        f"",
        f"---",
        f"",
        f"*由 NewsTrace 语义审计引擎自动生成 - [Data-Driven Trust]*"
    ])
    
    return "\n".join(report_lines)


def save_summary(results):
    """保存运行摘要"""
    summary = {
        "run_time": datetime.now().isoformat(),
        "total_analyzed": len(results),
        "high_risk_count": sum(1 for r in results if r.get("risk_level") in ["high", "critical"]),
        "provider": os.getenv("LLM_PROVIDER", "unknown")
    }
    
    with open("data/summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main():
    """主入口"""
    print("\n" + "=" * 50)
    print("📊 NewsTrace 零成本部署版")
    print("=" * 50 + "\n")
    
    # 配置环境
    setup_environment()
    
    # 获取运行模式
    mode = os.getenv("RUN_MODE", "full")
    logger.info(f"🚀 运行模式: {mode}")
    
    results = []
    
    try:
        if mode in ("full", "audit"):
            results = run_audit_mode()
        
        if mode in ("full", "tracking"):
            run_tracking_mode()
        
        # 保存摘要
        save_summary(results)
        
        logger.info("✅ NewsTrace 运行完成!")
        
    except Exception as e:
        logger.error(f"❌ 运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
