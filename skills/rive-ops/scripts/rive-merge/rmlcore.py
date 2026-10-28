#!/usr/bin/env python3
"""Shared helpers for the rive-merge tool chain (Rive CLI >= 1.8).

No third-party deps: only stdlib, so it runs on a bare Windows Python 3.8+.
Console output is ASCII-only (PowerShell 5.1 mangles UTF-8 pipes); every
non-ASCII detail goes into the --json report instead.

Self check:  python rmlcore.py --selftest
"""
import argparse
import hashlib
import json
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET

NULL_ID = '0:0'
ID_RE = re.compile(r'^-?\d+:\d+$')
# id lists appear as `a,b` (selectedAnimations) or `a-b` (sourcePathIds)
IDLIST_RE = re.compile(r'^-?\d+:\d+(?:[,-]-?\d+:\d+)*$')
IDTOKEN_RE = re.compile(r'-?\d+:\d+')
SPLIT_RE = re.compile(r'([,-])')

BINARY_EXT = ('.png', '.jpg', '.jpeg', '.webp', '.ttf', '.otf', '.woff', '.woff2', '.svg', '.riv')
TEXT_EXT = ('.luau', '.txt', '.json')
# Asset elements that own a file.  ComponentAsset is NOT one: it is an
# artboard container referenced through `expandedComponents`.
ASSET_TAGS = ('ImageAsset', 'FontAsset', 'SVGAsset', 'ScriptAsset', 'AudioAsset', 'VideoAsset')


# ---------------------------------------------------------------- rev scanning

def read_varint(buf, p, limit=None):
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


def scan_rev(buf):
    """Return {id: (offset, length)} for binary asset payloads in a .rev.

    A record is `d4 01 <LEB128 len> <bytes> d5 01 <n> <scope> <oid>`; the
    trailing id equals the RML `id` of the asset.  Text records (luau) use a
    different marker (`c7 07 <len> <text>`) and are not listed here.
    """
    table = {}
    i = 0
    n = len(buf)
    while True:
        i = buf.find(b'\xd4\x01', i)
        if i < 0 or i + 4 >= n:
            break
        try:
            ln, p = read_varint(buf, i + 2)
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
            scope, p2 = read_varint(buf, q + 1, q + 1 + count)
            oid, _ = read_varint(buf, p2, q + 1 + count)
        except (IndexError, ValueError):
            i += 2
            continue
        table.setdefault('%d:%d' % (scope, oid), (p, ln))
        i = p + ln
    return table


def rev_bytes(buf, hit):
    off, ln = hit
    return buf[off:off + ln]


# ---------------------------------------------------------------- misc helpers

def md5(data):
    return hashlib.md5(data).hexdigest()


def dims(data):
    """Pixel size for PNG / JPEG, else None."""
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


def magic_ok(data, ext):
    """Cheap sanity check that the bytes match the declared extension."""
    ext = ext.lower()
    if not data:
        return False
    if ext == '.png':
        return data[:8] == b'\x89PNG\r\n\x1a\n'
    if ext in ('.jpg', '.jpeg'):
        return data[:2] == b'\xff\xd8'
    if ext == '.webp':
        return data[:4] == b'RIFF' and data[8:12] == b'WEBP'
    if ext in ('.ttf', '.otf'):
        return data[:4] in (b'\x00\x01\x00\x00', b'OTTO', b'true')
    if ext == '.svg':
        head = data[:400].lstrip()
        return head.startswith(b'<') and b'svg' in head[:200].lower()
    if ext == '.luau':
        return b'\x00' not in data[:64]
    return True


def parse_id_list(value):
    """Return (parts, seps) for a pure id list, else None.

    `parts` are the ids, `seps` the separators between them, so a value can be
    rebuilt after remapping.
    """
    if not value or not IDLIST_RE.match(value):
        return None
    items = SPLIT_RE.split(value)
    return items[0::2], items[1::2]


def remap_value(value, table):
    parsed = parse_id_list(value)
    if not parsed:
        return value
    parts, seps = parsed
    out = []
    for k, part in enumerate(parts):
        out.append(table.get(part, part))
        if k < len(seps):
            out.append(seps[k])
    return ''.join(out)


def walk_ids(root):
    """Yield every `id` attribute in document order."""
    for el in root.iter():
        v = el.get('id')
        if v:
            yield v


