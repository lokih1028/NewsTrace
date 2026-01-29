"""
NewsTrace FastAPI接口
"""
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.newstrace_engine import NewsTraceEngine
from src.auth import JWTAuth, SimpleUserStore
from src.cost_tracker import CostTracker
from src.llm_cache import LLMCache

# Sentry 集成
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    SENTRY_DSN = os.getenv("SENTRY_DSN")
    if SENTRY_DSN:
        sentry_sdk.init(dsn=SENTRY_DSN, integrations=[FastApiIntegration()])
except ImportError:
    pass

app = FastAPI(
    title="NewsTrace API",
    description="金融新闻智能审计与回溯系统",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化组件
engine = NewsTraceEngine(config_path="config/config.yaml")
auth = JWTAuth()
user_store = SimpleUserStore(auth)
cost_tracker = CostTracker()
llm_cache = LLMCache()

# 创建默认管理员
try:
    user_store.create_user("admin", os.getenv("ADMIN_PASSWORD", "admin123"), "admin")
except ValueError:
    pass

security = HTTPBearer(auto_error=False)


# 认证依赖
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials is None:
        return None
    payload = auth.verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


async def require_auth(user = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_admin(user = Depends(require_auth)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# 请求模型
class NewsInput(BaseModel):
    title: str
    content: str
    source: str
    timestamp: Optional[str] = None


class TrackingRequest(BaseModel):
    news_id: str
    duration_days: Optional[int] = 7


class LoginRequest(BaseModel):
    username: str
    password: str


# ==================== 公开端点 ====================
@app.get("/", tags=["系统"])
async def root():
    """根路径"""
    return {
        "message": "NewsTrace API",
        "version": "2.0.0",
        "docs": "/docs"
    }


@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


# ==================== 认证端点 ====================
@app.post("/auth/login", tags=["认证"])
async def login(request: LoginRequest):
    """用户登录获取令牌"""
    token = user_store.authenticate(request.username, request.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": token, "token_type": "bearer"}


# ==================== 审计端点 ====================
@app.post("/audit", tags=["审计"])
async def audit_news(news: NewsInput):
    """审计新闻"""
    try:
        result = engine.audit_news(news.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 追踪端点 ====================
@app.post("/tracking/start", tags=["追踪"])
async def start_tracking(request: TrackingRequest):
    """开启追踪任务"""
    try:
        audit_result = engine.db.get_audit_result(request.news_id)
        if not audit_result:
            raise HTTPException(status_code=404, detail="新闻不存在")
        
        with engine.db.get_connection() as conn:
            cur = conn.cursor()
            if engine.db.db_type == 'postgresql':
                cur.execute("""
                    SELECT ticker_code, ticker_name, logic
                    FROM recommended_tickers WHERE news_id = %s
                """, (request.news_id,))
            else:
                cur.execute("""
                    SELECT ticker_code, ticker_name, logic
                    FROM recommended_tickers WHERE news_id = ?
                """, (request.news_id,))
            
            rows = cur.fetchall()
            tickers = [{'code': r[0], 'name': r[1], 'logic': r[2]} for r in rows]
        
        tracking_id = engine.start_tracking(
            news_id=request.news_id,
            tickers=tickers,
            duration_days=request.duration_days
        )
        
        return {
            "tracking_id": tracking_id,
            "news_id": request.news_id,
            "tickers": tickers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tracking/{tracking_id}", tags=["追踪"])
async def get_tracking_status(tracking_id: str):
    """获取追踪状态"""
    status = engine.get_tracking_status(tracking_id)
    if not status:
        raise HTTPException(status_code=404, detail="追踪任务不存在")
    return status


@app.get("/trackings/active", tags=["追踪"])
async def get_active_trackings():
    """获取活跃追踪任务"""
    return engine.get_active_trackings()


# ==================== 新闻端点 ====================
@app.get("/news/latest", tags=["新闻"])
async def get_latest_news(limit: int = 10):
    """获取最新新闻"""
    return engine.get_latest_news(limit=limit)


@app.get("/news/{news_id}/report", tags=["新闻"])
async def get_news_report(news_id: str):
    """获取新闻追踪报告"""
    report = engine.get_tracking_report(news_id)
    if not report['news']:
        raise HTTPException(status_code=404, detail="新闻不存在")
    return report


# ==================== 信源端点 ====================
@app.get("/sources/ranking", tags=["信源"])
async def get_source_ranking(days: int = 30):
    """获取信源排名"""
    return engine.get_source_ranking(days=days)


# ==================== 报告端点 ====================
@app.get("/reports/daily", tags=["报告"])
async def get_daily_report():
    """获取每日报告"""
    return engine.generate_daily_report()


@app.get("/reports/weekly", tags=["报告"])
async def get_weekly_report():
    """获取周报"""
    return engine.generate_weekly_report()


# ==================== 监控端点 (需认证) ====================
@app.get("/admin/cost/stats", tags=["监控"], dependencies=[Depends(require_admin)])
async def get_cost_stats():
    """获取 LLM 成本统计"""
    return cost_tracker.get_session_stats()


@app.get("/admin/cost/projection", tags=["监控"], dependencies=[Depends(require_admin)])
async def get_cost_projection():
    """获取月成本预估"""
    return cost_tracker.get_monthly_projection()


@app.get("/admin/cache/stats", tags=["监控"], dependencies=[Depends(require_admin)])
async def get_cache_stats():
    """获取缓存统计"""
    return llm_cache.get_stats()


@app.post("/admin/cache/clear", tags=["监控"], dependencies=[Depends(require_admin)])
async def clear_cache():
    """清除 LLM 缓存"""
    llm_cache.clear()
    return {"message": "缓存已清除"}


@app.post("/admin/update-prices", tags=["管理"], dependencies=[Depends(require_admin)])
async def update_tracking_prices():
    """手动更新追踪价格"""
    engine.update_tracking_prices()
    return {"message": "价格更新完成"}


@app.post("/admin/update-ratings", tags=["管理"], dependencies=[Depends(require_admin)])
async def update_source_ratings():
    """手动更新信源评级"""
    engine.source_rating.update_all_ratings()
    return {"message": "评级更新完成"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

