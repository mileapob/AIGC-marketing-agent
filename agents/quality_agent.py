"""
Quality Agent — 规则层文案质量检查
职责：检查 Script Agent 生成的文案是否达标，返回检查结果和更新后的重试次数
被 supervisor.py 的 node_quality_check 节点调用
"""


def run_quality_check(scripts: list, retry_count: int) -> dict:
    """
    对文案列表进行规则层质量检查

    检查规则：
      1. 必须生成3套文案（对应3个平台）
      2. 每套文案的正文（body）长度须超过50字

    不达标时自增 retry_count，supervisor 根据 retry_count 决定是否回退重试。
    retry_count >= 2 时 supervisor 强制放行，避免无限循环。

    Args:
        scripts:     Script Agent 生成的文案列表
        retry_count: 当前已重试次数

    Returns:
        {
            "quality_passed": bool,  # 本轮是否通过质量检查
            "retry_count":    int,   # 更新后的重试次数
        }
    """
    all_long_enough = all(len(s.get("body", "")) > 50 for s in scripts)
    passed = (len(scripts) == 3) and all_long_enough

    if not passed:
        # 不达标时自增 retry_count，确保最多重试2次后强制放行
        retry_count += 1
        print(f"[QualityAgent] 文案不达标（当前{len(scripts)}套），retry_count 更新为 {retry_count}")
    else:
        print(f"[QualityAgent] 文案通过质量检查，进入图片生成阶段")

    return {
        "quality_passed": passed,
        "retry_count": retry_count,
    }
