/* Final Bout motion variants. Included only by the game's standard plugin.
 * Data comes from the mounted game's RAM; no animation assets are bundled.
 * Original endpoint poses, root transforms and collision operands are preserved.
 * Selected normal/ranged actions get private scripts and private visual clips,
 * retimed through ONE piecewise clock. Cinematics and reactions stay stock.
 */
#define MOTION_BYTES 0x80000u
#define MOTION_CLIP_BYTES 0x10000u
#define MOTION_ACTIONS 173u
#define MOTION_ANIMS 512u
#define MOTION_MAGIC 0x464D4244u

typedef struct MotionKnot { uint32_t old_tick, new_tick; } MotionKnot;
static uint32_t s_motion_arena[2], s_motion_hash[2], s_motion_attempted[2];
static unsigned s_motion_ready[2];
/* Selected actions whose retimed clip was not installed (missing/aliased move).
 * They keep stock timing, so they must also keep stock damage. */
static uint32_t s_motion_unretimed[2][6];
/* Static tick total of each selected action after retiming. The cancel window
 * uses the action's own timeline instead of a guessed recovery constant. */
static uint32_t s_motion_ticks[2][MOTION_ACTIONS];
/* Runtime identity and recovery boundary of each private action. Script +4 is
 * an EVENT COUNTDOWN, not an elapsed action clock (STEP40 0x8004EE84). */
static uint32_t s_motion_start[2][MOTION_ACTIONS], s_motion_end[2][MOTION_ACTIONS];
static uint32_t s_motion_recovery[2][MOTION_ACTIONS];
static uint32_t s_motion_visual[2][MOTION_ACTIONS], s_motion_visual_start[2][MOTION_ACTIONS];
static uint8_t s_motion_build[MOTION_BYTES], s_motion_clip[MOTION_CLIP_BYTES];

static uint32_t motion_get(const uint8_t* b, uint32_t at) {
    return (uint32_t)b[at] | (uint32_t)b[at+1] << 8 |
           (uint32_t)b[at+2] << 16 | (uint32_t)b[at+3] << 24;
}
static void motion_put(uint8_t* b, uint32_t at, uint32_t value) {
    for (unsigned i = 0; i < 4; i++) b[at+i] = (uint8_t)(value >> (8*i));
}
#include "dbfb_pose.h"
static unsigned motion_words(unsigned op) {
    switch (op) {
    case 0: case 1: case 0x20: case 0x21: case 0x24: case 0x25: case 0x26:
    case 0x60: case 0x61: case 0x62: case 0x82: case 0x83: return 1;
    case 0x22: case 0x23: return 5;
    case 0x40: case 0x80: case 0x84: return 3;
    case 0x41: return 4;
    case 0x81: return 2;
    default: return 0;
    }
}
static int motion_selected(unsigned action) {
    return (action >= 0x64 && action <= 0x77) ||
           (action >= 0xA0 && action <= 0xA5) || action == 0x8C;
}
/* Both native special-command families: direct 78..7A/7E..80 and coordinated
 * 7B..7D/81..83. Only their positive ki cost is changed. Coordinated timelines,
 * poses, partner states, object lifetimes and collision parameters stay stock. */
static int motion_technique(unsigned action) {
    return action >= 0x78u && action <= 0x83u;
}
static int motion_primary(unsigned animation) {
    return (animation >= 0x78 && animation <= 0x8D) ||
           (animation >= 0xC8 && animation <= 0xCD);
}
/* True only when this side's private table is published AND this specific
 * action has a retimed clip installed. A failed rebuild therefore disables
 * every rule that depends on the retimed timeline. */
static int motion_clip_live(unsigned side, unsigned action) {
    if (side > 1 || action >= MOTION_ACTIONS || !motion_selected(action)) return 0;
    if (!(s_motion_attempted[side] & (1u << side)) || !s_motion_ready[side]) return 0;
    const uint32_t arena = s_motion_arena[side];
    if (!arena || psx_mod_read_word(arena) != MOTION_MAGIC ||
        psx_mod_read_word(arena+4u) != s_motion_hash[side] ||
        psx_mod_read_word(0x8006F794u+side*4u) != arena+16u ||
        psx_mod_read_word(0x8007EF3Cu+side*4u) != arena+712u) return 0;
    return !(s_motion_unretimed[side][action >> 5] & (1u << (action & 31)));
}
/* Damage may follow the faster clock only while the retimed clip is published.
 * Before the compiler ever ran, stock behaviour is preserved unchanged. */
