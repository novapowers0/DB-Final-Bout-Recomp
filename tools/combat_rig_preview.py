"""Static offline geometry proof in root-local space; NOT a game render.

Optional PNG, created exclusively at the caller's new path. Three panels:
source slot2, authored bridge tick3, bridge endpoint (slot1 selected parts,
slot2 protected carriers). Triangle/quad wireframes are
decoded from the private disc in memory; PNG must remain a private diagnostic.
Integer labels are PART IDs, never automatically inferred anatomical names.
"""
import argparse
import colorsys
from pathlib import Path
import struct
import zlib
from combat_assets import unpack_psdp
from combat_rigclip import (ROOT, bridge, local_matrix, mesh_vertices, packets,
                           pose, raw_clip, records, sources)


def world_polygons(exe, model, meshes, mapping, state):
    """Diagnostic local hierarchy composition. Floating accumulation is a
    preview approximation, not GTE fixed-point rounding/culling/lighting."""
    cache = {0: (((1, 0, 0), (0, 1, 0), (0, 0, 1)), (0, 0, 0))}

    def coord(part):
        if part in cache: return cache[part]
        # Explicit local origin for real root; do not invent a game world pose.
        if part in mapping['roots']:
            cache[part] = cache[0]
            return cache[part]
        p = state[part]
        r = local_matrix(exe, p['angle'])
        r = tuple(tuple(r[i][j]*p['scale'][j]/4096**2 for j in range(3)) for i in range(3))
        pr, pt = coord(mapping['parents'][part])
        rotation = tuple(tuple(sum(pr[i][k]*r[k][j] for k in range(3)) for j in range(3)) for i in range(3))
        position = tuple(pt[i]+sum(pr[i][k]*p['translation'][k] for k in range(3)) for i in range(3))
        cache[part] = rotation, position
        return cache[part]

    output = {}
    for part, mesh in mapping['mesh'].items():
        rotation, position = coord(part)
        output[part] = [tuple(tuple(position[i]+sum(rotation[i][k]*v[k] for k in range(3))
                                   for i in range(3)) for v in polygon)
                        for polygon in mesh_vertices(model, meshes[mesh])]
    return output


def make_preview(disc, record, path, selected=None):
    path = Path(path)
    if not path.parent.is_dir() or path.exists():
        raise ValueError('Preview requires an existing parent and a NEW file path')
    archive, menu, exe, _ = sources(disc)
    rows = list(records(archive, menu))
    if not 0 <= record < len(rows): raise ValueError('Unknown record')
    _, table, model_at, meshes, mapping = rows[record]
    model, _ = unpack_psdp(archive, model_at)
    a, b = (pose(raw_clip(archive, table, slot)) for slot in (2, 1))
    own, _ = bridge(a, b, mapping)
    # Evaluate first four groups using the same public pose reader.
    groups = packets(own)
    end = 4+sum(8+sum(4+len(p['payload']) for p in group) for _, group in groups[:4])
    middle = bytearray(own[:end])
    struct.pack_into('<H', middle, 2, 4)
    states = (a, pose(middle, a), pose(own, a))
    panels = [world_polygons(exe, model, meshes, mapping, state) for state in states]
    if selected is not None:
        if not selected or set(selected)-set(mapping['mesh']):
            raise ValueError('Preview parts must have verified geometry')
        panels = [{p: polygons for p, polygons in panel.items() if p in selected} for panel in panels]
    points = [v for panel in panels for polys in panel.values() for poly in polys for v in poly]
    # Two root-local orthographic views per panel: XY and ZY. +Y is DOWN here.
    lo = min(v[1] for v in points)
    hi = max(v[1] for v in points)
    centers = {axis: (min(v[axis] for v in points)+max(v[axis] for v in points))/2 for axis in (0, 2)}
    span = max(max(v[axis] for v in points)-min(v[axis] for v in points) for axis in (0, 2))
    scale = min(0.5, 540/max(hi-lo, 1), 270/max(span, 1))
    width, height = 1800, 650
    pixels = bytearray(bytes((13, 18, 28))*(width*height))

    def pixel(x, y, color):
        if 0 <= x < width and 0 <= y < height:
            at = 3*(y*width+x)
            pixels[at:at+3] = bytes(color)

    def line(a, b, color):
        x, y = a
        dx, dy = abs(b[0]-x), -abs(b[1]-y)
        sx, sy, error = (1 if x < b[0] else -1), (1 if y < b[1] else -1), dx+dy
        for _ in range(width+height):
            pixel(x, y, color)
            if (x, y) == b: break
            e = 2*error
            if e >= dy: error += dy; x += sx
            if e <= dx: error += dx; y += sy

    digits = ['111101101101111','010110010010111','111001111100111','111001111001111',
              '101101111001001','111100111001111','111100111101111','111001001001001',
              '111101111101111','111101111001111']
    def label(number, x, y):
        for char in str(number):
            for i, bit in enumerate(digits[int(char)]):
                if bit == '1':
                    for dx in range(2):
                        for dy in range(2): pixel(x+2*(i % 3)+dx, y+2*(i//3)+dy, (255, 255, 255))
            x += 8

    for panel_index, panel in enumerate(panels):
        label((2, 3, 1)[panel_index], 600*panel_index+10, 15)
        for view, axis in enumerate((0, 2)):
            def project(v):
                return round(600*panel_index+150+300*view+(v[axis]-centers[axis])*scale), round(65+(v[1]-lo)*scale)
            for part, polys in panel.items():
                color = tuple(round(v*255) for v in colorsys.hsv_to_rgb((part*0.618) % 1, 0.7, 0.95))
                for poly in polys:
                    for v, w in zip(poly, poly[1:]+poly[:1]): line(project(v), project(w), color)
                verts = [v for poly in polys for v in poly]
                center = tuple(sum(v[i] for v in verts)/len(verts) for i in range(3))
                label(part, *project(center))
        line((600*panel_index, 0), (600*panel_index, height-1), (80, 80, 80))

    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data))
    raw = b''.join(b'\0'+pixels[3*width*y:3*width*(y+1)] for y in range(height))
    png = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>2I5B', width, height, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw))+chunk(b'IEND', b'')
    with path.open('xb') as stream: stream.write(png)
    return {'record': record, 'png': str(path), 'panels': ['slot2', 'bridge tick3', 'slot1 parts / slot2 carriers'],
            'views': ['root-local XY', 'root-local ZY'], 'game_render': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disc', type=Path, default=ROOT/'disc/Dragon Ball GT - Final Bout (USA).bin')
    parser.add_argument('--record', type=int, default=0)
    parser.add_argument('--png', type=Path, required=True)
    parser.add_argument('--parts', help='Comma-separated verified part IDs; isolate geometry')
    args = parser.parse_args()
    print(make_preview(args.disc, args.record, args.png,
                       set(map(int, args.parts.split(','))) if args.parts else None))
