#!/usr/bin/env python3
"""列出 / 导出 .rev 里内嵌的素材字节，并按 RML 的 asset id 绑定。

.rev 里每条素材是 `d4 01 <LEB128 len> <bytes> d5 01 <n> <scope varint> <oid varint>`，
`scope:oid` 正好等于 RML 里的 id（如 0:769、14:537）。

用法：
  python rev_assets.py --rev src.rev                      # 只统计
  python rev_assets.py --rev src.rev --rml scene.rml      # 与 RML 绑定并核对尺寸
  python rev_assets.py --rev src.rev --rml scene.rml --out assets/
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import xml.etree.ElementTree as ET


def rv(buf, p, limit=None):
    v = 0
    sh = 0
    while True:
        if limit is not None and p >= limit:
            raise ValueError('varint past payload')
        b = buf[p]
        p += 1
        v |= (b & 0x7F) << sh
        sh += 7
        if not (b & 0x80):
            return v, p


def scan(buf):
    """返回 {scope:oid: (offset, length)}，只认带 d5 01 尾记录的 d4 01 记录。"""
    table = {}
    i = 0
    n = len(buf)
    while True:
        i = buf.find(b'\xd4\x01', i)
        if i < 0 or i + 4 >= n:
            break
        try:
            ln, p = rv(buf, i + 2)
        except (IndexError, ValueError):
            i += 2
            continue
        if ln <= 0 or p + ln + 2 >= n:
            i += 2
            continue
        if buf[p + ln:p + ln + 2] != b'\xd5\x01':
            i += 2
            continue
        q = p + ln + 2
        try:
            count = buf[q]
            scope, p2 = rv(buf, q + 1, q + 1 + count)
            oid, _ = rv(buf, p2, q + 1 + count)
        except (IndexError, ValueError):
            i += 2
            continue
        table.setdefault('%d:%d' % (scope, oid), (p, ln))
        i = p + ln
    return table


def dims(data):
    if data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24:
        return struct.unpack('>II', data[16:24])
    if data[:2] == b'\xff\xd8':
        j = 2
        while j < len(data) - 9:
            if data[j] != 0xFF:
                j += 1
                continue
            m = data[j + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3):
                h, w = struct.unpack('>HH', data[j + 5:j + 9])
                return w, h
            j += 2 + struct.unpack('>H', data[j + 2:j + 4])[0]
    return None


def load_rml(path):
    """返回 {id: {tag, file, name, assetId, width, height}} 与引用该 id 的元素数。"""
    root = ET.parse(path).getroot()
    decl = {}
    for el in root:
        if el.get('id') and el.tag.endswith('Asset'):
            decl[el.get('id')] = {
                'tag': el.tag,
                'file': el.get('file') or '',
                'name': el.get('name') or '',
                'assetId': el.get('assetId') or '',
                'width': el.get('width'),
                'height': el.get('height'),
            }
    return decl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rev', required=True)
    ap.add_argument('--rml')
    ap.add_argument('--out')
    ap.add_argument('--json')
    a = ap.parse_args()

    buf = open(a.rev, 'rb').read()
    table = scan(buf)
    print('rev %s  %d bytes  records %d' % (os.path.basename(a.rev), len(buf), len(table)))

    if not a.rml:
        for k in sorted(table, key=lambda s: (int(s.split(':')[0]), int(s.split(':')[1]))):
            off, ln = table[k]
            d = dims(buf[off:off + ln])
            print('  %-12s %8d bytes %s' % (k, ln, '%dx%d' % d if d else ''))
        return 0

    decl = load_rml(a.rml)
    print('rml %s  asset decls %d' % (os.path.basename(a.rml), len(decl)))
    rows = []
    bound = miss = mismatch = text = 0
    for aid, item in decl.items():
        hit = table.get(aid)
        if not hit:
            # ScriptAsset text (.luau) is never inside a d4 record: the CLI keeps
            # it as a loose file next to scene.rml.
            if item['tag'] == 'ScriptAsset':
                text += 1
                rows.append({'id': aid, 'status': 'text', **item})
            else:
                miss += 1
                rows.append({'id': aid, 'status': 'no-bytes', **item})
            continue
        off, ln = hit
        data = buf[off:off + ln]
        d = dims(data)
        want = None
        if item.get('width') and item.get('height'):
            want = (int(item['width']), int(item['height']))
        ok = True if (d is None or want is None) else d == want
        mismatch += 0 if ok else 1
        bound += 1
        rows.append({'id': aid, 'status': 'ok' if ok else 'dims-mismatch', 'bytes': ln,
                     'dims': '%dx%d' % d if d else '', 'md5': hashlib.md5(data).hexdigest(), **item})
        if a.out and item['file']:
            os.makedirs(a.out, exist_ok=True)
            with open(os.path.join(a.out, item['file']), 'wb') as f:
                f.write(data)

    for r in rows:
        if r['status'] not in ('ok', 'text'):
            print('  %-12s %-14s %s' % (r['id'], r['status'], r.get('file', '')))
    print('bound %d  text %d  no-bytes %d  dims-mismatch %d  (extract -> %s)' % (
        bound, text, miss, mismatch, a.out or 'off'))
    if a.json:
        json.dump(rows, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('report', a.json)
    return 1 if mismatch else 0


if __name__ == '__main__':
    sys.exit(main())
