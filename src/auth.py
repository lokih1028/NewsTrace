"""
JWT 认证模块
提供 API 端点的认证和鉴权
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from functools import wraps

logger = logging.getLogger(__name__)

try:
    from jose import jwt, JWTError
    HAS_JOSE = True
except ImportError:
    HAS_JOSE = False
    logger.warning("python-jose 未安装,JWT 认证不可用")

try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    HAS_PASSLIB = True
except ImportError:
    HAS_PASSLIB = False
    logger.warning("passlib 未安装,密码哈希不可用")


class JWTAuth:
    """JWT 认证管理器"""
    
    def __init__(
        self,
        secret_key: str = None,
        algorithm: str = "HS256",
        expire_minutes: int = 60
    ):
        """
        初始化 JWT 认证管理器
        
        Args:
            secret_key: JWT 密钥
            algorithm: 加密算法
            expire_minutes: Token 过期时间(分钟)
        """
        self.secret_key = secret_key or os.getenv("JWT_SECRET_KEY", "newstrace-secret-key-change-me")
        self.algorithm = algorithm
        self.expire_minutes = expire_minutes
        
        if self.secret_key == "newstrace-secret-key-change-me":
            logger.warning("使用默认 JWT 密钥,请在生产环境中设置 JWT_SECRET_KEY 环境变量")
        
        logger.info(f"JWT 认证管理器初始化完成, algorithm={algorithm}, expire={expire_minutes}min")
    
    def create_access_token(self, data: Dict, expires_delta: timedelta = None) -> str:
        """
        创建访问令牌
        
        Args:
            data: 要编码的数据
            expires_delta: 自定义过期时间
            
        Returns:
            JWT 令牌字符串
        """
        if not HAS_JOSE:
            raise RuntimeError("JWT 功能需要安装 python-jose: pip install python-jose[cryptography]")
        
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow()
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """
        验证令牌
        
        Args:
            token: JWT 令牌
            
        Returns:
            解码后的数据,验证失败返回 None
        """
        if not HAS_JOSE:
            return None
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.warning(f"JWT 验证失败: {e}")
            return None
    
    def hash_password(self, password: str) -> str:
        """哈希密码"""
        if not HAS_PASSLIB:
            # 降级方案: 简单哈希 (不推荐生产使用)
            import hashlib
            return hashlib.sha256(password.encode()).hexdigest()
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        if not HAS_PASSLIB:
            import hashlib
            return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password
        return pwd_context.verify(plain_password, hashed_password)


# FastAPI 依赖项
def get_current_user(auth: JWTAuth):
    """创建 FastAPI 认证依赖"""
    try:
        from fastapi import Depends, HTTPException, status
        from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
        
        security = HTTPBearer()
        
        async def _get_current_user(
            credentials: HTTPAuthorizationCredentials = Depends(security)
        ) -> Dict:
            token = credentials.credentials
            payload = auth.verify_token(token)
            
            if payload is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return payload
        
        return _get_current_user
    except ImportError:
        logger.warning("FastAPI 未安装,认证依赖不可用")
        return None


# 简易用户存储 (生产环境应使用数据库)
class SimpleUserStore:
    """简易用户存储"""
    
    def __init__(self, auth: JWTAuth):
        self.auth = auth
        self.users = {}
    
    def create_user(self, username: str, password: str, role: str = "user") -> Dict:
        """创建用户"""
        if username in self.users:
            raise ValueError(f"用户 {username} 已存在")
        
        hashed = self.auth.hash_password(password)
        self.users[username] = {
            "username": username,
            "hashed_password": hashed,
            "role": role,
            "created_at": datetime.now().isoformat()
        }
        return {"username": username, "role": role}
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """验证用户并返回令牌"""
        user = self.users.get(username)
        if not user:
            return None
        
        if not self.auth.verify_password(password, user["hashed_password"]):
            return None
        
        token = self.auth.create_access_token({
            "sub": username,
            "role": user["role"]
        })
        return token
