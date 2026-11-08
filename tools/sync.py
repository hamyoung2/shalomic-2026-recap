"""Sync the static web recap with the Claude album's photo records.

  python3 tools/sync.py plan  --db DB_DIR --repo REPO
      -> prints JSON list of asset ids that must be downloaded first
  python3 tools/sync.py build --db DB_DIR --assets ASSET_DIR --repo REPO
      -> writes photos/, thumbs/, data.js; deletes photos no longer in the album

DB_DIR holds one JSON file per record of the album's "moments" collection
(as saved by ArtifactData list with out_dir). Photos are resized and saved
without EXIF, so camera location data never reaches the public site.
"""
import argparse, glob, json, os, sys


def load(db):
    out = []
    for f in glob.glob(os.path.join(db, "**", "*.json"), recursive=True):
        d = json.load(open(f))
        x = d.get("data", d)
        x["id"] = d.get("id") or os.path.basename(f)[:-5]
        if x.get("assetId") and x.get("month"):
            out.append(x)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["plan", "build"])
    ap.add_argument("--db", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--assets")
    a = ap.parse_args()
    docs = load(a.db)
    if not docs:
        sys.exit("no records found in --db; refusing to wipe the site")
    have = {os.path.basename(f)[:-4] for f in glob.glob(os.path.join(a.repo, "photos", "*.jpg"))}
    need = sorted({d["assetId"] for d in docs} - have)
    if a.mode == "plan":
        print(json.dumps(need))
        return
    from PIL import Image, ImageOps
    added = 0
    for aid in need:
        src = None
        for ext in ("jpg", "jpeg", "png", "webp", "gif"):
            p = os.path.join(a.assets, f"{aid}.{ext}")
            if os.path.exists(p):
                src = p
                break
        if not src:
            sys.exit(f"missing download for {aid}")
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        p = im.copy(); p.thumbnail((1600, 1600))
        p.save(os.path.join(a.repo, "photos", f"{aid}.jpg"), quality=80, optimize=True, progressive=True)
        t = im.copy(); t.thumbnail((640, 640))
        t.save(os.path.join(a.repo, "thumbs", f"{aid}.jpg"), quality=78, optimize=True, progressive=True)
        added += 1
    keep = {d["assetId"] for d in docs}
    removed = 0
    for sub in ("photos", "thumbs"):
        for f in glob.glob(os.path.join(a.repo, sub, "*.jpg")):
            if os.path.basename(f)[:-4] not in keep:
                os.remove(f); removed += 1
    moments = [{"id": d["id"], "assetId": d["assetId"], "month": d["month"], "takenAt": d.get("takenAt", ""),
                "caption": d.get("caption", ""), "kind": "image", "createdAt": d.get("createdAt", 0)}
               for d in sorted(docs, key=lambda d: d["id"])]
    open(os.path.join(a.repo, "data.js"), "w").write(
        "window.RECAP_DATA=" + json.dumps({"moments": moments, "meta": {}}, ensure_ascii=False) + ";\n")
    print(json.dumps({"photos": len(moments), "added": added, "removed_files": removed}))


if __name__ == "__main__":
    main()
