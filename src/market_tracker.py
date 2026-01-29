"""
市场追踪管理器 (v2.0)
支持 T+1/T+3/T+7 多时间点追踪和 PnL 计算
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)


class MarketTracker:
    """市场追踪管理器 - 支持多时间点追踪"""
    
    def __init__(self, db, config: Dict):
        """
        初始化市场追踪器
        
        Args:
            db: 数据库实例
            config: 追踪配置
        """
        self.db = db
        self.config = config
        self.duration_days = config.get('duration_days', 7)
        
        logger.info(f"市场追踪器初始化完成: duration_days={self.duration_days}")
    
    def create_tracking(
        self, 
        news_id: str, 
        tickers: List[str],
        market_regime: str = "Neutral"
    ) -> List[int]:
        """
        创建市场追踪任务
        
        Args:
            news_id: 新闻ID
            tickers: 标的代码列表
            market_regime: 市场状态 (Bull/Bear/Neutral)
            
        Returns:
            追踪任务ID列表
        """
        tracking_ids = []
        
        for ticker in tickers:
            try:
                # 获取当前价格作为 T0 价格
                t0_price = self._get_current_price(ticker)
                t0_timestamp = datetime.now()
                
                # 插入到 market_tracking 表
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO market_tracking 
                        (news_id, ticker, price_t0, t0_timestamp, market_regime, status)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING tracking_id
                    """, (
                        news_id,
                        ticker,
                        t0_price,
                        t0_timestamp,
                        market_regime,
                        'active'
                    ))
                    
                    tracking_id = cursor.fetchone()[0]
                    tracking_ids.append(tracking_id)
                    conn.commit()
                
                logger.info(f"追踪任务已创建: ID={tracking_id}, {ticker} @ {t0_price}")
                
            except Exception as e:
                logger.error(f"创建追踪任务失败: {ticker} - {e}")
        
        return tracking_ids
    
    def update_all_prices(self):
        """更新所有活跃追踪任务的价格"""
        active_trackings = self._get_active_trackings()
        
        for tracking in active_trackings:
            try:
                tracking_id = tracking['tracking_id']
                ticker = tracking['ticker']
                t0_timestamp = tracking['t0_timestamp']
                
                # 计算天数偏移
                day_offset = (datetime.now().date() - t0_timestamp.date()).days
                
                # 获取当前价格
                current_price = self._get_current_price(ticker)
                
                # 在关键时间点保存快照
                if day_offset == 1:
                    self._update_price_snapshot(tracking_id, 'price_t1', 't1_timestamp', current_price)
                    logger.info(f"T+1 快照: {ticker} @ {current_price}")
                    
                elif day_offset == 3:
                    self._update_price_snapshot(tracking_id, 'price_t3', 't3_timestamp', current_price)
                    logger.info(f"T+3 快照: {ticker} @ {current_price}")
                    
                elif day_offset == 7:
                    self._update_price_snapshot(tracking_id, 'price_t7', 't7_timestamp', current_price)
                    # T+7 时计算 PnL 和最大回撤
                    self._calculate_and_save_metrics(tracking_id)
                    logger.info(f"T+7 快照: {ticker} @ {current_price}")
                
            except Exception as e:
                logger.error(f"更新价格失败: {tracking['tracking_id']} - {e}")
    
    def check_and_close_completed(self):
        """检查并结案已完成的追踪任务"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 查找 T+7 已完成的任务
            cursor.execute("""
                SELECT tracking_id, ticker, price_t0, price_t7
                FROM market_tracking
                WHERE status = 'active'
                AND t7_timestamp IS NOT NULL
            """)
            
            completed_tasks = cursor.fetchall()
            
            for task in completed_tasks:
                tracking_id, ticker, price_t0, price_t7 = task
                
                try:
                    # 计算最终 PnL
                    if price_t7 and price_t0:
                        final_pnl = (price_t7 - price_t0) / price_t0
                        
                        # 更新状态为 closed
                        cursor.execute("""
                            UPDATE market_tracking
                            SET status = 'closed', final_pnl = %s
                            WHERE tracking_id = %s
                        """, (final_pnl, tracking_id))
                        
                        conn.commit()
                        
                        logger.info(f"追踪任务已结案: {tracking_id} - {ticker} PnL: {final_pnl:.2%}")
                    
                except Exception as e:
                    logger.error(f"结案失败: {tracking_id} - {e}")
    
    def get_t3_completed_trackings(self) -> List[Dict]:
        """
        获取 T+3 已完成的追踪任务(用于权重进化)
        
        Returns:
            包含 news_id, ai_score, features, t3_return 的字典列表
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    mt.news_id,
                    mt.ticker,
                    mt.price_t0,
                    mt.price_t3,
                    mt.market_regime,
                    n.ai_audit_result
                FROM market_tracking mt
                JOIN news n ON mt.news_id = n.news_id
                WHERE mt.t3_timestamp IS NOT NULL
                AND mt.price_t3 IS NOT NULL
                AND mt.t3_timestamp::date = CURRENT_DATE - INTERVAL '1 day'
            """)
            
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                news_id, ticker, price_t0, price_t3, market_regime, audit_result = row
                
                if audit_result and price_t0:
                    t3_return = (price_t3 - price_t0) / price_t0
                    
                    results.append({
                        'news_id': news_id,
                        'ticker': ticker,
                        'ai_audit_score': audit_result.get('score', 50),
                        'detected_features': audit_result.get('detected_features', []),
                        'actual_return_t3': t3_return,
                        'market_regime': market_regime
                    })
            
            logger.info(f"获取到 {len(results)} 个 T+3 完成的追踪任务")
            return results
    
    def get_tracking_results(self, news_id: str) -> List[Dict]:
        """获取新闻的所有追踪结果"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    ticker,
                    price_t0,
                    price_t1,
                    price_t3,
                    price_t7,
                    max_drawdown,
                    final_pnl,
                    status,
                    market_regime
                FROM market_tracking
                WHERE news_id = %s
                ORDER BY tracking_id
            """, (news_id,))
            
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                ticker, t0, t1, t3, t7, drawdown, pnl, status, regime = row
                
                results.append({
                    'ticker': ticker,
                    'price_t0': float(t0) if t0 else None,
                    'price_t1': float(t1) if t1 else None,
                    'price_t3': float(t3) if t3 else None,
                    'price_t7': float(t7) if t7 else None,
                    'max_drawdown': float(drawdown) if drawdown else None,
                    'final_pnl': float(pnl) if pnl else None,
                    'status': status,
                    'market_regime': regime
                })
            
            return results
    
    def _get_active_trackings(self) -> List[Dict]:
        """获取所有活跃的追踪任务"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT tracking_id, news_id, ticker, price_t0, t0_timestamp, market_regime
                FROM market_tracking
                WHERE status = 'active'
                ORDER BY t0_timestamp DESC
            """)
            
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    'tracking_id': row[0],
                    'news_id': row[1],
                    'ticker': row[2],
                    'price_t0': row[3],
                    't0_timestamp': row[4],
                    'market_regime': row[5]
                })
            
            return results
    
    def _update_price_snapshot(self, tracking_id: int, price_col: str, timestamp_col: str, price: float):
        """更新价格快照"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(f"""
                UPDATE market_tracking
                SET {price_col} = %s, {timestamp_col} = NOW()
                WHERE tracking_id = %s
            """, (price, tracking_id))
            
            conn.commit()
    
    def _calculate_and_save_metrics(self, tracking_id: int):
        """计算并保存 PnL 和最大回撤"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取所有价格快照
            cursor.execute("""
                SELECT price_t0, price_t1, price_t3, price_t7
                FROM market_tracking
                WHERE tracking_id = %s
            """, (tracking_id,))
            
            row = cursor.fetchone()
            if not row:
                return
            
            t0, t1, t3, t7 = row
            
            # 计算最大回撤
            prices = [p for p in [t0, t1, t3, t7] if p is not None]
            if len(prices) < 2:
                return
            
            max_drawdown = 0
            for price in prices:
                drawdown = (price - t0) / t0
                max_drawdown = min(max_drawdown, drawdown)
            
            # 计算最终 PnL
            final_pnl = (t7 - t0) / t0 if t7 and t0 else 0
            
            # 更新数据库
            cursor.execute("""
                UPDATE market_tracking
                SET max_drawdown = %s, final_pnl = %s
                WHERE tracking_id = %s
            """, (max_drawdown, final_pnl, tracking_id))
            
            conn.commit()
            
            logger.info(f"指标已计算: tracking_id={tracking_id}, "
                       f"max_drawdown={max_drawdown:.2%}, final_pnl={final_pnl:.2%}")
    
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
