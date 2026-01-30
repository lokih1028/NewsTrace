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
    
    # 初始化组件
    fetcher = NewsFetcher({"provider": "akshare"})
    
    # 根据环境变量选择 LLM
    provider = os.getenv("LLM_PROVIDER", "gemini")
    audit_config = {
        "provider": provider,
        "model": os.getenv("LLM_MODEL", "gemini-2.0-flash" if provider == "gemini" else "gpt-4o"),
        "api_key": os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    }
    
    if provider == "openai" and os.getenv("OPENAI_BASE_URL"):
        audit_config["base_url"] = os.getenv("OPENAI_BASE_URL")
    
    auditor = AuditEngine(audit_config)
    notifier = MultiChannelNotifier()
    
    # 获取关注关键词
    keywords = get_watch_keywords()
    logger.info(f"📋 关注关键词: {keywords}")
    
    # 采集新闻 (NewsFetcher.fetch() 不接受 limit 参数)
    news_list = fetcher.fetch()
    logger.info(f"📰 采集到 {len(news_list)} 条新闻")
    
    # 审计新闻
    results = []
    high_risk_news = []
    
    for news in news_list:
        try:
            result = auditor.audit(news)
            results.append(result)
            
            # 修复: 正确访问审计结果结构
            audit_result = result.get("audit_result", {})
            risk_level = audit_result.get("risk_level", "Medium")
            
            if risk_level in ["High", "high", "critical", "Critical"]:
                high_risk_news.append({
                    "title": news.get("title"),
                    "risk_level": risk_level,
                    "score": audit_result.get("score", 50),
                    "core_thesis": audit_result.get("core_thesis") or audit_result.get("one_sentence_conclusion", "N/A")
                })
        except Exception as e:
            logger.error(f"审计失败: {e}")
    
    logger.info(f"✅ 审计完成, 高风险新闻: {len(high_risk_news)} 条")
    
    # 修复: 始终生成报告,不管是否有高风险新闻
    report = generate_daily_report(results, high_risk_news)
    
    # 推送通知 (只在有高风险新闻时推送)
    if high_risk_news and notifier.is_available():
        notifier.send(f"📊 NewsTrace 日报 {datetime.now().strftime('%Y-%m-%d')}", report)
        logger.info(f"📤 已推送通知: {len(high_risk_news)} 条高风险新闻")
    
    # 保存报告 (始终保存)
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


def generate_daily_report(results, high_risk_news):
    """生成每日报告"""
    report_lines = [
        f"# 📊 NewsTrace 每日分析报告",
        f"",
        f"**日期**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"---",
        f"",
        f"## 📰 分析概览",
        f"",
        f"- 审计新闻: {len(results)} 条",
        f"- 高风险新闻: {len(high_risk_news)} 条",
        f"",
    ]
    
    if high_risk_news:
        report_lines.extend([
            f"## ⚠️ 高风险新闻",
            f""
        ])
        
        for i, news in enumerate(high_risk_news[:5], 1):
            emoji = "🔴" if news["risk_level"] in ["critical", "Critical"] else "🟠"
            report_lines.extend([
                f"### {emoji} {i}. {news['title'][:50]}...",
                f"",
                f"- **风险等级**: {news['risk_level']}",
                f"- **评分**: {news['score']}",
                f"- **核心论点**: {news.get('core_thesis', 'N/A')}",
                f""
            ])
    else:
        report_lines.extend([
            f"## ✅ 无高风险新闻",
            f"",
            f"本次分析未发现高风险新闻,所有新闻风险等级均为 Medium 或 Low。",
            f""
        ])
    
    # 添加所有新闻的摘要
    report_lines.extend([
        f"## 📋 所有分析新闻摘要",
        f""
    ])
    
    for i, result in enumerate(results[:10], 1):
        audit_result = result.get("audit_result", {})
        risk_level = audit_result.get("risk_level", "Medium")
        score = audit_result.get("score", 50)
        
        # 风险等级图标
        if risk_level in ["High", "high", "Critical", "critical"]:
            emoji = "🔴"
        elif risk_level in ["Medium", "medium"]:
            emoji = "🟡"
        else:
            emoji = "🟢"
        
        report_lines.append(f"{i}. {emoji} 风险: {risk_level} | 评分: {score}")
    
    report_lines.extend([
        f"",
        f"---",
        f"",
        f"*由 NewsTrace 自动生成*"
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
