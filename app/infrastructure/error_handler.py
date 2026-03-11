# -*- coding: utf-8 -*-
"""
错误处理模块 - 统一的异常管理和错误恢复系统

文件说明:
- 作用：提供现代化的错误处理机制，替代大量重复的 try-except 块
- 核心实现：错误分类、错误码系统、装饰器模式、自动恢复策略
- 关联关系：与 LoggerController 集成，被所有业务模块调用

使用示例:
    @handle_errors(error_code="OCR_ENGINE_001", fallback_return=[])
    def process_image(self, image):
        # 处理逻辑
        pass
    
    @retry_on_error(max_retries=3, delay=1.0)
    def download_model(self, url):
        # 下载逻辑
        pass
"""

import os
import sys
import time
import traceback
import functools
from enum import Enum
from typing import Optional, Callable, Dict, Any, List, Type, Union
from dataclasses import dataclass, field
from datetime import datetime


# ============================================================================
# 错误分类和错误码定义
# ============================================================================

class ErrorCategory(Enum):
    """错误分类"""
    BUSINESS = "business"           # 业务逻辑错误
    SYSTEM = "system"               # 系统级错误
    IO = "io"                       # 输入输出错误
    NETWORK = "network"             # 网络错误
    VALIDATION = "validation"       # 数据验证错误
    CONFIGURATION = "configuration" # 配置错误
    DEPENDENCY = "dependency"       # 依赖错误
    RESOURCE = "resource"           # 资源错误（内存、磁盘等）
    PERMISSION = "permission"       # 权限错误
    TIMEOUT = "timeout"             # 超时错误


class ErrorCode(Enum):
    """
    错误码定义
    格式：{MODULE}_{CATEGORY}_{SEQUENCE}
    """
    # OCR 引擎相关 (OCR)
    OCR_ENGINE_001 = ("OCR", ErrorCategory.SYSTEM, "OCR 引擎初始化失败")
    OCR_ENGINE_002 = ("OCR", ErrorCategory.TIMEOUT, "OCR 识别超时")
    OCR_ENGINE_003 = ("OCR", ErrorCategory.RESOURCE, "OCR 内存不足")
    OCR_ENGINE_004 = ("OCR", ErrorCategory.DEPENDENCY, "OCR 模型文件缺失")
    
    # 依赖相关 (DEPENDENCY)
    DEPENDENCY = ("COMMON", ErrorCategory.DEPENDENCY, "依赖项错误")
    
    # 配置文件相关 (CONFIG)
    CONFIG_LOAD_001 = ("CONFIG", ErrorCategory.IO, "配置文件读取失败")
    CONFIG_SAVE_001 = ("CONFIG", ErrorCategory.IO, "配置文件写入失败")
    CONFIG_PARSE_001 = ("CONFIG", ErrorCategory.VALIDATION, "配置文件解析失败")
    CONFIG_INVALID_001 = ("CONFIG", ErrorCategory.VALIDATION, "配置项值无效")
    
    # 文件操作相关 (FILE)
    FILE_NOT_FOUND_001 = ("FILE", ErrorCategory.IO, "文件不存在")
    FILE_READ_001 = ("FILE", ErrorCategory.IO, "文件读取失败")
    FILE_WRITE_001 = ("FILE", ErrorCategory.IO, "文件写入失败")
    FILE_DELETE_001 = ("FILE", ErrorCategory.IO, "文件删除失败")
    FILE_PERMISSION_001 = ("FILE", ErrorCategory.PERMISSION, "文件访问权限不足")
    FILE_IO_001 = ("FILE", ErrorCategory.IO, "文件 IO 操作失败")
    
    # 目录操作相关 (DIR)
    DIR_CREATE_001 = ("DIR", ErrorCategory.IO, "目录创建失败")
    DIR_NOT_FOUND_001 = ("DIR", ErrorCategory.IO, "目录不存在")
    
    # 网络相关 (NETWORK)
    NETWORK_TIMEOUT_001 = ("NETWORK", ErrorCategory.TIMEOUT, "网络请求超时")
    NETWORK_FAILED_001 = ("NETWORK", ErrorCategory.NETWORK, "网络连接失败")
    DOWNLOAD_FAILED_001 = ("NETWORK", ErrorCategory.NETWORK, "文件下载失败")
    
    # 进程管理相关 (PROCESS)
    PROCESS_START_001 = ("PROCESS", ErrorCategory.SYSTEM, "子进程启动失败")
    PROCESS_CRASH_001 = ("PROCESS", ErrorCategory.SYSTEM, "子进程崩溃")
    PROCESS_TIMEOUT_001 = ("PROCESS", ErrorCategory.TIMEOUT, "子进程执行超时")
    
    # 结果处理相关 (RESULT)
    RESULT_EXPORT_001 = ("RESULT", ErrorCategory.IO, "结果导出失败")
    RESULT_FORMAT_001 = ("RESULT", ErrorCategory.VALIDATION, "结果格式错误")
    
    # UI 相关 (UI)
    UI_INIT_001 = ("UI", ErrorCategory.SYSTEM, "UI组件初始化失败")
    UI_RENDER_001 = ("UI", ErrorCategory.SYSTEM, "UI 渲染失败")
    UI_RENDER_002 = ("UI", ErrorCategory.SYSTEM, "UI 绘制事件处理失败")
    
    # 通用错误 (COMMON)
    UNKNOWN_001 = ("COMMON", ErrorCategory.SYSTEM, "未知错误")
    NOT_IMPLEMENTED_001 = ("COMMON", ErrorCategory.SYSTEM, "功能未实现")
    INVALID_OPERATION_001 = ("COMMON", ErrorCategory.BUSINESS, "无效操作")
    VALIDATION = ("COMMON", ErrorCategory.VALIDATION, "数据验证错误")
    
    def __init__(self, module: str, category: ErrorCategory, message: str):
        self.module = module
        self.category = category
        self.message = message
    
    @property
    def code(self) -> str:
        """获取错误码字符串"""
        return self.name
    
    @property
    def full_message(self) -> str:
        """获取完整错误消息"""
        return f"[{self.module}] {self.message}"


