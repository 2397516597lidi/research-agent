# memory.py —— 跨任务记忆：按主题存取"读过什么"
import os
import json
import hashlib


MEM_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),"memory")

def _key(topic):
    """主题 → 文件名。只保留字母数字汉字，再拼 md5 避免重名"""
    h=hashlib.md5(topic.encode("utf-8")).hexdigest()[:10]
    safe="".join(c for c in topic if c.isalnum())[:20]
    return f"{safe}_{h}.json"

def load(topic):
    """读取该主题的历史记忆，没有就返回空结果"""
    path=os.path.join(MEM_DIR,_key(topic))
    if not os.path.exists(path):
        return {"topic":topic,"pages":[],"runs":0}
    with open(path,encoding="utf-8") as f:
        return json.load(f)

def save(topic,mem):
    """写回记忆"""
    os.makedirs(MEM_DIR, exist_ok=True)
    path=os.path.join(MEM_DIR,_key(topic))
    with open(path,"w",encoding="utf-8") as f:
        json.dump(mem,f,ensure_ascii=False,indent=2)

def add_page(mem,url,title,summary):
    """记一条读过的页面，同一URL不重复记"""
    if any(p.get("url")==url for p in mem["pages"]):
        return False
    mem["pages"].append({
        "url":url,
        "title":title or "",
        "summary":(summary or "")[:200],
    })
    return True

def known_urls(mem):
    """返回已读 URL 集合，供 search_web 过滤"""
    return {p.get("url") for p in mem["pages"] if p.get('url')}

def digest(mem,max_items=12):
    """生成给模型看的已读摘要，注入 system prompt"""
    pages=mem.get("pages") or []
    if not pages:
        return ""
    lines=[f"你之前已经读过以下{len(pages)}篇资料，不要重复阅读："]
    for p in pages[:max_items]:
        lines.append(f"-{p.get('title')} ({p.get('url')})")
    if len(pages)>max_items:
        lines.append(f"-......另有{len(pages)-max_items}篇")
    return "\n".join(lines)

if __name__=="__main__":
    topic="测试主题"
    m=load(topic)
    add_page(m,"https://a.com","文章A","摘要内容"*20)
    add_page(m, "https://a.com", "重复的 A", "不该被加进去")
    add_page(m, "https://b.com", "文章 B", "摘要内容" * 20)
    m["runs"]=m.get("runs",0)+1
    save(topic,m)

    m2=load(topic)
    print(f"页面数：{len(m2['pages'])}")  # 应为 2
    print(f"runs：{m2['runs']}")
    print("\n" + digest(m2))