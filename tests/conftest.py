"""
Pytest配置文件
"""
import pytest
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_config():
    """模拟配置"""
    return {
        'llm': {
            'provider': 'openai',
            'model': 'gpt-4o',
            'api_key': 'test-key',
            'temperature': 0.3,
            'max_tokens': 2000
        },
        'data_source': {
            'provider': 'tushare',
            'api_key': 'test-token'
        },
        'tracking': {
            'duration_days': 7,
            'update_time': '15:30',
            'timezone': 'Asia/Shanghai'
        },
        'database': {
            'type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'database': 'test_newstrace',
            'username': 'test_user',
            'password': 'test_password'
        }
    }


@pytest.fixture
def sample_news():
    """示例新闻"""
    return {
        'title': '消费税改革方案出台',
        'content': '财政部发布消费税改革方案,将对部分消费品进行税率调整...',
        'source': '财联社',
        'timestamp': '2026-01-25 09:35:00'
    }


@pytest.fixture
def sample_audit_result():
    """示例审计结果"""
    return {
        'score': 75,
        'risk_level': 'Medium',
        'warnings': ['标题存在情绪化修饰'],
        'semantic_deviations': [],
        'recommended_tickers': [
            {
                'code': '600519',
                'name': '贵州茅台',
                'logic': '消费税改革可能影响高端白酒销售',
                'beta': 'negative'
            }
        ]
    }
