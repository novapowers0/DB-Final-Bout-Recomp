"""Offline geometry/part proof and own PS1 multipart bridge; metadata only.

No export of retail payloads, runtime launch or changes to shared modules.
The bridge is a new six-tick smoothstep local-pose trajectory, not retiming.
Anatomical names are limited to five visually inspected parts of record0.
In-game visual quality remains unverified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

from combat_assets import unpack_psdp
from combat_map import Iso, ROOT, step40
from combat_moves import animation_tables, clip, u32

STEP_HASH = '001adcdc2e129d3bd715c29b64e393fa8c2901a7ef39c2347874b321aae6b9dd'
MENU_HASH = 'a65555d55ed6a9bb10111469b3d9a2d1e08906e1c8c6b895185f50c7c69a969c'
EXE_HASH = '507f132cdcbb635bbbf7a75e15c62a9d0d51e22ce4432828da784ec03b67cbcc'
ARCHIVE_HASH = '7b254f3c843674556ac97170fa64cf3773592ae014f4d68adc5811d848471599'
# Manual observations, NOT inferred from numeric IDs or extended to the roster.
# Inspected private PNGs: dbfb-rigclip-arm0-20261019.png / -leg0-20261019.png,
# produced by combat_rig_preview.py from actual polygon corners in two views.
VISUAL_RECORD0 = {8: 'upper_arm', 9: 'forearm', 18: 'thigh', 19: 'lower_leg', 20: 'foot'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def packets(body):
    """Exact inner boundaries, unlike the outer-only combat_moves.clip reader."""
    info = clip(body, 0, len(body))
    if info['compressed'] or info['decoded_bytes'] != len(body):
        raise ValueError('Expected exact uncompressed animation')
    groups = []
    for group in info['groups']:
        at, end = group['offset']+8, group['offset']+4*group['words']
        decoded = []
        for _ in range(group['packets']):
            h = u32(body, at)
            size = h >> 24
            if not size or at+size*4 > end:
                raise ValueError('Packet crosses frame boundary')
            decoded.append({'part': h & 65535, 'op': (h >> 16) & 15,
                            'flags': (h >> 20) & 15,
                            'payload': body[at+4:at+4*size]})
            at += size*4
        if at != end:
            raise ValueError('Unclaimed packet bytes')
        groups.append((group['tick'], decoded))
    return groups


def transform(packet):
    """Native op1/op5 angular, scale and translation triples, in stream order.

    op5 angle/translation signed10; scale unsigned10 *64 (NOT signed).
    Flag1 is add for angle/translation, multiply-Q12 for scale.
    """
    op, flags, data = packet['op'], packet['flags'], packet['payload']
    if op not in (1, 5):
        raise ValueError('Not a transform')
    width = 8 if op == 1 else 4
    channels = [name for bit, name in ((2, 'angle'), (4, 'scale'), (8, 'translation')) if flags & bit]
    if len(data) != width*len(channels):
        raise ValueError('Transform size disagrees with channel mask')
    result = {}
    for index, name in enumerate(channels):
        if op == 1:
            fmt = '<3H' if name == 'scale' else '<3h'
            values = struct.unpack_from(fmt, data, index*width)
        else:
            word = u32(data, index*width)
            values = tuple((word >> (10*i)) & 1023 for i in range(3))
            values = tuple(v*64 if name == 'scale' else (v ^ 512)-512 for v in values)
        result[name] = values
    return result


def pose(body, entering=None):
    state = {k: dict(v) for k, v in (entering or {}).items()}
    for _, group in packets(body):
        for p in group:
            if p['op'] not in (1, 5):
                continue
            part = state.setdefault(p['part'], {})
            for channel, values in transform(p).items():
                if p['flags'] & 1:
                    if channel not in part:
                        continue  # unknown entering channel is not zero
                    if channel == 'scale':
                        values = tuple((a*b) >> 12 for a, b in zip(part[channel], values))
                    elif channel == 'angle':
                        values = tuple(((a+b+32768) & 65535)-32768 for a, b in zip(part[channel], values))
                    else:
                        values = tuple(a+b for a, b in zip(part[channel], values))
                part[channel] = values
    return state


def rig(body):
    remap, parents, geometry, allocated = None, {}, {}, set()
    for _, group in packets(body):
        for p in group:
            part, op, payload = p['part'], p['op'], p['payload']
            if op == 9 and p['flags'] == 2:
                values = list(struct.unpack('<'+'I'*(len(payload)//4), payload))
                if len(values) < 2 or values[-2:] != [0xFFFFFFFE, 0xFFFFFFFF] or remap is not None:
                    raise ValueError('Unknown geometry remap layout')
                remap = values[:-2]
                if len(set(remap)) != len(remap):
                    raise ValueError('Ambiguous geometry labels')
            elif op == 8 and p['flags'] == 0:
                allocated.add(part)
            elif op in (2, 3):
                if len(payload) != 4 or part in (geometry if op == 2 else parents):
                    raise ValueError('Ambiguous binding or hierarchy')
                (geometry if op == 2 else parents)[part] = u32(payload, 0) & 65535
    if remap is None or not parents or not allocated:
        raise ValueError('Missing initialization structure')
    for part in allocated:
        seen, node = set(), part
        while node:
            if node in seen or node not in allocated or node not in parents:
                raise ValueError('Cycle or incomplete hierarchy')
            seen.add(node)
            node = parents[node]
    if set(geometry)-allocated or any(label not in remap for label in geometry.values()):
        raise ValueError('Geometry label not mapped')
    roots = {part for part, parent in parents.items() if parent == 0}
    protected = roots | {part for part, parent in parents.items() if parent in roots}
    return {'remap': remap, 'parents': parents,
            'mesh': {part: remap.index(label) for part, label in geometry.items()},
            'roots': roots, 'protected': protected}


def compact_model(body):
    """EXE 80011C10..80011D64: compact descriptors -> draw model.

    Header has FIVE words, not a standard TMD's three. At +20: group count,
    optional six signed bbox halfwords (flag2), count byte offsets to primitives.
    The first two extra header words are allocation metadata, NOT descriptors.
    Geometry payload remains opaque; no triangle or vertex claims are made.
    """
    if len(body) < 20 or u32(body, 0) != 0x41 or u32(body, 4) not in (0, 2):
        raise ValueError('Not verified compact model')
    count, at = u32(body, 8), 20
    if not 1 <= count <= 64:
        raise ValueError('Unbounded mesh count')
    meshes = []
    for _ in range(count):
        groups = u32(body, at)
        at += 4
        if not 1 <= groups <= 128:
            raise ValueError('Unbounded primitive groups')
        bounds = None
        if u32(body, 4) & 2:
            if at+12 > len(body):
                raise ValueError('Truncated bounds')
            bounds = struct.unpack_from('<6h', body, at)
            if any(bounds[i] > bounds[i+3] for i in range(3)):
                raise ValueError('Invalid model bounds')
            at += 12
        offsets = [u32(body, at+4*i) for i in range(groups)]
        at += 4*groups
        for off in offsets:
            if off & 3 or off+4 > len(body) or not (u32(body, off) & 65535):
                raise ValueError('Primitive offset outside model')
        meshes.append({'bounds': bounds, 'primitive_groups': groups, 'offsets': offsets})
    if any(off < at for mesh in meshes for off in mesh['offsets']):
        raise ValueError('Primitive overlaps descriptor table')
    return meshes


PRIMITIVES = {1: (4, 40, 16), 8: (3, 40, 16), 9: (4, 48, 16),
              10: (3, 52, 16), 11: (4, 64, 16), 12: (3, 28, 4),
              13: (4, 36, 4), 14: (3, 48, 12), 15: (4, 64, 16)}


def mesh_vertices(body, mesh):
    """Nonindexed corners from EXE dispatch 8002BD90 and its actual handlers.

    Per kind: corner count, source stride, vertex offset; signed16 XYZ at +6/v.
    Return polygons in memory only. No name/anatomy inferred from bounds.
    """
    polygons = []
    for offset in mesh['offsets']:
        header = u32(body, offset)
        count, kind = header & 65535, header >> 16
        if kind not in PRIMITIVES:
            raise ValueError(f'Unverified geometry primitive kind {kind}')
        corners, size, vertex_at = PRIMITIVES[kind]
        if offset+4+count*size > len(body):
            raise ValueError('Truncated polygon group')
        for index in range(count):
            start = offset+4+index*size+vertex_at
            polygon = tuple(struct.unpack_from('<3h', body, start+6*v) for v in range(corners))
            polygons.append(polygon)
    return polygons


def raw_clip(data, table, slot):
    item = table['clips'][table['entries'][slot]]
    at = item['file_offset']
    return unpack_psdp(data, at)[0] if item['compressed'] else data[at:at+item['decoded_bytes']]


def arc(a, b):
    return (b-a+2048) % 4096-2048


def truncdiv(a, b):
    return (abs(a)//b) * (-1 if a < 0 else 1)


def local_matrix(exe, angles):
    """Fixed-Q12 RotMatrix, EXE 8002059C..80020824, Rx*Ry*Rz.

    Uses the retail sine/cosine lookup, including its exact rounding. Result is
    row-major. Signs/order below follow the native intermediate products.
    """
    values = []
    for angle in angles:
        word = u32(exe, 0x8002EA38-0x8000F800+4*(abs(angle) & 4095))
        sine, cosine = struct.unpack('<2h', struct.pack('<I', word))
        values.append((-sine if angle < 0 else sine, cosine))
    (sx, cx), (sy, cy), (sz, cz) = values
    ycz, ysz = (cz*-sy) >> 12, (sz*-sy) >> 12
    return (((cz*cy) >> 12, (-sz*cy) >> 12, sy),
            ((sz*cx >> 12)-(ycz*sx >> 12), (cz*cx >> 12)+(ysz*sx >> 12), (-cy*sx) >> 12),
            ((sz*sx >> 12)+(ycz*cx >> 12), (cz*sx >> 12)-(ysz*cx >> 12), (cy*cx) >> 12))


def bridge(start, end, mapping, ticks=6):
    if not 2 <= ticks <= 32:
        raise ValueError('Bridge duration out of bounds')
    selected = sorted(set(mapping['mesh'])-mapping['protected'])
    if not selected or max(selected) >= 64:
        raise ValueError('No bounded non-carrier geometry')
    for part in selected:
        for state in (start, end):
            if set(state.get(part, {})) != {'angle', 'scale', 'translation'}:
                raise ValueError('Unknown endpoint channel')
            if any(not -32768 <= v <= 32767 for v in state[part]['translation']):
                raise ValueError('Translation outside native op1 range')
        if start[part]['scale'] != end[part]['scale']:
            raise ValueError('Scale-changing bridge not supported')
    out = bytearray(struct.pack('<HH', 0x4F, ticks+1))
    for tick in range(ticks+1):
        final = int(tick == ticks)
        out += struct.pack('<HHI', 2+5*len(selected)+final, len(selected)+final, tick)
        weight = tick*tick*(3*ticks-2*tick)
        for part in selected:
            a, b = start[part], end[part]
            angles = tuple(b['angle'][i] if tick == ticks else
                           a['angle'][i]+truncdiv(arc(a['angle'][i], b['angle'][i])*weight, ticks**3)
                           for i in range(3))
            translation = tuple(a['translation'][i]+truncdiv(
                (b['translation'][i]-a['translation'][i])*weight, ticks**3) for i in range(3))
            out += struct.pack('<I4h4h', 0x05A10000 | part, *angles, 0, *translation, 0)
        if final:
            # Native player stops through op9/flag0, NOT through group count.
            out += struct.pack('<I', 0x01090000)
    packets(out)
    return bytes(out), selected


def sources(disc):
    iso = Iso(disc)
    files = {name: (lba, size) for name, lba, size in iso.files()}
    archive = iso.read(*files['TITLE/BTCHARA.DAT'])
    menu = iso.read(*files['MENU/STEP01.BIN'])
    exe = iso.read(*files['SLUS_004.93'])
    engine, _ = step40(disc)
    for name, data, expected in (('archive', archive, ARCHIVE_HASH), ('menu', menu, MENU_HASH),
                                 ('exe', exe, EXE_HASH), ('step40', engine, STEP_HASH)):
        if digest(data) != expected:
            raise ValueError(f'Unverified {name} identity')
    return archive, menu, exe, engine


def records(archive, menu):
    tables = animation_tables(archive)
    sector_table = 0x80053BE4-0x8003DFA0
    for record, table in enumerate(tables):
        # STEP01 archive schedule, 15 entries/record; source models precede clips.
        model_at = u32(menu, sector_table+4*(15*record+3))*2048
        anim_at = u32(menu, sector_table+4*(15*record+5))*2048
        if anim_at != table['file_offset']:
            raise ValueError('Archive schedule does not match animation table')
        model, _ = unpack_psdp(archive, model_at)
        meshes = compact_model(model)
        for mesh in meshes:
            polygons = mesh_vertices(model, mesh)
            vertices = [v for polygon in polygons for v in polygon]
            bounds = tuple(min(v[i] for v in vertices) for i in range(3)) + tuple(
                max(v[i] for v in vertices) for i in range(3))
            if mesh['bounds'] is not None and bounds != mesh['bounds']:
                raise ValueError('Decoded vertices do not reproduce stored model bounds')
            mesh['decoded_vertex_bounds'] = bounds
            mesh['polygon_count'] = len(polygons)
        mapping = rig(raw_clip(archive, table, 0))
        if len(meshes) != len(mapping['remap']) or any(m >= len(meshes) for m in mapping['mesh'].values()):
            raise ValueError('Mesh/remap count mismatch')
        yield record, table, model_at, meshes, mapping


def report(disc, record=0):
    archive, menu, exe, engine = sources(disc)
    rows = list(records(archive, menu))
    if not 0 <= record < len(rows):
        raise ValueError('Unknown archive record')
    _, table, model_at, meshes, mapping = rows[record]
    # Slots 2 -> 1 are real static pose setups referenced in native actions.
    # No assumption that action IDs or archive IDs are anatomical names.
    start = pose(raw_clip(archive, table, 2))
    end = pose(raw_clip(archive, table, 1))
    own, selected = bridge(start, end, mapping)
    changed = sum(start[p] != end[p] for p in selected)
    return {'record': record, 'verified_archive_records': len(rows),
            'source_sha256': {'archive': digest(archive), 'menu': digest(menu),
                              'exe': digest(exe), 'step40': digest(engine)},
            'model_file_offset': hex(model_at), 'animation_file_offset': hex(table['file_offset']),
            'roots': sorted(mapping['roots']), 'protected_carriers': sorted(mapping['protected']),
            'parts': [{'part': p, 'parent': mapping['parents'][p], 'mesh_index': m,
                       'geometry_label': mapping['remap'][m], 'local_bounds': meshes[m]['bounds'],
                       'primitive_groups': meshes[m]['primitive_groups'],
                       'polygons': meshes[m]['polygon_count'],
                       'anatomical_name': VISUAL_RECORD0.get(p) if record == 0 else None,
                       'anatomy_evidence': 'manually inspected decoded polygon preview, record0 only'
                           if record == 0 and p in VISUAL_RECORD0 else None}
                      for p, m in sorted(mapping['mesh'].items())],
            'own_bridge': {'from_slot': 2, 'to_slot': 1, 'ticks': 6, 'groups': 7,
                           'bytes': len(own), 'sha256': digest(own), 'parts': selected,
                           'changed_parts': changed, 'root_motion': False,
                           'native_end_packet': '0x01090000',
                           'protected_endpoint_differences': [p for p in sorted(mapping['protected'])
                               if start.get(p) != end.get(p)],
                           'policy': 'new smoothstep local angle+translation trajectory; constant scale'},
            'decoder_evidence': ['EXE 80011C10..80011D64 compact model conversion',
                                 'STEP40 8004201C geometry label lookup; 800401B4 mesh selection',
                                 'STEP40 80042568 parent binding to node+48',
                                 'STEP40 80042398/800425A0 transform decode',
                                 'EXE 8002059C..80020824 Q12 RotMatrix, Rx*Ry*Rz, 4096 units/turn',
                                 'STEP40 80042C50/80042C74 end packet -> NULL playback pointer'],
            'limits': ['Geometry labels are not mesh indices or anatomical names.',
                       'Polygon corners reproduce stored bounds exactly; anatomy only manually observed for five parts of record0.',
                       'Local axes and rotation order proven; game world facing/ground contact not validated.',
                       'Bridge excludes root and direct carriers; not a full-body/root-motion clip.',
                       'Excluded carrier endpoints may differ: caller must retain native carrier trajectory; do not substitute this for an entire action.',
                       'No runtime publication, native render or gameplay validation performed.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disc', type=Path, default=ROOT/'disc/Dragon Ball GT - Final Bout (USA).bin')
    parser.add_argument('--record', type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(report(args.disc, args.record), indent=2))


if __name__ == '__main__':
    main()
