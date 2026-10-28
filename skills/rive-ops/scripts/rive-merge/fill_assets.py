#!/usr/bin/env python3
"""Put every asset file declared by scene.rml on disk, from .rev or another project.

    python fill_assets.py --dir O --rev src.rev --rev tgt.rev
    python fill_assets.py --dir O --from ../built_project --overwrite

Binding order: manifest md5 -> .rev id -> file name in a --from project.
Binary assets (png/jpg/svg/ttf) live inside a .rev as `d4 01` records.  Script
text (luau) is NOT in those records; the CLI keeps it as loose files, so copy
those from the project dir that owns them.
"""
import argparse
import json
import os
import sys

import rmlcore as C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True, help='project dir (scene.rml + assets)')
    ap.add_argument('--rev', action='append', default=[], help='repeatable .rev source')
    ap.add_argument('--from', dest='from_dirs', action='append', default=[],
                    help='repeatable project dir to copy assets from')
    ap.add_argument('--overwrite', action='store_true', help='rewrite files that exist')
    ap.add_argument('--json')
    a = ap.parse_args()

    rml = os.path.join(a.dir, 'scene.rml')
    if not os.path.exists(rml):
        print('FAIL no scene.rml in %s' % a.dir)
        return 2
    root = C.load_rml(rml)

    by_md5 = {}
    by_id = {}
    for rev in a.rev:
        with open(rev, 'rb') as f:
            buf = f.read()
        table = C.scan_rev(buf)
        for aid, hit in table.items():
            data = C.rev_bytes(buf, hit)
            by_md5.setdefault(C.md5(data), data)
            by_id.setdefault(aid, data)

    manifest = {}
    mpath = os.path.join(a.dir, 'assets.manifest.json')
    if os.path.exists(mpath):
        with open(mpath, encoding='utf-8') as f:
            for entry in json.load(f).get('assets', []):
                if entry.get('md5'):
                    manifest[entry['file']] = entry['md5']

    filled = present = missing = bad = mismatch = 0
    rows = []
    for el in C.asset_decls(root):
        fname = el.get('file') or ''
        aid = el.get('id')
        if not fname:
            continue
        dest = os.path.join(a.dir, fname)
        data = None
        origin = ''
        exists = os.path.isfile(dest)
        if exists and not a.overwrite:
            with open(dest, 'rb') as f:
                data = f.read()
            origin = 'disk'
        if data is None:
            want = manifest.get(C.safe_rel(fname))
            data = by_md5.get(want) if want else None
            if data is not None:
                origin = 'rev-md5'
            elif aid in by_id:
                data = by_id[aid]
                origin = 'rev-id'
            else:
                for src in a.from_dirs:
                    cand = C.find_asset_file(src, fname) or C.find_asset_file(
                        src, (el.get('name') or '') + os.path.splitext(fname)[1])
                    if cand:
                        with open(cand, 'rb') as f:
                            data = f.read()
                        origin = 'from-dir'
                        break
        if data is None:
            missing += 1
            rows.append({'id': aid, 'file': fname, 'tag': el.tag, 'status': 'missing'})
            continue
        if origin != 'disk':
            os.makedirs(os.path.dirname(dest) or '.', exist_ok=True)
            with open(dest, 'wb') as f:
                f.write(data)
            filled += 1
        else:
            present += 1
        ok = C.magic_ok(data, os.path.splitext(fname)[1])
        dims = C.dims(data)
        want_dims = None
        if el.get('width') and el.get('height'):
            want_dims = (int(el.get('width')), int(el.get('height')))
        dim_ok = True if (not want_dims or not dims) else dims == want_dims
        if not ok:
            bad += 1
        if not dim_ok:
            mismatch += 1
        rows.append({'id': aid, 'file': fname, 'tag': el.tag, 'bytes': len(data),
                     'md5': C.md5(data), 'origin': origin,
                     'status': 'ok' if ok and dim_ok else ('bad-magic' if not ok else 'dims-mismatch')})

    for r in rows:
        if r['status'] != 'ok':
            print('  %-12s %-13s %s' % (r['id'], r['status'], r.get('file', '')))
    print('filled %d  present %d  missing %d  bad-magic %d  dims-mismatch %d' % (
        filled, present, missing, bad, mismatch))
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print('report %s' % a.json)
    return 1 if (missing or bad or mismatch) else 0


if __name__ == '__main__':
    sys.exit(main())
