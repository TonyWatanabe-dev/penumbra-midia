"""Coleta métricas e votos dos posts do penumbra067 no Zernio e grava metricas.json.
Roda pelo GitHub Actions (metricas.yml). Só olha posts cuja mídia está neste repo."""
import json, os, re, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

API = "https://zernio.com/api/v1"
KEY = os.environ["ZERNIO_API_KEY"]
REPO = "penumbra-midia"
log = []

def get(path, **q):
    url = API + path + ("?" + urllib.parse.urlencode(q) if q else "")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        log.append(f"{path} {q} -> HTTP {e.code}: {e.read().decode()[:300]}"); return {}
    except Exception as e:
        log.append(f"{path} {q} -> {e}"); return {}

VOTO = re.compile(r"^\W*(1|2|um|dois)\b|^\W*(1️⃣|2️⃣)", re.I)
def voto(msg):
    m = VOTO.search((msg or "").strip())
    if not m: return None
    s = (m.group(1) or m.group(2) or "").lower()
    return "1" if s in ("1", "um", "1️⃣") else "2"

# Molde v4: o voto da continuação é A/B e a escolha relâmpago é 1/2/3.
AB = re.compile(r"^\W*(🅰️|🅱️|[abAB])\W*$|^\W*(🅰️|🅱️|[AB])\b")
def voto_ab(msg):
    t = (msg or "").strip()
    m = AB.search(t)
    if not m: return None
    if m.group(2) and len(t) > 25: return None
    s = (m.group(1) or m.group(2)).lower()
    return "A" if s in ("a", "🅰️") else "B"
NUM = re.compile(r"^\W*(1|2|3|um|dois|tr[eê]s|1️⃣|2️⃣|3️⃣)(\b|\W|$)", re.I)
def escolha(msg):
    m = NUM.search((msg or "").strip())
    if not m: return None
    s = m.group(1).lower()
    return {"um": "1", "1️⃣": "1", "dois": "2", "2️⃣": "2", "três": "3", "tres": "3", "3️⃣": "3"}.get(s, s)

contas = {a.get("_id") or a.get("id"): a for a in get("/accounts").get("accounts", [])
          if "penumbra" in f'{a.get("username","")} {a.get("displayName","")}'.lower()}
desde = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
saida = {"atualizado": datetime.now(timezone.utc).isoformat(), "posts": {}, "log": log}

for status in ("published", "partial"):
    for p in get("/posts", status=status, limit=100).get("posts", []):
        midia = " ".join(m.get("url", "") for m in p.get("mediaItems", []))
        if REPO not in midia: continue
        vid = midia.split(REPO + "/main/")[-1].split()[0]
        item = saida["posts"].setdefault(vid, {"publicado": p.get("publishedAt") or p.get("scheduledFor"), "redes": {}})
        for pl in p.get("platforms", []):
            acc = pl.get("accountId") if isinstance(pl.get("accountId"), str) else (pl.get("accountId") or {}).get("_id")
            if acc not in contas: continue
            rede = pl.get("platform")
            r = {"url": pl.get("platformPostUrl"), "status": pl.get("status")}
            c = get(f'/inbox/comments/{p.get("_id")}', accountId=acc, platform=rede, limit=100)
            coms = c.get("comments") or c.get("data") or []
            votos = {"1": 0, "2": 0}; ab = {"A": 0, "B": 0}; num = {"1": 0, "2": 0, "3": 0}
            for k in coms:
                txt = k.get("message") or k.get("text") or ""
                v = voto(txt)
                if v: votos[v] += 1
                w = voto_ab(txt)
                if w: ab[w] += 1
                n = escolha(txt)
                if n: num[n] += 1
            r["comentarios_lidos"] = len(coms); r["votos"] = votos; r["votos_ab"] = ab; r["escolha_123"] = num
            item["redes"][rede] = r

for rede in ("tiktok", "instagram", "youtube"):
    a = get("/analytics", platform=rede, fromDate=desde)
    for p in a.get("posts", []):
        midia = json.dumps(p.get("mediaItems", []))
        if REPO not in midia: continue
        vid = midia.split(REPO + "/main/")[-1].split('"')[0]
        alvo = saida["posts"].setdefault(vid, {"redes": {}})["redes"].setdefault(rede, {})
        alvo["metricas"] = p.get("analytics") or {k: p.get(k) for k in ("views", "likes", "comments", "shares", "saves", "impressions", "reach")}

for vid, it in saida["posts"].items():
    t = {"1": 0, "2": 0}
    for r in it["redes"].values():
        for k in t: t[k] += r.get("votos", {}).get(k, 0)
    it["votos_total"] = t
    for chave, base in (("votos_ab", {"A": 0, "B": 0}), ("escolha_123", {"1": 0, "2": 0, "3": 0})):
        for r in it["redes"].values():
            for k in base: base[k] += r.get(chave, {}).get(k, 0)
        it[chave + "_total"] = base
json.dump(saida, open("metricas.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v.get("votos_total") for k, v in saida["posts"].items()}, ensure_ascii=False))
