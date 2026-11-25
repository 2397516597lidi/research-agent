# agent.py —— 自动调研 Agent：自主搜索 → 按需取细节 → 写带出处的报告
import os
import json
import time
import requests
from datetime import datetime, timezone
from refs import rebuild_refs


# 搜索层从 filter_demo.py 复用，保证只有一份实现
from filter_demo import search as search_raw, filter_results, text_of

# ========== 配置 ==========
DS_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DS_KEY:
    raise RuntimeError("先设环境变量：set DEEPSEEK_API_KEY=sk-...")

CHAT_URL = "https://api.deepseek.com/chat/completions"
SEARCH_URL = "https://api.deepseek.com/v1/tools/search"

MAX_STEPS = 12          # 硬上限，防死循环
MAX_PAGE_CHARS = 2000   # read_page 单次最多返回多少字

POOL={}# 结果池 {编号: 原始结果}，供 read_page 按编号取全文
_next_idx=0# 全局编号，多次搜索不重号


# ========== 工具 1：搜索（只返回摘要，省上下文）==========
def search_web(query,count=6):
    """搜索网页，返回标题/摘要/日期/URL/编号。不给全文"""
    global _next_idx
    kept,_=filter_results(search_raw(query,count=count*2))
    kept=kept[:count]

    if not kept:
        return json.dumps({"msg":"没有搜到符合条件的结果，换个关键词试试"},ensure_ascii=False)

    out=[]
    for r in kept:
        _next_idx+=1
        POOL[_next_idx]=r
        out.append({
            "idx":_next_idx,
            "title":r.get("title"),
            "summary":(r.get("summary") or "")[:600],
            "date":(r.get("date") or "")[:10],
            "url":r.get("url"),
        })

    return json.dumps(out,ensure_ascii=False)


# ========== 工具 2：读正文（按编号取，可翻页）==========
def read_page(idx,start=0):
    """读取第 idx 条结果的正文，从 start 字开始，最多 MAX_PAGE_CHARS 字"""
    try:
        idx=int(idx)
        start=int(start)
    except (TypeError,ValueError):
        return json.dumps({"error": "idx 和 start 必须是数字"},
                          ensure_ascii=False)

    r=POOL.get(idx)
    if not r:
        return json.dumps({"error":f"编号{idx}不存在,请先用search_web搜索"},
                          ensure_ascii=False)

    content=text_of(r)
    part=content[start:start+MAX_PAGE_CHARS]

    return json.dumps({
        "idx":idx,
        "title":r.get("title"),
        "url":r.get("url"),
        "total_chars":len(content),
        "returned":len(part),
        "has_more":start+MAX_PAGE_CHARS<len(content),
        "content":part
    },ensure_ascii=False)


# ========== 工具说明书 ==========
def tool(name, desc, props, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }

TOOLS=[
    tool(
        name="search_web",
        desc="搜索网页，返回标题、摘要（约600字）、发布日期、URL 和编号。想看全文需再用 read_page",
        props={
            "query":{"type":"string","description":"搜索关键词，支持 site: 等语法"},
            "count":{"type":"integer","description":"返回条数：1~10，默认6"},
        },
        required=["query"],
    ),
    tool(
      name="read_page",
      desc="按编号读取某条搜索结果的正文，单次最多返回 2000 字，超出需用 start 翻页",
      props={
          "idx":{"type":"integer","description":"search_web返回的编号"},
          "start":{"type":"integer","description":"从第几个字开始，默认0"},
      },
      required=["idx"],
    ),
]

FUNC_MAP={"search_web":search_web,"read_page":read_page}


# ========== 系统提示 ==========
SYSTEM = """你是调研助手。给定一个主题，你自己搜索、阅读，最后写出一份调研报告。

工作方式：
1. 先把主题拆成 2~3 个关键词方向，分别调用 search_web
2. 看摘要判断哪些值得细读，对关键的 3~5 条调用 read_page 取正文
3. 发现信息不够就再搜，够了就停止调用工具，直接输出报告
4. 报告用 markdown：第一行用 # 写报告标题，之后每个章节必须用 ## 开头（如 "## 一、xxx"），
   至少 3 个章节；每个论断后用 [编号] 标出处
5. 报告末尾用 `## 参考来源` 作为标题，按编号列出所有引用过的 URL

硬性要求：
- 只能写搜索结果里有的信息，不要用你自己的知识补充
- 资料不足就明确说"公开资料有限"，不要硬凑
- 最多 12 步，不要无限搜索"""


# ========== 循环主体 ==========
def run(topic):
    global _next_idx
    POOL.clear()  # 清空上次的结果池
    _next_idx = 0  # 编号从 1 重新开始

    messages=[
        {"role":"system","content":SYSTEM},
        {"role":"user","content":f"请调研这个主题并写出报告：{topic}"},
    ]
    t0=time.time()# ← 新增：记开始时间
    stats={"steps":0,"search":0,"read":0,"secs":0}# ← 新增：统计容器

    for step in range(1,MAX_STEPS+1):
        stats["steps"] = step # ← 新增：记当前是第几步（循环覆盖，最后留下的是总步数）

        resp=requests.post(CHAT_URL,timeout=120,
                           headers={"Authorization":f"Bearer {DS_KEY}","Content-Type":"application/json"},
                           json={"model": "deepseek-flash", "messages": messages,
                                 "tools": TOOLS, "stream": False},
        )
        resp.raise_for_status()
        msg=resp.json()["choices"][0]["message"]
        messages.append(msg)

        #不再调用工具=写完
        if not msg.get("tool_calls"):
            stats["secs"]=round(time.time()-t0,1) # ← 新增：出口一，正常结束补耗时
            print(f"\n[{step}]生成报告\n")
            #return msg.get("content"),stats
            report,missing=rebuild_refs(msg.get('content') or "",POOL)# ← 新增
            if missing:
                print(f"  ⚠ 正文引用了不存在的编号：{missing}")
            return report,stats

        for tc in msg["tool_calls"]:
            name=tc["function"]["name"]
            stats["search" if name=="search_web" else "read"]+=1# ← 新增：按工具名累加次数

            try:
                args=json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args={}

            fn=FUNC_MAP.get(name)
            try:
                result=fn(**args) if fn else json.dumps(
                    {"error":f"没有工具{name}"},ensure_ascii=False
                )
            except Exception as e:
                result=json.dumps({"error":str(e)},ensure_ascii=False)

            preview=result[:110].replace("\n"," ")
            print(f"[{step}]{name}({args}) -> {preview}...")

            messages.append({
                "role":"tool",
                "tool_call_id":tc["id"],
                "content":result,
            })

    stats["secs"]=round(time.time()-t0,1)# ← 新增：出口二，撞上限补耗时
    print(f"\n到达最大步数{MAX_STEPS}，强制停止")
    return None,stats


if __name__=="__main__":
    report,stats=run("企业级 AI Agent 在 2026 年的落地现状与主要阻碍")
    print(f"\n统计：步数{stats['steps']} | 搜索{stats['search']}次 | "
          f"读页{stats['read']}次 | 耗时{stats['secs']}s")
    if report:
        print("="*70)
        print(report)