static int motion_damage_scales(unsigned side, unsigned action) {
    if (side > 1 || action >= MOTION_ACTIONS || !motion_selected(action)) return 0;
    if (!(s_motion_attempted[side] & (1u << side))) return 0;
    return motion_clip_live(side, action);
}
/* Retimed static length in interpreter ticks, or 0 when the action was not
 * compiled. The cancel rule never guesses a duration when this is 0. */
static uint32_t motion_total_ticks(unsigned side, unsigned action) {
    if (side > 1 || action >= MOTION_ACTIONS) return 0;
    return s_motion_ticks[side][action];
}
/* Resolve the stored pointer (last operand of the current event) and remaining
 * duration against this exact private script. The animation clock supplies the
 * tail that opcode 0 waits for; it is used only with the exact private clip. */
static int motion_recovery_ready(unsigned side, unsigned action, uint32_t pointer,
                                 uint16_t remaining) {
    if (!motion_clip_live(side, action)) return 0;
    const uint32_t start = s_motion_start[side][action], end = s_motion_end[side][action];
    const uint32_t recovery = s_motion_recovery[side][action];
    if (!recovery || pointer < recovery || pointer < start || pointer >= end) return 0;
    uint32_t elapsed = 0;
    int matched = 0;
    for (uint32_t at = start; at < end;) {
        const uint32_t word = psx_mod_read_word(at);
        const unsigned words = motion_words((word >> 16) & 255u);
        if (!words || words * 4u > end-at) return 0;
        const uint32_t duration = word >> 24;
        if (pointer == at+(words-1u)*4u) {
            if (remaining > duration) return 0;
            elapsed += duration-remaining;
            matched = 1;
            break;
        }
        elapsed += duration;
        at += words*4u;
    }
    if (!matched) return 0;
    const uint32_t context = 0x800A8624u+side*0x20u;
    if (psx_mod_read_word(context) == s_motion_visual[side][action]) {
        const uint32_t visual_tick = psx_mod_read_word(context+4u);
        if (visual_tick <= s_motion_ticks[side][action]) {
            const uint32_t visual_elapsed = s_motion_visual_start[side][action]+visual_tick;
            if (visual_elapsed > elapsed) elapsed = visual_elapsed;
        }
    }
    return elapsed >= (motion_total_ticks(side, action)*3u+3u)/4u;
}
/* Keep each positive control checkpoint: duration 1 has interpreter semantics.
 * The animation uses the resulting knots, rather than a separate speed scale. */
static uint32_t motion_time(uint32_t tick, const MotionKnot* knots, unsigned count,
                            unsigned numerator, unsigned denominator) {
    for (unsigned i = 1; i < count; i++) {
        if (tick <= knots[i].old_tick) {
            const MotionKnot a = knots[i-1], b = knots[i];
            return a.new_tick + ((tick - a.old_tick) * (b.new_tick - a.new_tick) +
                   b.old_tick - a.old_tick - 1u) / (b.old_tick - a.old_tick);
        }
    }
    const MotionKnot last = knots[count-1];
    return last.new_tick + ((tick-last.old_tick)*numerator+denominator-1u)/denominator;
}

/* Read a bounded raw/Psdp clip from the original animation container. */
static uint32_t motion_decode(uint32_t source, uint32_t begin, uint32_t limit) {
    if ((source & 3u) || source < begin || source + 8u > limit) return 0;
    uint32_t cursor = source, size = 0;
    if (psx_mod_read_word(source) == 0x70647350u) {
        size = psx_mod_read_word(source+4u);
        if (size < 4 || size > MOTION_CLIP_BYTES || (size & 3u)) return 0;
        cursor += 8;
        uint32_t out = 0, flags = 0;
        while (out < size) {
            flags >>= 1;
            if (!(flags & 0x100u)) {
                if (cursor >= limit) return 0;
                flags = psx_mod_read_byte(cursor++) | 0xFF00u;
            }
            if (flags & 1u) {
                if (cursor >= limit) return 0;
                s_motion_clip[out++] = psx_mod_read_byte(cursor++);
            } else {
                if (cursor+2u > limit) return 0;
                const uint32_t token = psx_mod_read_byte(cursor) |
                                       (uint32_t)psx_mod_read_byte(cursor+1u) << 8;
                cursor += 2;
                const uint32_t distance = token >> 5, length = (token & 31u)+3u;
                if (!distance || out+length > size) return 0;
                for (uint32_t i = 0; i < length; i++, out++)
                    s_motion_clip[out] = out < distance ? 0 : s_motion_clip[out-distance];
            }
        }
    } else {
        const uint32_t header = psx_mod_read_word(source), groups = header >> 16;
        if ((header & 0xFFFFu) != 0x4Fu || !groups || groups > 4096u) return 0;
        cursor += 4;
        for (uint32_t g = 0; g < groups; g++) {
            if (cursor+8u > limit) return 0;
            const uint32_t words = psx_mod_read_half(cursor);
            if (words < 2 || words*4u > limit-cursor) return 0;
            cursor += words*4u;
            if (cursor-source > MOTION_CLIP_BYTES) return 0;
        }
        size = cursor-source;
        for (uint32_t i = 0; i < size; i += 4)
            motion_put(s_motion_clip, i, psx_mod_read_word(source+i));
    }
    return size;
}

