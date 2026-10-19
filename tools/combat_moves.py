"""Final Bout action/animation linkage, derived from the retail STEP40 reader.

Reads the user's local disc in memory and emits metadata only. No asset payloads
or runtime execution are included in reports. Action time is interpreter ticks,
not measured frame advantage. The 0x4f packet stream is NOT a bone-name mapping.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from combat_assets import OPCODES, script_tables, unpack_psdp
from combat_map import Iso, ROOT

# STEP40 handlers advance s1 past operands, then the common fetch adds 4.
WORDS = {op: 1 for op in OPCODES}
WORDS.update({0x22: 5, 0x23: 5, 0x40: 3, 0x41: 4, 0x80: 3, 0x81: 2, 0x84: 3})
NAMES = {0: 'wait_animation', 1: 'nop', 0x20: 'animation', 0x21: 'global_event',
         0x22: 'camera', 0x23: 'spawn', 0x24: 'speed', 0x25: 'collision_registration',
         0x26: 'fighter_event', 0x40: 'effect', 0x41: 'sound',
          0x60: 'audio_bank_event', 0x61: 'audio_channel_event', 0x62: 'audio_event',
         0x80: 'attack_parameters', 0x81: 'attack_chain', 0x82: 'clear_attack_flag',
         0x83: 'nop', 0x84: 'secondary_attack_parameters'}


def u32(data, offset):
    if offset < 0 or offset + 4 > len(data):
        raise ValueError('Truncated word')
    return struct.unpack_from('<I', data, offset)[0]


def clip(data, offset, limit):
    """0x8004216C and 0x80042240: frame groups with word length/packet count/time.

    Validate every boundary, monotonic time and exact decoded extent. Parsing the
    inner transform opcodes is a separate step; never infer a skeleton here.
    """
    if not 0 <= offset < limit <= len(data):
        raise ValueError('Invalid clip extent')
    encoded = data[offset:limit]
    compressed = encoded[:4] == b'Psdp'
    body = unpack_psdp(encoded)[0] if compressed else encoded
    magic, count = struct.unpack_from('<HH', body) if len(body) >= 4 else (0, 0)
    if magic != 0x4F or not 0 < count <= 4096:
        raise ValueError('Not a bounded 0x4f animation')
    cursor, groups, previous = 4, [], -1
    for _ in range(count):
        if cursor + 8 > len(body):
            raise ValueError('Truncated frame group')
        words, packets, tick = struct.unpack_from('<HHI', body, cursor)
        if words < 2 or not 0 < packets <= words - 2 or tick <= previous:
            raise ValueError('Invalid frame group')
        end = cursor + words * 4
        if end > len(body):
            raise ValueError('Frame group exceeds clip')
        groups.append({'offset': cursor, 'words': words, 'packets': packets, 'tick': tick})
        cursor, previous = end, tick
    if compressed and cursor != len(body):
        raise ValueError('Unaccounted decoded animation bytes')
    return {'file_offset': offset, 'compressed': compressed, 'decoded_bytes': cursor,
            'sha256': hashlib.sha256(body[:cursor]).hexdigest(),
            'groups': groups, 'last_tick': previous}


def animation_tables(data):
    """0x826a container: BYTE offsets from after table, unlike action WORD offsets.

    0x800420EC rebases these pointers in RAM and changes magic to 0x826b.
    Tables on disc are sector-aligned; validate all clips, including aliases.
    """
    tables = []
    for offset in range(0, len(data) - 8, 2048):
        magic, count = struct.unpack_from('<HH', data, offset)
        if magic != 0x826A or not 32 <= count <= 512:
            continue
        stream = offset + 4 * (count + 1)
        if stream >= len(data):
            continue
        entries = struct.unpack_from('<' + 'I' * count, data, offset + 4)
        unique = sorted(set(entries))
        if any(v & 3 or stream + v >= len(data) for v in unique):
            continue
        clips = {}
        try:
            for v in unique:
                clips[v] = clip(data, stream + v, len(data))
        except ValueError:
            continue
        tables.append({'file_offset': offset, 'slots': count, 'unique_offsets': len(unique),
                       'entries': list(entries), 'clips': clips})
    return tables


def action(data, offset, end):
    """Decode one bounded action. No cross-slot fallthrough is silently invented.

    A zero event waits on the animation context, so its duration is unresolved.
    Attack-chain/secondary parameters depend on game code: this is a static path,
    never reported as observed startup, active duration or recovery advantage.
    """
    if offset & 3 or end & 3 or not 0 <= offset < end <= len(data):
        raise ValueError('Invalid action extent')
    cursor, tick, events = offset, 0, []
    while cursor < end:
        word = u32(data, cursor)
        op, duration, operand = (word >> 16) & 255, word >> 24, word & 0xFFFF
        if op not in WORDS:
            raise ValueError(f'Unknown action opcode {op:#x} at {cursor:#x}')
        size = WORDS[op] * 4
        if cursor + size > end:
            raise ValueError('Action operands cross boundary')
        events.append({'file_offset': cursor, 'tick': tick, 'duration': duration,
                       'opcode': op, 'name': NAMES[op], 'operand': operand,
                        'words': WORDS[op]})
        if op == 0x84:
            # 0x8004ED18..74 stores the signed high byte at script+0x16;
            # 0x8004F204..224 subtracts that field when spawning a technique.
            cost = u32(data, cursor+4) >> 24
            events[-1]['ki_cost'] = cost if cost < 128 else cost-256
        tick += duration
        cursor += size
        if word == 0:
            break  # wait completes the action; following words can be opaque data
    return {'file_offset': offset, 'bytes': end - offset, 'events': events,
            'trailing_bytes': end - cursor,
            'static_ticks': tick,
            'waits_animation': any(e['opcode'] == 0 for e in events),
            'contains_control': any(e['opcode'] in (0x81, 0x84) for e in events)}


def roster(data):
    """Link the 0x4244 action tables to verified 0x826a animation containers.

    RAM separation is 0x48800: 0x800CF000 -> 0x80117800 (side 1) and
    0x80147800 -> 0x80190000 (side 2). All shipped candidates must corroborate
    that separation, all event boundaries and every referenced animation slot.
    """
    tables = {t['file_offset']: t for t in animation_tables(data)}
    result = []
    for table in script_tables(data):
        offset, count = table['file_offset'], table['action_slots']
        if struct.unpack_from('<H', data, offset)[0] != 0x4244:
            continue
        anim = tables.get(offset - 0x48800)
        if not anim:
            raise ValueError(f'Action table has no linked animation container: {offset:#x}')
        entries = struct.unpack_from('<' + 'I' * count, data, offset + 4)
        unique = sorted(set(v for v in entries if v != 0xFFFFFFFF))
        stream = offset + 4 * (count + 1)
        decoded = {}
        for index, v in enumerate(unique):
            # Final script is zero-terminated; its bound is not the next sector.
            start = stream + v * 4
            if index + 1 < len(unique):
                end = stream + unique[index + 1] * 4
            else:
                end = start
                while end < min(start + 4096, len(data)):
                    word = u32(data, end)
                    op = (word >> 16) & 255
                    if op not in WORDS:
                        raise ValueError('Unbounded final action')
                    end += WORDS[op] * 4
                    if word == 0:
                        break
                else:
                    raise ValueError('Final action missing terminator')
            decoded[v] = action(data, start, end)
        actions = []
        for index, v in enumerate(entries):
            if v == 0xFFFFFFFF:
                actions.append({'id': index, 'missing': True})
                continue
            item = dict(decoded[v], id=index)
            for event in item['events']:
                if event['opcode'] == 0x20 and event['operand'] >= anim['slots']:
                    # Animation number indexes container pointer slot +1.
                    raise ValueError(f'Action {index:#x} at {offset:#x} references animation '
                                     f'{event["operand"]:#x} outside {anim["slots"]} slots')
            actions.append(item)
        result.append({'roster_index': len(result), 'action_table_offset': offset,
                       'animation_table_offset': anim['file_offset'],
                       'action_slots': count, 'unique_action_starts': len(unique),
                       'animation_slots': anim['slots'],
                       'unique_animation_offsets': anim['unique_offsets'],
                       'unique_animation_payloads': len({c['sha256'] for c in anim['clips'].values()}),
                       'animation_aliases': anim['slots'] - anim['unique_offsets'],
                       'actions': actions,
                       'animations': [{'slot': i, **anim['clips'][v]} for i, v in enumerate(anim['entries'])]})
    return result


def move_card(character, item):
    """Evidence-only card: static event checkpoints, never measured frame data.

    Use archive/action IDs until character names and command routes are proven.
    Retiming follows the production per-event clock and preserves duration 1.
    Collision registration/clear is not equivalent to a measured active window.
    """
    selected = (0x64 <= item['id'] <= 0x77 or 0xA0 <= item['id'] <= 0xA5 or item['id'] == 0x8C)
    technique = 0x78 <= item['id'] <= 0x83
    family = None
    if technique:
        command = 1 if item['id'] <= 0x7D else 0
        coordinated = 0x7B <= item['id'] <= 0x7D or 0x81 <= item['id'] <= 0x83
        family = {'command': command, 'coordinated': coordinated,
                  'native_handler': '0x8006026c' if command else '0x8005ff9c',
                  'timing_policy': 'native', 'damage_policy': 'native',
                  'ki_policy': 'positive_cost_4_over_5'}
    numerator, denominator = (3, 4) if 0x72 <= item['id'] <= 0x77 else (4, 5)
    original_tick = retimed_tick = 0
    primary = None
    checkpoints = []
    for event in item['events']:
        if event['opcode'] == 0x20 and (0x78 <= event['operand'] <= 0x8D or
                                       0xC8 <= event['operand'] <= 0xCD):
            primary = event['operand']
        duration = event['duration']
        mapped = max(1, duration*numerator//denominator) if duration and primary is not None and selected else duration
        if event['opcode'] in (0x20, 0x23, 0x25, 0x80, 0x81, 0x82, 0x84):
            checkpoint = {'event': event['name'], 'source_tick': original_tick,
                          'standard_tick': retimed_tick}
            if event['opcode'] == 0x20:
                checkpoint['animation_slot'] = event['operand']
            if 'ki_cost' in event:
                checkpoint['native_ki_cost'] = event['ki_cost']
                cost = event['ki_cost']
                if cost > 0 and technique:
                    checkpoint['standard_ki_cost'] = max(1, cost*4//5)
                elif cost > 0 and selected and primary is not None and 0x72 <= item['id'] <= 0x77:
                    checkpoint['standard_ki_cost'] = max(1, cost*3//4)
                else:
                    checkpoint['standard_ki_cost'] = cost
            checkpoints.append(checkpoint)
        original_tick += duration
        retimed_tick += mapped
    return {'archive_record': character['roster_index'], 'action_id': hex(item['id']),
            'action_aliases': [hex(a['id']) for a in character['actions']
                               if not a.get('missing') and a['file_offset'] == item['file_offset'] and a['id'] != item['id']],
             'primary_animation_slot': primary,
             'native_special_route': family,
            'standard_variant_candidate': selected and primary is not None,
            'source_static_ticks': original_tick, 'standard_static_ticks': retimed_tick,
            'checkpoints': checkpoints,
            'waits_for_animation': item['waits_animation'],
            'has_control_events': item['contains_control'],
            'measured_startup_active_recovery': None,
            'character_and_move_names': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disc', type=Path, default=ROOT / 'disc/Dragon Ball GT - Final Bout (USA).bin')
    parser.add_argument('--detail', action='store_true')
    parser.add_argument('--cards', action='store_true', help='Static action cards, including native technique costs')
    parser.add_argument('--character', type=int)
    parser.add_argument('--action', type=lambda v: int(v, 0))
    args = parser.parse_args()
    iso = Iso(args.disc)
    _, lba, size = next(x for x in iso.files() if x[0] == 'TITLE/BTCHARA.DAT')
    data = iso.read(lba, size)
    characters = roster(data)
    if args.character is not None:
        characters = [c for c in characters if c['roster_index'] == args.character]
    if args.cards:
        cards = [move_card(c, a) for c in characters for a in c['actions']
                 if not a.get('missing') and (args.action is None or a['id'] == args.action)]
        print(json.dumps({'source_sha256': hashlib.sha256(data).hexdigest(), 'cards': cards,
                          'evidence': 'Static script checkpoints; ticks are not measured frames or collision windows.'}, indent=2))
        return
    if args.action is not None:
        for c in characters:
            c['actions'] = [a for a in c['actions'] if a['id'] == args.action]
            del c['animations']
    elif not args.detail:
        for c in characters:
            del c['actions'], c['animations']
    print(json.dumps({'source_sha256': hashlib.sha256(data).hexdigest(),
                      'characters': characters,
                      'evidence': 'Static disc data linked through STEP40 reader; not a gameplay measurement',
                      'limits': 'Roster index is archive order, not a character name. Bone identities and retargeting unresolved.'},
                     indent=2))


if __name__ == '__main__':
    main()