# ============================================================================
# 错误上下文和数据类
# ============================================================================

@dataclass
class ErrorContext:
    """错误上下文信息"""
    error_code: ErrorCode
    original_exception: Exception
    timestamp: datetime = field(default_factory=datetime.now)
    component: str = ""
    operation: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    stack_trace: str = ""
    
    def __post_init__(self):
        """自动生成堆栈跟踪"""
        if not self.stack_trace:
            self.stack_trace = traceback.format_exc()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'error_code': self.error_code.code,
            'module': self.error_code.module,
            'category': self.error_code.category.value,
            'message': self.error_code.message,
            'component': self.component,
            'operation': self.operation,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details,
            'stack_trace': self.stack_trace
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"[{self.error_code.code}] {self.error_code.message}\n"
                f"组件：{self.component}, 操作：{self.operation}\n"
                f"原因：{self.original_exception}")


# ============================================================================
# 自定义异常类
# ============================================================================

class OCRError(Exception):
    """OCR 系统基础异常类"""
    def __init__(self, error_code: ErrorCode, message: str = "", 
                 context: Optional[ErrorContext] = None):
        self.error_code = error_code
        self.context = context
        custom_msg = f"{error_code.full_message}"
        if message:
            custom_msg += f": {message}"
        super().__init__(custom_msg)


class BusinessError(OCRError):
    """
    业务逻辑错误
    
    使用场景:
    - 违反业务规则（如：库存不足、余额不足）
    - 数据状态不合法（如：未激活用户尝试登录）
    - 操作流程错误（如：未支付先发货）
    
    示例:
        if user.balance < order.amount:
            raise BusinessError(
                ErrorCode.INVALID_OPERATION_001,
                f"余额不足：需要{order.amount}, 当前{user.balance}"
            )
    """
    def __init__(self, error_code: ErrorCode, message: str = "", 
                 context: Optional[ErrorContext] = None):
        super().__init__(error_code, message, context)
        self.error_category = "business"


