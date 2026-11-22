"""S1-RES-006 交付物自检脚本（只用 Python 标准库，Python 3.9+）。

用法：
    python check_sources.py            # 全部检查，含逐条请求来源链接
    python check_sources.py --offline  # 跳过联网检查（无网络环境）

可选环境变量：
    CHECK_TIMEOUT   单条链接超时秒数，默认 30
    CHECK_RETRIES   单条链接失败重试次数，默认 2

任何一项不通过，退出码为 1；全部通过为 0。
"""
import csv
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
MEMO = os.path.join(HERE, "memo.md")
TABLE_CSV = os.path.join(HERE, "membership_rights_matrix.csv")
TABLE_MD = os.path.join(HERE, "membership_rights_matrix.md")
SOURCES = os.path.join(HERE, "sources.csv")
DELIVERABLES = [MEMO, TABLE_CSV, TABLE_MD, SOURCES, os.path.join(HERE, "README.md")]

OBJECTS = ["对象一：正和岛", "对象二：中国软件行业协会", "对象三：中国互联网协会"]
SUBSECTIONS = ["### 对象", "### 做法", "### 可借鉴点", "### 不适用点", "### 公开来源链接"]
QUESTIONS = ["①", "②", "③", "④", "⑤", "⑥"]
MODULES = ["资源对接与商机流转", "会员数据中台与 CRM", "小程序会员端"]
# 会费金额：货币符号加数字，或数字加货币单位
MONEY = re.compile(r"[¥￥$]\s*\d|\d[\d,，.]*\s*(元|万元|万|亿元|千元|块|RMB|CNY|USD|美元)", re.I)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def section(text, title, level="## "):
    """取出从标题行到下一个同级标题之间的内容。"""
    start = text.find(level + title)
    if start < 0:
        return ""
    nxt = text.find("\n" + level, start + 1)
    return text[start:] if nxt < 0 else text[start:nxt]


def fetch(url, timeout, retries):
    last = ""
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 S1-RES-006-check"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, ""
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code < 500 and e.code != 429:
                return e.code, last
        except Exception as e:  # 网络错误
            last = type(e).__name__
        time.sleep(2 * (i + 1))
    return None, last


