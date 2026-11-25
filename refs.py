# refs.py —— 用正文实际引用的编号重建来源列表，保证正文与列表一致

TITLES = ("参考来源", "参考资料", "参考文献", "信息来源", "引用来源")

def rebuild_refs(report,pool):
    """从正文提取 [N]，按出现顺序用 pool 里的 URL 重列来源。返回 (新报告, 缺失编号)"""
    # 1. 切出正文（丢掉模型自己写的旧列表）
    cut=-1
    for key in TITLES:
        p=report.find(key)
        if p>0:
            cut=p
            break

    body=report[:cut] if cut>0 else report

    # 2. 按首次出现顺序收集编号
    order,i=[],0
    while True:
        a=body.find("[",i)
        if a==-1:
            break
        b=body.find("]",a)
        if b==-1:
            break
        s=body[a+1:b]
        #内容是纯数字且尚未收录
        if s.isdigit() and int(s) not in order:
            order.append(int(s))#加入列表，保留首次出现顺序
        i=b+1

    # 3. 按 order 生成列表
    lines,missing=[],[]
    for n in order:
        r=pool.get(n)
        if r:
            lines.append(f"[{n}] {r.get('title')} -- {r.get('url')}")
        else:
            missing.append(n)

    # 4. 拼回去
    out=body.rstrip()+"\n\n##参考来源\n\n"+"\n".join(lines)
    if missing:
        out+=f"\n\n>注：编号{missing}在检索结果中不存在，相关论断请谨慎参考"

    return out,missing