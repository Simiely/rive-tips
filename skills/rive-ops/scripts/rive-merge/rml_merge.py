#!/usr/bin/env python3
"""Merge all artboards of one Rive project into another WITHOUT clearing it.

Both sides are CLI projects (`scene.rml` + `rive.yaml`).  The merged result is a
new project dir; the two inputs are never modified.

    python rml_merge.py --target T --source S --out O
    python rml_merge.py --target T --source S --out O \
        --source-rev S.rev --target-rev T.rev --prune-orphans

Conflict policy for top-level elements (artboards, viewmodels, enums, ...):
  replace (default)  same id -> the source version wins, in the same slot
  skip               same id -> keep the target version, drop the source one
  keep               same id -> keep both, the source copy gets fresh ids

Assets are matched by id first, then by identical file bytes; a name clash with
different bytes gets a `__2` suffix instead of silently overwriting a picture.

Anything that still needs bytes (assets that only live inside a .rev) is listed
in `assets.manifest.json` and can be filled by build/fill_assets.py.

Asset files are renamed to `asset_NNN.<ext>` by default: a non-ASCII file name
(CJK, full-width brackets) makes the Rive CLI 1.8.0 builder abort with
0xC0000409 and no message, while identical bytes under an ASCII name build
clean.  Use --keep-names only when you know the project stays offline.
"""
import argparse
import copy
import json
import os
import sys

import rmlcore as C


class ByteSource:
    """Asset bytes for one side: .rev first, then files already on disk."""

    def __init__(self, rev_path, project_dir):
        self.buf = open(rev_path, 'rb').read() if rev_path else b''
        self.table = C.scan_rev(self.buf) if self.buf else {}
        self.dir = project_dir
        self.paths = {}

    def get(self, aid, fname):
        hit = self.table.get(aid)
        if hit:
            return C.rev_bytes(self.buf, hit), 'rev'
        path = C.find_asset_file(self.dir, fname)
        if path:
            self.paths[aid] = path
            with open(path, 'rb') as f:
                return f.read(), 'dir'
        return None, 'missing'


