"""Posta o primeiro comentário (campo comentario_fixado do posts.json) no TikTok e no YouTube
logo depois que cada vídeo do penumbra067 é publicado. O Instagram já recebe pelo firstComment do publicar.py.
Estado em comentados.json para nunca comentar duas vezes. Só contas com "penumbra" no nome."""
import json, os, sys, uuid, urllib.request

API = "https://zernio.com/api/v1"
RAW = "https://raw.githubusercontent.com/TonyWatanabe-dev/penumbra-midia/main/"
KEY = os.environ["ZERNIO_API_KEY"]
DRY = "--dry-run" in sys.argv

def call(method, path, body=None, headers=None):
    req = urllib.request.Request(API + path, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:500]

st, data = call("GET", "/accounts")
contas = {(a.get("_id") or a.get("id")): a.get("platform") for a in (data.get("accounts", []) if isinstance(data, dict) else [])
          if "penumbra" in f'{a.get("username","")} {a.get("displayName","")}'.lower()}
if not contas: sys.exit("Nenhuma conta penumbra067 nesta chave.")

estado = json.load(open("comentados.json")) if os.path.exists("comentados.json") else {}
entradas = {RAW + p["video"]: p for p in json.load(open("posts.json", encoding="utf-8")) if p.get("comentario_fixado")}

publicados = []
for s in ("published", "partial"):
    stp, d = call("GET", f"/posts?status={s}&limit=100")
    publicados += d.get("posts", []) if isinstance(d, dict) else []

novos = 0
for post in publicados:
    urls = [m.get("url", "") for m in post.get("mediaItems", [])]
    p = next((entradas[u] for u in urls if u in entradas), None)
    if not p: continue
    for pl in post.get("platforms", []):
        rede = pl.get("platform")
        acc = pl.get("accountId") if isinstance(pl.get("accountId"), str) else (pl.get("accountId") or {}).get("_id")
        if rede not in ("tiktok", "youtube") or acc not in contas: continue
        if pl.get("status") not in (None, "published"): continue
        chave = f'{p["id"]}:{rede}'
        if estado.get(chave, {}).get("ok"): continue
        if DRY:
            print("DRY", chave, json.dumps({k: pl.get(k) for k in ("platformPostId", "status", "platformPostUrl")})); continue
        idem = str(uuid.uuid5(uuid.NAMESPACE_URL, chave + "|" + p["comentario_fixado"]))
        alvos = [x for x in (pl.get("platformPostId"), post.get("_id")) if x]
        res = None
        for alvo in alvos:
            code, r = call("POST", f"/inbox/comments/{alvo}", {"accountId": acc, "message": p["comentario_fixado"]},
                           {"Idempotency-Key": idem + "|" + str(alvo)})
            res = {"ok": 200 <= code < 300, "code": code, "alvo": alvo, "resposta": r if isinstance(r, str) else "ok"}
            if res["ok"]: break
        estado[chave] = res; novos += 1
        print(chave, res)

json.dump(estado, open("comentados.json", "w"), ensure_ascii=False, indent=1)
print("comentários novos:", novos)
