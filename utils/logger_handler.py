# 系统库
import logging
import os
import json
import uuid
from datetime import datetime
from threading import local
# 本地工具
from utils.path_tool import get_abs_path


#日志保存的根目录
LOG_ROOT = get_abs_path("logs")

#确保日志目录存在
os.makedirs(LOG_ROOT, exist_ok=True)

#日志格式配置
DEFAULT_LOG_FORMAT = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)

# ===================== 第一次修改：请求追踪相关 =====================
# 线程本地存储，用于在同一个线程内共享请求ID
THREAD_LOCAL = local()


class RequestIDFilter(logging.Filter):
    """第一次修改：日志过滤器，自动为每条日志注入请求ID"""
    def filter(self, record):
        # 从线程本地存储获取当前请求ID，如果不存在则返回'N/A'
        record.request_id = getattr(THREAD_LOCAL, 'request_id', 'N/A')
        return True


class StructuredLogFormatter(logging.Formatter):
    """第一次修改：结构化日志格式化器，输出JSON格式日志"""
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'request_id': getattr(record, 'request_id', 'N/A'),
            'file': record.filename,
            'line': record.lineno,
            'function': record.funcName,
            'message': record.getMessage()
        }
        # 如果日志记录包含额外字段，也一并加入JSON
        if hasattr(record, 'extra'):
            log_entry.update(record.extra)
        return json.dumps(log_entry, ensure_ascii=False)


def set_request_id(request_id=None):
    """第一次修改：设置当前线程的请求ID，自动生成8位UUID"""
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]
    THREAD_LOCAL.request_id = request_id
    return request_id


def get_request_id():
    """第一次修改：获取当前线程的请求ID"""
    return getattr(THREAD_LOCAL, 'request_id', 'N/A')


def clear_request_id():
    """第一次修改：清除当前线程的请求ID"""
    if hasattr(THREAD_LOCAL, 'request_id'):
        delattr(THREAD_LOCAL, 'request_id')


# ===================== 日志器创建函数 =====================
def get_logger(
        name: str = "agent",                #给日志器起名字，默认叫agent
        console_level: int = logging.INFO,  #控制台输出的日志级别默认只输出 INFO 及以上（INFO/WARNING/ERROR）
        file_level: int = logging.DEBUG,    #日志文件输出的级别，默认记录 DEBUG 及以上所有日志
        log_file = None,                    #指定日志保存到哪个文件，不传就用默认日志文件
        structured: bool = False             #第一次修改：是否启用结构化JSON日志输出
) -> logging.Logger:                        #函数最终会返回一个日志器实例
    logger = logging.getLogger(name)        #核心，根据以上参数获取 / 创建一个日志器实例
    logger.setLevel(logging.DEBUG)          #给logger对象设置全局日志级别，低于这个级别的日志会被丢弃，不被任何handler处理

    #避免重复添加handler
    if logger.handlers:
        return logger


    #可以配置若干个handler处理器，先配置控制台的handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)         #在上面函数传参中配置了
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)#上面配置过了
    console_handler.addFilter(RequestIDFilter())    #第一次修改：添加请求ID过滤器
    logger.addHandler(console_handler)



    #配置文件handler，调用日志工具后，日志不仅在控制台显示，而且会写入文件
    if not log_file:
        log_file = os.path.join(LOG_ROOT, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(log_file,encoding="utf-8")
    file_handler.setLevel(file_level)               #在上面函数传参中配置了
    file_handler.setFormatter(DEFAULT_LOG_FORMAT)   #上面配置过了
    file_handler.addFilter(RequestIDFilter())       #第一次修改：添加请求ID过滤器
    logger.addHandler(file_handler)


    return logger

#快捷获取日志器
logger = get_logger()