def unique_name(name, taken):
    stem, ext = os.path.splitext(name)
    k = 2
    while True:
        cand = '%s__%d%s' % (stem, k, ext)
        if cand not in taken:
            return cand
        k += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', required=True, help='project dir that keeps its content')
    ap.add_argument('--source', required=True, help='project dir that is merged in')
    ap.add_argument('--out', required=True, help='new project dir to write')
    ap.add_argument('--target-rev', help='optional .rev of the target (asset bytes)')
    ap.add_argument('--source-rev', help='optional .rev of the source (asset bytes)')
    ap.add_argument('--on-conflict', choices=('replace', 'skip', 'keep'), default='replace')
    ap.add_argument('--prune-orphans', action='store_true',
                    help='drop assets that nothing references after the merge')
    ap.add_argument('--keep-names', action='store_true',
                    help='keep the original asset file names (non-ASCII names crash '
                         '`rive --verify` with 0xC0000409, so renaming is the default)')
    ap.add_argument('--artboard', action='append', default=None,
                    help='only merge these artboards (name or id), repeatable')
    ap.add_argument('--name', help='rive.yaml name: (default <target>-merged)')
    ap.add_argument('--main', help='rive.yaml main: (default: kept from target)')
    ap.add_argument('--force', action='store_true', help='overwrite out/scene.rml')
    ap.add_argument('--json')
    a = ap.parse_args()

    out_rml = os.path.join(a.out, 'scene.rml')
    if os.path.exists(out_rml) and not a.force:
        print('FAIL out already exists: %s (use --force)' % out_rml)
        return 2

    tgt = C.load_rml(os.path.join(a.target, 'scene.rml'))
    src = C.load_rml(os.path.join(a.source, 'scene.rml'))
    tgt_yaml = C.read_project_yaml(os.path.join(a.target, 'rive.yaml'))
    tb = ByteSource(a.target_rev, a.target)
    sb = ByteSource(a.source_rev, a.source)

    tgt_ids = {el.get('id'): el for el in tgt.iter() if el.get('id')}
    tgt_arts = sum(1 for el in tgt if el.tag == 'Artboard')
    src_arts = sum(1 for el in src if el.tag == 'Artboard')
    maxid = {}
    for root in (tgt, src):
        for i in C.walk_ids(root):
            scope, oid = i.split(':')
            scope, oid = int(scope), int(oid)
            if oid > maxid.get(scope, 0):
                maxid[scope] = oid

    def alloc(scope):
        nxt = maxid.get(scope, 0) + 1
        maxid[scope] = nxt
        return '%d:%d' % (scope, nxt)

    remap = {}            # src id -> new id (real collisions only)
    report = {'target': os.path.abspath(a.target), 'source': os.path.abspath(a.source),
              'on_conflict': a.on_conflict, 'prune_orphans': a.prune_orphans,
              'replaced': [], 'skipped': [], 'kept_copies': [], 'kept_assets': [],
              'dropped_assets': [],
              'renamed': [], 'reallocated': [], 'pruned': [], 'missing_bytes': []}

    # ---------------------------------------------------------------- assets
    tgt_assets = {el.get('id'): el for el in C.asset_decls(tgt)}
    by_file = {}
    bytes_map = {}
    for aid, el in tgt_assets.items():
        data, origin = tb.get(aid, el.get('file') or '')
        if data is not None:
            bytes_map[aid] = (data, origin)
            if el.get('file'):
                by_file.setdefault(el.get('file'), []).append((aid, C.md5(data)))

    taken = {el.get('file') for el in C.asset_decls(tgt) if el.get('file')}
    kept_src = []
    for el in C.asset_decls(src):
        aid, fname = el.get('id'), el.get('file') or ''
        data, origin = sb.get(aid, fname)

        if aid in tgt_assets:
            other = tgt_assets[aid]
            odata, _ = tb.get(aid, other.get('file') or '')
            if data is not None and odata is not None and C.md5(data) != C.md5(odata):
                report['reallocated'].append({'id': aid, 'reason': 'same-id-different-bytes'})
                remap[aid] = alloc(int(aid.split(':')[0]))
                el.set('id', remap[aid])
            else:
                report['dropped_assets'].append({'id': aid, 'reason': 'same-id'})
                continue
        elif fname and fname in taken:
            same = [aid2 for aid2, m in by_file.get(fname, []) if data is not None and m == C.md5(data)]
            if same and same[0] != aid:
                remap[aid] = same[0]
                report['dropped_assets'].append({'id': aid, 'reason': 'same-bytes', 'into': same[0]})
                continue
            new_name = unique_name(fname, taken)
            report['renamed'].append({'id': aid, 'from': fname, 'to': new_name})
            el.set('file', new_name)
            fname = new_name

        taken.add(fname)
        kept_src.append(el)
        if data is not None:
            bytes_map[el.get('id')] = (data, origin)
        else:
            report['missing_bytes'].append({'id': el.get('id'), 'file': fname})
        report['kept_assets'].append({'id': el.get('id'), 'file': fname, 'tag': el.tag})

    # ------------------------------------------------------- top-level copies
    wanted = set(a.artboard or [])
    replaced = skip_count = 0
    inserts = []                                   # (index or None, element)
    for el in list(src):
        if C.is_asset_tag(el.tag):
            continue                               # handled above
        if el.tag == 'Artboard' and wanted:
            if el.get('id') not in wanted and (el.get('name') or '') not in wanted:
                skip_count += 1
                continue

        aid = el.get('id')
        new = copy.deepcopy(el)
        table = dict(remap)
        occupied = set(C.walk_ids(tgt))            # ids taken right now
        keep_id = None
        if aid is not None and aid in occupied:
            if a.on_conflict == 'skip':
                report['skipped'].append(aid)
                continue
            if a.on_conflict == 'keep':
                for node in new.iter():
                    i = node.get('id')
                    if i:
                        table[i] = alloc(int(i.split(':')[0]))
                name = new.get('name')
                if name:
                    new.set('name', name + ' (2)')
                report['kept_copies'].append(aid)
            else:
                # same id at top level: the source version takes the slot, and
                # the top-level id itself is allowed to stay.
                report['replaced'].append(aid)
                old = tgt_ids.get(aid)
                for parent in tgt.iter():
                    if old is not None and old in list(parent):
                        parent.remove(old)
                        break
                occupied.discard(aid)
                keep_id = aid
                replaced += 1

        occupied = set(C.walk_ids(tgt))            # after any removal

        # A descendant id that already exists elsewhere in the target (e.g. an
        # interpolator kept at document level there but nested in an artboard
        # here) must get a fresh id, otherwise the merged file has duplicate
        # ids and the animation silently binds to the wrong object.
        for node in new.iter():
            i = node.get('id')
            if i and i != keep_id and i in occupied:
                table.setdefault(i, alloc(int(i.split(':')[0])))

        if table:
            for node in new.iter():
                for k, v in list(node.attrib.items()):
                    nv = C.remap_value(v, table)
                    if nv != v:
                        node.set(k, nv)
        inserts.append((None, None, new))

    # append / slot insert
    tgt.extend([el for parent, idx, el in inserts if el is not None])
    tgt.extend(kept_src)

    # --------------------------------------------------------------- orphans
    if a.prune_orphans:
        refs = C.id_refs(tgt)
        for el in C.asset_decls(tgt):
            aid = el.get('id')
            if refs.get(aid, 0) == 0 and aid not in remap.values():
                report['pruned'].append({'id': aid, 'tag': el.tag,
                                         'file': el.get('file') or ''})
                tgt.remove(el)
                bytes_map.pop(aid, None)

    # ------------------------------------------------------- rename assets
    ascii_renamed = {}
    if not a.keep_names:
        seq = 0
        for el in C.asset_decls(tgt):
            old = el.get('file') or ''
            if not old:
                continue
            if old in ascii_renamed:
                el.set('file', ascii_renamed[old])   # one file, several decls
                continue
            seq += 1
            ext = os.path.splitext(old)[1] or '.bin'
            new = 'asset_%03d%s' % (seq, ext)
            ascii_renamed[old] = new
            el.set('file', new)
        report['ascii_renamed'] = ascii_renamed

    # ---------------------------------------------------------------- write
    os.makedirs(a.out, exist_ok=True)
    size = C.dump_rml(tgt, out_rml)
    name = a.name or (tgt_yaml.get('name') or 'merged') + '-merged'
    main = a.main or tgt_yaml.get('main')
    C.write_project_yaml(os.path.join(a.out, 'rive.yaml'), name, main)

    manifest = []
    for el in C.asset_decls(tgt):
        aid, fname = el.get('id'), el.get('file') or ''
        data, origin = bytes_map.get(aid, (None, 'missing'))
        entry = {'id': aid, 'file': C.safe_rel(fname), 'tag': el.tag,
                 'bytes': len(data) if data is not None else None,
                 'md5': C.md5(data) if data is not None else None,
                 'origin': origin}
        if data is not None and origin == 'dir':
            path = tb.paths.get(aid) or sb.paths.get(aid)
            if path:
                with open(os.path.join(a.out, os.path.basename(fname)), 'wb') as f:
                    f.write(data)
                entry['copied'] = True
        manifest.append(entry)
    with open(os.path.join(a.out, 'assets.manifest.json'), 'w', encoding='utf-8') as f:
        json.dump({'scene': 'scene.rml', 'assets': manifest}, f, ensure_ascii=False, indent=1)

    # --------------------------------------------------------------- report
    stats = C.element_stats(tgt)
    refs = C.id_refs(tgt)
    live = set(C.walk_ids(tgt))
    # negative scoped ids (-0:12, -2:839) point at code/linked files, not at
    # objects in this document, so they are not dangling references.
    dangling = sorted(k for k in refs
                      if k not in live and k != C.NULL_ID and not k.startswith('-'))
    report.update({
        'out': os.path.abspath(a.out),
        'scene_bytes': size,
        'artboards': stats['artboards'],
        'elements': stats['elements'],
        'assets': len(C.asset_decls(tgt)),
        'assets_missing_bytes': sum(1 for m in manifest if m['md5'] is None),
        'dangling_refs': dangling,
    })
    same_bytes = [d for d in report['dropped_assets'] if d['reason'] == 'same-bytes']
    print('target      %d artboards  %d assets' % (tgt_arts, len(tgt_assets)))
    print('source      %d artboards  %d assets' % (src_arts, len(C.asset_decls(src))))
    print('conflict    %s  replaced %d  skipped %d  artboard-filter-dropped %d' % (
        a.on_conflict, replaced, len(report['skipped']), skip_count))
    print('assets      src-kept %d  same-id-dropped %d  same-bytes-dropped %d  '
          'renamed %d  re-id %d  missing-bytes %d' % (
              len(kept_src), len(report['dropped_assets']) - len(same_bytes),
              len(same_bytes), len(report['renamed']), len(report['reallocated']),
              len(report['missing_bytes'])))
    if a.prune_orphans:
        print('pruned      %d orphan assets' % len(report['pruned']))
    if ascii_renamed:
        print('renamed     %d asset files -> asset_NNN.<ext> (non-ASCII names break the CLI)'
              % len(ascii_renamed))
    print('out         %d artboards  %d assets  %d elements  %d bytes' % (
        stats['artboards'], len(C.asset_decls(tgt)), stats['elements'], size))
    print('dangling refs %d (must be 0)' % len(dangling))
    print('manifest    %s' % os.path.join(a.out, 'assets.manifest.json'))
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print('report      %s' % a.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
