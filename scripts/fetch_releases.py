#!/usr/bin/env python3
"""Apple公式のRSS(Developer Releases)とSoftware Lookup Service(GDMF)から
iPadOSのリリース情報を取得し、data/releases.json に「追記マージ」する。
RSSは直近分しか載らないため、毎回マージして履歴を蓄積する。"""
import html as H, json, re, sys, urllib.request, email.utils, datetime as dt, pathlib
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
CONTENT = '{http://purl.org/rss/1.0/modules/content/}encoded'
SEC = 'https://support.apple.com/en-us/100100'  # Apple security releases（更新ごとの対応機種を製品名で掲載）

RSS = "https://developer.apple.com/news/releases/rss/releases.rss"
GDMF = "https://gdmf.apple.com/v2/pmv"
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "releases.json"
TITLE = re.compile(r"^iPadOS (\d+(?:\.\d+)*)(?: (beta(?: \d+)?|RC(?: \d+)?|Release Candidate(?: \d+)?))? \(([0-9A-Za-z]+)\)")

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ipados-defer-tracker/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def iso(d):
    return d.astimezone(dt.timezone.utc).isoformat(timespec="seconds")

def main():
    db = {"releases": [], "betas": []}
    if OUT.exists():
        db = json.loads(OUT.read_text(encoding="utf-8"))
    rel = {(r["version"], r["build"]): r for r in db["releases"]}
    bet = {(r["version"], r["build"]): r for r in db["betas"]}

    # 1) RSS（主データ源: 正確な公開日時を持つ）
    for it in ET.fromstring(get(RSS)).iter("item"):
        m = TITLE.match((it.findtext("title") or "").strip())
        if not m:
            continue
        ver, label, build = m.groups()
        when = iso(email.utils.parsedate_to_datetime(it.findtext("pubDate")))
        key = (ver, build)
        n = re.search(r"href=\s*(\S+)\s+class=more>View release notes", it.findtext(CONTENT) or "")
        extra = {"link": it.findtext("link"), "notes": urljoin("https://developer.apple.com", n.group(1)) if n else None}
        if label:
            r = bet.setdefault(key, {"version": ver, "build": build, "label": label, "seen": when})
        else:
            r = rel.setdefault(key, {"version": ver, "build": build, "released": when, "expires": None, "src": "rss"})
        old = rel.pop((ver, ""), None) if not label else None  # セキュリティ情報だけで先に作った仮レコードを統合
        r.update({k: v for k, v in extra.items() if v})
        if old and r is rel.get(key):
            for k in ("models", "sec"):
                if old.get(k): r.setdefault(k, old[k])

    # 2) GDMF（補助: 配信終了日・RSSに無い版）。失敗しても続行
    try:
        pub = json.loads(get(GDMF)).get("PublicAssetSets", {})
        for items in pub.values():
            for a in items:
                if not any(str(d).startswith("iPad") for d in a.get("SupportedDevices", [])):
                    continue  # iPad対象の版だけ使う（識別子は保存・表示しない）
                key = (a["ProductVersion"], a["Build"])
                r = rel.setdefault(key, {"version": key[0], "build": key[1], "src": "gdmf",
                                         "released": f'{a["PostingDate"]}T00:00:00+00:00'})
                r["expires"] = a.get("ExpirationDate") or r.get("expires")

    except Exception as e:  # noqa
        print("WARN: GDMF取得失敗（RSSのみで続行）:", e, file=sys.stderr)

    # 3) Apple security releases: 更新ごとの「対応機種（製品名）」と日付・リンク。失敗しても続行
    try:
        page = get(SEC).decode("utf-8", "ignore")
        for tr in re.findall(r"<tr.*?</tr>", page, re.S):
            td = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            m = len(td) >= 3 and re.search(r"iPadOS (\d+(?:\.\d+)*)", H.unescape(re.sub(r"<[^>]+>", " ", td[0])))
            if not m:
                continue
            ver = m.group(1)
            txt = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", td[1]))).strip().replace(", and iPad", ", iPad").replace(" and iPad", ", iPad")
            phrases = [p.strip() for p in txt.split(",") if p.strip().startswith("iPad ")]
            href = re.search(r'href="([^"]+)"', td[0])
            day = dt.datetime.strptime(re.sub(r"<[^>]+>", "", td[2]).strip(), "%d %b %Y")
            r = next((x for k, x in rel.items() if k[0] == ver), None)
            if r is None:  # RSSにまだ無い版（ビルドは後でRSSから統合）
                r = rel[(ver, "")] = {"version": ver, "build": "", "src": "security", "expires": None,
                                      "released": iso(day.replace(hour=17, tzinfo=dt.timezone.utc))}
            r["models"] = sorted(set(r.get("models", [])) | set(phrases))
            if href:
                r["sec"] = urljoin("https://support.apple.com", href.group(1))
    except Exception as e:  # noqa
        print("WARN: security releases取得失敗（対応機種は前回値のまま）:", e, file=sys.stderr)
    # ベータ履歴: 正式版が出ると betas から消えるため、betaLog に全ビルドを恒久的に蓄積する（削除しない。公開日予測の統計用）
    log = {(e["version"], e["label"], e.get("build", "")): e for e in db.get("betaLog", [])}
    for (ver, build), b in bet.items():
        k = (ver, b["label"], build)
        old = log.get(k, {})
        log[k] = {**old, **{x: y for x, y in b.items() if y}, "seen": min(old.get("seen", b["seen"]), b["seen"])}
    db["betaLog"] = sorted(log.values(), key=lambda e: e["seen"])
    released_versions = {v for v, _ in rel}
    db["releases"] = sorted(rel.values(), key=lambda r: r["released"], reverse=True)
    db["betas"] = sorted((b for k, b in bet.items() if k[0] not in released_versions),
                         key=lambda b: b["seen"], reverse=True)
    db["updated"] = iso(dt.datetime.now(dt.timezone.utc))
    OUT.write_text(json.dumps(db, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f'OK: releases={len(db["releases"])} betas={len(db["betas"])}')

if __name__ == "__main__":
    main()
