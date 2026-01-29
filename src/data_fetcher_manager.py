# -*- coding: utf-8 -*-
"""
统一数据源管理器
从 daily_stock_analysis 项目借鉴并适配

设计模式：策略模式 (Strategy Pattern)
- BaseFetcher: 抽象基类，定义统一接口
- DataFetcherManager: 策略管理器，实现自动切换

防封禁策略：
1. 每个 Fetcher 内置流控逻辑
2. 失败自动切换到下一个数据源
3. 指数退避重试机制
"""

import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict

import pandas as pd

logger = logging.getLogger(__name__)

# === 标准化列名定义 ===
STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']


class DataFetchError(Exception):
    """数据获取异常基类"""
    pass


class RateLimitError(DataFetchError):
    """API 速率限制异常"""
    pass


class DataSourceUnavailableError(DataFetchError):
    """数据源不可用异常"""
    pass


class BaseFetcher(ABC):
    """
    数据源抽象基类
    
    职责：
    1. 定义统一的数据获取接口
    2. 提供数据标准化方法
    3. 实现通用的技术指标计算
    """
    
    name: str = "BaseFetcher"
    priority: int = 99  # 优先级数字越小越优先
    
    @abstractmethod
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从数据源获取原始数据（子类必须实现）"""
        pass
    
    @abstractmethod
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """标准化数据列名（子类必须实现）"""
        pass
    
    def get_daily_data(
        self, 
        stock_code: str, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30
    ) -> pd.DataFrame:
        """获取日线数据（统一入口）"""
        # 计算日期范围
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        if start_date is None:
            start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=days * 2)
            start_date = start_dt.strftime('%Y-%m-%d')
        
        logger.info(f"[{self.name}] 获取 {stock_code} 数据: {start_date} ~ {end_date}")
        
        try:
            raw_df = self._fetch_raw_data(stock_code, start_date, end_date)
            
            if raw_df is None or raw_df.empty:
                raise DataFetchError(f"[{self.name}] 未获取到 {stock_code} 的数据")
            
            df = self._normalize_data(raw_df, stock_code)
            df = self._clean_data(df)
            df = self._calculate_indicators(df)
            
            logger.info(f"[{self.name}] {stock_code} 获取成功，共 {len(df)} 条数据")
            return df
            
        except Exception as e:
            logger.error(f"[{self.name}] 获取 {stock_code} 失败: {str(e)}")
            raise DataFetchError(f"[{self.name}] {stock_code}: {str(e)}") from e
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗"""
        df = df.copy()
        
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.dropna(subset=['close', 'volume'])
        df = df.sort_values('date', ascending=True).reset_index(drop=True)
        
        return df
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        df = df.copy()
        
        df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()
        df['ma10'] = df['close'].rolling(window=10, min_periods=1).mean()
        df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
        
        avg_volume_5 = df['volume'].rolling(window=5, min_periods=1).mean()
        df['volume_ratio'] = df['volume'] / avg_volume_5.shift(1)
        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
        
        for col in ['ma5', 'ma10', 'ma20', 'volume_ratio']:
            if col in df.columns:
                df[col] = df[col].round(2)
        
        return df
    
    @staticmethod
    def random_sleep(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """智能随机休眠（防封禁）"""
        sleep_time = random.uniform(min_seconds, max_seconds)
        time.sleep(sleep_time)


class AkShareFetcher(BaseFetcher):
    """AkShare 数据源"""
    
    name = "AkShareFetcher"
    priority = 1
    
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        try:
            import akshare as ak
            
            # 转换日期格式
            start = start_date.replace('-', '')
            end = end_date.replace('-', '')
            
            # 获取日线数据
            df = ak.stock_zh_a_hist(
                symbol=stock_code.split('.')[0],
                period="daily",
                start_date=start,
                end_date=end,
                adjust="qfq"
            )
            
            self.random_sleep(0.5, 1.5)
            return df
            
        except Exception as e:
            raise DataFetchError(f"AkShare 获取失败: {e}")
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        column_mapping = {
            '日期': 'date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '成交额': 'amount',
            '涨跌幅': 'pct_chg'
        }
        df = df.rename(columns=column_mapping)
        return df


class TuShareFetcher(BaseFetcher):
    """Tushare 数据源"""
    
    name = "TuShareFetcher"
    priority = 2
    
    def __init__(self, token: str = None):
        import os
        self.token = token or os.getenv("TUSHARE_TOKEN")
        self.pro = None
        
        if self.token:
            try:
                import tushare as ts
                ts.set_token(self.token)
                self.pro = ts.pro_api()
                self.priority = 0  # 有 Token 时提升优先级
            except Exception as e:
                logger.warning(f"Tushare 初始化失败: {e}")
    
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if not self.pro:
            raise DataFetchError("Tushare 未配置 Token")
        
        try:
            # 转换股票代码格式
            if '.' not in stock_code:
                if stock_code.startswith('6'):
                    ts_code = f"{stock_code}.SH"
                else:
                    ts_code = f"{stock_code}.SZ"
            else:
                ts_code = stock_code
            
            df = self.pro.daily(
                ts_code=ts_code,
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', '')
            )
            
            self.random_sleep(0.3, 0.8)
            return df
            
        except Exception as e:
            raise DataFetchError(f"Tushare 获取失败: {e}")
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        column_mapping = {
            'trade_date': 'date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'vol': 'volume',
            'amount': 'amount',
            'pct_chg': 'pct_chg'
        }
        df = df.rename(columns=column_mapping)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
        return df


class DataFetcherManager:
    """
    数据源策略管理器
    
    职责：
    1. 管理多个数据源（按优先级排序）
    2. 自动故障切换（Failover）
    3. 提供统一的数据获取接口
    """
    
    def __init__(self, fetchers: Optional[List[BaseFetcher]] = None):
        self._fetchers: List[BaseFetcher] = []
        
        if fetchers:
            self._fetchers = sorted(fetchers, key=lambda f: f.priority)
        else:
            self._init_default_fetchers()
    
    def _init_default_fetchers(self) -> None:
        """初始化默认数据源列表"""
        fetchers = [
            AkShareFetcher(),
            TuShareFetcher(),
        ]
        
        self._fetchers = sorted(fetchers, key=lambda f: f.priority)
        
        priority_info = ", ".join([f"{f.name}(P{f.priority})" for f in self._fetchers])
        logger.info(f"已初始化 {len(self._fetchers)} 个数据源: {priority_info}")
    
    def add_fetcher(self, fetcher: BaseFetcher) -> None:
        """添加数据源并重新排序"""
        self._fetchers.append(fetcher)
        self._fetchers.sort(key=lambda f: f.priority)
    
    def get_daily_data(
        self, 
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30
    ) -> Tuple[pd.DataFrame, str]:
        """获取日线数据（自动切换数据源）"""
        errors = []
        
        for fetcher in self._fetchers:
            try:
                logger.info(f"尝试使用 [{fetcher.name}] 获取 {stock_code}...")
                df = fetcher.get_daily_data(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    days=days
                )
                
                if df is not None and not df.empty:
                    logger.info(f"[{fetcher.name}] 成功获取 {stock_code}")
                    return df, fetcher.name
                    
            except Exception as e:
                error_msg = f"[{fetcher.name}] 失败: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue
        
        error_summary = f"所有数据源获取 {stock_code} 失败:\n" + "\n".join(errors)
        logger.error(error_summary)
        raise DataFetchError(error_summary)
    
    @property
    def available_fetchers(self) -> List[str]:
        """返回可用数据源名称列表"""
        return [f.name for f in self._fetchers]
