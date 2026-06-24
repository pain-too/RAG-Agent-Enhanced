""" 规则编译器 —— 把人类能看懂的 YAML 规则，翻译成机器能跑的正则表达式"""

#关键语法解释
    # 一个点 . 是正则里的通配符，匹配任意一个字符（除了换行符）
    # {0,10} 是重复次数，意思是「前面的东西出现 0 到 10 次」
    # gap 是关键词和关键词之间，可以被隔开多远。比如：两个关键词是刀、枪，"刀旁边有一把枪" 隔5个字也能识别

"""
三个函数的关系

compile_rules()          ← 入口。「启动时调我一次就行」
  │
  └─ 遍历 YAML 每条规则 ─→ compile_rule()
                              │
                              ├─ 有 raw_pattern？ → 直接用
                              └─ 没有？           → compile_keyword_pools()
                                                      │
                                                    把 [["忽略","忘记"],["指令","规则"]]
                                                    变成 "(忽略|忘记).{0,10}(指令|规则)"
"""

import re

def compile_keyword_pools(pools: list[list[str]], max_gap: int = 10) -> str:
    """ 将多组关键词池编译为一个正则表达式。
    参数:
        pools:   关键词池列表，如 [
                    ["忽略", "忘记", "ignore", "forget"],
                    ["之前", "指令", "previous", "instructions"],
                    ["规则", "约束", "rules", "constraints"],
                ]
        max_gap: 组间最大字符间距

    返回:
        编译后的正则字符串（已开启大小写不敏感），如:
        "(忽略|忘记|ignore|forget).{0,10}(之前|指令|previous|instructions).{0,10}(规则|约束|rules|constraints)"
    """

    if not pools or len(pools) < 1:
        raise ValueError("pools 至少需要一组关键词")

    groups = []
    for pool in pools:
        if not pool:
            raise ValueError("每组关键词池不能为空")
        # re.escape 转义每个关键词中的正则特殊字符
        escaped = [re.escape(k) for k in pool]
        groups.append(f"({'|'.join(escaped)})")

    # 组间允许 0～max_gap 个任意字符
    gap = ".{0," + str(max_gap) + "}"
    return gap.join(groups)


def compile_rule(rule: dict) -> str:
    """ 编译单条规则为正则字符串。
    参数:
        rule: YAML 中的单条规则字典，可包含:
              - pools + max_gap → 编译关键词池
              - raw_pattern      → 直接使用（优先级更高）
    返回:
        编译后的正则字符串
    """
    # raw_pattern 优先 —— 复杂模式直接使用
    if "raw_pattern" in rule and rule["raw_pattern"]:
        return rule["raw_pattern"]

    # 关键词池编译
    pools = rule.get("pools", [])
    if not pools:
        raise ValueError(f"规则 '{rule.get('name', 'unknown')}' 既无 pools 也无 raw_pattern")

    max_gap = rule.get("max_gap", 10)
    return compile_keyword_pools(pools, max_gap)


def compile_rules(patterns_config: dict) -> list[dict]:
    """ 以compile_rule为核心的大循环，反复执行"""
    patterns = patterns_config.get("patterns", [])
    compiled_list = []

    for attack_group in patterns:
        attack_type = attack_group.get("attack_type", "UNKNOWN")
        severity = attack_group.get("severity", "WARNING")
        rules = attack_group.get("rules", [])

        for rule in rules:
            rule_name = rule.get("name", "unnamed")
            try:
                pattern_str = compile_rule(rule)
            except Exception as e:
                # 编译失败的规则跳过并告警，不影响其他规则
                import logging
                logging.getLogger(__name__).warning(
                    f"[规则编译] 跳过规则 '{rule_name}': {str(e)}"
                )
                continue

            # 给规则新增了两个字段 
            # compiled_pattern: "(忽略|忘记|...).{0,10}(...)"
            # compiled_regex: 编译后的正则表达式对象，用于后续匹配
            compiled_list.append({
                "name": rule_name,
                "attack_type": attack_type,
                "severity": severity,
                "description": rule.get("description", ""),
                #新增
                "compiled_pattern": pattern_str,
                "compiled_regex": re.compile(pattern_str, re.IGNORECASE),
                # 保留原始关键词池，供安全剥离时做精确定位
                "pools": rule.get("pools", []),
                "raw_pattern": rule.get("raw_pattern", ""),
            })
    return compiled_list