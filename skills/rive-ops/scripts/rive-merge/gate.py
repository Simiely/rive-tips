#!/usr/bin/env python3
"""Static gate for a CLI project before building / pushing.

Catches, without running a 70 MB build, the things that actually break
`rive <dir> --once`: dangling ids, duplicate ids, missing asset bytes,
duplicate asset file names, and non-ASCII asset file names (the real cause of
a silent 0xC0000409 stack-overflow crash in Rive CLI 1.8.0: identical bytes
under an ASCII name build clean, a CJK name aborts with no message).

    python gate.py --dir O
    python gate.py --dir O --fix                 # rename assets to ASCII + embed fonts
    python gate.py --dir O --verify              # also run `rive <dir> --verify`
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import rmlcore as C


def find_rive():
    exe = 'rive.exe' if os.name == 'nt' else 'rive'
    cand = os.path.join(os.path.expanduser('~'), '.rive', 'bin', exe)
    if os.path.isfile(cand):
        return cand
    return shutil.which('rive')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--fix-fonts', action='store_true',
                    help='set exportTypeValue=embedded on FontAssets')
    ap.add_argument('--fix-names', action='store_true',
                    help='rename non-ASCII asset files to asset_NNN.<ext>')
    ap.add_argument('--fix', action='store_true', help='--fix-names + --fix-fonts')
    ap.add_argument('--verify', action='store_true', help='run rive --verify as well')
    ap.add_argument('--json')
    a = ap.parse_args()

    rml = os.path.join(a.dir, 'scene.rml')
    fails, warns = [], []
    if not os.path.exists(rml):
        print('FAIL scene.rml missing')
        return 2
    root = C.load_rml(rml)

    if root.tag != 'Rive':
        fails.append('root tag is %s, expected Rive' % root.tag)

    # 1. duplicate ids
    seen = {}
    for i in C.walk_ids(root):
        seen[i] = seen.get(i, 0) + 1
    dup = sorted(k for k, v in seen.items() if v > 1)
    if dup:
        fails.append('%d duplicate ids, e.g. %s' % (len(dup), ', '.join(dup[:5])))

    # 2. dangling refs
    refs = C.id_refs(root)
    dangling = sorted(k for k in refs
                      if k not in seen and k != C.NULL_ID and not k.startswith('-'))
    if dangling:
        fails.append('%d dangling refs, e.g. %s' % (len(dangling), ', '.join(dangling[:5])))

    # 2b. asset file names must be ASCII -- a CJK name aborts the builder with
    # 0xC0000409 before it prints anything.
    def non_ascii(el):
        f = el.get('file') or ''
        return bool(f) and not all(ord(ch) < 128 for ch in f)

    offenders = [el for el in C.asset_decls(root) if non_ascii(el)]
    if offenders and (a.fix_names or a.fix):
        mapping = {}
        seq = 0
        for el in C.asset_decls(root):
            old = el.get('file') or ''
            if not old or old in mapping:
                continue
            if all(ord(ch) < 128 for ch in old):
                continue
            while True:
                seq += 1
                ext = os.path.splitext(old)[1] or '.bin'
                new = 'asset_%03d%s' % (seq, ext)
                if not os.path.exists(os.path.join(a.dir, new)):
                    break
            mapping[old] = new
        for el in C.asset_decls(root):
            old = el.get('file') or ''
            if old in mapping:
                el.set('file', mapping[old])
        for old, new in mapping.items():
            src = C.find_asset_file(a.dir, old)
            if src:
                os.rename(src, os.path.join(os.path.dirname(src), new))
        size = C.dump_rml(root, rml)
        print('renamed   %d asset files -> ASCII (scene.rml rewritten, %d bytes)' % (
            len(mapping), size))
        offenders = [el for el in C.asset_decls(root) if non_ascii(el)]
    if offenders:
        fails.append('%d asset files with a non-ASCII name (run --fix-names), e.g. %s' % (
            len(offenders), offenders[0].get('file')))

    # 3. assets on disk
    files = {}
    missing, bad, mismatch = [], [], []
    for el in C.asset_decls(root):
        fname = el.get('file') or ''
        aid = el.get('id')
        if not fname:
            warns.append('asset %s (%s) has no file name' % (aid, el.tag))
            continue
        if fname in files:
            fails.append('duplicate asset file name %r (%s and %s)' % (fname, files[fname], aid))
        files[fname] = aid
        path = C.find_asset_file(a.dir, fname)
        if not path:
            missing.append((aid, fname))
            continue
        with open(path, 'rb') as f:
            data = f.read()
        if not C.magic_ok(data, os.path.splitext(fname)[1]):
            bad.append((aid, fname))
        d = C.dims(data)
        if d and el.get('width') and el.get('height'):
            if d != (int(el.get('width')), int(el.get('height'))):
                mismatch.append((aid, fname))
    if missing:
        fails.append('%d asset files missing on disk, e.g. %s' % (
            len(missing), ', '.join(m[1] for m in missing[:5])))
    if bad:
        fails.append('%d asset files with wrong magic, e.g. %s' % (len(bad), bad[0][1]))
    if mismatch:
        warns.append('%d asset files whose size differs from the RML width/height: %s' % (
            len(mismatch), ', '.join(m[1] for m in mismatch[:3])))

    # 4. fonts -- only an explicit `referenced` value is dangerous; a missing
    # attribute means the default (embedded).
    fonts = [el for el in root if el.tag == 'FontAsset']
    referenced = [el for el in fonts if (el.get('exportTypeValue') or 'embedded') != 'embedded']
    if referenced and (a.fix_fonts or a.fix):
        for el in referenced:
            el.set('exportTypeValue', 'embedded')
        size = C.dump_rml(root, rml)
        print('fixed   %d fonts -> embedded (scene.rml rewritten, %d bytes)' % (
            len(referenced), size))
        referenced = []
    if referenced:
        fails.append('%d FontAsset still not embedded (run --fix-fonts): %s' % (
            len(referenced), ', '.join(el.get('id') or '?' for el in referenced[:4])))

    # 5. project yaml
    y = C.read_project_yaml(os.path.join(a.dir, 'rive.yaml'))
    if not y.get('name'):
        warns.append('rive.yaml has no name: (output .riv file name is taken from it)')
    if y.get('push.fileId'):
        warns.append('rive.yaml carries push.fileId %s: `rive push` will overwrite it'
                     % y['push.fileId'])

    stats = C.element_stats(root)
    print('project   %s' % os.path.abspath(a.dir))
    print('artboards %d  elements %d  assets %d (fonts %d)' % (
        stats['artboards'], stats['elements'], len(C.asset_decls(root)), len(fonts)))

    # 6. optional CLI verify
    if a.verify:
        exe = find_rive()
        if not exe:
            fails.append('rive CLI not found (expected ~/.rive/bin/rive)')
        else:
            try:
                p = subprocess.run([exe, a.dir, '--verify'], capture_output=True,
                                   text=True, errors='replace', timeout=900)
                out = (p.stdout or '') + (p.stderr or '')
                m = re.search(r'(\d+)\s+errors?', out)
                n = int(m.group(1)) if m else None
                tail = [ln for ln in out.strip().splitlines() if ln.strip()][-2:]
                print('verify    exit %d  errors %s' % (p.returncode, n))
                for ln in tail:
                    print('          %s' % ln.strip().encode('ascii', 'replace').decode('ascii'))
                if p.returncode != 0 or (n is None) or n > 0:
                    fails.append('rive --verify reported errors (exit %d)' % p.returncode)
            except subprocess.TimeoutExpired:
                fails.append('rive --verify timed out')

    for v in warns:
        print('warn      %s' % v.encode('ascii', 'replace').decode('ascii'))
    for v in fails:
        print('FAIL      %s' % v.encode('ascii', 'replace').decode('ascii'))
    print('gate      %s' % ('PASS' if not fails else 'FAIL (%d)' % len(fails)))
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump({'dir': os.path.abspath(a.dir), 'fails': fails, 'warns': warns,
                       'dangling': dangling[:200], 'duplicate_ids': dup[:200],
                       'missing_files': missing, 'stats': stats}, f,
                      ensure_ascii=False, indent=1)
        print('report    %s' % a.json)
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
