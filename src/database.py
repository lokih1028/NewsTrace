import logging
import sqlite3
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, date
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    """数据库管理类"""
    
    def __init__(self, config: Dict):
        """
        初始化数据库连接
        
        Args:
            config: 数据库配置
        """
        self.config = config
        self.db_type = config.get('type', 'postgresql')
        
        if self.db_type == 'postgresql' and not HAS_PSYCOPG2:
            logger.warning("未安装 psycopg2，将尝试使用 sqlite 模式")
            self.db_type = 'sqlite'

        if self.db_type == 'postgresql':
            self.connection_params = {
                'host': config.get('host', 'localhost'),
                'port': config.get('port', 5432),
                'database': config.get('database', 'newstrace'),
                'user': config.get('username'),
                'password': config.get('password')
            }
        else:
            self.sqlite_path = config.get('sqlite_path', 'newstrace.db')
            logger.info(f"使用 SQLite 数据库: {self.sqlite_path}")
            self._init_sqlite()
        
        # 测试连接
        self._test_connection()
        
        logger.info(f"数据库连接初始化完成 ({self.db_type})")
    
    def _init_sqlite(self):
        """初始化 SQLite 数据库表"""
        if os.path.exists(self.sqlite_path):
            return
            
        with sqlite3.connect(self.sqlite_path) as conn:
            cur = conn.cursor()
            # 创建新闻表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    news_id TEXT UNIQUE,
                    title TEXT,
                    content TEXT,
                    source TEXT,
                    publish_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 创建审计结果表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    news_id TEXT UNIQUE,
                    score INTEGER,
                    risk_level TEXT,
                    warnings TEXT,
                    semantic_deviations TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 创建推荐标的表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS recommended_tickers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    news_id TEXT,
                    ticker_code TEXT,
                    ticker_name TEXT,
                    logic TEXT,
                    beta TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 创建追踪任务表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tracking_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracking_id TEXT UNIQUE,
                    news_id TEXT,
                    status TEXT,
                    expected_close_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _test_connection(self):
        """测试数据库连接"""
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1")
            logger.info("数据库连接测试成功")
        except Exception as e:
            if self.db_type == 'postgresql':
                logger.warning(f"PostgreSQL 连接失败，尝试切换到 SQLite: {e}")
                self.db_type = 'sqlite'
                self.sqlite_path = 'newstrace.db'
                self._init_sqlite()
                self._test_connection()
            else:
                logger.error(f"数据库连接失败: {e}")
                raise
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接(上下文管理器)"""
        if self.db_type == 'postgresql':
            conn = psycopg2.connect(**self.connection_params)
        else:
            conn = sqlite3.connect(self.sqlite_path)
            conn.row_factory = sqlite3.Row
            
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            conn.close()
    
    def save_news(self, news: Dict):
        """保存新闻"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.db_type == 'postgresql':
                cur.execute("""
                    INSERT INTO news (news_id, title, content, source, publish_time)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (news_id) DO NOTHING
                """, (
                    news['news_id'],
                    news['title'],
                    news.get('content', ''),
                    news.get('source', 'Unknown'),
                    news.get('timestamp', datetime.now())
                ))
            else:
                cur.execute("""
                    INSERT OR IGNORE INTO news (news_id, title, content, source, publish_time)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    news['news_id'],
                    news['title'],
                    news.get('content', ''),
                    news.get('source', 'Unknown'),
                    news.get('timestamp', datetime.now())
                ))
        
        logger.debug(f"新闻已保存: {news['news_id']}")
    
    def save_audit_result(self, result: Dict):
        """保存审计结果"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            audit = result['audit_result']
            if self.db_type == 'postgresql':
                cur.execute("""
                    INSERT INTO audit_results 
                    (news_id, score, risk_level, warnings, semantic_deviations)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    result['news_id'],
                    audit['score'],
                    audit['risk_level'],
                    Json(audit.get('warnings', [])),
                    Json(audit.get('semantic_deviations', []))
                ))
            else:
                cur.execute("""
                    INSERT OR REPLACE INTO audit_results 
                    (news_id, score, risk_level, warnings, semantic_deviations)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    result['news_id'],
                    audit['score'],
                    audit['risk_level'],
                    json.dumps(audit.get('warnings', [])),
                    json.dumps(audit.get('semantic_deviations', []))
                ))
        
        logger.debug(f"审计结果已保存: {result['news_id']}")
    
    def save_recommended_ticker(self, ticker: Dict):
        """保存推荐标的"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.db_type == 'postgresql':
                cur.execute("""
                    INSERT INTO recommended_tickers 
                    (news_id, ticker_code, ticker_name, logic, beta)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    ticker['news_id'],
                    ticker['code'],
                    ticker['name'],
                    ticker['logic'],
                    ticker.get('beta', '')
                ))
            else:
                cur.execute("""
                    INSERT INTO recommended_tickers 
                    (news_id, ticker_code, ticker_name, logic, beta)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    ticker['news_id'],
                    ticker['code'],
                    ticker['name'],
                    ticker['logic'],
                    ticker.get('beta', '')
                ))
        
        logger.debug(f"推荐标的已保存: {ticker['code']}")
    
    def get_news(self, news_id: str) -> Optional[Dict]:
        """获取新闻"""
        with self.get_connection() as conn:
            if self.db_type == 'postgresql':
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT * FROM news WHERE news_id = %s", (news_id,))
            else:
                cur = conn.cursor()
                cur.execute("SELECT * FROM news WHERE news_id = ?", (news_id,))
            
            row = cur.fetchone()
            return dict(row) if row else None
    
    def get_audit_result(self, news_id: str) -> Optional[Dict]:
        """获取审计结果"""
        with self.get_connection() as conn:
            if self.db_type == 'postgresql':
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT * FROM audit_results WHERE news_id = %s", (news_id,))
            else:
                cur = conn.cursor()
                cur.execute("SELECT * FROM audit_results WHERE news_id = ?", (news_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            result = dict(row)
            if self.db_type == 'sqlite':
                # 反序列化 JSON 字段
                if result.get('warnings'):
                    result['warnings'] = json.loads(result['warnings'])
                if result.get('semantic_deviations'):
                    result['semantic_deviations'] = json.loads(result['semantic_deviations'])
            return result
    
    def get_latest_news_with_audit(self, limit: int = 10) -> List[Dict]:
        """获取最新新闻及审计结果"""
        with self.get_connection() as conn:
            if self.db_type == 'postgresql':
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT 
                        n.*,
                        a.score,
                        a.risk_level,
                        a.warnings,
                        COALESCE(
                            json_agg(
                                json_build_object(
                                    'code', t.ticker_code,
                                    'name', t.ticker_name,
                                    'logic', t.logic
                                )
                            ) FILTER (WHERE t.ticker_code IS NOT NULL),
                            '[]'
                        ) as tickers
                    FROM news n
                    LEFT JOIN audit_results a ON n.news_id = a.news_id
                    LEFT JOIN recommended_tickers t ON n.news_id = t.news_id
                    GROUP BY n.id, n.news_id, n.title, n.content, n.source, 
                             n.publish_time, n.created_at, a.score, a.risk_level, a.warnings
                    ORDER BY n.created_at DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
                return [dict(row) for row in rows]
            else:
                cur = conn.cursor()
                # SQLite 不支持 json_agg，我们需要分两步或在 Python 中处理
                cur.execute("""
                    SELECT 
                        n.*,
                        a.score,
                        a.risk_level,
                        a.warnings
                    FROM news n
                    LEFT JOIN audit_results a ON n.news_id = a.news_id
                    ORDER BY n.created_at DESC
                    LIMIT ?
                """, (limit,))
                news_rows = [dict(row) for row in cur.fetchall()]
                
                for news in news_rows:
                    # 获取每个新闻的标的
                    cur.execute("""
                        SELECT ticker_code as code, ticker_name as name, logic
                        FROM recommended_tickers
                        WHERE news_id = ?
                    """, (news['news_id'],))
                    news['tickers'] = [dict(t) for t in cur.fetchall()]
                    
                    # 反序列化 JSON
                    if news.get('warnings'):
                        news['warnings'] = json.loads(news['warnings'])
                
                return news_rows

    def count_news_by_date(self, target_date: date) -> int:
        """统计指定日期的新闻数量"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.db_type == 'postgresql':
                cur.execute("""
                    SELECT COUNT(*) FROM news 
                    WHERE DATE(created_at) = %s
                """, (target_date,))
            else:
                cur.execute("""
                    SELECT COUNT(*) FROM news 
                    WHERE date(created_at) = ?
                """, (target_date.isoformat(),))
            return cur.fetchone()[0]
    
    def get_risk_distribution(self, target_date: date) -> Dict:
        """获取风险分布"""
        with self.get_connection() as conn:
            if self.db_type == 'postgresql':
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT 
                        risk_level,
                        COUNT(*) as count
                    FROM audit_results a
                    JOIN news n ON a.news_id = n.news_id
                    WHERE DATE(n.created_at) = %s
                    GROUP BY risk_level
                """, (target_date,))
            else:
                cur = conn.cursor()
                cur.execute("""
                    SELECT 
                        risk_level,
                        COUNT(*) as count
                    FROM audit_results a
                    JOIN news n ON a.news_id = n.news_id
                    WHERE date(n.created_at) = ?
                    GROUP BY risk_level
                """, (target_date.isoformat(),))
            
            rows = cur.fetchall()
            return {row['risk_level']: row['count'] for row in rows}
    
    def get_high_risk_news(self, target_date: date, limit: int = 10) -> List[Dict]:
        """获取高风险新闻"""
        with self.get_connection() as conn:
            if self.db_type == 'postgresql':
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT n.*, a.score, a.warnings
                    FROM news n
                    JOIN audit_results a ON n.news_id = a.news_id
                    WHERE DATE(n.created_at) = %s AND a.risk_level = 'High'
                    ORDER BY a.score ASC
                    LIMIT %s
                """, (target_date, limit))
            else:
                cur = conn.cursor()
                cur.execute("""
                    SELECT n.*, a.score, a.warnings
                    FROM news n
                    JOIN audit_results a ON n.news_id = a.news_id
                    WHERE date(n.created_at) = ? AND a.risk_level = 'High'
                    ORDER BY a.score ASC
                    LIMIT ?
                """, (target_date.isoformat(), limit))
            
            rows = cur.fetchall()
            results = [dict(row) for row in rows]
            if self.db_type == 'sqlite':
                for r in results:
                    if r.get('warnings'):
                        r['warnings'] = json.loads(r['warnings'])
            return results
    
    def get_closed_trackings(self, target_date: date) -> List[Dict]:
        """获取指定日期结案的追踪任务"""
        with self.get_connection() as conn:
            if self.db_type == 'postgresql':
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT * FROM tracking_tasks
                    WHERE DATE(expected_close_date) = %s AND status = 'closed'
                """, (target_date,))
            else:
                cur = conn.cursor()
                cur.execute("""
                    SELECT * FROM tracking_tasks
                    WHERE date(expected_close_date) = ? AND status = 'closed'
                """, (target_date.isoformat(),))
            
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    
    def count_news_since(self, start_date: date) -> int:
        """统计从指定日期开始的新闻数量"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.db_type == 'postgresql':
                cur.execute("""
                    SELECT COUNT(*) FROM news 
                    WHERE DATE(created_at) >= %s
                """, (start_date,))
            else:
                cur.execute("""
                    SELECT COUNT(*) FROM news 
                    WHERE date(created_at) >= ?
                """, (start_date.isoformat(),))
            return cur.fetchone()[0]
    
    def count_trackings_since(self, start_date: date) -> int:
        """统计从指定日期开始的追踪任务数量"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.db_type == 'postgresql':
                cur.execute("""
                    SELECT COUNT(*) FROM tracking_tasks 
                    WHERE DATE(created_at) >= %s
                """, (start_date,))
            else:
                cur.execute("""
                    SELECT COUNT(*) FROM tracking_tasks 
                    WHERE date(created_at) >= ?
                """, (start_date.isoformat(),))
            return cur.fetchone()[0]