/* Coalesce groups that land on the same tick. Packet order is retained even
 * for relative transforms; only the intermediate display sample is removed. */
static uint32_t motion_retime(uint32_t size, uint32_t destination,
                              const MotionKnot* knots, unsigned count,
                              unsigned numerator, unsigned denominator) {
    const uint32_t header = motion_get(s_motion_clip, 0), groups = header >> 16;
    if ((header & 0xFFFFu) != 0x4Fu || !groups || groups > 4096u) return 0;
    uint32_t input = 4, output = destination+4, total = 0, last_at = 0;
    uint32_t previous = 0, last_tick = UINT32_MAX;
    for (uint32_t g = 0; g < groups; g++) {
        if (input+8u > size) return 0;
        const uint32_t info = motion_get(s_motion_clip, input);
        const uint32_t words = info & 0xFFFFu, packets = info >> 16;
        const uint32_t tick = motion_get(s_motion_clip, input+4u);
        if (words < 2 || !packets || packets > words-2u ||
            words*4u > size-input || (g && tick <= previous)) return 0;
        previous = tick;
        const uint32_t mapped = motion_time(tick, knots, count, numerator, denominator);
        if (mapped != last_tick) {
            if (output+8u > MOTION_BYTES) return 0;
            last_at = output;
            motion_put(s_motion_build, output, 2u);
            motion_put(s_motion_build, output+4u, mapped);
            output += 8;
            last_tick = mapped;
            total++;
        }
        const uint32_t current = motion_get(s_motion_build, last_at);
        const uint32_t new_words = (current & 0xFFFFu)+words-2u;
        const uint32_t new_packets = (current >> 16)+packets;
        const uint32_t bytes = (words-2u)*4u;
        if (new_words > 0xFFFFu || new_packets > 0xFFFFu || bytes > MOTION_BYTES-output)
            return 0;
        motion_put(s_motion_build, last_at, new_words | new_packets << 16);
        memcpy(s_motion_build+output, s_motion_clip+input+8u, bytes);
        output += bytes;
        input += words*4u;
    }
    if (input != size) return 0;
    motion_put(s_motion_build, destination, 0x4Fu | total << 16);
    return output;
}

static uint32_t motion_source_hash(uint32_t scripts, uint32_t animations, unsigned slots) {
    uint32_t h = code_fnv(scripts, 4u*(MOTION_ACTIONS+1u));
    return h ^ code_fnv(animations, 4u*(slots+1u));
}

#include "dbfb_pose_settle.h"

/* Build a complete replacement in private memory, then publish two pointers.
 * Originals remain available at fixed addresses, allowing idempotent rebuilds
 * after a reload or savestate. No partial table is ever published. */
