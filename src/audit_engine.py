"""
AI审计引擎
使用LLM进行新闻语义审计
"""
import logging
import json
import random
import datetime
from typing import Dict
import os

from .llm_cache import LLMCache

logger = logging.getLogger(__name__)


class AuditEngine:
    """AI审计引擎"""
    
    def __init__(self, config: Dict, db=None):
        """
        初始化审计引擎
        
        Args:
            config: LLM配置
            db: 数据库实例(可选,用于加载动态权重)
        """
        self.config = config
        self.provider = config.get('provider', 'openai')
        self.model = config.get('model', 'gpt-4o')
        self.api_key = config.get('api_key') or os.getenv('OPENAI_API_KEY')
        # 方案2: 提高基础 temperature 并引入随机波动增加输出多样性\r\n        base_temp = config.get('temperature', 0.5)\r\n        self.temperature = base_temp + random.uniform(-0.1, 0.1)
        self.max_tokens = config.get('max_tokens', 2000)
        self.thinking_level = config.get('thinking_level', 'low')  # 新增: Gemini 3 思考等级
        self.db = db
        
        # 加载提示词模板
        self.prompt_template = self._load_prompt_template()
        
        # 加载JSON Schema
        self.json_schema = self._load_json_schema()
        
        # 初始化LLM客户端
        self._init_client()
        
        # 加载动态权重配置
        self.dynamic_weights = self._load_latest_weights()
        
        # 初始化 LLM 缓存
        self.cache = LLMCache()
        
        logger.info(f"AI审计引擎初始化完成: provider={self.provider}, model={self.model}")
        logger.info(f"动态权重配置: {self.dynamic_weights}")
    
    def _init_client(self):
        """初始化LLM客户端"""
        if self.provider == 'openai':
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                logger.info("OpenAI客户端初始化成功")
            except ImportError:
                logger.error("OpenAI SDK未安装,请运行: pip install openai")
                self.client = None
                
        elif self.provider == 'anthropic':
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=self.api_key)
                logger.info("Anthropic客户端初始化成功")
            except ImportError:
                logger.error("Anthropic SDK未安装,请运行: pip install anthropic")
                self.client = None
                
        elif self.provider == 'gemini':
            # 使用 OpenAI 兼容模式调用 Gemini API (最稳定的方式)
            # 文档: https://ai.google.dev/gemini-api/docs/openai
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
                )
                logger.info(f"Gemini客户端初始化成功 (OpenAI兼容模式): {self.model}")
            except ImportError:
                logger.error("OpenAI SDK未安装,请运行: pip install openai")
                self.client = None
            except Exception as e:
                logger.error(f"Gemini初始化失败: {e}")
                self.client = None
        else:
            logger.warning(f"未知的LLM提供商: {self.provider}")
            self.client = None
    
    def _load_prompt_template(self) -> str:
        """加载提示词模板"""
        template_path = "NewsTrace_Skills/prompt_templates/semantic_audit_v2.txt"
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            logger.info(f"提示词模板加载成功: {template_path}")
            return template
        except FileNotFoundError:
            logger.warning(f"提示词模板未找到: {template_path}, 尝试加载 v1 版本")
            template_path_v1 = "NewsTrace_Skills/prompt_templates/semantic_audit.txt"
            try:
                with open(template_path_v1, 'r', encoding='utf-8') as f:
                    template = f.read()
                return template
            except FileNotFoundError:
                return self._get_default_prompt_template()
    
    def _get_default_prompt_template(self) -> str:
        """获取默认提示词模板"""
        return """你是一个专业的金融新闻语义审计专家。请分析以下新闻,识别情绪化修饰、逻辑漏洞和翻译失真。

新闻标题: {title}
新闻内容: {content}
新闻来源: {source}

请按照以下JSON格式输出审计结果:
{{
  "audit_result": {{
    "score": <0-100的整数>,
    "risk_level": "<High|Medium|Low>",
    "warnings": ["警告1", "警告2"]
  }},
  "recommended_tickers": [
    {{
      "code": "股票代码",
      "name": "股票名称",
      "logic": "推荐逻辑"
    }}
  ]
}}
"""
    
    def _load_json_schema(self) -> Dict:
        """加载JSON Schema"""
        schema_path = "NewsTrace_Skills/schemas/audit_result.json"
        
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)
            logger.info("JSON Schema加载成功")
            return schema
        except FileNotFoundError:
            logger.warning(f"JSON Schema未找到: {schema_path}")
            return {}
    
    def _load_latest_weights(self) -> Dict:
        """从数据库加载最新权重配置"""
        # 默认权重配置
        default_weights = {
            "hype_language": -20.0,
            "policy_demand": 15.0,
            "uncertainty": -30.0,
            "logical_rigor": 25.0,
            "data_support": 20.0
        }
        
        if self.db is None:
            logger.info("数据库未提供,使用默认权重配置")
            return default_weights
        
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 从视图获取最新权重
                cursor.execute("""
                    SELECT feature_name, current_weight
                    FROM v_latest_weights
                """)
                
                rows = cursor.fetchall()
                
                if rows:
                    weights = {}
                    for row in rows:
                        feature_name, current_weight = row
                        weights[feature_name] = float(current_weight)
                    
                    logger.info(f"从数据库加载了 {len(weights)} 个权重配置")
                    return weights
                else:
                    logger.info("数据库中无权重记录,使用默认配置")
                    return default_weights
                    
        except Exception as e:
            logger.error(f"加载权重配置失败: {e}, 使用默认配置")
            return default_weights
    
    def audit(self, news: Dict) -> Dict:
        """
        审计新闻
        
        Args:
            news: 新闻字典 {title, content, source}
            
        Returns:
            审计结果字典
        """
        logger.debug(f"审计新闻: {news.get('title', '')[:50]}")
        
        if self.client is None:
            logger.error("LLM客户端未初始化")
            return self._get_fallback_result()
        
        title = news.get('title', '')
        content = news.get('content', '')
        
        # 检查缓存
        cached_result = self.cache.get(title, content)
        if cached_result:
            logger.info(f"缓存命中: {title[:30]}...")
            return cached_result
        
        try:
            # 构建提示词
            prompt = self._build_prompt(news)
            
            # 调用LLM
            result = self._call_llm(prompt)
            
            # 验证JSON Schema
            validated_result = self._validate_result(result)
            
            # 写入缓存
            self.cache.set(title, content, validated_result)
            
            return validated_result
            
        except Exception as e:
            logger.error(f"审计失败: {e}")
            return self._get_fallback_result()
    
    def _build_prompt(self, news: Dict) -> str:
        """构建提示词(包含动态指令和时间上下文)"""
        # 先生成动态指令
        dynamic_instruction = self._generate_dynamic_instruction()
        
        # 方案4: 注入时间上下文
        current_date = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M")
        market_context = self._get_market_context()
        
        # 一次性填充所有占位符
        full_prompt = self.prompt_template.format(
            title=news.get('title', ''),
            content=news.get('content', '')[:1000],  # 限制长度
            source=news.get('source', 'Unknown'),
            dynamic_instruction=dynamic_instruction,
            current_date=current_date,
            market_context=market_context
        )
        
        return full_prompt
    
    def _get_market_context(self) -> str:
        """
        获取当前市场上下文描述
        方案4: 增加输出多样性，可后续对接实时行情API
        """
        # 随机选择市场描述模板，增加输出多样性
        templates = [
            "市场整体情绪偏谨慎，关注政策面变化",
            "A股震荡调整中，资金偏好防御型板块",
            "市场活跃度提升，题材轮动加快",
            "观望情绪浓厚，等待财报季催化",
            "外围市场波动加剧，避险情绪上升",
            "成交量萎缩，市场等待方向选择",
            "热点板块轮动快速，短线机会为主",
            "资金面相对宽松，关注政策边际变化"
        ]
        return random.choice(templates)
    
    def _generate_dynamic_instruction(self) -> str:
        """根据当前权重生成动态审计指令"""
        instructions = ["### 动态审计指令 (基于市场反馈):"]
        w = self.dynamic_weights
        
        # 方案5: 随机选择本次审计的特别关注点
        special_focus_options = [
            "⚡ 本次审计特别关注：新闻来源的权威性和历史准确率",
            "⚡ 本次审计特别关注：时间敏感性——这条新闻的时效窗口有多长？",
            "⚡ 本次审计特别关注：逆向思维——如果这条新闻是利空而非利好呢？",
            "⚡ 本次审计特别关注：板块联动——哪些相关板块可能受到波及？",
            "⚡ 本次审计特别关注：情绪指标——市场对此类消息的历史反应模式",
            "⚡ 本次审计特别关注：信息对称性——该消息是否已被市场充分消化？",
            "⚡ 本次审计特别关注：政策敏感度——监管层可能如何解读此消息？",
            "⚡ 本次审计特别关注：资金面——该消息对市场流动性有何影响？"
        ]
        instructions.append(random.choice(special_focus_options))
        
        # 标题党/夸大表达
        if w.get("hype_language", -20) > -5:
            instructions.append("- ⚠️ 市场处于情绪亢奋期:暂停对'夸大表达'的降权,将其视为动量因子。")
        elif w.get("hype_language", -20) < -30:
            instructions.append("- 🚫 高度警惕夸大表达:市场对标题党惩罚严厉,大幅降权。")
        
        # 政策强度
        if w.get("policy_demand", 15) > 20:
            instructions.append("- ✅ 强语态偏好:对于'要求/必须'类词汇,给予额外加权。")
        elif w.get("policy_demand", 15) < 5:
            instructions.append("- ⚠️ 政策疲劳:市场对政策类新闻反应钝化,降低权重。")
        
        # 不确定性
        if w.get("uncertainty", -30) > -15:
            instructions.append("- 📊 容忍不确定性:市场接受'可能/或将'等模糊表达,适度放宽。")
        elif w.get("uncertainty", -30) < -40:
            instructions.append("- ⛔ 零容忍不确定性:严格惩罚模糊表达,要求明确性。")
        
        # 逻辑严谨性
        if w.get("logical_rigor", 25) > 30:
            instructions.append("- 🎯 逻辑为王:市场高度奖励逻辑严密的分析,大幅加分。")
        
        # 数据支撑
        if w.get("data_support", 20) > 25:
            instructions.append("- 📈 数据驱动:有具体数据支撑的新闻获得显著加权。")
        
        instructions.append("\n**重要**: 请在输出中包含 `detected_features` 字段,列出检测到的特征(如 hype_language, policy_demand 等)。")
        
        return "\n".join(instructions)
    
    def _call_llm(self, prompt: str, max_retries: int = 3) -> Dict:
        """
        调用LLM API
        
        Args:
            prompt: 提示词
            max_retries: 最大重试次数
            
        Returns:
            解析后的JSON结果
        """
        for attempt in range(max_retries):
            try:
                if self.provider == 'openai':
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "你是一个专业的金融新闻审计专家。"},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        response_format={"type": "json_object"}
                    )
                    
                    content = response.choices[0].message.content
                    result = json.loads(content)
                    return result
                    
                elif self.provider == 'anthropic':
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        messages=[
                            {"role": "user", "content": prompt}
                        ]
                    )
                    
                    content = response.content[0].text
                    result = json.loads(content)
                    return result
                    
                elif self.provider == 'gemini':
                    # 使用 OpenAI 兼容模式
                    logger.info(f"[Gemini] 调用模型: {self.model}")
                    
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "你是一个专业的金融新闻审计专家。请以 JSON 格式返回分析结果。"},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        response_format={"type": "json_object"}
                    )
                    
                    content = response.choices[0].message.content
                    logger.info(f"[Gemini API] 响应成功, 长度: {len(content) if content else 0}")
                    
                    result = json.loads(content)
                    return result
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                    
            except Exception as e:
                logger.error(f"LLM调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
        
        raise Exception("LLM调用失败,已达到最大重试次数")
    
    def _parse_gemini_response(self, response_text: str) -> Dict:
        """
        解析 Gemini 响应 (参考 daily_stock_analysis 项目实现)
        
        尝试从响应中提取 JSON，包含多种容错处理
        """
        import re
        
        try:
            # 清理响应文本：移除 markdown 代码块标记
            cleaned_text = response_text.strip()
            
            if '```json' in cleaned_text:
                cleaned_text = cleaned_text.replace('```json', '').replace('```', '')
            elif '```' in cleaned_text:
                cleaned_text = cleaned_text.replace('```', '')
            
            cleaned_text = cleaned_text.strip()
            
            # 尝试找到 JSON 内容
            json_start = cleaned_text.find('{')
            json_end = cleaned_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = cleaned_text[json_start:json_end]
                
                # 修复常见的 JSON 问题
                json_str = self._fix_json_string(json_str)
                
                logger.info(f"[JSON解析] 提取内容长度: {len(json_str)}")
                data = json.loads(json_str)
                return data
            else:
                # 没有找到 JSON
                logger.warning(f"[JSON解析] 未找到 JSON 结构, 返回默认结果")
                logger.debug(f"原始响应: {response_text[:200]}")
                return self._get_fallback_result()
                
        except json.JSONDecodeError as e:
            logger.error(f"[JSON解析] 解析失败: {e}")
            logger.debug(f"尝试解析的内容: {response_text[:500]}")
            raise
    
    def _fix_json_string(self, json_str: str) -> str:
        """
        修复常见的 JSON 格式问题 (参考 daily_stock_analysis 项目)
        """
        import re
        
        # 移除 JavaScript 风格的注释
        json_str = re.sub(r'//.*?\n', '\n', json_str)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # 修复尾随逗号 (JSON 不允许)
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # 确保布尔值是小写 (Python True/False 转 JSON true/false)
        json_str = json_str.replace('True', 'true').replace('False', 'false')
        
        # 移除可能的 BOM 或其他控制字符
        json_str = json_str.strip('\ufeff\u200b\u200c\u200d')
        
        return json_str
    
    def _validate_result(self, result: Dict) -> Dict:
        """
        验证结果是否符合JSON Schema
        
        Args:
            result: LLM返回的结果
            
        Returns:
            验证后的结果
        """
        # 检查必需字段
        if 'audit_result' not in result:
            logger.warning("缺少audit_result字段")
            result['audit_result'] = {
                'score': 50,
                'risk_level': 'Medium',
                'warnings': ['审计结果格式不完整'],
                'detected_features': []  # 新增
            }
        
        if 'recommended_tickers' not in result:
            logger.warning("缺少recommended_tickers字段")
            result['recommended_tickers'] = []
        
        # 确保 detected_features 字段存在
        if 'detected_features' not in result['audit_result']:
            result['audit_result']['detected_features'] = []
        
        # 验证评分范围
        score = result['audit_result'].get('score', 50)
        if not (0 <= score <= 100):
            logger.warning(f"评分超出范围: {score}, 已修正为50")
            result['audit_result']['score'] = 50
        
        # 验证风险等级
        risk_level = result['audit_result'].get('risk_level', 'Medium')
        if risk_level not in ['High', 'Medium', 'Low']:
            logger.warning(f"无效的风险等级: {risk_level}, 已修正为Medium")
            result['audit_result']['risk_level'] = 'Medium'
        
        # 限制推荐标的数量
        if len(result['recommended_tickers']) > 3:
            logger.warning(f"推荐标的过多: {len(result['recommended_tickers'])}, 已截取前3个")
            result['recommended_tickers'] = result['recommended_tickers'][:3]
        
        return result
    
    def _get_fallback_result(self) -> Dict:
        """获取降级结果"""
        return {
            'audit_result': {
                'score': 50,
                'risk_level': 'Medium',
                'warnings': ['审计引擎不可用,使用降级结果']
            },
            'recommended_tickers': []
        }
