# -*- coding: utf-8 -*-
"""
sweep_works.py —— 跑完 update_metadata.py 之后的工作区清扫器。

做两件事（都遵循「文件名/原值优先」的项目铁律）：

1. 剔除格式化噪声
   update_metadata 落盘用 json.dumps(indent=2)，与仓库既有文件的 1 空格缩进不同，
   会制造大量「内容没变、只有缩进变了」的假改动。凡语义与 HEAD 完全一致的文件，
   按 HEAD 原始字节整份写回，让 git diff 只剩真实改动。

2. 还原被抓取器覆盖的归属字段
   codeav 按设计只返回 JSON-LD actor 单例（共演作品只报主演）。若拿它去覆盖
   来自 115 文件名的归属，会把共演作品误杀，且 source 标记还会停留在 filename
   说谎。故 actress / source 一律以 HEAD 原值为准；原值为空、由抓取器首次
   补全的属合法填充，予以保留。

3. 回退「冲突型 cast 填充」
   HEAD 原本没有 actresses，本次却填进了一个与 owner 归一化后不同的女优。
   这种单例 cast 极可能是抓取器只报主演造成的，留着会造出
   owner=甲 / actresses=[乙] 的自相矛盾数据，令归属校验与 build_index 的
   owner 兜底持续误判。故一律回退到 HEAD 状态。

用法：
    python scripts/sweep_works.py            # 实际执行
    python scripts/sweep_works.py --dry-run  # 只看会做什么
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources.base import normalize_name  # 去括号别名 + 已知变体

WORKS_DIR = os.path.join("data", "works")
# 归属语义字段，成对还原，杜绝「值来自抓取器但 source 谎称 filename」
ATTRIB_KEYS = ("actress", "source")


def _head_blobs(path_prefix):
    """一次性取 HEAD 下某目录全部文件的原始内容（批量 cat-file，避免 N 次子进程）。"""
    out = subprocess.run(
        ["git", "ls-tree", "-r", "HEAD", path_prefix],
        capture_output=True, text=True,
    ).stdout
    entries = []
    for line in out.splitlines():
        if "\t" not in line:
            continue
        meta, path = line.split("\t", 1)
        parts = meta.split()
        if len(parts) < 3:
            continue
        entries.append((path, parts[2]))
    if not entries:
        return {}

    p = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    )
    buf, _ = p.communicate(("\n".join(s for _, s in entries) + "\n").encode())

    blobs = {}
    idx = 0
    for path, sha in entries:
        nl = buf.index(b"\n", idx)
        _sha, _type, size = buf[idx:nl].decode().split()
        size = int(size)
        start = nl + 1
        blobs[path] = buf[start:start + size].decode("utf-8")
        idx = start + size + 1
    return blobs


def main():
    dry = "--dry-run" in sys.argv
    if dry:
        print("### DRY-RUN：只报告，不写盘 ###\n")

    blobs = _head_blobs(WORKS_DIR)

    changed = subprocess.run(
        ["git", "diff", "--name-only", WORKS_DIR],
        capture_output=True, text=True,
    ).stdout.split()

    n_fmt = 0       # 纯格式化噪声
    n_attrib = 0    # 归属被还原
    n_cast = 0      # 冲突型 cast 填充被回退
    n_keep = 0      # 真实补全，保留
    n_err = []

    for f in changed:
        raw = blobs.get(f)
        if raw is None:
            n_err.append((f, "HEAD 无此文件"))
            continue
        try:
            old = json.loads(raw)
        except Exception as e:
            n_err.append((f, "HEAD 解析失败: %s" % e))
            continue
        if not os.path.exists(f):
            n_err.append((f, "工作区文件缺失（被中途截断？需 git checkout 恢复）"))
            continue
        try:
            new = json.loads(open(f, encoding="utf-8").read())
        except Exception as e:
            n_err.append((f, "当前文件解析失败: %s" % e))
            continue

        # 1) 归属还原：仅在 HEAD 原值非空时覆盖回去
        reverted = False
        for k in ATTRIB_KEYS:
            if old.get(k) and old.get(k) != new.get(k):
                new[k] = old[k]
                reverted = True

        # 1.5) 冲突型 cast 回退：HEAD 无演员表，新填的又不含 owner
        cast_reverted = False
        owner = new.get("actress")
        if not old.get("actresses") and new.get("actresses") and owner:
            if normalize_name(owner) not in {normalize_name(x) for x in new["actresses"]}:
                if "actresses" in old:
                    new["actresses"] = old["actresses"]
                else:
                    new.pop("actresses", None)
                cast_reverted = True

        # 2) 语义无变化 -> 按原始字节整份还原，消除缩进噪声
        if new == old:
            if not dry:
                with open(f, "w", encoding="utf-8", newline="") as fh:
                    fh.write(raw)
            # 只因冲突 cast 被回退才归于「无变化」的，单列统计
            if cast_reverted:
                n_cast += 1
            else:
                n_fmt += 1
            continue

        if not dry:
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(new, ensure_ascii=False, indent=2) + "\n")
        if cast_reverted:
            n_cast += 1
        elif reverted:
            n_attrib += 1
        else:
            n_keep += 1

    print("清扫结果：")
    print("  纯格式化噪声（已按原始字节还原）: %d" % n_fmt)
    print("  归属字段被还原（actress/source）: %d" % n_attrib)
    print("  冲突型 cast 填充被回退          : %d" % n_cast)
    print("  真实补全，保留                  : %d" % n_keep)
    print("  异常                            : %d" % len(n_err))
    for f, why in n_err[:20]:
        print("    -", f, "|", why)
    return 0


if __name__ == "__main__":
    sys.exit(main())
