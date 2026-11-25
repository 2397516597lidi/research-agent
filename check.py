# check.py —— 检查报告里的引用是否完整（自动化部分）
import re
import glob
import os

TITLES = ("参考来源", "参考资料", "参考文献", "信息来源", "引用来源")

LB, RB = re.escape("["), re.escape("]")   # 运行时生成转义符，源码里不出现字面反斜杠

for path in sorted(glob.glob("reports/*.md")):
    text=open(path,encoding="utf-8").read()

    # 用「参考来源」切开：前面是正文，后面是来源列表
    idx=-1
    for key in TITLES:
        p=text.find(key)
        if p>0:
            idx=p
            break

    body=text[:idx] if idx>0 else text
    tail=text[idx:] if idx>0 else ""

    cited={int(m) for m in re.findall(LB+r"(\d+)"+RB,body)}# 正文引用过的编号
    # 来源列表里的编号，兼容「1. xxx」和「[1] xxx」两种写法
    listed = {int(m) for m in re.findall(r"^ *(\d+)[.]", tail, re.M)}
    listed |= {int(m) for m in re.findall("^ *" + LB + r"(\d+)" + RB, tail, re.M)}

    orphan=cited-listed
    unused=listed-cited

    name=os.path.basename(path)
    found="找到" if idx>0 else "未找到"
    print(f"\n{name}：正文引用{len(cited)}个编号，来源列表{len(listed)}条（{found}分隔标题）")

    if orphan:
        print(f"  ⚠ 引用了但列表缺失：{sorted(orphan)}")
    else:
        print("  ✓ 引用编号都有对应来源")

    if unused:
        print(f"  列表里未被引用：{sorted(unused)}")