static int motion_build(unsigned side, uint32_t animations, uint32_t scripts,
                         unsigned slots, uint32_t arena, uint32_t hash) {
    const uint32_t script_stream = scripts+4u*(MOTION_ACTIONS+1u);
    const uint32_t new_scripts = arena+16u;
    const uint32_t new_stream = new_scripts+4u*(MOTION_ACTIONS+1u);
    const uint32_t animation_at = 16u+4u*(MOTION_ACTIONS+1u);
    const uint32_t new_animations = arena+animation_at;
    uint32_t output = animation_at+4u*(MOTION_ANIMS+1u);
    unsigned next_slot = slots, variants = 0, pose_samples = 0, techniques = 0;
    uint64_t roots = 0;
    /* Initialization clip supplies this fighter's actual roots; never assume
     * that the same numeric part denotes the same joint on another fighter. */
    const uint32_t initial_size = motion_decode(psx_mod_read_word(animations+4u), animations, scripts);
    if (initial_size) {
        PoseAngles initial[POSE_PARTS] = {{ {0,0,0}, 0 }};
        uint32_t at = 4;
        for (unsigned g = 0; g < motion_get(s_motion_clip, 0) >> 16; g++) {
            int only = 1;
            if (!pose_group(s_motion_clip, at, initial_size, initial, &roots, &only)) { roots = 0; break; }
            at += (motion_get(s_motion_clip, at) & 65535u)*4u;
        }
        /* Also anchor each actual root's immediate children. This leaves the
         * body's carrier chain untouched without assuming anatomical names. */
        const uint64_t actual_roots = roots;
        at = 4;
        for (unsigned g = 0; roots && g < motion_get(s_motion_clip, 0) >> 16; g++) {
            const uint32_t limit = at+(motion_get(s_motion_clip, at) & 65535u)*4u;
            for (uint32_t p = at+8u; p < limit;) {
                const uint32_t h = motion_get(s_motion_clip, p), id = h & 65535u;
                if (((h >> 16) & 15u) == 3u && h >> 24 >= 2u && id < POSE_PARTS) {
                    const unsigned parent = motion_get(s_motion_clip, p+4u) & 65535u;
                    if (parent < POSE_PARTS && (actual_roots & (UINT64_C(1) << parent)))
                        roots |= UINT64_C(1) << id;
                }
                p += (h >> 24)*4u;
            }
            at = limit;
        }
    }
    s_motion_attempted[side] |= 1u << side;
    s_motion_ready[side] = 0;
    memset(s_motion_ticks[side], 0, sizeof s_motion_ticks[side]);
    memset(s_motion_recovery[side], 0, sizeof s_motion_recovery[side]);
    memset(s_motion_unretimed[side], 0, sizeof s_motion_unretimed[side]);
    for (unsigned a = 0; a < MOTION_ACTIONS; a++)
        if (motion_selected(a))
            s_motion_unretimed[side][a >> 5] |= 1u << (a & 31);
    memset(s_motion_build, 0, output);
    motion_put(s_motion_build, 0, MOTION_MAGIC);
    motion_put(s_motion_build, 4, hash);
    motion_put(s_motion_build, 16, 0x4244u | MOTION_ACTIONS << 16);
    for (unsigned a = 0; a < MOTION_ACTIONS; a++) {
        const uint32_t offset = psx_mod_read_word(scripts+4u*(a+1u));
        if (offset == UINT32_MAX) {
            motion_put(s_motion_build, 20u+4u*a, UINT32_MAX);
            continue;
        }
        if (offset >= (0x8000u-4u*(MOTION_ACTIONS+1u))/4u) return 0;
        const uint32_t start = script_stream+offset*4u;
        motion_put(s_motion_build, 20u+4u*a, (start-new_stream)/4u);
        if (!motion_selected(a) && !motion_technique(a)) continue;
        uint32_t instructions[256], length = 0, cursor = start, total_ticks = 0;
        MotionKnot knots[257];
        unsigned knot_count = 1, primary = UINT32_MAX, primary_word = 0;
        uint32_t visual_start = 0, recovery_word = UINT32_MAX, recovery_tick = 0;
        knots[0].old_tick = knots[0].new_tick = 0;
        int ended = 0;
        while (length < 251u && cursor+4u <= scripts+0x8000u) {
            const uint32_t word = psx_mod_read_word(cursor);
            const unsigned op = (word >> 16) & 255u, words = motion_words(op);
            if (!words || cursor+words*4u > scripts+0x8000u) return 0;
            for (unsigned i = 0; i < words; i++)
                instructions[length+i] = psx_mod_read_word(cursor+4u*i);
            if (motion_selected(a) && op == 0x20u && motion_primary(word & 0xFFFFu)) {
                if (primary != UINT32_MAX) return 0;
                primary = word & 0xFFFFu;
                primary_word = length;
                visual_start = total_ticks;
            } else if (op == 0x20u && primary != UINT32_MAX) {
                return 0; /* selected scripts must contain a single visual phase */
            }
            if (op == 0x84u && (motion_technique(a) ||
                (a >= 0x72u && a <= 0x77u && primary != UINT32_MAX))) {
                /* Native spawn subtracts the signed high byte of operand 1
                 * (0x8004ED50/74 -> 0x8004F210). Keep damage/ki proportional
                 * to the 3/4 volley clock; preserve zero/negative sentinels. */
                const unsigned cost = instructions[length+1u] >> 24;
                if (cost && cost < 128u) {
                    unsigned adjusted = motion_technique(a) ? cost*4u/5u : cost*3u/4u;
                    if (!adjusted) adjusted = 1;
                    instructions[length+1u] = (instructions[length+1u] & 0xFFFFFFu) | adjusted << 24;
                }
            }
            if (primary != UINT32_MAX && (word >> 24)) {
                const uint32_t old_duration = word >> 24;
                /* Normals: 80% clock. Basic ki volleys: 75%. */
                const unsigned num = a >= 0x72u && a <= 0x77u ? 3u : 4u;
                const unsigned den = a >= 0x72u && a <= 0x77u ? 4u : 5u;
                uint32_t duration = old_duration*num/den;
                if (!duration) duration = 1;
                instructions[length] = (word & 0xFFFFFFu) | duration << 24;
                knots[knot_count].old_tick = knots[knot_count-1].old_tick+old_duration;
                knots[knot_count].new_tick = knots[knot_count-1].new_tick+duration;
                knot_count++;
            }
            total_ticks += instructions[length] >> 24;
            if (op == 0x82u) { recovery_word = length; recovery_tick = total_ticks; }
            /* A later attack registration invalidates an earlier clear. */
            if (op == 0x80u || op == 0x81u || op == 0x84u || op == 0x23u)
                recovery_word = UINT32_MAX;
            length += words;
            cursor += words*4u;
            if (word == 0) { ended = 1; break; }
        }
        if (!ended) return 0;
        if (motion_technique(a)) {
            if (length*4u > MOTION_BYTES-output) return 0;
            motion_put(s_motion_build, 20u+4u*a, (arena+output-new_stream)/4u);
            for (unsigned i = 0; i < length; i++) motion_put(s_motion_build, output+4u*i, instructions[i]);
            output += length*4u;
            techniques++;
            continue;
        }
        if (primary == UINT32_MAX) continue; /* missing/aliased move, e.g. boss */
        if (primary >= slots || next_slot >= MOTION_ANIMS) return 0;
        const uint32_t source = psx_mod_read_word(animations+4u*(primary+1u));
        const uint32_t size = motion_decode(source, animations, scripts);
        if (!size) return 0;
        const unsigned num = a >= 0x72u && a <= 0x77u ? 3u : 4u;
        const unsigned den = a >= 0x72u && a <= 0x77u ? 4u : 5u;
        uint32_t end = motion_retime(size, output, knots, knot_count, num, den);
        if (!end || end+4u*length > MOTION_BYTES) return 0;
        s_motion_visual[side][a] = arena+output;
        s_motion_visual_start[side][a] = visual_start;
        uint32_t group = output+4u, visual_end = 0;
        for (uint32_t g = 0; g < motion_get(s_motion_build, output) >> 16; g++) {
            visual_end = motion_get(s_motion_build, group+4u);
            group += (motion_get(s_motion_build, group) & 0xFFFFu)*4u;
        }
        if (visual_start+visual_end+1u > total_ticks) total_ticks = visual_start+visual_end+1u;
        if (recovery_word != UINT32_MAX) {
            uint32_t begin = (total_ticks*3u+3u)/4u;
            if (recovery_tick > begin) begin = recovery_tick;
            if (begin >= visual_start)
                end = pose_refine(output, end, begin-visual_start, roots, &pose_samples);
            if (end+4u*length > MOTION_BYTES) return 0;
        }
        motion_put(s_motion_build, animation_at+4u*(next_slot+1u), arena+output);
        instructions[primary_word] = (instructions[primary_word] & 0xFFFF0000u) | next_slot++;
        output = end;
        s_motion_start[side][a] = arena+output;
        s_motion_end[side][a] = arena+output+length*4u;
        if (recovery_word != UINT32_MAX)
            s_motion_recovery[side][a] = arena+output+recovery_word*4u;
        motion_put(s_motion_build, 20u+4u*a, (arena+output-new_stream)/4u);
        for (unsigned i = 0; i < length; i++) motion_put(s_motion_build, output+4u*i, instructions[i]);
        output += length*4u;
        s_motion_unretimed[side][a >> 5] &= ~(1u << (a & 31));
        s_motion_ticks[side][a] = total_ticks;
        variants++;
    }
    if (!variants) return 0;
    /* Native action6 owns this finite, same-duration upper-limb transition.
     * It never acquires attack timing/damage/cancel rules. No new hook needed. */
    output = motion_settle_build(animations, scripts, slots, arena, output, &next_slot, &pose_samples);
    motion_put(s_motion_build, animation_at, 0x826Bu | next_slot << 16);
    for (unsigned a = 0; a < slots; a++)
        motion_put(s_motion_build, animation_at+4u*(a+1u), psx_mod_read_word(animations+4u*(a+1u)));
    motion_put(s_motion_build, 8, output);
    motion_put(s_motion_build, 12, variants);
    for (uint32_t i = 0; i < output; i += 4u)
        psx_mod_write_word(arena+i, motion_get(s_motion_build, i));
    psx_mod_write_word(0x8006F794u+side*4u, new_scripts);
    psx_mod_write_word(0x8007EF3Cu+side*4u, new_animations);
    s_motion_ready[side] = 1;
    psx_mod_counter_add("dbfb.responsive.motion_variants", variants);
    if (techniques) psx_mod_counter_add("dbfb.responsive.technique_variants", techniques);
    if (pose_samples) psx_mod_counter_add("dbfb.responsive.pose_transitions", pose_samples);
    return 1;
}

