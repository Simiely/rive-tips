#!/usr/bin/env python3
"""svg-prep: get an Illustrator SVG ready for Rive import, and verify what came out.

Subcommands (run with --help on any of them):

  clean   IN.svg OUT.svg
          Strip <font> blocks (Rive never reads them), expand inline style="k:v"
          into presentation attributes (Rive does not parse style), add explicit
          width/height from the viewBox, normalise the XML encoding to utf-8.

  images  FILE.svg --outdir DIR [--json OUT.json]
          Extract every embedded <image> as a PNG/JPEG on disk, together with the
          rect it must occupy in artboard coordinates. Needed because
          addSvgInstance silently drops embedded rasters: they have to be uploaded
          and placed as separate Image instances.

          The scale percent is computed against the bitmap's REAL pixel size, not
          the width/height AI writes on the <image> element -- those two differ
          (declared 378x504, pixels 379x505) and Rive places at pixel size. A
          mismatch is flagged with a leading "!" line.

  clip    FILE.svg
          Print every <clipPath> resolved to a plain rect (plus corner radius when
          the path is a rounded rect). Rive ignores clipPath, so this geometry is
          what you bake into the bitmap's alpha channel.

  mask    IN.png OUT.png --img-rect x,y,w,h --clip x,y,w,h[,r]
          Bake a rounded-rect alpha mask into the bitmap. Coordinates are in SVG
          user space (same numbers images/clip print); the image rect is used to
          convert them to image pixels.

  verify  CAPTURE.png REF.png [--size WxH]
          Pixel-compare a Rive capture against the .ai render. Prints mean
          absolute difference (0-255) and the share of pixels differing by >6%.
          Measured: correct imports land at 0.10-0.14, a half-icon offset at
          2.5-3.2. The PASS threshold is 0.5.

Typical run:
  python svg-prep.py clean in.svg out.svg
  python svg-prep.py images out.svg --outdir img --json img.json
  python svg-prep.py clip out.svg
  python svg-prep.py mask img/a.png img/a_masked.png --img-rect 786.893,455.857,126.214,168.286 --clip 788,478,124,124,20.571
  python svg-prep.py verify shot.png ref.png --size 2048x1152

Only mask/verify need Pillow; the rest is stdlib.
"""
import argparse
import base64
import json
import math
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET

NS = "{http://www.w3.org/2000/svg}"
XLINK = "{http://www.w3.org/1999/xlink}href"


# --------------------------------------------------------------------------- clean
STYLE_RE = re.compile(r'\sstyle="([^"]*)"')


def _expand_style(m):
    props = []
    for part in m.group(1).split(";"):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        props.append('%s="%s"' % (k.strip(), v.strip()))
    return (" " + " ".join(props)) if props else ""


def cmd_clean(args):
    raw = open(args.src, "rb").read()
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError:
        txt = raw.decode("latin-1")

    before = {"text": len(re.findall(r"<text", txt)), "font": len(re.findall(r"<font", txt)),
              "style": len(re.findall(r"\sstyle=", txt)), "image": len(re.findall(r"<image", txt))}

    txt = re.sub(r"<font[\s\S]*?</font>", "", txt)
    txt = STYLE_RE.sub(_expand_style, txt)

    m = re.search(r"<svg\b[^>]*>", txt)
    if m:
        tag = m.group(0)
        vb = re.search(r'viewBox="([\d.\-\s]+)"', tag)
        new_tag = tag
        if vb and "width=" not in tag:
            p = vb.group(1).split()
            if len(p) == 4:
                new_tag = tag[:-1].rstrip() + ' width="%s" height="%s">' % (p[2], p[3])
        new_tag = new_tag.replace('encoding="iso-8859-1"', 'encoding="utf-8"')
        txt = txt.replace(tag, new_tag, 1)
    txt = txt.replace('<?xml version="1.0" encoding="iso-8859-1"?>',
                      '<?xml version="1.0" encoding="utf-8"?>')

    with open(args.dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)

    after = {"text": len(re.findall(r"<text", txt)), "font": len(re.findall(r"<font", txt)),
             "style": len(re.findall(r"\sstyle=", txt)), "image": len(re.findall(r"<image", txt))}
    print("clean %s -> %s  %.1f KB" % (args.src, args.dst, os.path.getsize(args.dst) / 1024.0))
    print("  text %d->%d  font %d->%d  style %d->%d  image %d" % (
        before["text"], after["text"], before["font"], after["font"],
        before["style"], after["style"], after["image"]))
    if after["text"]:
        print("  WARN: %d <text> left - Rive maps font-family to bundled Inter (no CJK)." % after["text"])
        print("        Outline the text in Illustrator (createOutline) before exporting.")
    return 0


