"""
统一日志配置
"""
import logging
import sys
from pathlib import Path


def setup_logging(log_level=logging.INFO):
    """
    配置日志系统
    
    Args:
        log_level: 日志级别
    """
    # 创建日志目录
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # 日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # 配置根日志记录器
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            # 控制台输出
            logging.StreamHandler(sys.stdout),
            # 文件输出
            logging.FileHandler(
                log_dir / 'newstrace.log',
                encoding='utf-8'
            )
        ]
    )
    
    # 设置第三方库日志级别
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.INFO)
    logging.getLogger('anthropic').setLevel(logging.INFO)
    logging.getLogger('celery').setLevel(logging.INFO)
    
    logger = logging.getLogger(__name__)
    logger.info("日志系统初始化完成")
