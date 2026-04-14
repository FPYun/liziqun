"""
日志配置模块

为整个项目提供统一的日志记录功能
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(
    name: str = "radar_deployment",
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_dir: str = "logs"
) -> logging.Logger:
    """
    设置并返回配置好的日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        log_to_file: 是否写入日志文件
        log_dir: 日志文件保存目录

    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 清除现有处理器
    logger.handlers.clear()

    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_path / f"{name}_{timestamp}.log"

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.info(f"日志文件已创建: {log_file}")

    return logger


# 全局日志记录器实例
_logger = None


def get_logger() -> logging.Logger:
    """获取全局日志记录器"""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


class LogMixin:
    """
    日志混入类

    为类提供便捷的日志记录功能
    """

    def __init__(self):
        self._logger = None

    @property
    def logger(self) -> logging.Logger:
        """获取类日志记录器"""
        if self._logger is None:
            self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger

    def log_debug(self, msg: str):
        """记录调试信息"""
        self.logger.debug(msg)

    def log_info(self, msg: str):
        """记录一般信息"""
        self.logger.info(msg)

    def log_warning(self, msg: str):
        """记录警告信息"""
        self.logger.warning(msg)

    def log_error(self, msg: str):
        """记录错误信息"""
        self.logger.error(msg)


# 使用示例
if __name__ == "__main__":
    # 设置日志
    logger = setup_logger(level=logging.DEBUG)

    # 测试各级别日志
    logger.debug("这是调试信息")
    logger.info("这是一般信息")
    logger.warning("这是警告信息")
    logger.error("这是错误信息")

    # 使用混入类
    class MyClass(LogMixin):
        def do_something(self):
            self.log_info("正在执行操作...")

    obj = MyClass()
    obj.do_something()
