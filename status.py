"""Lista os posts recentes do Zernio com o status por rede."""
import json, os, urllib.request
KEY = os.environ["ZERNIO_API_KEY"]
for st in ("published", "failed", "scheduled", "publishing", "partial"):
    req = urllib.request.Request(f"https://zernio.com/api/v1/posts?status={st}&limit=100", headers={"Authorization": f"Bearer {KEY}"})
    try:
        d = json.loads(urllib.request.urlopen(req).read())
    except Exception as e:
        print(st, "erro", e); continue
    for p in d.get("posts", []):
        vid = " ".join(m.get("url", "").split("/")[-1] for m in p.get("mediaItems", []))
        plats = [(x.get("platform"), x.get("status"), (x.get("errorMessage") or x.get("error") or "")[:120], x.get("platformPostUrl")) for x in p.get("platforms", [])]
        print(f'[{st}] {p.get("_id")} {vid} {p.get("scheduledFor") or p.get("publishedAt")}')
        for x in plats: print("   ", x)
