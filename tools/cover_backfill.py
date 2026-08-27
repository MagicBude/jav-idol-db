import json, glob, re, os, urllib.request, concurrent.futures, sys
from urllib.parse import urlparse
from collections import Counter

DRY = '--dry-run' in sys.argv
WORKS_DIR = 'data/works'
NESTED = 'data/actresses'

def load_works():
    d = {}
    for fp in glob.glob(os.path.join(WORKS_DIR, '*.json')):
        try:
            w = json.load(open(fp, encoding='utf-8'))
        except Exception:
            continue
        c = w.get('code')
        if c:
            d[c] = (fp, w)
    return d

def load_nested_covers():
    m = {}
    for fp in glob.glob(os.path.join(NESTED, '*', 'works', '*.json')):
        try:
            w = json.load(open(fp, encoding='utf-8'))
        except Exception:
            continue
        c = w.get('code')
        cov = w.get('cover')
        if c and cov and c not in m:
            m[c] = cov
    return m

def learn_templates(works):
    t = {}
    for code, (fp, w) in works.items():
        cov = w.get('cover') or ''
        if 'dmm.co.jp' not in cov:
            continue
        ps = [x for x in urlparse(cov).path.split('/') if x]
        if len(ps) < 2:
            continue
        cid = ps[-2]
        sm = re.search(r'(pl|ps|_b|jp|pb)\.jpg$', ps[-1])
        if not sm:
            continue
        suffix = sm.group(1)
        section = '/'.join(ps[:-2])
        lm = re.match(r'^([A-Za-z]+)', code)
        if not lm:
            continue
        letters = lm.group(1).lower()
        i = cid.find(letters)
        if i < 0:
            continue
        numprefix = cid[:i]
        digits = cid[i + len(letters):]
        if not digits.isdigit():
            continue
        pad = len(digits)
        pref = lm.group(1).upper()
        t.setdefault(pref, []).append((numprefix, pad, section, suffix))
    return {p: Counter(v).most_common(1)[0][0] for p, v in t.items()}

def parse_code(code):
    # strip a single trailing letter (e.g. START-227V -> START-227)
    c2 = re.sub(r'[A-Za-z]$', '', code)
    m = re.match(r'^([A-Za-z]+[0-9]*)-([0-9]+)$', c2)
    if not m:
        return None
    return m.group(1), int(m.group(2))

def candidates(code, tmpl):
    pc = parse_code(code)
    if not pc:
        return []
    series, num = pc
    letters = re.sub(r'[0-9]', '', series).lower()
    pref = re.match(r'^([A-Za-z]+)', series).group(1).upper()
    cands = []
    if pref in tmpl:
        np, pad, sec, suf = tmpl[pref]
        cid = np + letters + str(num).zfill(pad)
        cands.append(('https://pics.dmm.co.jp/%s/%s/%s%s.jpg' % (sec, cid, cid, suf), 'tmpl'))
        altpad = 5 if pad == 3 else 3
        if altpad != pad:
            cid2 = np + letters + str(num).zfill(altpad)
            cands.append(('https://pics.dmm.co.jp/%s/%s/%s%s.jpg' % (sec, cid2, cid2, suf), 'tmpl-pad'))
    else:
        for sec, suf in [('digital/video', 'pl'), ('mono/movie/adult', 'ps'), ('digital/amateur', 'pl')]:
            for np in ['', '1', '61', '13']:
                for pad in [3, 5]:
                    cid = np + letters + str(num).zfill(pad)
                    cands.append(('https://pics.dmm.co.jp/%s/%s/%s%s.jpg' % (sec, cid, cid, suf), 'guess'))
    return cands

def valid(u):
    try:
        req = urllib.request.Request(u, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://www.dmm.co.jp/'})
        r = urllib.request.urlopen(req, timeout=8)
        ok = r.status == 200 and 'image' in (r.headers.get('Content-Type') or '')
        r.close()
        return ok
    except Exception:
        return False

def main():
    works = load_works()
    nested = load_nested_covers()
    tmpl = learn_templates(works)
    missing = [c for c, (fp, w) in works.items() if not w.get('cover')]
    print("total=%d have=%d missing=%d" % (len(works), sum(1 for c, (fp, w) in works.items() if w.get('cover')), len(missing)))
    print("learned templates for %d prefixes" % len(tmpl))

    def process(code):
        if code in nested and valid(nested[code]):
            return (code, nested[code], 'nested')
        for u, kind in candidates(code, tmpl):
            if valid(u):
                return (code, u, kind)
        return (code, None, 'none')

    results, kinds = {}, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        for code, u, kind in ex.map(process, missing):
            if u:
                results[code], kinds[code] = u, kind
    print("RECOVERED: %d / %d missing" % (len(results), len(missing)))
    print("by source:", Counter(kinds.values()))
    unrec = [c for c in missing if c not in results]
    print("UNRECOVERED: %d ->" % len(unrec), unrec)
    if not DRY:
        for code, u in results.items():
            fp, w = works[code]
            w['cover'] = u
            json.dump(w, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print("WROTE %d cover fields" % len(results))

if __name__ == '__main__':
    main()
