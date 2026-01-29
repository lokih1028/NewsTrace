# -*- coding: utf-8 -*-
"""
机器人交互模块
支持钉钉和飞书的消息处理
"""

import os
import json
import logging
import hashlib
import hmac
import base64
import time
from typing import Dict, Optional, Callable
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class BotMessage:
    """机器人消息结构"""
    platform: str  # dingtalk, feishu
    user_id: str
    user_name: str
    content: str
    chat_id: str = ""
    message_id: str = ""
    is_group: bool = False
    raw_data: Dict = None


@dataclass
class BotReply:
    """机器人回复结构"""
    content: str
    msg_type: str = "markdown"  # text, markdown


class DingTalkBot:
    """钉钉机器人"""
    
    def __init__(self, webhook: str = None, secret: str = None):
        """
        初始化钉钉机器人
        
        Args:
            webhook: Webhook URL
            secret: 签名密钥
        """
        self.webhook = webhook or os.getenv("DINGTALK_WEBHOOK")
        self.secret = secret or os.getenv("DINGTALK_SECRET")
    
    def _sign(self) -> Dict:
        """生成签名"""
        if not self.secret:
            return {}
        
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{self.secret}'
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(
            secret_enc,
            string_to_sign_enc,
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        
        return {"timestamp": timestamp, "sign": sign}
    
    def send_text(self, content: str, at_all: bool = False) -> bool:
        """发送文本消息"""
        if not self.webhook:
            logger.warning("钉钉 Webhook 未配置")
            return False
        
        params = self._sign()
        url = self.webhook
        if params:
            url = f"{self.webhook}&timestamp={params['timestamp']}&sign={params['sign']}"
        
        data = {
            "msgtype": "text",
            "text": {"content": content},
            "at": {"isAtAll": at_all}
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            if result.get("errcode") == 0:
                logger.info("钉钉消息发送成功")
                return True
            else:
                logger.error(f"钉钉消息发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"钉钉消息发送异常: {e}")
            return False
    
    def send_markdown(self, title: str, content: str) -> bool:
        """发送 Markdown 消息"""
        if not self.webhook:
            return False
        
        params = self._sign()
        url = self.webhook
        if params:
            url = f"{self.webhook}&timestamp={params['timestamp']}&sign={params['sign']}"
        
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            }
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            return result.get("errcode") == 0
        except Exception as e:
            logger.error(f"钉钉 Markdown 发送异常: {e}")
            return False


class FeishuBot:
    """飞书机器人"""
    
    def __init__(self, webhook: str = None, app_id: str = None, app_secret: str = None):
        """
        初始化飞书机器人
        
        Args:
            webhook: Webhook URL
            app_id: 应用 ID (用于 API 调用)
            app_secret: 应用密钥
        """
        self.webhook = webhook or os.getenv("FEISHU_WEBHOOK_URL")
        self.app_id = app_id or os.getenv("FEISHU_APP_ID")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
        self._access_token = None
        self._token_expires = 0
    
    def _get_tenant_access_token(self) -> Optional[str]:
        """获取 tenant_access_token"""
        if not self.app_id or not self.app_secret:
            return None
        
        if self._access_token and time.time() < self._token_expires:
            return self._access_token
        
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            if result.get("code") == 0:
                self._access_token = result["tenant_access_token"]
                self._token_expires = time.time() + result["expire"] - 60
                return self._access_token
        except Exception as e:
            logger.error(f"获取飞书 Token 失败: {e}")
        
        return None
    
    def send_webhook(self, title: str, content: str) -> bool:
        """通过 Webhook 发送消息"""
        if not self.webhook:
            return False
        
        data = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue"
                },
                "elements": [
                    {"tag": "markdown", "content": content}
                ]
            }
        }
        
        try:
            response = requests.post(self.webhook, json=data, timeout=10)
            result = response.json()
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                logger.info("飞书 Webhook 发送成功")
                return True
            else:
                logger.error(f"飞书 Webhook 发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"飞书 Webhook 发送异常: {e}")
            return False
    
    def send_to_chat(self, chat_id: str, content: str, msg_type: str = "text") -> bool:
        """发送消息到群聊"""
        token = self._get_tenant_access_token()
        if not token:
            return False
        
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        if msg_type == "text":
            msg_content = json.dumps({"text": content})
        else:
            msg_content = content
        
        params = {"receive_id_type": "chat_id"}
        data = {
            "receive_id": chat_id,
            "msg_type": msg_type,
            "content": msg_content
        }
        
        try:
            response = requests.post(url, headers=headers, params=params, json=data, timeout=10)
            result = response.json()
            return result.get("code") == 0
        except Exception as e:
            logger.error(f"飞书消息发送异常: {e}")
            return False


class BotDispatcher:
    """
    机器人消息调度器
    
    功能:
    1. 注册命令处理器
    2. 解析消息并分发
    """
    
    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self.default_handler: Optional[Callable] = None
    
    def command(self, name: str):
        """注册命令处理器装饰器"""
        def decorator(func: Callable):
            self.handlers[name] = func
            return func
        return decorator
    
    def set_default_handler(self, func: Callable):
        """设置默认处理器"""
        self.default_handler = func
    
    def dispatch(self, message: BotMessage) -> Optional[BotReply]:
        """
        分发消息
        
        Args:
            message: 机器人消息
            
        Returns:
            回复内容
        """
        content = message.content.strip()
        
        # 提取命令
        parts = content.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # 查找处理器
        handler = self.handlers.get(cmd)
        
        if handler:
            try:
                return handler(message, args)
            except Exception as e:
                logger.error(f"命令处理异常: {e}")
                return BotReply(content=f"处理失败: {e}")
        
        # 默认处理器
        if self.default_handler:
            try:
                return self.default_handler(message)
            except Exception as e:
                logger.error(f"默认处理器异常: {e}")
        
        return None


# 创建全局调度器
dispatcher = BotDispatcher()


# 示例命令注册
@dispatcher.command("/help")
def handle_help(message: BotMessage, args: str) -> BotReply:
    """帮助命令"""
    help_text = """
📚 **可用命令**

- `/help` - 显示帮助
- `/status` - 系统状态
- `/audit <新闻链接>` - 审计新闻
- `/source <信源名>` - 查询信源评级

💡 直接发送文本也会尝试分析
"""
    return BotReply(content=help_text)


@dispatcher.command("/status")
def handle_status(message: BotMessage, args: str) -> BotReply:
    """状态命令"""
    status_text = """
📊 **系统状态**

- 运行状态: ✅ 正常
- 缓存状态: ✅ 可用
- 数据源: AkShare, Tushare
"""
    return BotReply(content=status_text)