class SystemError(OCRError):
    """
    系统级错误
    
    使用场景:
    - 关键服务初始化失败
    - 核心组件崩溃
    - 资源耗尽（内存、磁盘等）
    - 依赖服务不可用
    
    示例:
        if not paddle_available:
            raise SystemError(
                ErrorCode.OCR_ENGINE_001,
                "PaddlePaddle 引擎初始化失败"
            )
    """
    def __init__(self, error_code: ErrorCode, message: str = "", 
                 context: Optional[ErrorContext] = None):
        super().__init__(error_code, message, context)
        self.error_category = "system"


class ResourceError(OCRError):
    """
    资源访问错误（替代与内置类型冲突的 IOError）
    
    使用场景:
    - 文件读写失败
    - 数据库连接断开
    - 网络 socket 错误
    - 外部设备访问失败
    
    注意: 不使用 IOError 名称，避免与 Python 内置 OSError 冲突
    
    示例:
        try:
            with open(file_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            raise ResourceError(
                ErrorCode.FILE_READ_001,
                f"无法读取文件：{file_path}"
            )
    """
    def __init__(self, error_code: ErrorCode, message: str = "", 
                 context: Optional[ErrorContext] = None):
        super().__init__(error_code, message, context)
        self.error_category = "resource"
    
    # 提供原始异常的便捷访问
    @property
    def os_error(self):
        """获取底层的操作系统错误（如果有）"""
        if self.context and self.context.original_exception:
            orig = self.context.original_exception
            if isinstance(orig, OSError):
                return orig
        return None
    
    @property
    def errno(self):
        """获取错误码（如果有）"""
        os_err = self.os_error
        return os_err.errno if os_err else None


class NetworkError(OCRError):
    """
    网络相关错误
    
    使用场景:
    - HTTP 请求失败
    - DNS 解析错误
    - 连接超时
    - SSL/TLS 握手失败
    
    示例:
        try:
            response = requests.get(url, timeout=10)
        except requests.Timeout:
            raise NetworkError(
                ErrorCode.NETWORK_TIMEOUT_001,
                f"请求超时：{url}"
            )
    """
    def __init__(self, error_code: ErrorCode, message: str = "", 
                 context: Optional[ErrorContext] = None):
        super().__init__(error_code, message, context)
        self.error_category = "network"
    
    @property
    def status_code(self):
        """获取 HTTP 状态码（如果适用）"""
        if self.context and self.context.original_exception:
            orig = self.context.original_exception
            if hasattr(orig, 'response') and orig.response:
                return orig.response.status_code
        return None
    
    @property
    def retry_after(self):
        """获取建议的重试时间（如果服务器提供）"""
        if self.context and self.context.original_exception:
            orig = self.context.original_exception
            if hasattr(orig, 'response'):
                return orig.response.headers.get('Retry-After')
        return None


class ValidationError(OCRError):
    """
    数据验证错误
    
    使用场景:
    - 输入格式不符合要求
    - 参数值超出有效范围
    - 必填字段缺失
    - 数据类型错误
    
    示例:
        if not email or '@' not in email:
            raise ValidationError(
                ErrorCode.VALIDATION,
                f"无效的邮箱地址：{email}"
            )
    """
    def __init__(self, error_code: ErrorCode, message: str = "", 
                 context: Optional[ErrorContext] = None,
                 field_name: str = None, invalid_value=None):
        super().__init__(error_code, message, context)
        self.error_category = "validation"
        self.field_name = field_name
        self.invalid_value = invalid_value
    
    def to_dict(self):
        """转换为字典格式，包含验证详情"""
        base_dict = {
            'error_code': self.error_code.code,
            'message': str(self),
            'category': 'validation'
        }
        if self.field_name:
            base_dict['field'] = self.field_name
        if self.invalid_value is not None:
            base_dict['invalid_value'] = str(self.invalid_value)
        return base_dict