static void motion_reset(void) {
    memset(s_motion_arena, 0, sizeof s_motion_arena);
    memset(s_motion_hash, 0, sizeof s_motion_hash);
    memset(s_motion_attempted, 0, sizeof s_motion_attempted);
    memset(s_motion_ready, 0, sizeof s_motion_ready);
    memset(s_motion_unretimed, 0, sizeof s_motion_unretimed);
    memset(s_motion_ticks, 0, sizeof s_motion_ticks);
    memset(s_motion_recovery, 0, sizeof s_motion_recovery);
}
static void motion_restore(void) {
    memset(s_motion_ready, 0, sizeof s_motion_ready);
    memset(s_motion_hash, 0, sizeof s_motion_hash);
    memset(s_motion_ticks, 0, sizeof s_motion_ticks);
}

static void motion_tick(void) {
    for (unsigned p = 0; p < 2; p++) {
        const uint32_t animations = p ? 0x80147800u : 0x800CF000u;
        const uint32_t scripts = p ? 0x80190000u : 0x80117800u;
        const uint32_t header = psx_mod_read_word(animations), slots = header >> 16;
        if (psx_mod_read_word(scripts) != (0x4244u | MOTION_ACTIONS << 16) ||
            (header & 0xFFFFu) != 0x826Bu || slots < 216u || slots > 219u) continue;
        if (code_fnv(0x8004E530u, 0xAE4u) != 0x6949A1DFu ||
            code_fnv(0x800420ECu, 0xC24u) != 0x0637584Du) continue;
        const uint32_t hash = motion_source_hash(scripts, animations, slots);
        uint32_t arena = s_motion_arena[p];
        const uint32_t current = psx_mod_read_word(0x8006F794u+p*4u);
        const uint32_t current_anim = psx_mod_read_word(0x8007EF3Cu+p*4u);
        if (current != scripts && (!arena || current != arena+16u)) continue;
        if (current_anim != animations && (!arena || current_anim != arena+712u)) continue;
        if (arena && hash == s_motion_hash[p] && psx_mod_read_word(arena) == MOTION_MAGIC &&
            psx_mod_read_word(arena+4u) == hash) {
            if (current == scripts) psx_mod_write_word(0x8006F794u+p*4u, arena+16u);
            if (current_anim == animations) psx_mod_write_word(0x8007EF3Cu+p*4u, arena+712u);
            continue;
        }
        if (!arena) {
            arena = psx_mod_alloc_guest_memory(MOTION_BYTES, 16u);
            if (!arena) continue;
            s_motion_arena[p] = arena;
        }
        if (motion_build(p, animations, scripts, slots, arena, hash)) s_motion_hash[p] = hash;
        else psx_mod_counter_add("dbfb.responsive.motion_rejected", 1);
    }
}
