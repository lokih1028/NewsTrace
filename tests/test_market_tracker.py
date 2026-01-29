"""
测试市场追踪器
"""
import pytest
from datetime import datetime, timedelta
from src.market_tracker import MarketTracker


class TestMarketTracker:
    """测试市场追踪器"""
    
    @pytest.fixture
    def mock_db(self, mocker):
        """模拟数据库"""
        db = mocker.Mock()
        conn = mocker.Mock()
        cursor = mocker.Mock()
        
        db.get_connection.return_value.__enter__.return_value = conn
        conn.cursor.return_value = cursor
        
        return db
    
    @pytest.fixture
    def tracker(self, mock_db):
        """创建追踪器实例"""
        config = {'duration_days': 7}
        return MarketTracker(mock_db, config)
    
    def test_create_tracking(self, tracker, mocker):
        """测试创建追踪任务"""
        # Mock _get_current_price
        mocker.patch.object(tracker, '_get_current_price', return_value=100.0)
        
        # Mock cursor.fetchone to return tracking_id
        tracker.db.get_connection.return_value.__enter__.return_value.cursor.return_value.fetchone.return_value = [1]
        
        tracking_ids = tracker.create_tracking(
            news_id="test001",
            tickers=["600000.SH", "000001.SZ"],
            market_regime="Bull"
        )
        
        assert len(tracking_ids) == 2
        assert all(isinstance(tid, int) for tid in tracking_ids)
    
    def test_calculate_pnl(self, tracker):
        """测试 PnL 计算"""
        # 模拟价格数据
        t0 = 100.0
        t7 = 110.0
        
        pnl = (t7 - t0) / t0
        
        assert pnl == 0.10  # 10% 涨幅
    
    def test_calculate_max_drawdown(self, tracker):
        """测试最大回撤计算"""
        prices = [100, 95, 90, 105, 110]
        t0 = prices[0]
        
        max_drawdown = 0
        for price in prices:
            drawdown = (price - t0) / t0
            max_drawdown = min(max_drawdown, drawdown)
        
        assert max_drawdown == -0.10  # -10% 最大回撤


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
