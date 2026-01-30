"""
LLM 提供商抽象层
支持 OpenAI、Anthropic、Ollama 等多种 LLM 后端
"""
import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Generator
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLM 响应结构"""
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str = "stop"
    raw_response: Optional[Dict] = None


class BaseLLMProvider(ABC):
    """LLM 提供商基类"""
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """生成响应"""
        pass
    
    @abstractmethod
    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """流式生成响应"""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict:
        """获取模型信息"""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI 提供商"""
    
    def __init__(
        self,
        api_key: str = None,
        model: str = "gpt-4o",
        base_url: str = None,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = None
        
        self._init_client()
    
    def _init_client(self):
        try:
            from openai import OpenAI
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self.client = OpenAI(**kwargs)
            logger.info(f"OpenAI 提供商初始化成功: {self.model}")
        except ImportError:
            logger.error("OpenAI SDK 未安装")
    
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        if not self.client:
            raise RuntimeError("OpenAI 客户端未初始化")
        
        response = self.client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens)
        )
        
        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            finish_reason=response.choices[0].finish_reason,
            raw_response=response.model_dump()
        )
    
    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        if not self.client:
            raise RuntimeError("OpenAI 客户端未初始化")
        
        stream = self.client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def get_model_info(self) -> Dict:
        return {
            "provider": "openai",
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }


class OllamaProvider(BaseLLMProvider):
    """Ollama 本地 LLM 提供商"""
    
    def __init__(
        self,
        model: str = "llama3.1",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.3,
        max_tokens: int = 2000
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        logger.info(f"Ollama 提供商初始化: {self.model} @ {self.base_url}")
    
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        import requests
        
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": kwargs.get("model", self.model),
            "prompt": prompt,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
                "num_predict": kwargs.get("max_tokens", self.max_tokens)
            },
            "stream": False
        }
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            
            return LLMResponse(
                content=data.get("response", ""),
                model=data.get("model", self.model),
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
                finish_reason="stop",
                raw_response=data
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama 请求失败: {e}")
            raise
    
    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        import requests
        
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": kwargs.get("model", self.model),
            "prompt": prompt,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
                "num_predict": kwargs.get("max_tokens", self.max_tokens)
            },
            "stream": True
        }
        
        try:
            with requests.post(url, json=payload, stream=True, timeout=120) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama 流式请求失败: {e}")
            raise
    
    def get_model_info(self) -> Dict:
        return {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
    
    def list_models(self) -> List[str]:
        """列出可用模型"""
        import requests
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"获取 Ollama 模型列表失败: {e}")
            return []


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini 提供商 (新版 google-genai SDK)
    
    文档: https://ai.google.dev/gemini-api/docs
    迁移指南: https://ai.google.dev/gemini-api/docs/migrate
    
    免费额度:
    - 60 QPM (每分钟请求数)
    - 每日无上限
    
    获取 API Key: https://aistudio.google.com/
    """
    
    def __init__(
        self,
        api_key: str = None,
        model: str = "gemini-2.0-flash",  # 使用稳定版本
        temperature: float = 0.3,
        max_tokens: int = 2000,
        thinking_level: str = "low"  # 新增: Gemini 3 思考等级 (high/low)
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.thinking_level = thinking_level
        self.client = None
        
        if not self.api_key:
            logger.warning("GEMINI_API_KEY 未配置")
        else:
            self._init_client()
    
    def _init_client(self):
        """初始化新版 google-genai SDK 客户端"""
        try:
            from google import genai
            # 新版 SDK 使用 Client 对象
            self.client = genai.Client(api_key=self.api_key)
            logger.info(f"Gemini 提供商初始化成功 (新版SDK): {self.model}")
        except ImportError as e:
            logger.warning(f"google-genai SDK 未安装, 使用 REST API: {e}")
            logger.info("请运行: pip install google-genai")
            self.client = "REST"
        except Exception as e:
            logger.error(f"Gemini 初始化失败: {e}")
            self.client = None
    
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """使用新版 SDK 生成内容"""
        if self.client == "REST" or self.client is None:
            return self._generate_rest(prompt, **kwargs)
        
        try:
            from google.genai import types
            
            # 构建生成配置
            config = types.GenerateContentConfig(
                temperature=kwargs.get("temperature", self.temperature),
                max_output_tokens=kwargs.get("max_tokens", self.max_tokens),
            )
            
            logger.info(f"[Gemini API] 调用模型: {self.model}, Prompt长度: {len(prompt)}")
            
            # 使用新版 API 调用
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config
            )
            
            # 获取响应文本
            content = response.text
            
            # 估算 Token 数
            input_tokens = len(prompt) // 4
            output_tokens = len(content) // 4 if content else 0
            
            logger.info(f"[Gemini API] 响应成功, 长度: {len(content) if content else 0}")
            
            return LLMResponse(
                content=content,
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason="stop",
                raw_response=None
            )
        except Exception as e:
            logger.error(f"Gemini 生成失败: {e}")
            # 尝试 REST API 作为降级
            logger.info("尝试使用 REST API 降级...")
            return self._generate_rest(prompt, **kwargs)
    
    def _generate_rest(self, prompt: str, **kwargs) -> LLMResponse:
        """使用 REST API 直接调用 Gemini"""
        import requests
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}
        
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": kwargs.get("temperature", self.temperature),
                "maxOutputTokens": kwargs.get("max_tokens", self.max_tokens)
            }
        }
        
        try:
            response = requests.post(url, headers=headers, params=params, json=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            
            return LLMResponse(
                content=content,
                model=self.model,
                input_tokens=len(prompt) // 4,
                output_tokens=len(content) // 4,
                finish_reason="stop",
                raw_response=result
            )
        except Exception as e:
            logger.error(f"Gemini REST API 失败: {e}")
            raise
    
    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """流式生成 (Gemini SDK 支持)"""
        if self.client and self.client != "REST":
            try:
                response = self.client.generate_content(
                    prompt,
                    generation_config={
                        "temperature": kwargs.get("temperature", self.temperature),
                        "max_output_tokens": kwargs.get("max_tokens", self.max_tokens)
                    },
                    stream=True
                )
                
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
            except Exception as e:
                logger.error(f"Gemini 流式生成失败: {e}")
                raise
        else:
            # REST API 不支持流式,降级为一次性返回
            response = self._generate_rest(prompt, **kwargs)
            yield response.content
    
    def get_model_info(self) -> Dict:
        return {
            "provider": "gemini",
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "free_tier": True
        }


class LLMProviderFactory:
    """LLM 提供商工厂"""
    
    PROVIDERS = {
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
        "gemini": GeminiProvider,
    }
    
    @classmethod
    def create(cls, provider: str, **kwargs) -> BaseLLMProvider:
        """
        创建 LLM 提供商实例
        
        Args:
            provider: 提供商名称 (openai, ollama, gemini)
            **kwargs: 提供商配置参数
        """
        provider_class = cls.PROVIDERS.get(provider.lower())
        if not provider_class:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")
        
        return provider_class(**kwargs)
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """获取可用提供商列表"""
        return list(cls.PROVIDERS.keys())



class UnifiedLLM:
    """
    统一 LLM 接口
    支持自动降级和负载均衡
    """
    
    def __init__(self, config: Dict):
        """
        初始化统一 LLM 接口
        
        Args:
            config: 配置字典,示例:
            {
                "primary": {"provider": "openai", "model": "gpt-4o"},
                "fallback": {"provider": "ollama", "model": "llama3.1"}
            }
        """
        self.config = config
        self.primary = None
        self.fallback = None
        
        # 初始化主提供商
        primary_config = config.get("primary", {})
        if primary_config:
            provider = primary_config.pop("provider", "openai")
            self.primary = LLMProviderFactory.create(provider, **primary_config)
        
        # 初始化降级提供商
        fallback_config = config.get("fallback", {})
        if fallback_config:
            provider = fallback_config.pop("provider", "ollama")
            try:
                self.fallback = LLMProviderFactory.create(provider, **fallback_config)
            except Exception as e:
                logger.warning(f"降级提供商初始化失败: {e}")
        
        logger.info(f"统一 LLM 初始化完成: primary={self.primary}, fallback={self.fallback}")
    
    def generate(self, prompt: str, use_fallback: bool = True, **kwargs) -> LLMResponse:
        """
        生成响应,支持自动降级
        """
        # 尝试主提供商
        if self.primary:
            try:
                return self.primary.generate(prompt, **kwargs)
            except Exception as e:
                logger.warning(f"主提供商失败: {e}")
                if not use_fallback or not self.fallback:
                    raise
        
        # 使用降级提供商
        if self.fallback:
            logger.info("使用降级提供商")
            return self.fallback.generate(prompt, **kwargs)
        
        raise RuntimeError("无可用的 LLM 提供商")
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "primary": self.primary.get_model_info() if self.primary else None,
            "fallback": self.fallback.get_model_info() if self.fallback else None
        }
