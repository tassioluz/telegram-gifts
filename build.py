#!/usr/bin/env python3
"""Build a static Telegram Gifts catalog (pt-BR) from keyless public sources.

Sources (no API key):
  - api.changes.tg  (gift list, models/backdrops/symbols with rarity)
  - cdn.changes.tg  (PNG / Lottie assets)
  - portal-market.com/api/collections/floors (floor prices in TON)
  - t.me/nft/<Slug>-1 public preview (issued / total supply)
"""
import json, os, re, sys, time, html, io, datetime, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs")
CACHE = os.path.join(ROOT, ".cache")
API = "https://api.changes.tg"
CDN = "https://cdn.changes.tg/gifts"
UA = {"User-Agent": "Mozilla/5.0 (telegram-gifts-site static builder)"}
THUMBS = os.environ.get("THUMBS", "1") == "1"

def get(url, binary=False, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read()
                return data if binary else data.decode("utf-8", "replace")
        except Exception as e:
            if getattr(e, "code", None) == 404:
                return None
            time.sleep(1.5 * (i + 1))
    print("FAIL", url, file=sys.stderr)
    return None

def q(s): return urllib.parse.quote(s, safe="")
def fq(s): return q(s.replace("\u2019", "'").replace("/", "\\"))  # CDN file names use straight quotes and backslash
def slug(name): return re.sub(r"[^a-z0-9]", "", name.lower())
def tslug(name): return re.sub(r"[^A-Za-z0-9]", "", name)
def esc(s): return html.escape(str(s), quote=True)
def pct(r):
    r = float(r or 0)
    s = f"{r:.1f}" if r >= 0.1 or r == 0 else f"{r:.2f}"
    return s.rstrip("0").rstrip(".").replace(".", ",") + "%" if "." in s else s + "%"

def model_png(g, m): return f"{CDN}/models/{q(g)}/png/{fq(m)}.png"
def model_lottie(g, m): return f"{CDN}/models/{q(g)}/lottie/{fq(m)}.json"
def symbol_png(g, s): return f"{CDN}/patterns/{q(g)}/png/{fq(s)}.png"
def original_png(gid): return f"{CDN}/originals/{gid}/Original.png"
def original_lottie(gid): return f"{CDN}/originals/{gid}/Original.json"

def fetch_gift(name):
    raw = get(f"{API}/gift/{q(name)}")
    if not raw:
        return None
    d = json.loads(raw)
    issued, supply = (None, None)
    d["_issued"], d["_supply"] = issued, supply
    return d

def fetch_supply(name, tries=2):
    """Issued/total from the public t.me/nft/<Slug>-<n> preview page."""
    for t in range(tries):
        for num in (1, 2, 3, 5, 10):
            page = get(f"https://t.me/nft/{tslug(name)}-{num}")
            m = re.search(r"Quantity</th><td>([^<]*)</td>", page or "")
            if m:
                nums = [int(re.sub(r"\D", "", x)) for x in m.group(1).split("/") if re.sub(r"\D", "", x)]
                if len(nums) == 2:
                    return nums
            time.sleep(0.6)
        time.sleep(3)
    return (None, None)

def thumb(url, path, size):
    if os.path.exists(path):
        return True
    data = get(url, binary=True)
    if not data:
        return False
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("RGBA")
        im.thumbnail((size, size), Image.LANCZOS)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        im.save(path, "WEBP", quality=82, method=4)
        return True
    except Exception as e:
        print("thumb err", url, e, file=sys.stderr)
        return False

def main():
    os.makedirs(OUT, exist_ok=True); os.makedirs(CACHE, exist_ok=True)
    names = json.loads(get(f"{API}/gifts"))
    print("gifts:", len(names))
    floors = {}
    fr = get("https://portal-market.com/api/collections/floors")
    if fr:
        try: floors = json.loads(fr).get("floorPrices", {})
        except Exception: pass
    print("floors:", len(floors))
    with ThreadPoolExecutor(8) as ex:
        gifts = list(ex.map(fetch_gift, names))
    prev = {}
    try:
        prev = {c["name"]: c for c in json.load(open(os.path.join(OUT, "data.json")))["collections"]}
    except Exception:
        pass
    with ThreadPoolExecutor(3) as ex:
        sup = list(ex.map(fetch_supply, names))
    for name, d, (iss, tot) in zip(names, gifts, sup):
        if d is None: continue
        if tot is None and name in prev:  # keep last known value
            iss, tot = prev[name].get("issued"), prev[name].get("supply")
        d["_issued"], d["_supply"] = iss, tot
    cols = []
    for name, d in zip(names, gifts):
        if not d:
            print("skip", name); continue
        g = d["gift"]
        s = slug(name)
        fl = floors.get(s)
        col = {
            "name": name, "slug": s, "tslug": tslug(name), "id": g.get("id"),
            "released": g.get("releasedAt"), "upgradable": g.get("upgradable"),
            "floor": round(float(fl), 2) if fl not in (None, "") else None,
            "supply": d["_supply"], "issued": d["_issued"],
            "models": sorted([{"n": m["name"], "r": m.get("rarity", m.get("rarityPermille", 0) / 10)} for m in d.get("models", [])], key=lambda x: (x["r"], x["n"])),
            "backdrops": sorted([{"n": b["name"], "r": b.get("rarity", b.get("rarityPermille", 0) / 10),
                                  "c": b["hex"]["centerColor"], "e": b["hex"]["edgeColor"],
                                  "p": b["hex"]["patternColor"], "t": b["hex"]["textColor"]} for b in d.get("backdrops", [])], key=lambda x: (x["r"], x["n"])),
            "symbols": sorted([{"n": x["name"], "r": x.get("rarity", x.get("rarityPermille", 0) / 10)} for x in d.get("symbols", [])], key=lambda x: (x["r"], x["n"])),
        }
        cols.append(col)
    # thumbnails (covers + models) stored locally for speed
    jobs = []
    for c in cols:
        if c["id"]:
            jobs.append((original_png(c["id"]), os.path.join(OUT, "img", "c", c["slug"] + ".webp"), 256))
        for m in c["models"]:
            jobs.append((model_png(c["name"], m["n"]), os.path.join(OUT, "img", "m", c["slug"], slug(m["n"]) + ".webp"), 192))
    if THUMBS:
        with ThreadPoolExecutor(16) as ex:
            res = list(ex.map(lambda j: thumb(*j), jobs))
        print("thumbs ok:", sum(res), "/", len(res))
    for c in cols:
        c["cover"] = f"img/c/{c['slug']}.webp" if os.path.exists(os.path.join(OUT, "img", "c", c["slug"] + ".webp")) else (original_png(c["id"]) if c["id"] else "")
        for m in c["models"]:
            p = os.path.join(OUT, "img", "m", c["slug"], slug(m["n"]) + ".webp")
            m["img"] = f"img/m/{c['slug']}/{slug(m['n'])}.webp" if os.path.exists(p) else model_png(c["name"], m["n"])
    cols.sort(key=lambda c: c["name"].lower())
    built = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump({"built": built, "collections": cols}, open(os.path.join(OUT, "data.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    render(cols, built)
    print("collections:", len(cols), "models:", sum(len(c["models"]) for c in cols),
          "backdrops:", sum(len(c["backdrops"]) for c in cols), "symbols:", sum(len(c["symbols"]) for c in cols),
          "with floor:", sum(1 for c in cols if c["floor"] is not None), "with supply:", sum(1 for c in cols if c["supply"]))

# ---------------------------------------------------------------- rendering
def fmt_int(n): return f"{n:,}".replace(",", ".") if n is not None else "—"
def fmt_ton(v): return (f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " TON") if v is not None else "—"
def fmt_date(ts):
    if not ts: return "—"
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%d/%m/%Y")

def page(title, body, depth=0, desc="Catálogo completo dos Presentes colecionáveis do Telegram", extra_head=""):
    pre = "../" * depth
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🎁</text></svg>">
<link rel="stylesheet" href="{pre}style.css">{extra_head}</head>
<body data-root="{pre}">
<header class="top"><a class="brand" href="{pre}index.html">🎁 <b>Presentes</b> Telegram</a>
<nav><a href="{pre}index.html">Coleções</a><a href="{pre}fundos.html">Fundos</a><a href="{pre}sobre.html">Sobre</a></nav></header>
<main>{body}</main>
<footer>Dados públicos de <a href="https://changes.tg" rel="noopener">changes.tg</a>, preços mínimos de <a href="https://portal-market.com" rel="noopener">Portals</a> e prévias de <a href="https://t.me/nft" rel="noopener">t.me/nft</a>. Site não oficial, sem vínculo com o Telegram.</footer>
<script src="{pre}app.js" defer></script></body></html>"""

def render(cols, built):
    built_br = datetime.datetime.strptime(built, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M")
    all_bd = {}
    all_sym = {}
    for c in cols:
        for b in c["backdrops"]:
            all_bd.setdefault(b["n"], {"b": b, "cols": []})["cols"].append((c, b["r"]))
        for s in c["symbols"]:
            all_sym.setdefault(s["n"], 0); all_sym[s["n"]] += 1
    total_models = sum(len(c["models"]) for c in cols)
    # ---- index
    cards = []
    for c in cols:
        cards.append(f"""<a class="card" href="c/{c['slug']}.html" data-slug="{c['slug']}">
<div class="thumb"><img loading="lazy" decoding="async" src="{esc(c['cover'])}" alt="{esc(c['name'])}" width="160" height="160"></div>
<h3>{esc(c['name'])}</h3>
<div class="meta"><span title="Preço mínimo (Portals)">💎 {fmt_ton(c['floor'])}</span><span title="Emitidos / total">📦 {fmt_int(c['issued'])}{' / ' + fmt_int(c['supply']) if c['supply'] else ''}</span></div>
<div class="meta small"><span>{len(c['models'])} modelos</span><span>{len(c['backdrops'])} fundos</span><span>{len(c['symbols'])} símbolos</span></div>
<div class="hit"></div></a>""")
    bd_opts = "".join(f'<option value="{esc(n)}">{esc(n)}</option>' for n in sorted(all_bd))
    sym_opts = "".join(f'<option value="{esc(n)}">{esc(n)}</option>' for n in sorted(all_sym))
    body = f"""<section class="hero"><h1>Todos os Presentes colecionáveis do Telegram</h1>
<p>{len(cols)} coleções · {fmt_int(total_models)} modelos · {len(all_bd)} fundos · {len(all_sym)} símbolos. Atualizado em {built_br} (Brasília).</p></section>
<section class="filters" id="filters">
<input id="q" type="search" placeholder="Buscar coleção ou modelo… (ex.: Pepe, Gold)" autocomplete="off">
<select id="fBackdrop"><option value="">Fundo: todos</option>{bd_opts}</select>
<select id="fSymbol"><option value="">Símbolo: todos</option>{sym_opts}</select>
<input id="fModel" type="search" placeholder="Modelo…" list="modelList" autocomplete="off">
<select id="fRarity" title="Raridade máxima do atributo filtrado"><option value="">Raridade: qualquer</option><option value="0.5">≤ 0,5% (lendário)</option><option value="1">≤ 1% (épico)</option><option value="2">≤ 2% (raro)</option><option value="5">≤ 5%</option></select>
<select id="sort"><option value="name">Ordenar: nome</option><option value="floor-desc">Preço mínimo ↓</option><option value="floor-asc">Preço mínimo ↑</option><option value="supply-asc">Menor tiragem</option><option value="supply-desc">Maior tiragem</option><option value="new">Mais recentes</option><option value="old">Mais antigos</option></select>
<span id="count" class="count"></span></section>
<datalist id="modelList"></datalist>
<section class="grid" id="grid">{''.join(cards)}</section>
<p class="empty" id="empty" hidden>Nenhuma coleção encontrada com esses filtros.</p>"""
    open(os.path.join(OUT, "index.html"), "w").write(page("Presentes do Telegram — catálogo completo de NFTs", body, extra_head='\n<script>window.PAGE="index"</script>'))
    # ---- collection pages
    os.makedirs(os.path.join(OUT, "c"), exist_ok=True)
    for c in cols:
        models = "".join(f"""<button class="item model" data-n="{esc(m['n'])}" data-r="{m['r']}" data-lottie="{esc(model_lottie(c['name'], m['n']))}">
<img loading="lazy" decoding="async" src="{esc(m['img'] if m['img'].startswith('http') else '../' + m['img'])}" alt="{esc(m['n'])}" width="96" height="96">
<span class="n">{esc(m['n'])}</span><span class="r {rcls(m['r'])}">{pct(m['r'])}</span></button>""" for m in c["models"])
        bds = "".join(f"""<div class="item bd" data-n="{esc(b['n'])}" data-r="{b['r']}" data-c="{b['c']}" data-e="{b['e']}" data-p="{b['p']}">
<div class="swatch" style="background:radial-gradient(circle,{b['c']} 0%,{b['e']} 100%)"><i style="background:{b['p']}"></i></div>
<span class="n">{esc(b['n'])}</span><span class="r {rcls(b['r'])}">{pct(b['r'])}</span><span class="hex">{b['c']} · {b['e']}</span></div>""" for b in c["backdrops"])
        syms = "".join(f"""<div class="item sym" data-n="{esc(s['n'])}" data-r="{s['r']}">
<img loading="lazy" decoding="async" src="{esc(symbol_png(c['name'], s['n']))}" alt="{esc(s['n'])}" width="56" height="56">
<span class="n">{esc(s['n'])}</span><span class="r {rcls(s['r'])}">{pct(s['r'])}</span></div>""" for s in c["symbols"])
        cover = c["cover"] if c["cover"].startswith("http") else "../" + c["cover"]
        mopts = "".join(f'<option value="{esc(m["n"])}">{esc(m["n"])} ({pct(m["r"])})</option>' for m in c["models"])
        bopts = "".join(f'<option value="{esc(b["n"])}">{esc(b["n"])} ({pct(b["r"])})</option>' for b in c["backdrops"])
        sopts = "".join(f'<option value="{esc(s["n"])}">{esc(s["n"])} ({pct(s["r"])})</option>' for s in c["symbols"])
        body = f"""<p class="crumb"><a href="../index.html">← Todas as coleções</a></p>
<section class="head">
<div class="cover" id="coverAnim" data-lottie="{esc(original_lottie(c['id'])) if c['id'] else ''}"><img src="{esc(cover)}" alt="{esc(c['name'])}" width="200" height="200"></div>
<div><h1>{esc(c['name'])}</h1>
<dl class="stats">
<div><dt>Preço mínimo</dt><dd>{fmt_ton(c['floor'])}</dd></div>
<div><dt>Emitidos</dt><dd>{fmt_int(c['issued'])}</dd></div>
<div><dt>Tiragem total</dt><dd>{fmt_int(c['supply'])}</dd></div>
<div><dt>Lançamento</dt><dd>{fmt_date(c['released'])}</dd></div>
<div><dt>Modelos</dt><dd>{len(c['models'])}</dd></div>
<div><dt>Fundos</dt><dd>{len(c['backdrops'])}</dd></div>
<div><dt>Símbolos</dt><dd>{len(c['symbols'])}</dd></div>
</dl>
<p class="links"><a href="https://t.me/nft/{c['tslug']}-1" target="_blank" rel="noopener">Ver #1 no Telegram</a> · <a href="https://fragment.com/gifts/{c['slug']}" target="_blank" rel="noopener">Fragment</a> · <a href="https://t.me/portals" target="_blank" rel="noopener">Portals</a></p>
</div></section>
<section class="builder" id="builder"><h2>Monte um presente</h2>
<div class="bwrap"><div class="preview" id="preview"><div class="pat" id="pat"></div><img id="pModel" alt=""></div>
<div class="bctl"><label>Modelo<select id="bModel">{mopts}</select></label><label>Fundo<select id="bBackdrop">{bopts}</select></label><label>Símbolo<select id="bSymbol">{sopts}</select></label>
<p id="bOdds" class="odds"></p><button id="bRandom" type="button">🎲 Aleatório (pela raridade)</button></div></div></section>
<nav class="tabs"><button data-tab="models" class="on">Modelos ({len(c['models'])})</button><button data-tab="backdrops">Fundos ({len(c['backdrops'])})</button><button data-tab="symbols">Símbolos ({len(c['symbols'])})</button></nav>
<section class="filters"><input id="iq" type="search" placeholder="Filtrar por nome…" autocomplete="off">
<select id="ir"><option value="">Raridade: qualquer</option><option value="0.5">≤ 0,5%</option><option value="1">≤ 1%</option><option value="2">≤ 2%</option><option value="5">≤ 5%</option></select>
<select id="is"><option value="rar">Mais raros primeiro</option><option value="com">Mais comuns primeiro</option><option value="az">A–Z</option></select><span id="icount" class="count"></span></section>
<section class="items models-grid" data-pane="models">{models}</section>
<section class="items bd-grid" data-pane="backdrops" hidden>{bds}</section>
<section class="items sym-grid" data-pane="symbols" hidden>{syms}</section>
<dialog id="dlg"><button class="x" id="dlgClose" aria-label="Fechar">×</button><div id="anim"></div><h3 id="dlgTitle"></h3><p id="dlgSub"></p></dialog>
<script>window.PAGE="collection";window.GIFT={json.dumps({"name": c["name"], "slug": c["slug"], "cdn": CDN}, ensure_ascii=False)};</script>
<script src="https://cdn.jsdelivr.net/npm/lottie-web@5.12.2/build/player/lottie_light.min.js" defer></script>"""
        desc = f"{c['name']}: {len(c['models'])} modelos, {len(c['backdrops'])} fundos e {len(c['symbols'])} símbolos com raridade, imagens e preço mínimo."
        open(os.path.join(OUT, "c", c["slug"] + ".html"), "w").write(page(f"{c['name']} — Presentes do Telegram", body, depth=1, desc=desc))
    # ---- backdrops page
    rows = []
    for n in sorted(all_bd):
        b = all_bd[n]["b"]; cl = all_bd[n]["cols"]
        rs = sorted(set(r for _, r in cl))
        links = ", ".join(f'<a href="c/{c["slug"]}.html">{esc(c["name"])}</a>' for c, _ in sorted(cl, key=lambda x: x[0]["name"]))
        rows.append(f"""<div class="item bd wide" data-n="{esc(n)}"><div class="swatch" style="background:radial-gradient(circle,{b['c']} 0%,{b['e']} 100%)"><i style="background:{b['p']}"></i></div>
<div><span class="n">{esc(n)}</span><span class="hex">centro {b['c']} · borda {b['e']} · padrão {b['p']} · texto {b['t']}</span>
<span class="r">raridade: {' / '.join(pct(r) for r in rs)} · em {len(cl)} coleções</span><details><summary>Coleções</summary>{links}</details></div></div>""")
    body = f"""<section class="hero"><h1>Fundos (backdrops)</h1><p>{len(all_bd)} fundos usados nos presentes colecionáveis, com as cores oficiais.</p></section>
<section class="filters"><input id="iq" type="search" placeholder="Filtrar fundos…"></section><section class="items bd-list" data-pane="all">{''.join(rows)}</section>
<script>window.PAGE="list"</script>"""
    open(os.path.join(OUT, "fundos.html"), "w").write(page("Fundos — Presentes do Telegram", body))
    body = f"""<section class="hero prose"><h1>Sobre</h1>
<p>Catálogo público e não oficial de todos os Presentes colecionáveis (NFT) do Telegram: coleções, modelos, fundos e símbolos, com a porcentagem de raridade de cada atributo.</p>
<h2>Fontes de dados (sem chave de API)</h2><ul>
<li><a href="https://changes.tg">changes.tg</a> (api.changes.tg e cdn.changes.tg): lista de presentes, modelos, fundos, símbolos, raridades, imagens PNG e animações Lottie.</li>
<li><a href="https://portal-market.com">Portals</a>: preço mínimo (floor) de cada coleção, em TON.</li>
<li><a href="https://t.me/nft">t.me/nft</a>: quantidade emitida e tiragem total (página pública do presente #1).</li></ul>
<p>Os dados são coletados no momento da construção do site (atualização diária). Última atualização: {built_br} (horário de Brasília).</p>
<p>Raridade: lendário ≤ 0,5%, épico ≤ 1%, raro ≤ 2%, incomum ≤ 5%.</p></section>"""
    open(os.path.join(OUT, "sobre.html"), "w").write(page("Sobre — Presentes do Telegram", body))
    open(os.path.join(OUT, ".nojekyll"), "w").write("")
    import shutil
    for f in os.listdir(os.path.join(ROOT, "static")):
        shutil.copy(os.path.join(ROOT, "static", f), os.path.join(OUT, f))

def rcls(r):
    r = float(r or 0)
    return "leg" if r <= 0.5 else "epi" if r <= 1 else "rar" if r <= 2 else "unc" if r <= 5 else "com"

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "render":
        d = json.load(open(os.path.join(OUT, "data.json")))
        render(d["collections"], d["built"])
    else:
        main()