class ConfigurationError(OCRError):
    """
    配置相关错误
    
    使用场景:
    - 配置文件格式错误
    - 缺少必需的配置项
    - 配置值类型不匹配
    - 配置值超出有效范围
    
    示例:
        if 'api_key' not in config:
            raise ConfigurationError(
                ErrorCode.CONFIG_LOAD_001,
                "配置文件缺少必需的字段：api_key"
            )
    """
    def __init__(self, error_code: ErrorCode, message: str = "", 
                 context: Optional[ErrorContext] = None,
                 config_key: str = None, expected_type=None):
        # 调用父类构造函数，传递必要参数
        super().__init__(error_code, message, context)
        self.error_category = "configuration"
        self.config_key = config_key
        self.expected_type = expected_type
    
    def to_dict(self):
        """转换为字典格式，包含配置详情"""
        base_dict = {
            'error_code': self.error_code.code,
            'message': str(self),
            'category': 'configuration'
        }
        if self.config_key:
            base_dict['missing_key'] = self.config_key
        if self.expected_type:
            base_dict['expected_type'] = self.expected_type.__name__ if hasattr(self.expected_type, '__name__') else str(self.expected_type)
        return base_dict


# 保持 IOError 作为 ResourceError 的别名（向后兼容）
# 但不推荐使用，建议使用 ResourceError
IOError = ResourceError

# ============================================================================
# 错误恢复策略
# ============================================================================

class RecoveryStrategy(Enum):
    """恢复策略类型"""
    NONE = "none"                   # 不恢复
    RETRY = "retry"                 # 重试
    FALLBACK = "fallback"           # 降级
    CIRCUIT_BREAKER = "circuit_breaker"  # 熔断
    IGNORE = "ignore"               # 忽略


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    delay: float = 1.0              # 初始延迟（秒）
    backoff_factor: float = 2.0     # 退避因子
    exceptions: tuple = (Exception,)  # 需要重试的异常类型