def id_refs(root, skip_assets=False, ignore=('codeFileId',)):
    """Count id tokens used in non-`id` attributes (i.e. real references).

    `codeFileId` points at an external code file entry that is absent from the
    RML even in untouched documents, so it is ignored by default.
    """
    counts = {}
    for el in root.iter():
        if skip_assets and is_asset_tag(el.tag):
            continue
        for k, v in el.attrib.items():
            if k == 'id' or k in ignore or not v or ':' not in v:
                continue
            for tok in IDTOKEN_RE.findall(v):
                counts[tok] = counts.get(tok, 0) + 1
    return counts


def is_asset_tag(tag):
    return tag in ASSET_TAGS


def asset_decls(root):
    return [el for el in root if is_asset_tag(el.tag)]


def element_stats(root):
    per_tag = {}
    for el in root.iter():
        per_tag[el.tag] = per_tag.get(el.tag, 0) + 1
    return {
        'top': len(list(root)),
        'elements': sum(per_tag.values()),
        'artboards': per_tag.get('Artboard', 0),
        'per_tag': per_tag,
    }


def indent_tree(elem, space='    ', level=0):
    """ET.indent fallback for Python < 3.9."""
    pad = '\n' + space * level
    if len(elem):
        if not (elem.text or '').strip():
            elem.text = pad + space
        for child in elem:
            indent_tree(child, space, level + 1)
        if not (child.tail or '').strip():
            child.tail = pad
    if level and not (elem.tail or '').strip():
        elem.tail = pad


def dump_rml(root, path):
    if hasattr(ET, 'indent'):
        ET.indent(root, space='    ')
    else:
        indent_tree(root)
    body = ET.tostring(root, encoding='unicode')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(body)
    return len(body)


def load_rml(path):
    return ET.parse(path).getroot()


def file_md5(path):
    with open(path, 'rb') as f:
        return md5(f.read())


# ------------------------------------------------------------ rive.yaml (lite)

def read_project_yaml(path):
    out = {}
    if not os.path.exists(path):
        return out
    section = None
    with open(path, encoding='utf-8-sig') as f:
        for raw in f:
            line = raw.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            if not line.startswith(' ') and line.rstrip().endswith(':'):
                section = line.strip()[:-1]
                continue
            if not line.startswith(' ') and ':' in line:
                k, v = line.split(':', 1)
                out[k.strip()] = strip_scalar(v)
                section = None
                continue
            if section and ':' in line:
                k, v = line.split(':', 1)
                out[section + '.' + k.strip()] = strip_scalar(v)
    return out


def strip_scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'':
        return v[1:-1]
    return v


def write_project_yaml(path, name, main=None, project_id=None, file_id=None):
    lines = ['name: %s' % name]
    if main:
        lines.append('main: %s' % json.dumps(main, ensure_ascii=False))
    if project_id is not None and file_id is not None:
        lines += ['push:', '  projectId: %s' % project_id, '  fileId: %s' % file_id]
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')


def find_asset_file(project_dir, name):
    """Assets live flat in the project root; also accept assets/ subdir."""
    if not name:
        return None
    for cand in (os.path.join(project_dir, name), os.path.join(project_dir, 'assets', name)):
        if os.path.isfile(cand):
            return cand
    return None


def safe_rel(name):
    return name.replace('\\', '/').lstrip('/')


# --------------------------------------------------------------------- selftest

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--rev')
    ap.add_argument('--rml')
    a = ap.parse_args()
    if a.rev:
        buf = open(a.rev, 'rb').read()
        print('rev bytes %d records %d' % (len(buf), len(scan_rev(buf))))
    if a.rml:
        root = load_rml(a.rml)
        print('rml stats', json.dumps(element_stats(root)))
        print('refs unique %d orphans-candidates %d' % (
            len(id_refs(root)), sum(1 for _ in asset_decls(root))))
    if not a.rev and not a.rml and not a.selftest:
        ap.print_help()
        return 0
    if a.selftest:
        assert parse_id_list('0:1,0:2') == (['0:1', '0:2'], [','])
        assert parse_id_list('0:1-0:2') == (['0:1', '0:2'], ['-'])
        assert parse_id_list('0:1') == (['0:1'], [])
        assert parse_id_list('12') is None
        assert remap_value('0:1-0:2', {'0:2': '0:9'}) == '0:1-0:9'
        assert remap_value('abc', {'0:1': '0:9'}) == 'abc'
        assert dims(b'\x89PNG\r\n\x1a\n' + b'\x00' * 8 + struct.pack('>II', 3, 4)) == (3, 4)
        assert magic_ok(b'\x89PNG\r\n\x1a\n' + b'\x00' * 16, '.png')
        print('selftest ok')
    return 0


if __name__ == '__main__':
    sys.exit(main())
