/* R3 native-owned upper-limb settle, archive record0 only.
 * Native action6: slot2 (duration1) -> slot105 -> wait for native end.
 * 105 is already the five-sample 2->near1 return. No extra action/attack time.
 * New smoothstep angular trajectory for verified upper arm8 / forearm9 only.
 * Corrections are RELATIVE and telescope to zero at sample5 for ANY entering
 * pose, including wrap. All source packets, root/carrier transforms and the
 * final op9/flag0 survive byte-for-byte and in order. No host playback clock.
 * Native context+8 is the owner: pause/hit-stop stop its normal playback;
 * interrupts replace it normally; save/load preserves its exact group pointer.
 * Included by motion.h; only the existing offline standard poll publishes it.
 */
#define SETTLE_INPUT_BYTES 792u
#define SETTLE_OUTPUT_BYTES (SETTLE_INPUT_BYTES+120u)
static uint32_t settle_fnv(const uint8_t* data, uint32_t size) {
    uint32_t hash = 2166136261u;
    for (uint32_t i = 0; i < size; ++i) { hash ^= data[i]; hash *= 16777619u; }
    return hash;
}
/* Fully validated before touching output. Header/payload bytes are LE. */
static uint32_t settle_curve(const uint8_t* source, uint32_t size,
                              uint8_t* destination, uint32_t capacity) {
    if (size != SETTLE_INPUT_BYTES || capacity < SETTLE_OUTPUT_BYTES ||
        settle_fnv(source, size) != 0x34BD7AC0u || motion_get(source, 0) != 0x0005004Fu) return 0;
    uint32_t offsets[5], at = 4;
    int32_t sum[2][3] = {{0}}, cumulative[5][2][3];
    for (unsigned g = 0; g < 5; ++g) {
        if (at+8u > size) return 0;
        const uint32_t info = motion_get(source, at), words = info & 65535u;
        if (words < 2 || words*4u > size-at || motion_get(source, at+4u) != g+1u) return 0;
        const uint32_t end = at+words*4u;
        offsets[g] = at;
        uint32_t p = at+8u;
        unsigned seen = 0;
        for (unsigned n = 0; n < info >> 16; ++n) {
            if (p+4u > end) return 0;
            const uint32_t h = motion_get(source, p), part = h & 65535u, length = h >> 24;
            const unsigned op = (h >> 16) & 15u, flags = (h >> 20) & 15u;
            if (!length || length*4u > end-p) return 0;
            if (op == 9u) {
                if (h != 0x01090000u || g != 4u || n+1u != info >> 16) return 0;
            } else if (op != 1u && op != 5u) return 0;
            if (part == 8u || part == 9u) {
                const unsigned joint = part-8u;
                if (op != 5u || flags != 3u || length != 2u || (seen & (1u << joint))) return 0;
                seen |= 1u << joint;
                const uint32_t packed = motion_get(source, p+4u);
                for (unsigned axis = 0; axis < 3; ++axis) {
                    const unsigned v = (packed >> (10u*axis)) & 1023u;
                    sum[joint][axis] += (int32_t)(v ^ 512u)-512;
                }
            }
            p += length*4u;
        }
        if (p != end || seen != 3u) return 0;
        memcpy(cumulative[g], sum, sizeof sum);
        at = end;
    }
    if (at != size) return 0;
    for (unsigned joint = 0; joint < 2; ++joint)
        for (unsigned axis = 0; axis < 3; ++axis)
            if (sum[joint][axis] < -1024 || sum[joint][axis] > 1024) return 0;
    motion_put(destination, 0, motion_get(source, 0));
    uint32_t output = 4;
    int32_t previous[2][3] = {{0}};
    for (unsigned g = 0; g < 5; ++g) {
        const uint32_t info = motion_get(source, offsets[g]);
        const uint32_t bytes = (info & 65535u)*4u;
        const int32_t t = (int32_t)g+1, weight = t*t*(15-2*t);
        motion_put(destination, output, info+0x00020006u);
        motion_put(destination, output+4u, (uint32_t)t);
        output += 8;
        for (unsigned joint = 0; joint < 2; ++joint) {
            uint16_t delta[3];
            for (unsigned axis = 0; axis < 3; ++axis) {
                const int32_t c = sum[joint][axis]*weight/125-cumulative[g][joint][axis];
                delta[axis] = (uint16_t)(c-previous[joint][axis]);
                previous[joint][axis] = c;
            }
            pose_packet(destination, output, joint+8u, delta);
            output += 12;
        }
        memcpy(destination+output, source+offsets[g]+8u, bytes-8u);
        output += bytes-8u;
    }
    return output;
}

/* Returns the old end on unsupported data; originals remain referenced.
 * FNV identities pin the proven model/parts and both absolute pose setups.
 * Only action6 is cloned, so other users of slot105 stay original. */
static uint32_t motion_settle_build(uint32_t animations, uint32_t scripts,
        unsigned slots, uint32_t arena, uint32_t output, unsigned* next_slot,
        unsigned* samples) {
    if (slots != 218u || *next_slot >= MOTION_ANIMS || output > MOTION_BYTES-924u) return output;
    const uint32_t stream = scripts+4u*(MOTION_ACTIONS+1u);
    const uint32_t offset = psx_mod_read_word(scripts+4u*7u);
    if (offset >= 0x2000u) return output;
    const uint32_t action = stream+offset*4u;
    if (psx_mod_read_word(action) != 0x01200002u ||
        psx_mod_read_word(action+4u) != 0x00200069u || psx_mod_read_word(action+8u)) return output;
    const unsigned slot[3] = {0, 1, 2};
    const uint32_t hashes[3] = {0x0316328Bu, 0x8824B1AEu, 0xB2F6C6BEu};
    const uint32_t sizes[3] = {1092u, 616u, 616u};
    for (unsigned i = 0; i < 3; ++i) {
        const uint32_t size = motion_decode(psx_mod_read_word(animations+4u*(slot[i]+1u)), animations, scripts);
        if (size != sizes[i] || settle_fnv(s_motion_clip, size) != hashes[i]) return output;
    }
    const uint32_t size = motion_decode(psx_mod_read_word(animations+4u*106u), animations, scripts);
    const uint32_t length = settle_curve(s_motion_clip, size, s_motion_build+output, MOTION_BYTES-output);
    if (!length) return output;
    const uint32_t new_stream = arena+16u+4u*(MOTION_ACTIONS+1u);
    const uint32_t new_action = output+length;
    motion_put(s_motion_build, 20u+6u*4u, (arena+new_action-new_stream)/4u);
    motion_put(s_motion_build, 712u+4u*(*next_slot+1u), arena+output);
    motion_put(s_motion_build, new_action, 0x01200002u);
    motion_put(s_motion_build, new_action+4u, 0x00200000u | (*next_slot)++);
    motion_put(s_motion_build, new_action+8u, 0);
    (*samples)++;
    return new_action+12u;
}
