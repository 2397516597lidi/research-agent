# eval.py —— 批量跑 10 个主题，统计成功率与成本
import re
import os
from agent import run
import shutil

if os.path.exists("memory"):
    shutil.rmtree("memory")

TOPICS = [
    "企业级 AI Agent 在 2026 年的落地现状与主要阻碍",
    "RAG 技术在企业知识库问答中的应用与局限",
    "AI Agent 记忆机制的主流技术方案对比",
    "小模型替代大模型在垂直场景中的可行性",
    "多智能体协作系统的主要失败原因",
    "2026 年 AI 编程助手工具的格局与差异",
    "MCP（模型上下文协议）的采用现状与企业实践",
    "AI 客服系统在真实业务中的效果与问题",
    "医疗影像 AI 产品落地的主要障碍",
    "向量数据库的选型对比与性能瓶颈",
]

def judge(report):
    """判定一次调研是否成功，返回 (是否成功, 原因)"""
    if not report or len(report)<300:
        return False,"报告过短"

    urls=set(re.findall(r"https?://[^\s)\]>]+",report))
    if len(urls)<5:
        return False,f"引用不足({len(urls)}条)"

    sections=len(re.findall(r"^##\s",report,re.M))
    if sections<3:
        return False,f"结构不足({sections}节)"

    tail=report[-300:]
    if "公开资料有限" in tail or "资料不足" in tail:
        return False,"以资料不足收尾"


    return True,"OK"


if __name__=="__main__":
    rows=[]
    for i,topic in enumerate(TOPICS,1):
        print(f"\n{'='*66}\n[{i}/{len(TOPICS)}] {topic}")
        report,st=run(topic)
        # 落盘，跑完可以抽查
        os.makedirs("reports",exist_ok=True)
        with open(f"reports/{i:02d}.md","w",encoding="utf-8") as f:
            f.write(report or "")

        ok,why=judge(report or "")
        rows.append((i,topic,ok,why,st))
        print(f"  =>{'成功' if ok else '失败'}: {why}")

    print(f"\n{'='*66}\n评测汇总\n")
    print(f"{'#':<3}{'结果':<6}{'步数':<6}{'搜索':<6}{'读页':<6}{'耗时':<8}主题")
    for i,topic,ok,why,st in rows:
        mark="成功" if ok else "失败"
        print(f"{i:<3}{mark:<6}{st['steps']:<6}{st['search']:<6}"
              f"{st['read']:<6}{str(st['secs']) + 's':<8}{topic[:22]}")


    passed=sum(1 for r in rows if r[2])
    total_steps=sum(r[4]["steps"] for r in rows)
    total_secs=sum(r[4]["secs"] for r in rows)
    print(f"\n成功率：{passed}/{len(rows)}")
    print(f"平均步数：{total_steps/len(rows):.1f}")
    print(f"总耗时：{total_secs:.0f}s | 平均{total_secs/len(rows):.1f}s")

    fails=[(r[1],r[3]) for r in rows if not r[2]]
    if fails:
        print("\n失败明细：")
        for topic,why in fails:
            print(f"  -{topic[:24]} <- {why}")
