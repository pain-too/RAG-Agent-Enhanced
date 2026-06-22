"""
安全门模块（Input Guard）—— Agent 输入安全防护

对外接口：
    input_guard(user_input: str) → GuardResult

数据结构（无需 langchain 依赖，可独立导入）：
    GuardResult     — 最终判定结果
    SanitizeResult  — Layer 1 清洗结果
    DetectionResult — Layer 2 检测结果
    RewriteResult   — Layer 3 重写结果
    Verdict         — 判定枚举（ALLOW / SANITIZE / BLOCK）
"""

# 数据结构无第三方依赖，直接导出
from guard.guard_types import (
    GuardResult,
    SanitizeResult,
    DetectionResult,
    RewriteResult,
    Verdict,
)


def __getattr__(name):
    """
    懒加载 input_guard（它依赖 langchain，不是所有场景都需要）。
    只有在代码中写 from guard import input_guard 或 guard.input_guard(...) 时才触发导入。
    """
    if name == "input_guard":
        from guard.input_guard import input_guard as _input_guard
        # 缓存到模块字典中，下次访问不再走 __getattr__
        import sys
        this_module = sys.modules[__name__]
        this_module.input_guard = _input_guard
        return _input_guard

    raise AttributeError(f"模块 'guard' 没有属性 '{name}'")


__all__ = [
    "input_guard",
    "GuardResult",
    "SanitizeResult",
    "DetectionResult",
    "RewriteResult",
    "Verdict",
]
