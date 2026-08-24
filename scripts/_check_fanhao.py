import json, re, os

# 加载番号大全数据
with open(os.path.join(os.environ.get("TEMP",""), "fanhao_data.json"), encoding="utf-8") as f:
    fanhao = json.load(f)

# 建 code -> (actress, title) 映射
code_map = {}
for a in fanhao:
    for item in a.get("data", []):
        code = (item.get("code") or "").strip().upper()
        if code and code not in code_map:
            code_map[code] = (a["name"], item.get("title",""))

print(f"番号大全总女优数: {len(fanhao)}, 总番号数: {len(code_map)}")

# 加载我们的 881 部
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ours = {}
ad = os.path.join(BASE, "data", "actresses")
for name in os.listdir(ad):
    wdir = os.path.join(ad, name, "works")
    if not os.path.isdir(wdir): continue
    for fn in os.listdir(wdir):
        code = fn[:-5]
        ours[code] = name

print(f"我们的番号数: {len(ours)}")
hit = [c for c in ours if c in code_map]
print(f"覆盖命中: {len(hit)}/{len(ours)} ({100*len(hit)/len(ours):.1f}%)")

# 按女优统计
from collections import Counter
cnt = Counter(ours[c] for c in hit)
tot = Counter(ours.values())
for name in tot:
    print(f"  {name}: {cnt.get(name,0)}/{tot[name]}")

# 看看 title 字段的脏数据格式
print("\n--- title 字段样例（含分隔符）---")
for c in hit[:5]:
    print(f"{c}: {code_map[c][1][:150]!r}")