# ------------------------------------------------------------------------ transform
def _mat_mul(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def _parse_transform(s):
    m = (1, 0, 0, 1, 0, 0)
    if not s:
        return m
    for name, arg in re.findall(r"(\w+)\s*\(([^)]*)\)", s):
        v = [float(x) for x in re.split(r"[,\s]+", arg.strip()) if x]
        cur = None
        if name == "matrix" and len(v) >= 6:
            cur = tuple(v[:6])
        elif name == "translate":
            cur = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0.0)
        elif name == "scale":
            cur = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        if cur:
            m = _mat_mul(m, cur)
    return m


# --------------------------------------------------------------------------- images
def _img_size(path):
    """Real pixel size of a PNG/JPEG, without Pillow.

    This matters: AI writes the <image> element's width/height as the DISPLAY
    size (378x504) while the embedded bitmap is (379x505). Rive places the
    instance at the bitmap's PIXEL size, so the scale percent must be computed
    against these numbers, not against the SVG attributes.
    """
    with open(path, "rb") as f:
        head = f.read(32)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", head[16:24])[:2]
        f.seek(0)
        data = f.read()
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            m = data[i + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                     0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            if m == 0xD9:
                break
            if m in (0xD8,) or 0xD0 <= m <= 0xD7:
                i += 2
                continue
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg
    return None, None


def cmd_images(args):
    tree = ET.parse(args.svg)
    root = tree.getroot()
    out = []

    def walk(el, ctm):
        ctm = _mat_mul(ctm, _parse_transform(el.get("transform")))
        if el.tag.replace(NS, "") == "image":
            href = el.get(XLINK) or el.get("href") or ""
            if href.startswith("data:"):
                head, b64 = href.split(",", 1)
                w = float(el.get("width", 0) or 0)
                h = float(el.get("height", 0) or 0)
                a, b, c, d, e, f = ctm
                sx, sy = math.hypot(a, b), math.hypot(c, d)
                out.append({
                    "svg": os.path.basename(args.svg),
                    "mediatype": head.split(";")[0].replace("data:", ""),
                    "x": round(e, 3), "y": round(f, 3),
                    "w": round(w * sx, 3), "h": round(h * sy, 3),
                    "native_w": w, "native_h": h, "scale": round(sx, 4),
                    "bytes": len(base64.b64decode(b64)),
                    "_b64": b64,
                })
        for ch in el:
            walk(ch, ctm)

    walk(root, (1, 0, 0, 1, 0, 0))
    os.makedirs(args.outdir, exist_ok=True)
    for i, im in enumerate(out):
        ext = im["mediatype"].split("/")[-1].replace("jpeg", "jpg")
        ext = "png" if ext not in ("png", "jpg") else ext
        p = os.path.join(args.outdir, "%s_img%d.%s" % (
            os.path.splitext(os.path.basename(args.svg))[0], i, ext))
        open(p, "wb").write(base64.b64decode(im.pop("_b64")))
        im["file"] = p
        rw, rh = _img_size(p)
        im["pixel_w"], im["pixel_h"] = rw, rh
        base_w = rw or im["native_w"] or 1
        base_h = rh or im["native_h"] or 1
        print("%-28s %-10s x=%-9s y=%-9s %.2fx%.2f  scale=%s  %d KB" % (
            os.path.basename(p), im["mediatype"], im["x"], im["y"],
            im["w"], im["h"], im["scale"], im["bytes"] // 1024))
        if rw and (abs(rw - im["native_w"]) > 0.5 or abs(rh - im["native_h"]) > 0.5):
            print("    ! SVG declares %gx%g but the bitmap is %dx%d "
                  "-- Rive places it at PIXEL size, use the scale below"
                  % (im["native_w"], im["native_h"], rw, rh))
        print("    place at centre: x=%s y=%s  scale %%: sx=%.4f sy=%.4f" % (
            round(im["x"] + im["w"] / 2, 3), round(im["y"] + im["h"] / 2, 3),
            im["w"] / base_w * 100, im["h"] / base_h * 100))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print("json -> %s" % args.json)
    if not out:
        print("no embedded <image> found")
    return 0


# ----------------------------------------------------------------------------- clip
def _path_points(d):
    """Absolute points of an SVG path (M/L/C + h/v shorthand). Enough for AI's
    rounded-rect clip paths; not a general renderer."""
    toks = re.findall(r"[MmLlHhVvCcZz]|-?\d*\.?\d+(?:e[-+]?\d+)?", d)
    pts, cur, cmd, x, y = [], (0.0, 0.0), None, 0.0, 0.0
    i = 0

    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v

    while i < len(toks):
        t = toks[i]
        if re.match(r"[A-Za-z]", t):
            cmd = t; i += 1
            if cmd in "Zz":
                continue
        if cmd in "Mm":
            x, y = num(), num()
            if cmd == "m":
                x += cur[0]; y += cur[1]
            cur = (x, y); pts.append(cur)
            cmd = "L" if cmd == "M" else "l"
        elif cmd in "Ll":
            dx, dy = num(), num()
            x, y = (x + dx, y + dy) if cmd == "l" else (dx, dy)
            cur = (x, y); pts.append(cur)
        elif cmd in "Hh":
            v = num()
            x = x + v if cmd == "h" else v
            cur = (x, y); pts.append(cur)
        elif cmd in "Vv":
            v = num()
            y = y + v if cmd == "v" else v
            cur = (x, y); pts.append(cur)
        elif cmd in "Cc":
            vals = [num() for _ in range(6)]
            if cmd == "c":
                vals = [vals[0] + x, vals[1] + y, vals[2] + x, vals[3] + y, vals[4] + x, vals[5] + y]
            pts.extend([(vals[0], vals[1]), (vals[2], vals[3]), (vals[4], vals[5])])
            x, y = vals[4], vals[5]; cur = (x, y)
        else:
            i += 1
    return pts


def cmd_clip(args):
    tree = ET.parse(args.svg)
    root = tree.getroot()
    ids = {}
    for el in root.iter():
        if el.get("id"):
            ids[el.get("id")] = el

    found = []
    for cp in root.iter(NS + "clipPath"):
        target = None
        for ch in cp:
            href = (ch.get(XLINK) or ch.get("href") or "").lstrip("#")
            target = ids.get(href) if href else ch
            if target is not None:
                break
        if target is None:
            continue
        tag = target.tag.replace(NS, "")
        rec = {"clipPathId": cp.get("id")}
        if tag == "rect":
            x, y = float(target.get("x", 0)), float(target.get("y", 0))
            w, h = float(target.get("width", 0)), float(target.get("height", 0))
            rx = target.get("rx") or target.get("ry")
            rec.update({"x": x, "y": y, "w": w, "h": h, "r": float(rx) if rx else 0.0})
        elif tag == "path":
            pts = _path_points(target.get("d", ""))
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            x0, y0 = min(xs), min(ys)
            r = 0.0
            first_c = re.search(r'[Cc]\s*(-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)',
                                target.get("d", ""))
            if first_c:
                r = round(abs(float(first_c.group(5)) - x0), 3)
            rec.update({"x": x0, "y": y0, "w": round(max(xs) - x0, 3),
                        "h": round(max(ys) - y0, 3), "r": r})
        else:
            continue
        found.append(rec)

    if not found:
        print("no resolvable clipPath (nothing to bake)")
        return 0
    print(json.dumps(found, ensure_ascii=False, indent=1))
    print("\nRive ignores clipPath: bake each into the matching bitmap, e.g.")
    for rec in found:
        print("  --clip %s,%s,%s,%s,%s" % (rec["x"], rec["y"], rec["w"], rec["h"], rec["r"]))
    return 0


# ----------------------------------------------------------------------------- mask
def _rect(s):
    v = [float(x) for x in s.split(",")]
    return v


def cmd_mask(args):
    from PIL import Image, ImageDraw

    img_rect = _rect(args.img_rect)          # x, y, w, h in SVG units
    clip = _rect(args.clip)                  # x, y, w, h[, r] in SVG units
    cr = clip[4] if len(clip) > 4 else 0.0

    im = Image.open(args.src).convert("RGBA")
    W, H = im.size
    sx, sy = W / img_rect[2], H / img_rect[3]
    x0 = (clip[0] - img_rect[0]) * sx
    y0 = (clip[1] - img_rect[1]) * sy
    cw, ch, r = clip[2] * sx, clip[3] * sy, cr * sx

    S = 4                                    # supersample, or the corners crawl
    m = Image.new("L", (W * S, H * S), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        [x0 * S, y0 * S, (x0 + cw) * S, (y0 + ch) * S], radius=r * S, fill=255)
    m = m.resize((W, H), Image.LANCZOS)

    out = im.copy()
    out.putalpha(Image.composite(im.getchannel("A"), Image.new("L", (W, H), 0), m))
    out.save(args.dst)
    print("masked %s -> %s  (clip in image px: %.1f,%.1f %.1fx%.1f r=%.1f)" % (
        args.src, args.dst, x0, y0, cw, ch, r))
    return 0


# --------------------------------------------------------------------------- verify
def cmd_verify(args):
    from PIL import Image, ImageChops

    a = Image.open(args.capture).convert("RGB")
    b = Image.open(args.ref).convert("RGB")
    if args.size:
        w, h = [int(v) for v in args.size.lower().split("x")]
        a = a.resize((w, h), Image.LANCZOS)
        b = b.resize((w, h), Image.LANCZOS)
    elif a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    w, h = a.size

    hist = ImageChops.difference(a, b).convert("L").histogram()
    total = float(w * h)
    mean = sum(i * n for i, n in enumerate(hist)) / total
    r6 = 100.0 * sum(hist[16:]) / total
    verdict = "PASS" if mean < 0.5 else ("CHECK" if mean < 2.0 else "FAIL")
    print("mean=%.2f/255  differ>6%%=%.3f%%  %dx%d  -> %s" % (mean, r6, w, h, verdict))
    if verdict != "PASS":
        print("  >0.5 usually means misplacement, wrong scale, or a missing/extra layer")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="svg-prep", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("clean", help="strip <font>, expand style, add width/height")
    c.add_argument("src"); c.add_argument("dst")
    c.set_defaults(func=cmd_clean)

    c = sub.add_parser("images", help="extract embedded <image> + its target rect")
    c.add_argument("svg"); c.add_argument("--outdir", required=True); c.add_argument("--json")
    c.set_defaults(func=cmd_images)

    c = sub.add_parser("clip", help="resolve clipPath to a rect (+ radius)")
    c.add_argument("svg")
    c.set_defaults(func=cmd_clip)

    c = sub.add_parser("mask", help="bake a rounded-rect alpha mask into a bitmap")
    c.add_argument("src"); c.add_argument("dst")
    c.add_argument("--img-rect", required=True, help="x,y,w,h in SVG units")
    c.add_argument("--clip", required=True, help="x,y,w,h[,r] in SVG units")
    c.set_defaults(func=cmd_mask)

    c = sub.add_parser("verify", help="pixel-compare a capture against the .ai render")
    c.add_argument("capture"); c.add_argument("ref")
    c.add_argument("--size", help="WxH, e.g. 2048x1152")
    c.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
