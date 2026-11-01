#!/usr/bin/env python3
"""Coleta os donos dos primeiros N presentes de cada coleção (páginas públicas t.me/nft)."""
import json, os, re, sys, time, html, urllib.request, concurrent.futures as cf
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs")
N = int(os.environ.get("OWNERS_N", "100"))
UA = {"User-Agent": "Mozilla/5.0 (telegram-gifts-site owners scraper)"}

def fetch(slug):
    h = None
    for t in range(5):  # o t.me às vezes devolve uma página resumida sem a tabela; tenta de novo
        try:
            h = urllib.request.urlopen(urllib.request.Request("https://t.me/nft/" + slug, headers=UA), timeout=20).read().decode()
            if "tgme_gift_table" in h: return h
        except Exception:
            pass
        time.sleep(0.5 + t * 0.7)
    return h

def parse(h):
    m = re.search(r"<th>Owner</th><td>(.*?)</td>", h or "", re.S)
    if not m: return None
    o = m.group(1)
    addr = "tgme_gift_owner_address" in o
    txt = html.unescape(re.sub(r"<[^>]+>", "", o)).strip()
    def attr(name):
        a = re.search(r"<th>%s</th><td>(.*?)(?:<mark|</td>)" % name, h, re.S)
        return html.unescape(re.sub(r"<[^>]+>", "", a.group(1))).strip() if a else ""
    return [txt, 1 if addr else 0, attr("Model"), attr("Backdrop"), attr("Symbol")]

def one(args):
    tslug, i = args
    return i, parse(fetch(f"{tslug}-{i}"))

def main():
    d = json.load(open(os.path.join(OUT, "data.json")))
    os.makedirs(os.path.join(OUT, "o"), exist_ok=True)
    only = set(sys.argv[1:])
    for c in d["collections"]:
        if only and c["slug"] not in only: continue
        k = min(N, c.get("issued") or N)
        with cf.ThreadPoolExecutor(8) as ex:
            res = list(ex.map(one, [(c["tslug"], i) for i in range(1, k + 1)]))
        items = [[i] + r for i, r in res if r]
        json.dump({"tslug": c["tslug"], "items": items}, open(os.path.join(OUT, "o", c["slug"] + ".json"), "w"), ensure_ascii=False, separators=(",", ":"))
        print(c["slug"], len(items), "/", k, flush=True)

if __name__ == "__main__":
    main()
