# NewsTrace 测试套件

## 测试结构

```
tests/
├── conftest.py              # Pytest配置和夹具
├── test_audit_engine.py     # 审计引擎测试
├── test_news_fetcher.py     # 新闻采集器测试
└── test_source_rating.py    # 信源评级测试
```

## 运行测试

### 运行所有测试

```bash
pytest tests/
```

### 运行特定测试文件

```bash
pytest tests/test_audit_engine.py
```

### 运行特定测试类

```bash
pytest tests/test_audit_engine.py::TestAuditEngine
```

### 运行特定测试方法

```bash
pytest tests/test_audit_engine.py::TestAuditEngine::test_init
```

### 显示详细输出

```bash
pytest tests/ -v
```

### 显示测试覆盖率

```bash
pytest tests/ --cov=src --cov-report=html
```

## 测试夹具 (Fixtures)

### mock_config

模拟的完整配置,包含:

- LLM配置 (OpenAI/Anthropic)
- 数据源配置 (Tushare/AkShare)
- 追踪配置
- 数据库配置

### sample_news

示例新闻数据,用于测试新闻处理功能

### sample_audit_result

示例审计结果,用于测试结果处理功能

## 注意事项

1. 测试使用模拟数据,不会连接真实的API或数据库
2. 需要安装 pytest: `pip install pytest pytest-cov`
3. 部分测试可能需要模拟外部依赖

## 待添加的测试

- [ ] 数据库操作测试
- [ ] 追踪调度器测试
- [ ] API端点测试
- [ ] 集成测试
- [ ] 性能测试
