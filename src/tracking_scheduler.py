"""
追踪任务调度器
管理T+7追踪任务的生命周期
"""
import logging
from typing import Dict, List
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)


class TrackingScheduler:
    """追踪任务调度器"""
    
    def __init__(self, db, config: Dict):
        """
        初始化调度器
        
        Args:
            db: 数据库实例
            config: 追踪配置
        """
        self.db = db
        self.config = config
        self.duration_days = config.get('duration_days', 7)
        
        logger.info(f"追踪调度器初始化完成: duration_days={self.duration_days}")
    
    def create_tracking(
        self, 
        news_id: str, 
        tickers: List[Dict],
        duration_days: int = None
    ) -> str:
        """
        创建追踪任务
        
        Args:
            news_id: 新闻ID
            tickers: 标的列表
            duration_days: 追踪天数
            
        Returns:
            追踪任务ID
        """
        if duration_days is None:
            duration_days = self.duration_days
        
        tracking_id = self._generate_tracking_id()
        
        # 获取当前价格作为T0价格
        for ticker in tickers:
            try:
                t0_price = self._get_current_price(ticker['code'])
                t0_timestamp = datetime.now()
                expected_close_date = t0_timestamp + timedelta(days=duration_days)
                
                # 保存追踪任务
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    if self.db.db_type == 'postgresql':
                        cur.execute("""
                            INSERT INTO tracking_tasks 
                            (tracking_id, news_id, ticker_code, t0_price, 
                             t0_timestamp, expected_close_date, status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            tracking_id,
                            news_id,
                            ticker['code'],
                            t0_price,
                            t0_timestamp,
                            expected_close_date,
                            'active'
                        ))
                    else:
                        cur.execute("""
                            INSERT INTO tracking_tasks 
                            (tracking_id, news_id, ticker_code, t0_price, 
                             t0_timestamp, expected_close_date, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            tracking_id,
                            news_id,
                            ticker['code'],
                            t0_price,
                            t0_timestamp,
                            expected_close_date,
                            'active'
                        ))
                
                # 保存T0价格到历史表
                self._save_price_history(
                    tracking_id=tracking_id,
                    ticker_code=ticker['code'],
                    price=t0_price,
                    day_offset=0
                )
                
                logger.info(f"追踪任务已创建: {tracking_id} - {ticker['code']} @ {t0_price}")
                
            except Exception as e:
                logger.error(f"创建追踪任务失败: {ticker['code']} - {e}")
        
        return tracking_id
    
    def update_all_prices(self):
        """更新所有活跃追踪任务的价格"""
        active_trackings = self.get_active_trackings()
        
        for tracking in active_trackings:
            try:
                # 计算天数偏移
                t0_timestamp = tracking['t0_timestamp']
                day_offset = (datetime.now().date() - t0_timestamp.date()).days
                
                # 获取当前价格
                current_price = self._get_current_price(tracking['ticker_code'])
                
                # 保存价格历史
                self._save_price_history(
                    tracking_id=tracking['tracking_id'],
                    ticker_code=tracking['ticker_code'],
                    price=current_price,
                    day_offset=day_offset
                )
                
                logger.debug(f"价格已更新: {tracking['ticker_code']} T+{day_offset} @ {current_price}")
                
            except Exception as e:
                logger.error(f"更新价格失败: {tracking['tracking_id']} - {e}")
    
    def check_and_close_completed(self):
        """检查并结案已完成的追踪任务"""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            # 查找已到期的任务
            if self.db.db_type == 'postgresql':
                cur.execute("""
                    SELECT tracking_id, ticker_code, t0_price
                    FROM tracking_tasks
                    WHERE status = 'active' 
                    AND expected_close_date <= CURRENT_DATE
                """)
            else:
                cur.execute("""
                    SELECT tracking_id, ticker_code, t0_price
                    FROM tracking_tasks
                    WHERE status = 'active' 
                    AND expected_close_date <= date('now')
                """)
            
            completed_tasks = cur.fetchall()
            
            for task in completed_tasks:
                tracking_id, ticker_code, t0_price = task
                
                try:
                    # 获取最终价格
                    final_price = self._get_latest_price(tracking_id)
                    
                    # 计算PnL
                    pnl = ((final_price - t0_price) / t0_price) * 100
                        
                    # 更新状态为closed
                    if self.db.db_type == 'postgresql':
                        cur.execute("""
                            UPDATE tracking_tasks
                            SET status = 'closed'
                            WHERE tracking_id = %s
                        """, (tracking_id,))
                    else:
                        cur.execute("""
                            UPDATE tracking_tasks
                            SET status = 'closed'
                            WHERE tracking_id = ?
                        """, (tracking_id,))
                    
                    logger.info(f"追踪任务已结案: {tracking_id} - {ticker_code} PnL: {pnl:.2f}%")
                        
                except Exception as e:
                    logger.error(f"结案失败: {tracking_id} - {e}")
    
    def get_status(self, tracking_id: str) -> Dict:
        """获取追踪任务状态"""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if self.db.db_type == 'postgresql':
                cur.execute("""
                    SELECT * FROM tracking_tasks
                    WHERE tracking_id = %s
                """, (tracking_id,))
            else:
                cur.execute("""
                    SELECT * FROM tracking_tasks
                    WHERE tracking_id = ?
                """, (tracking_id,))
                
                row = cur.fetchone()
                if not row:
                    return {}
                
                # 计算当前天数
                t0_timestamp = row[5]  # t0_timestamp列
                current_day = (datetime.now().date() - t0_timestamp.date()).days
                
                # 获取价格历史
                if self.db.db_type == 'postgresql':
                    cur.execute("""
                        SELECT ticker_code, price, day_offset
                        FROM price_history
                        WHERE tracking_id = %s
                        ORDER BY day_offset
                    """, (tracking_id,))
                else:
                    cur.execute("""
                        SELECT ticker_code, price, day_offset
                        FROM price_history
                        WHERE tracking_id = ?
                        ORDER BY day_offset
                    """, (tracking_id,))
                
                price_rows = cur.fetchall()
                
                # 构建标的字典
                tickers = {}
                for price_row in price_rows:
                    ticker_code, price, day_offset = price_row
                    if ticker_code not in tickers:
                        tickers[ticker_code] = {
                            't0_price': row[4],  # t0_price列
                            'current_price': price,
                            'pnl': f"{((price - row[4]) / row[4]) * 100:.2f}%"
                        }
                
                return {
                    'tracking_id': tracking_id,
                    'current_day': current_day,
                    'status': row[7],  # status列
                    'tickers': tickers
                }
    
    def get_tracking_results(self, news_id: str) -> List[Dict]:
        """获取新闻的所有追踪结果"""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if self.db.db_type == 'postgresql':
                cur.execute("""
                    SELECT 
                        t.ticker_code,
                        t.t0_price,
                        t.t0_timestamp,
                        t.status,
                        COALESCE(
                            json_agg(
                                json_build_object(
                                    'day', p.day_offset,
                                    'price', p.price
                                ) ORDER BY p.day_offset
                            ) FILTER (WHERE p.price IS NOT NULL),
                            '[]'
                        ) as price_history
                    FROM tracking_tasks t
                    LEFT JOIN price_history p ON t.tracking_id = p.tracking_id
                    WHERE t.news_id = %s
                    GROUP BY t.ticker_code, t.t0_price, t.t0_timestamp, t.status
                """, (news_id,))
            else:
                # SQLite 不支持 json_agg
                cur.execute("""
                    SELECT 
                        t.ticker_code,
                        t.t0_price,
                        t.t0_timestamp,
                        t.status
                    FROM tracking_tasks t
                    WHERE t.news_id = ?
                """, (news_id,))
                
                tasks = [dict(row) for row in cur.fetchall()]
                results = []
                for task in tasks:
                    cur.execute("""
                        SELECT day_offset as day, price
                        FROM price_history
                        WHERE tracking_id = (
                            SELECT tracking_id FROM tracking_tasks 
                            WHERE news_id = ? AND ticker_code = ? LIMIT 1
                        )
                        ORDER BY day_offset
                    """, (news_id, task['ticker_code']))
                    price_history = [dict(p) for p in cur.fetchall()]
                    
                    # 计算最终PnL
                    t0_price = task['t0_price']
                    if price_history and len(price_history) > 0:
                        final_price = price_history[-1]['price']
                        pnl = ((final_price - t0_price) / t0_price) * 100
                    else:
                        final_price = t0_price
                        pnl = 0
                    
                    results.append({
                        'code': task['ticker_code'],
                        't0_price': float(t0_price),
                        't7_price': float(final_price),
                        'pnl': f"{pnl:+.2f}%",
                        'status': task['status'],
                        'price_history': price_history
                    })
                return results
                
                rows = cur.fetchall()
                
                results = []
                for row in rows:
                    ticker_code, t0_price, t0_timestamp, status, price_history = row
                    
                    # 计算最终PnL
                    if price_history and len(price_history) > 0:
                        final_price = price_history[-1]['price']
                        pnl = ((final_price - t0_price) / t0_price) * 100
                    else:
                        final_price = t0_price
                        pnl = 0
                    
                    results.append({
                        'code': ticker_code,
                        't0_price': float(t0_price),
                        't7_price': float(final_price),
                        'pnl': f"{pnl:+.2f}%",
                        'status': status,
                        'price_history': price_history
                    })
                
                return results
    
    def get_active_trackings(self) -> List[Dict]:
        """获取所有活跃的追踪任务"""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM tracking_tasks
                WHERE status = 'active'
                ORDER BY created_at DESC
            """)
                
            rows = cur.fetchall()
            
            # 转换为字典列表
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in rows]
    
    def _generate_tracking_id(self) -> str:
        """生成追踪任务ID"""
        return f"TRK{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6]}"
    
    def _get_current_price(self, ticker_code: str) -> float:
        """
        获取股票当前价格
        
        Args:
            ticker_code: 股票代码
            
        Returns:
            当前价格
        """
        try:
            import tushare as ts
            
            # 解析股票代码
            code = ticker_code.split('.')[0]
            
            # 获取实时行情
            df = ts.get_realtime_quotes(code)
            
            if not df.empty:
                price = float(df.iloc[0]['price'])
                return price
            else:
                logger.warning(f"无法获取价格: {ticker_code}, 使用模拟价格")
                return 100.0  # 模拟价格
                
        except Exception as e:
            logger.error(f"获取价格失败: {ticker_code} - {e}")
            return 100.0  # 降级返回模拟价格
    
    def _get_latest_price(self, tracking_id: str) -> float:
        """获取追踪任务的最新价格"""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if self.db.db_type == 'postgresql':
                cur.execute("""
                    SELECT price FROM price_history
                    WHERE tracking_id = %s
                    ORDER BY time DESC
                    LIMIT 1
                """, (tracking_id,))
            else:
                cur.execute("""
                    SELECT price FROM price_history
                    WHERE tracking_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (tracking_id,))
                
                row = cur.fetchone()
                return float(row[0]) if row else 0.0
    
    def _save_price_history(
        self, 
        tracking_id: str, 
        ticker_code: str,
        price: float,
        day_offset: int
    ):
        """保存价格历史"""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if self.db.db_type == 'postgresql':
                cur.execute("""
                    INSERT INTO price_history 
                    (time, tracking_id, ticker_code, price, day_offset)
                    VALUES (NOW(), %s, %s, %s, %s)
                """, (tracking_id, ticker_code, price, day_offset))
            else:
                cur.execute("""
                    INSERT INTO price_history 
                    (tracking_id, ticker_code, price, day_offset)
                    VALUES (?, ?, ?, ?)
                """, (tracking_id, ticker_code, price, day_offset))