class CircuitBreaker:
    """
    熔断器实现
    当连续失败次数达到阈值时，触发熔断，拒绝后续请求一段时间
    """
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half-open
    
    def record_success(self):
        """记录成功"""
        self.failures = 0
        self.state = "closed"
    
    def record_failure(self):
        """记录失败"""
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "open"
    
    def can_execute(self) -> bool:
        """检查是否可以执行"""
        if self.state == "closed":
            return True
        
        if self.state == "open":
            if self.last_failure_time and \
               (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        
        # half-open 状态允许一次尝试
        return True


# ============================================================================
# 错误处理器核心类
# ============================================================================

class ErrorHandler:
    """
    统一错误处理器
    
    功能:
    1. 统一错误日志记录
    2. 错误分类和处理策略
    3. 自动恢复和重试
    4. 错误统计和监控
    """
    
    _instance = None
    _lock = None
    
    def __new__(cls):
        if cls._instance is None:
            import threading
            if cls._lock is None:
                cls._lock = threading.Lock()
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # 防止重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.error_counts: Dict[str, int] = {}
        self._initialized = True
    
    @classmethod
    def get_instance(cls) -> 'ErrorHandler':
        """获取单例实例"""
        return cls()
    
    def handle_error(self, error_code: ErrorCode, exception: Exception,
                     component: str = "", operation: str = "",
                     details: Optional[Dict] = None,
                     log_level: str = "error") -> ErrorContext:
        """
        统一错误处理方法
        
        Args:
            error_code: 错误码
            exception: 原始异常
            component: 组件名
            operation: 操作名
            details: 详细信息
            log_level: 日志级别
            
        Returns:
            ErrorContext: 错误上下文
        """
        # 创建错误上下文
        context = ErrorContext(
            error_code=error_code,
            original_exception=exception,
            component=component,
            operation=operation,
            details=details or {},
        )
        
        # 记录错误日志
        self._log_error(context, log_level)
        
        # 更新错误统计
        self._update_stats(error_code.code)
        
        # 检查是否需要触发熔断
        if error_code.category in [ErrorCategory.SYSTEM, ErrorCategory.NETWORK]:
            self._check_circuit_breaker(error_code.code)
        
        return context
    
    def _log_error(self, context: ErrorContext, log_level: str = "error"):
        """记录错误日志"""
        from app.log.log_bus import get_logger
        logger = get_logger()
        
        log_method = getattr(logger, log_level, logger.error)
        log_method(
            component=context.component or "error_handler",
            action=context.operation or "error_occurred",
            message=str(context),
            show_in_status=(log_level == "error")
        )
    
    def _update_stats(self, error_code: str):
        """更新错误统计"""
        self.error_counts[error_code] = self.error_counts.get(error_code, 0) + 1
    
    def _check_circuit_breaker(self, error_code: str):
        """检查并更新熔断器状态"""
        if error_code not in self.circuit_breakers:
            self.circuit_breakers[error_code] = CircuitBreaker()
        
        breaker = self.circuit_breakers[error_code]
        breaker.record_failure()
        
        if breaker.state == "open":
            from app.log.log_bus import get_logger
            logger = get_logger()
            logger.warning(
                component="circuit_breaker",
                action="tripped",
                message=f"熔断器已触发：{error_code}",
                show_in_status=True
            )
    
    def can_proceed(self, error_code: str) -> bool:
        """检查是否可以继续执行（熔断器检查）"""
        if error_code not in self.circuit_breakers:
            return True
        
        breaker = self.circuit_breakers[error_code]
        if not breaker.can_execute():
            from app.log.log_bus import get_logger
            logger = get_logger()
            logger.warning(
                component="circuit_breaker",
                action="blocked",
                message=f"操作被熔断器阻止：{error_code}",
            )
            return False
        
        return True
    
    def reset_circuit_breaker(self, error_code: str):
        """重置熔断器"""
        if error_code in self.circuit_breakers:
            self.circuit_breakers[error_code].record_success()
    
    def get_error_stats(self) -> Dict[str, int]:
        """获取错误统计"""
        return self.error_counts.copy()
    
    def reset_stats(self):
        """重置错误统计"""
        self.error_counts.clear()


# ============================================================================
# 装饰器
# ============================================================================

def handle_errors(error_code: Union[ErrorCode, str], 
                  fallback_return: Any = None,
                  component: str = "",
                  operation: str = "",
                  log_level: str = "error",
                  raise_on_error: bool = False):
    """
    错误处理装饰器
    
    Args:
        error_code: 错误码或错误码字符串
        fallback_return: 出错时的返回值
        component: 组件名（可选，默认使用函数所在类名）
        operation: 操作名（可选，默认使用函数名）
        log_level: 日志级别
        raise_on_error: 是否重新抛出异常
        
    Returns:
        装饰后的函数
        
    使用示例:
        @handle_errors(error_code=ErrorCode.OCR_ENGINE_001, fallback_return=[])
        def process_image(self, image):
            # 处理逻辑
            pass
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 提取组件名和操作名
            comp_name = component
            if not comp_name and args and hasattr(args[0], '__class__'):
                comp_name = args[0].__class__.__name__
            
            op_name = operation or func.__name__
            
            # 确定错误码
            if isinstance(error_code, str):
                try:
                    ec = ErrorCode[error_code]
                except KeyError:
                    ec = ErrorCode.UNKNOWN_001
            else:
                ec = error_code
            
            try:
                # 检查熔断器
                error_handler = ErrorHandler.get_instance()
                if not error_handler.can_proceed(ec.code):
                    raise OCRError(
                        ec, 
                        "操作被熔断器阻止",
                        component=comp_name,
                        operation=op_name
                    )
                
                # 执行原函数
                return func(*args, **kwargs)
                
            except Exception as e:
                # 处理异常
                error_handler.handle_error(
                    error_code=ec,
                    exception=e,
                    component=comp_name,
                    operation=op_name,
                    details={
                        'args': str(args)[:100],
                        'kwargs': str(kwargs)[:100]
                    },
                    log_level=log_level
                )
                
                if raise_on_error:
                    raise
                
                return fallback_return
        
        return wrapper
    return decorator


def retry_on_error(max_retries: int = 3, 
                   delay: float = 1.0,
                   backoff_factor: float = 2.0,
                   exceptions: tuple = (Exception,),
                   error_code: Optional[ErrorCode] = None):
    """
    自动重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff_factor: 退避因子（每次重试延迟倍增）
        exceptions: 需要重试的异常类型元组
        error_code: 错误码（用于日志记录）
        
    Returns:
        装饰后的函数
        
    使用示例:
        @retry_on_error(max_retries=3, delay=1.0, exceptions=(NetworkError,))
        def download_file(self, url):
            # 下载逻辑
            pass
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        # 记录重试日志
                        from app.log.log_bus import get_logger
                        logger = get_logger()
                        
                        comp_name = ""
                        if args and hasattr(args[0], '__class__'):
                            comp_name = args[0].__class__.__name__
                        
                        logger.warning(
                            component=comp_name or "retry",
                            action="retrying",
                            message=f"第{attempt + 1}次重试，等待{current_delay:.1f}秒",
                            show_in_status=False
                        )
                        
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        # 所有重试失败
                        if error_code:
                            error_handler = ErrorHandler.get_instance()
                            error_handler.handle_error(
                                error_code=error_code,
                                exception=e,
                                component=comp_name,
                                operation=func.__name__,
                            )
                        raise
            
            # 理论上不会到这里
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")
        
        return wrapper
    return decorator


def with_circuit_breaker(failure_threshold: int = 5, 
                         recovery_timeout: float = 60.0,
                         error_code: Optional[ErrorCode] = None):
    """
    熔断器装饰器
    
    Args:
        failure_threshold: 失败阈值
        recovery_timeout: 恢复超时（秒）
        error_code: 错误码（用于标识熔断器）
        
    Returns:
        装饰后的函数
        
    使用示例:
        @with_circuit_breaker(failure_threshold=5, error_code=ErrorCode.NETWORK_FAILED_001)
        def call_external_api(self):
            # API 调用逻辑
            pass
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            ec = error_code
            if ec is None:
                ec = ErrorCode.UNKNOWN_001
            
            error_handler = ErrorHandler.get_instance()
            
            # 检查熔断器状态
            if not error_handler.can_proceed(ec.code):
                raise OCRError(
                    ec,
                    "熔断器已打开，拒绝执行",
                    operation=func.__name__
                )
            
            try:
                result = func(*args, **kwargs)
                # 成功后重置熔断器
                error_handler.reset_circuit_breaker(ec.code)
                return result
            except Exception as e:
                # 失败时记录
                error_handler.handle_error(
                    error_code=ec,
                    exception=e,
                    operation=func.__name__,
                )
                raise
        
        return wrapper
    return decorator


# ============================================================================
# 便捷函数
# ============================================================================

def raise_error(error_code: ErrorCode, message: str = "", 
                component: str = "", operation: str = ""):
    """
    快速抛出错误
    
    Args:
        error_code: 错误码
        message: 附加消息
        component: 组件名
        operation: 操作名
    """
    error_handler = ErrorHandler.get_instance()
    context = error_handler.handle_error(
        error_code=error_code,
        exception=Exception(message),
        component=component,
        operation=operation,
    )
    
    # 根据错误类型抛出相应异常
    category = error_code.category
    if category == ErrorCategory.BUSINESS:
        raise BusinessError(error_code, message, context)
    elif category == ErrorCategory.IO:
        raise IOError(error_code, message, context)
    elif category == ErrorCategory.NETWORK:
        raise NetworkError(error_code, message, context)
    elif category == ErrorCategory.VALIDATION:
        raise ValidationError(error_code, message, context)
    elif category == ErrorCategory.CONFIGURATION:
        raise ConfigurationError(error_code, message, context)
    else:
        raise SystemError(error_code, message, context)


def ensure_condition(condition: bool, error_code: ErrorCode, 
                     message: str = "", component: str = "", 
                     operation: str = ""):
    """
    确保条件满足，否则抛出错误
    
    Args:
        condition: 需要确保的条件
        error_code: 错误码
        message: 附加消息
        component: 组件名
        operation: 操作名
    """
    if not condition:
        raise_error(error_code, message, component, operation)


# ============================================================================
# 全局辅助函数
# ============================================================================

def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器实例"""
    return ErrorHandler.get_instance()


def init_error_handler():
    """初始化错误处理器（如果需要特殊配置）"""
    return ErrorHandler.get_instance()
