"""日志系统封装

提供四级日志输出，自动按日期轮转落盘。
控制台保留 Rich UI，日志用于程序运行追踪。
"""
import logging
import sys
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from typing import Optional


# 日志格式
DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 日志级别映射
LEVEL_DEBUG = logging.DEBUG    # LLM 原始响应、详细调试
LEVEL_INFO = logging.INFO      # 状态流转、关键操作
LEVEL_WARNING = logging.WARNING  # 解析降级、非致命异常
LEVEL_ERROR = logging.ERROR    # 异常、错误


class LoggerManager:
    """日志管理器：统一管理应用日志配置"""

    _instance: Optional["LoggerManager"] = None
    _initialized = False

    def __new__(cls, *args, **kwargs) -> "LoggerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir: str = "./logs", level: int = LEVEL_DEBUG):
        if LoggerManager._initialized:
            return

        self.log_dir = Path(log_dir)
        self.level = level
        self._setup()
        LoggerManager._initialized = True

    def _setup(self):
        """初始化日志配置"""
        # 创建日志目录
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 根日志器配置
        root_logger = logging.getLogger("teacher_skill")
        root_logger.setLevel(self.level)

        # 清除已有处理器（避免重复）
        root_logger.handlers.clear()

        # 文件处理器：按天轮转，保留30天
        log_file = self.log_dir / "app.log"
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when="midnight",      # 每天午夜轮转
            interval=1,           # 间隔1天
            backupCount=30,       # 保留30天历史
            encoding="utf-8"
        )
        file_handler.setLevel(self.level)
        file_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT, DATE_FORMAT))
        root_logger.addHandler(file_handler)

        # 可选：控制台处理器（用于调试，生产可关闭）
        # 注意：不替代 Rich UI，仅用于开发调试
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(LEVEL_WARNING)  # 控制台只显示警告及以上
        console_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT, DATE_FORMAT))
        root_logger.addHandler(console_handler)

        self.root_logger = root_logger

    def get_logger(self, name: str) -> logging.Logger:
        """获取指定模块的日志器

        Args:
            name: 模块名，建议使用 __name__

        Returns:
            配置好的 Logger 实例
        """
        return logging.getLogger(f"teacher_skill.{name}")


# 全局管理器实例
_manager: Optional[LoggerManager] = None


def init_logger(log_dir: str = "./logs", level: int = LEVEL_DEBUG) -> LoggerManager:
    """初始化日志系统

    Args:
        log_dir: 日志存放目录，默认 ./logs
        level: 日志级别，默认 DEBUG

    Returns:
        LoggerManager 实例
    """
    global _manager
    _manager = LoggerManager(log_dir=log_dir, level=level)
    return _manager


def get_logger(name: str) -> logging.Logger:
    """获取日志器

    如果未初始化，会自动使用默认配置初始化。

    Args:
        name: 模块名，建议使用 __name__

    Returns:
        Logger 实例
    """
    global _manager
    if _manager is None:
        _manager = init_logger()
    return _manager.get_logger(name)


# 便捷函数：可直接 import 使用
def debug(msg: str, module: str = "app"):
    """输出 DEBUG 级别日志"""
    get_logger(module).debug(msg)


def info(msg: str, module: str = "app"):
    """输出 INFO 级别日志"""
    get_logger(module).info(msg)


def warning(msg: str, module: str = "app"):
    """输出 WARNING 级别日志"""
    get_logger(module).warning(msg)


def error(msg: str, module: str = "app"):
    """输出 ERROR 级别日志"""
    get_logger(module).error(msg)