def main():
    offline = "--offline" in sys.argv
    timeout = int(os.environ.get("CHECK_TIMEOUT", "30"))
    retries = int(os.environ.get("CHECK_RETRIES", "2"))
    memo = read(MEMO)

    # 1. 字数：同时给出两种口径，都必须在 3000–5000
    cjk = len(re.findall(r"[一-鿿]", memo))
    punct = len(re.findall(r"[　-〿＀-￯—…“”‘’]", memo))
    words = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9._:/%\-]*", memo))
    word_style = cjk + punct + words
    check("备忘录字数 3000–5000（汉字数 与 Word 口径：汉字+标点+英文数字词）",
          3000 <= cjk <= 5000 and 3000 <= word_style <= 5000, f"汉字 {cjk}，Word 口径 {word_style}")

    # 2. 三个对象各有独立小节，每节五段，做法覆盖 ①–⑥
    for obj in OBJECTS:
        sec = section(memo, obj)
        subs = [s for s in SUBSECTIONS if s in sec]
        qs = [q for q in QUESTIONS if q in section(sec, "做法", "### ")]
        check(f"「{obj}」独立小节，五段齐全，做法覆盖研究问题①–⑥",
              bool(sec) and len(subs) == 5 and len(qs) == 6, f"五段 {len(subs)}/5，研究问题 {len(qs)}/6")

    # 3. 商会章程来源为官方网站公开文件
    rows = list(csv.DictReader(open(SOURCES, encoding="utf-8")))
    by_id = {r["编号"]: r for r in rows}
    charters = [r for r in rows if "章程" in r["标题"]]
    official = [r for r in charters if "官方网站" in r["发布方"] and r["链接"].startswith("https://www.")]
    check("两家商会章程来源都是官方网站公开文件，并在备忘录写明名称与来源",
          len(official) == 2 and all(r["编号"] in memo for r in official) and "章程来源 S08" in memo and "章程来源 S13" in memo,
          "；".join(f"{r['编号']} {r['发布方']}" for r in official))

    # 4. 会员分级 × 权利义务表：至少 4 个级别（按对象统计）
    trows = list(csv.DictReader(open(TABLE_CSV, encoding="utf-8")))
    per_obj = Counter(r["对象"] for r in trows)
    filled = all(r["主要权利"].strip() and r["主要义务"].strip() and r["来源"].strip() for r in trows)
    md_rows = [l for l in read(TABLE_MD).splitlines() if l.startswith("| ") and not l.startswith("| 对象")]
    check("「会员分级 × 权利义务」表至少覆盖 4 个会员级别（每个对象都不少于 4 个）",
          len(per_obj) == 3 and min(per_obj.values()) >= 4 and filled and len(md_rows) == len(trows),
          f"共 {len(trows)} 行：" + "，".join(f"{k} {v} 级" for k, v in per_obj.items()) + f"；md 与 csv 行数一致 {len(md_rows)}={len(trows)}")

    # 5. 供需对接机制单列一节，至少 5 个，且每个都映射到商机流转环节并给出字段
    sd = section(memo, "供需对接机制（单列）")
    mechs = re.findall(r"^- (M\d+) .*$", sd, re.M)
    mapped = [m for m in re.findall(r"^- (M\d+ .*)$", sd, re.M) if "环节：" in m and "字段：" in m]
    check("供需对接机制单列一节，至少 5 个机制，每个写明商机流转环节和字段",
          bool(sd) and len(mechs) >= 5 and len(mapped) == len(mechs), f"机制 {len(mechs)} 个：{', '.join(mechs)}；写明环节和字段 {len(mapped)} 个")

    # 6. 来源不少于 8 条，均有访问日期；备忘录引用与登记表一致
    dated = [r for r in rows if re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["访问日期"] or "")]
    cited = set(re.findall(r"S\d{2}", memo))
    check("公开来源不少于 8 条且均有访问日期", len(rows) >= 8 and len(dated) == len(rows), f"{len(rows)} 条，有访问日期 {len(dated)} 条")
    check("备忘录引用的来源编号与登记表完全一致", cited == set(by_id), f"备忘录 {len(cited)} 个，登记表 {len(by_id)} 个，差异 {sorted(cited ^ set(by_id))}")
    urls_in_memo = all(r["链接"] in memo for r in rows)
    check("每条来源链接都写在备忘录的「公开来源链接」段", urls_in_memo)

    # 7. 来源链接逐条可打开
    if offline:
        print("[SKIP] 联网检查已跳过（--offline）")
    else:
        bad = []
        for r in rows:
            code, err = fetch(r["链接"], timeout, retries)
            # 只打印编号和状态，链接见 sources.csv（输出要能原样贴进交付正文，平台正文不接受站外链接）
            print(f"       {r['编号']} HTTP {code if code else '-'}" + (f" ({err})" if err and code != 200 else ""))
            if code != 200:
                bad.append(r["编号"])
        check("全部来源链接实时请求返回 HTTP 200", not bad, f"失败 {bad}" if bad else f"{len(rows)}/{len(rows)}")

    # 8. 全文不出现会费金额
    hits = []
    for p in DELIVERABLES:
        if not os.path.exists(p):
            continue
        for n, line in enumerate(read(p).splitlines(), 1):
            for m in MONEY.finditer(line):
                hits.append(f"{os.path.basename(p)}:{n} {m.group(0)}")
    check("全部交付文件不出现会费金额（货币符号或货币单位前后的数字）", not hits, "; ".join(hits[:5]) if hits else "0 处")

    # 9. 范围补充：可借鉴点映射三个模块；不适用点分析社团法人约束与主管单位指导属性
    take = "".join(section(section(memo, o), "可借鉴点", "### ") for o in OBJECTS)
    check("可借鉴点映射到三个模块", all(m in take for m in MODULES), "，".join(f"{m} {take.count(m)} 次" for m in MODULES))
    na = [section(section(memo, o), "不适用点", "### ") for o in OBJECTS[1:]]
    check("两家协会的不适用点都分析了社团法人章程约束和行业主管单位指导属性",
          all("社团法人" in s and "主管单位指导属性" in s for s in na))

    ok = all(results)
    print(f"\n{'ALL PASS' if ok else 'FAILED'}（{sum(results)}/{len(results)} 项）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
