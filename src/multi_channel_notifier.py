# -*- coding: utf-8 -*-
"""
多渠道通知服务
从 daily_stock_analysis 项目借鉴并适配

支持渠道:
- 企业微信 (Webhook)
- 飞书 (Webhook)
- Telegram Bot
- 邮件 (SMTP)
- PushPlus
- 自定义 Webhook
"""

import os
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """通知渠道类型"""
    WECHAT = "wechat"
    FEISHU = "feishu"
    TELEGRAM = "telegram"
    EMAIL = "email"
    PUSHPLUS = "pushplus"
    CUSTOM = "custom"


# SMTP 服务器配置
SMTP_CONFIGS = {
    "qq.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "163.com": {"server": "smtp.163.com", "port": 465, "ssl": True},
    "126.com": {"server": "smtp.126.com", "port": 465, "ssl": True},
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False, "tls": True},
    "outlook.com": {"server": "smtp.office365.com", "port": 587, "ssl": False, "tls": True},
    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "ssl": True},
}


class MultiChannelNotifier:
    """
    多渠道通知服务
    
    功能:
    1. 自动检测已配置的渠道
    2. 并发推送到所有渠道
    3. 支持 Markdown 格式
    """
    
    def __init__(self, config: Dict = None):
        """
        初始化通知服务
        
        Args:
            config: 配置字典,示例:
            {
                "wechat_webhook": "https://...",
                "feishu_webhook": "https://...",
                "telegram_bot_token": "xxx",
                "telegram_chat_id": "xxx",
                "email_sender": "xxx@qq.com",
                "email_password": "xxx",
                "email_receivers": ["a@b.com"],
                "pushplus_token": "xxx",
                "custom_webhooks": ["https://..."]
            }
        """
        self.config = config or {}
        
        # 从环境变量加载配置
        self._load_from_env()
        
        # 检测已配置的渠道
        self.channels = self._detect_channels()
        
        logger.info(f"多渠道通知服务初始化完成, 可用渠道: {[c.value for c in self.channels]}")
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        env_mapping = {
            "wechat_webhook": "WECHAT_WEBHOOK_URL",
            "feishu_webhook": "FEISHU_WEBHOOK_URL",
            "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
            "telegram_chat_id": "TELEGRAM_CHAT_ID",
            "email_sender": "EMAIL_SENDER",
            "email_password": "EMAIL_PASSWORD",
            "email_receivers": "EMAIL_RECEIVERS",
            "pushplus_token": "PUSHPLUS_TOKEN",
            "custom_webhooks": "CUSTOM_WEBHOOK_URLS",
        }
        
        for config_key, env_key in env_mapping.items():
            if config_key not in self.config:
                value = os.getenv(env_key)
                if value:
                    if config_key in ("email_receivers", "custom_webhooks"):
                        self.config[config_key] = [v.strip() for v in value.split(",")]
                    else:
                        self.config[config_key] = value
    
    def _detect_channels(self) -> List[NotificationChannel]:
        """检测已配置的渠道"""
        channels = []
        
        if self.config.get("wechat_webhook"):
            channels.append(NotificationChannel.WECHAT)
        
        if self.config.get("feishu_webhook"):
            channels.append(NotificationChannel.FEISHU)
        
        if self.config.get("telegram_bot_token") and self.config.get("telegram_chat_id"):
            channels.append(NotificationChannel.TELEGRAM)
        
        if self.config.get("email_sender") and self.config.get("email_password"):
            channels.append(NotificationChannel.EMAIL)
        
        if self.config.get("pushplus_token"):
            channels.append(NotificationChannel.PUSHPLUS)
        
        if self.config.get("custom_webhooks"):
            channels.append(NotificationChannel.CUSTOM)
        
        return channels
    
    def send(self, title: str, content: str, channels: List[NotificationChannel] = None) -> Dict:
        """
        发送通知到所有已配置的渠道
        
        Args:
            title: 消息标题
            content: Markdown 格式内容
            channels: 指定渠道列表 (可选,默认所有)
            
        Returns:
            {
                "success": ["wechat", "feishu"],
                "failed": [{"channel": "telegram", "error": "..."}]
            }
        """
        target_channels = channels or self.channels
        results = {"success": [], "failed": []}
        
        if not target_channels:
            logger.warning("无可用通知渠道")
            return results
        
        # 并发推送
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            
            for channel in target_channels:
                future = executor.submit(self._send_to_channel, channel, title, content)
                futures[future] = channel
            
            for future in as_completed(futures):
                channel = futures[future]
                try:
                    success = future.result()
                    if success:
                        results["success"].append(channel.value)
                    else:
                        results["failed"].append({"channel": channel.value, "error": "发送失败"})
                except Exception as e:
                    results["failed"].append({"channel": channel.value, "error": str(e)})
        
        logger.info(f"通知发送完成: 成功={results['success']}, 失败={len(results['failed'])}")
        return results
    
    def _send_to_channel(self, channel: NotificationChannel, title: str, content: str) -> bool:
        """发送到指定渠道"""
        try:
            if channel == NotificationChannel.WECHAT:
                return self._send_wechat(title, content)
            elif channel == NotificationChannel.FEISHU:
                return self._send_feishu(title, content)
            elif channel == NotificationChannel.TELEGRAM:
                return self._send_telegram(title, content)
            elif channel == NotificationChannel.EMAIL:
                return self._send_email(title, content)
            elif channel == NotificationChannel.PUSHPLUS:
                return self._send_pushplus(title, content)
            elif channel == NotificationChannel.CUSTOM:
                return self._send_custom(title, content)
        except Exception as e:
            logger.error(f"发送到 {channel.value} 失败: {e}")
            return False
        
        return False
    
    def _send_wechat(self, title: str, content: str) -> bool:
        """发送到企业微信"""
        webhook = self.config.get("wechat_webhook")
        if not webhook:
            return False
        
        # 企业微信 Markdown 格式
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {title}\n\n{content}"
            }
        }
        
        response = requests.post(webhook, json=data, timeout=10)
        result = response.json()
        
        if result.get("errcode") == 0:
            logger.info("企业微信发送成功")
            return True
        else:
            logger.error(f"企业微信发送失败: {result}")
            return False
    
    def _send_feishu(self, title: str, content: str) -> bool:
        """发送到飞书"""
        webhook = self.config.get("feishu_webhook")
        if not webhook:
            return False
        
        # 飞书消息格式
        data = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content
                    }
                ]
            }
        }
        
        response = requests.post(webhook, json=data, timeout=10)
        result = response.json()
        
        if result.get("StatusCode") == 0 or result.get("code") == 0:
            logger.info("飞书发送成功")
            return True
        else:
            logger.error(f"飞书发送失败: {result}")
            return False
    
    def _send_telegram(self, title: str, content: str) -> bool:
        """发送到 Telegram"""
        bot_token = self.config.get("telegram_bot_token")
        chat_id = self.config.get("telegram_chat_id")
        
        if not bot_token or not chat_id:
            return False
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        # Telegram 支持 Markdown
        text = f"*{title}*\n\n{content}"
        
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        
        if result.get("ok"):
            logger.info("Telegram 发送成功")
            return True
        else:
            logger.error(f"Telegram 发送失败: {result}")
            return False
    
    def _send_email(self, title: str, content: str) -> bool:
        """发送邮件"""
        sender = self.config.get("email_sender")
        password = self.config.get("email_password")
        receivers = self.config.get("email_receivers", [sender])
        
        if not sender or not password:
            return False
        
        # 自动识别 SMTP 配置
        domain = sender.split("@")[-1]
        smtp_config = SMTP_CONFIGS.get(domain, {"server": f"smtp.{domain}", "port": 465, "ssl": True})
        
        # 创建邮件
        msg = MIMEMultipart("alternative")
        msg["Subject"] = title
        msg["From"] = sender
        msg["To"] = ", ".join(receivers)
        
        # HTML 内容
        html_content = f"<html><body><pre>{content}</pre></body></html>"
        msg.attach(MIMEText(html_content, "html", "utf-8"))
        
        try:
            if smtp_config.get("ssl"):
                server = smtplib.SMTP_SSL(smtp_config["server"], smtp_config["port"])
            else:
                server = smtplib.SMTP(smtp_config["server"], smtp_config["port"])
                if smtp_config.get("tls"):
                    server.starttls()
            
            server.login(sender, password)
            server.sendmail(sender, receivers, msg.as_string())
            server.quit()
            
            logger.info("邮件发送成功")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
    
    def _send_pushplus(self, title: str, content: str) -> bool:
        """发送到 PushPlus"""
        token = self.config.get("pushplus_token")
        if not token:
            return False
        
        url = "http://www.pushplus.plus/send"
        data = {
            "token": token,
            "title": title,
            "content": content,
            "template": "markdown"
        }
        
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        
        if result.get("code") == 200:
            logger.info("PushPlus 发送成功")
            return True
        else:
            logger.error(f"PushPlus 发送失败: {result}")
            return False
    
    def _send_custom(self, title: str, content: str) -> bool:
        """发送到自定义 Webhook"""
        webhooks = self.config.get("custom_webhooks", [])
        if not webhooks:
            return False
        
        success = True
        for webhook in webhooks:
            try:
                data = {
                    "title": title,
                    "content": content,
                    "msgtype": "markdown"
                }
                
                response = requests.post(webhook, json=data, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"自定义 Webhook 发送失败: {webhook}")
                    success = False
                    
            except Exception as e:
                logger.error(f"自定义 Webhook 异常: {e}")
                success = False
        
        return success
    
    def get_available_channels(self) -> List[str]:
        """获取可用渠道列表"""
        return [c.value for c in self.channels]
    
    def is_available(self) -> bool:
        """检查是否有可用渠道"""
        return len(self.channels) > 0
