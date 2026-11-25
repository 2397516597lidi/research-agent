# filter_demo.py —— 搜索结果预处理：相关性 + 来源 + 时效 三道筛，并算上下文预算
import os
import requests
from datetime import datetime, timezone

KEY = os.getenv("DEEPSEEK_API_KEY")
if not KEY:
    raise RuntimeError("先设环境变量：set DEEPSEEK_API_KEY=sk-...")

SEARCH_URL = "https://api.deepseek.com/v1/tools/search"

def search(query,count=10):
    """调 Search 接口，返回 results 列表"""
    resp=requests.post(SEARCH_URL,timeout=60,headers={
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
    },json={"query":query,"count":count,"need_content":True})
    resp.raise_for_status()
    return resp.json().get("results",[])

def parse_date(s):
    """'2026-11-02T16:00:00Z' -> datetime；解析失败返回 None"""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError:
        return None

def filter_results(results,max_age_days=180,min_score=1.5,min_authority=3):
    """三道筛：相关性 / 来源权威 / 时效。返回 (保留, 丢弃[(标题, 原因)])"""
    kept,dropped=[],[]
    now=datetime.now(timezone.utc)

    for r in results:
        title=(r.get("title") or "")[:30]

        # 筛 1：相关性。官方口径 rerank_score 0~3，>=1.5 为优质
        score=r.get("rerank_score")
        if score is None:
            dropped.append((title,"无重排分"))
            continue
        if score<min_score:
            dropped.append((title,f"相关性弱：{score:.2f}<{min_score}"))
            continue

        # 筛 2：来源权威。authority 0~4，-1 表示未知（未知放行，不当 0 分打死）
        auth=r.get("authority")
        if auth is not None and 0<=auth<min_authority:
            dropped.append((title,f"来源弱：authority={auth}<{min_authority}"))
            continue

        # 筛 3：时效。date 缺失不丢，只是无法判断新旧
        d=parse_date(r.get("date") or "")
        if d:
            age_days=(now-d).total_seconds()/86400
            if age_days>max_age_days:
                dropped.append((title,f"太旧：{age_days:.0f}天前"))
                continue

        kept.append(r)

    return kept,dropped

def text_of(r):
    """取正文：need_content=True 时在 content；content 空则退回 summary"""
    return r.get("content") or r.get("summary") or ""

if __name__=="__main__":
    q="企业级AI Agent 落地 2026"
    results=search(q)
    print(f"搜索【{q}】返回{len(results)}条\n")
    kept,dropped=filter_results(results)

    print(f"保留{len(kept)}条：")
    for r in kept:
        d=(r.get("date") or "")[:10]
        n=len(text_of(r))
        print(f"  {r.get("rerank_score",0):.2f} auth={r.get("authority")}  {d}  "
              f"正文{n}字  {(r.get("title") or "")[:28]}")

    print(f"\n丢弃{len(dropped)}条：")
    for title,reason in dropped:
        print(f"  {title} <- {reason}")

    # 上下文预算：这是决定要不要压缩的依据
    if kept:
        lens=[len(text_of(r)) for r in kept]
        total=sum(lens)
        print(f"\n正文合计{total:,}字，最长{max(lens):,}字")
        print(f"按中文约1.5字/token估算：约{int(total/1.5):,}tokens")