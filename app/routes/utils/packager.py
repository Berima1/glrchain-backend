import hashlib, json, tempfile, os

def package_evidence(meta: dict, file_paths: list):
    bundle = {'meta': meta, 'files': []}
    for p in file_paths:
        if not os.path.exists(p):
            continue
        with open(p,'rb') as f:
            data = f.read()
        bundle['files'].append({'name': os.path.basename(p), 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)})
    raw = json.dumps(bundle, default=str).encode('utf-8')
    overall = hashlib.sha256(raw).hexdigest()
    out = os.path.join(tempfile.gettempdir(), f'evidence_{overall}.json')
    with open(out,'wb') as f:
        f.write(raw)
    return overall, out
