"""
审计引擎测试
"""
import pytest
from src.audit_engine import AuditEngine


class TestAuditEngine:
    """审计引擎测试类"""
    
    def test_init(self, mock_config):
        """测试审计引擎初始化"""
        engine = AuditEngine(mock_config['llm'])
        assert engine.config == mock_config['llm']
        assert engine.provider == 'openai'
        assert engine.model == 'gpt-4o'
    
    def test_build_prompt(self, mock_config, sample_news):
        """测试提示词构建"""
        engine = AuditEngine(mock_config['llm'])
        prompt = engine._build_prompt(sample_news)
        
        # 验证提示词包含关键信息
        assert '消费税改革方案出台' in prompt
        assert '财联社' in prompt
        assert sample_news['content'] in prompt
    
    def test_get_default_prompt_template(self, mock_config):
        """测试默认提示词模板"""
        engine = AuditEngine(mock_config['llm'])
        template = engine._get_default_prompt_template()
        
        assert '新闻标题' in template
        assert '新闻内容' in template
        assert '信源' in template
    
    def test_validate_result_valid(self, mock_config, sample_audit_result):
        """测试结果验证 - 有效结果"""
        engine = AuditEngine(mock_config['llm'])
        
        # 应该不抛出异常
        validated = engine._validate_result(sample_audit_result)
        assert validated['score'] == 75
        assert validated['risk_level'] == 'Medium'
    
    def test_validate_result_invalid_score(self, mock_config):
        """测试结果验证 - 无效评分"""
        engine = AuditEngine(mock_config['llm'])
        
        invalid_result = {
            'score': 150,  # 超出范围
            'risk_level': 'Medium',
            'warnings': [],
            'semantic_deviations': [],
            'recommended_tickers': []
        }
        
        # 应该使用降级结果
        validated = engine._validate_result(invalid_result)
        assert validated['score'] == 50  # 降级默认值
    
    def test_get_fallback_result(self, mock_config):
        """测试降级结果"""
        engine = AuditEngine(mock_config['llm'])
        fallback = engine._get_fallback_result()
        
        assert fallback['score'] == 50
        assert fallback['risk_level'] == 'Medium'
        assert '审计失败' in fallback['warnings'][0]
