import os
import time
import json
import requests
import datetime
from sqlalchemy import create_engine, text
from openai import OpenAI
from src.news_fetcher import NewsFetcher
from src.rate_limiter import AdaptiveRateLimiter
from src.audit_engine import AuditEngine
from src.cost_tracker import CostTracker

# ==================== Sentry 异常监控 ====================
try:
    import sentry_sdk
    SENTRY_DSN = os.getenv("SENTRY_DSN")
    if SENTRY_DSN:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=0.1,
            environment=os.getenv("ENV", "development")
        )
        print("✅ Sentry 异常监控已启用")
    else:
        print("⚠️ SENTRY_DSN 未配置,异常监控禁用")
except ImportError:
    print("⚠️ sentry-sdk 未安装,异常监控禁用")
# =========================================================

# ==================== 核心配置区 ====================
# 1. 你的 OpenAI Key (必须开启 VPN)
API_KEY = os.getenv("OPENAI_API_KEY", "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")
BASE_URL = "https://api.openai.com/v1"
MODEL_NAME = "gpt-4o"

# 2. 你的 PushPlus Token (微信推送用)
PUSH_TOKEN = os.getenv("PUSHPLUS_TOKEN", "a348f2f0e5b545f79a96acb472c20fb6")

# 3. 你的关注清单 (Active Input)
WATCH_KEYWORDS = ["黄金", "茅台", "英伟达", "央行", "GDP"] 

# 4. 采集频率 (秒)
Loop_Interval = 20 

# 数据库连接
DB_URI = os.getenv("DATABASE_URL", "postgresql://postgres:123456@localhost:5432/newstrace")
# ====================================================

print("\n=== NewsTrace 3.0 (7x24h 实时雷达版) 启动 ===")


from src.multi_channel_notifier import MultiChannelNotifier

try:
    db_engine = create_engine(DB_URI)
    ai_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    
    # 初始化新组件
    fetcher = NewsFetcher({"provider": "tushare", "api_key": "your_tushare_token"}) 
    rate_limiter = AdaptiveRateLimiter(min_interval=Loop_Interval, max_interval=Loop_Interval*2)
    audit_engine = AuditEngine({"provider": "openai", "model": MODEL_NAME, "api_key": API_KEY})
    
    # 初始化推送管理器 (使用新版多渠道通知器)
    notifier = MultiChannelNotifier({
        "pushplus_token": PUSH_TOKEN,
        # "wechat_webhook": "...", # 可选
        # "feishu_webhook": "...", # 可选
    })
    
    # 验证数据库连接
    try:
        with db_engine.connect() as conn: conn.execute(text("SELECT 1"))
        print("✅ 数据库连接正常")
    except Exception as db_e:
        print(f"⚠️ 数据库连接失败 (程序将继续运行,但无法保存数据): {db_e}")

    print("✅ 基础设施初始化完成")
except Exception as e:
    print(f"❌ 初始化失败: {e}"); exit()

# --- 内存缓存 (用于去重) ---
seen_news_ids = set()

def process_news_item(item):
    """处理单条新闻"""
    news_id = item.get('docid') or f"NEWS_{hash(item['title'])}"
    title = item['title']
    
    if news_id in seen_news_ids:
        return
    
    # 数据库去重
    try:
        with db_engine.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM news_intelligence WHERE news_id = :id"), {"id": news_id}).fetchone()
            if exists:
                seen_news_ids.add(news_id)
                return
    except:
        pass

    # 关键词过滤
    if WATCH_KEYWORDS:
        is_match = False
        for keyword in WATCH_KEYWORDS:
            if keyword in title:
                is_match = True
                print(f"🎯 命中关键词: [{keyword}] -> {title}")
                break
        if not is_match:
            seen_news_ids.add(news_id)
            return

    print(f"\n⚡ 发现新情报: {title}")
    
    try:
        # 使用 AuditEngine 进行审计
        audit_output = audit_engine.audit(item)
        res_json = audit_output.get('audit_result', {})
        
        # 存入数据库
        try:
            with db_engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO news_intelligence (news_id, raw_content, publish_time, ai_audit_result)
                    VALUES (:id, :c, :t, :j)
                """), {"id": news_id, "c": title, "t": datetime.datetime.now(), "j": json.dumps(audit_output)})
        except Exception as db_e:
            print(f"⚠️ 数据库写入失败: {db_e}")
            
        seen_news_ids.add(news_id)
        
        # 统一推送
        notifier.broadcast(title, title, res_json)

    except Exception as e:
        print(f"⚠️ 处理出错: {e}")

import argparse

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='NewsTrace 3.0')
    parser.add_argument('--mode', type=str, default='loop', choices=['loop', 'single_run'],
                        help='运行模式: loop (持续监控) 或 single_run (单次运行)')
    parser.add_argument('--dry-run', action='store_true', help='仅获取数据,不进行 AI 分析')
    return parser.parse_args()

# ================= 主循环 =================
if __name__ == "__main__":
    args = parse_arguments()
    
    print(f"👀 正在监控关键词: {WATCH_KEYWORDS if WATCH_KEYWORDS else 'ALL (全部推送)'}")
    print(f"运行模式: {args.mode}")
    print("----------------------------------------")
    
    while True:
        try:
            # 1. 多源容错获取最新列表
            news_list = fetcher.fetch_with_fallback()
            
            if news_list:
                rate_limiter.record_result(True)
                for item in reversed(news_list):
                    process_news_item(item)
            else:
                rate_limiter.record_result(False)
            
            # 2. 模式判断
            if args.mode == 'single_run':
                print("\n✅ 单次运行模式完成, 退出程序。")
                break
                
            # 3. 自适应休息
            print(".", end="", flush=True)
            rate_limiter.wait()
            
        except KeyboardInterrupt:
            print("\n🛑 用户停止监控")
            break
        except Exception as e:
            print(f"\n❌ 运行异常: {e}")
            if args.mode == 'single_run':
                break
            rate_limiter.record_result(False)
            rate_limiter.wait()
