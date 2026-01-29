# NewsTrace Skills 配置文件

## 基础配置

```yaml
# config.yaml
newstrace:
  # LLM配置
  llm:
    provider: "openai"  # openai / anthropic / azure
    model: "gpt-4o"
    api_key: "${OPENAI_API_KEY}"
    temperature: 0.3
    max_tokens: 2000
    
  # 数据源配置
  data_source:
    provider: "tushare"  # tushare / akshare
    api_key: "${TUSHARE_TOKEN}"
    
  # 追踪配置
  tracking:
    duration_days: 7
    update_time: "15:30"  # A股收盘后30分钟
    timezone: "Asia/Shanghai"
    
  # 数据库配置
  database:
    type: "postgresql"  # postgresql / mongodb
    host: "localhost"
    port: 5432
    database: "newstrace"
    username: "${DB_USER}"
    password: "${DB_PASSWORD}"
    
  # 风险阈值
  risk_thresholds:
    high_risk_score: 50  # 低于此分数为高风险
    medium_risk_score: 70
    rumor_rate_blacklist: 0.30  # 辟谣率超过30%加入黑名单
    
  # 推荐配置
  recommendation:
    max_tickers_per_news: 3
    min_logic_score: 40
```

## 环境变量

```bash
# .env
OPENAI_API_KEY=sk-xxx
TUSHARE_TOKEN=your_tushare_token
DB_USER=newstrace_user
DB_PASSWORD=your_secure_password
```

## JSON Schema配置

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "NewsTrace Audit Result",
  "type": "object",
  "required": ["audit_result", "recommended_tickers"],
  "properties": {
    "audit_result": {
      "type": "object",
      "required": ["score", "risk_level", "warnings"],
      "properties": {
        "score": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100,
          "description": "逻辑公信力评分"
        },
        "risk_level": {
          "type": "string",
          "enum": ["High", "Medium", "Low"],
          "description": "风险等级"
        },
        "warnings": {
          "type": "array",
          "items": {"type": "string"},
          "description": "风险警告列表"
        },
        "semantic_deviations": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "type": {"type": "string"},
              "original": {"type": "string"},
              "translated": {"type": "string"},
              "impact": {"type": "string"}
            }
          }
        }
      }
    },
    "recommended_tickers": {
      "type": "array",
      "minItems": 1,
      "maxItems": 3,
      "items": {
        "type": "object",
        "required": ["code", "name", "logic"],
        "properties": {
          "code": {
            "type": "string",
            "pattern": "^\\d{6}\\.(SH|SZ)$",
            "description": "股票代码"
          },
          "name": {
            "type": "string",
            "description": "股票名称"
          },
          "logic": {
            "type": "string",
            "description": "推荐逻辑"
          },
          "beta": {
            "type": "string",
            "enum": ["高贝塔", "低贝塔"],
            "description": "波动属性"
          }
        }
      }
    }
  }
}
```
