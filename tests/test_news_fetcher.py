"""
新闻采集器测试
"""
import pytest
from src.news_fetcher import NewsFetcher


class TestNewsFetcher:
    """新闻采集器测试类"""
    
    def test_init_tushare(self, mock_config):
        """测试Tushare初始化"""
        fetcher = NewsFetcher(mock_config['data_source'])
        assert fetcher.provider == 'tushare'
        assert fetcher.api_key == 'test-token'
    
    def test_init_akshare(self, mock_config):
        """测试AkShare初始化"""
        config = mock_config['data_source'].copy()
        config['provider'] = 'akshare'
        
        fetcher = NewsFetcher(config)
        assert fetcher.provider == 'akshare'
    
    def test_normalize(self, mock_config, sample_news):
        """测试新闻标准化"""
        fetcher = NewsFetcher(mock_config['data_source'])
        normalized = fetcher.normalize(sample_news)
        
        assert 'title' in normalized
        assert 'content' in normalized
        assert 'source' in normalized
        assert 'timestamp' in normalized
        assert 'url' in normalized
    
    def test_normalize_missing_fields(self, mock_config):
        """测试缺少字段的新闻标准化"""
        fetcher = NewsFetcher(mock_config['data_source'])
        
        incomplete_news = {
            'title': '测试标题'
        }
        
        normalized = fetcher.normalize(incomplete_news)
        
        # 应该填充默认值
        assert normalized['content'] == ''
        assert normalized['source'] == 'Unknown'
        assert 'timestamp' in normalized
    
    def test_switch_provider(self, mock_config):
        """测试切换数据源"""
        fetcher = NewsFetcher(mock_config['data_source'])
        assert fetcher.provider == 'tushare'
        
        fetcher.switch_provider('akshare')
        assert fetcher.provider == 'akshare'
