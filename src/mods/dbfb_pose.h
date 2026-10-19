/* Native PS1 recovery transitions. Recipe authored for Final Bout, not imported
 * animation data. STEP40 0x80042398/0x800425A0 decode these same channels.
 * Only small joint rotations during recovery are eased. Root, geometry, scale,
 * translation, collision times and all original endpoint poses are preserved.
 * Relative corrections cancel at the next anchor, for ANY entering pose.
 */
#define POSE_PARTS 64u
#define POSE_BYTES 0x20000u
typedef struct PoseAngles { uint16_t angle[3]; unsigned known; } PoseAngles;
static uint8_t s_pose_output[POSE_BYTES];

static int pose_group(const uint8_t* data, uint32_t at, uint32_t end,
                      PoseAngles* state, uint64_t* roots, int* transforms_only) {
    if (at+8u > end) return 0;
    const uint32_t header = motion_get(data, at), words = header & 65535u;
    if (words < 2u || words*4u > end-at) return 0;
    const uint32_t limit = at+words*4u;
    uint32_t p = at+8u;
    for (unsigned n = 0; n < header >> 16; n++) {
        if (p+4u > limit) return 0;
        const uint32_t h = motion_get(data, p);
        const unsigned op = (h >> 16) & 15u, flags = (h >> 20) & 15u;
        const unsigned size = h >> 24, id = h & 65535u;
        if (!size || size*4u > limit-p) return 0;
        if (op != 1u && op != 5u) *transforms_only = 0;
        if (op == 3u && size >= 2u && id < POSE_PARTS &&
            !(motion_get(data, p+4u) & 65535u)) *roots |= UINT64_C(1) << id;
        if (op == 1u || op == 5u) {
            const unsigned channels = !!(flags & 2u)+!!(flags & 4u)+!!(flags & 8u);
            if (size != 1u+channels*(op == 1u ? 2u : 1u)) return 0;
            if ((flags & 2u) && id < POSE_PARTS) {
                PoseAngles* s = &state[id];
                if (!(flags & 1u) || s->known) {
                    for (unsigned axis = 0; axis < 3; axis++) {
                        int value;
                        if (op == 1u) {
                            const uint32_t v = motion_get(data, p+4u+(axis/2u)*4u);
                            value = (int16_t)(v >> ((axis & 1u)*16u));
                        } else {
                            const unsigned v = (motion_get(data, p+4u) >> (axis*10u)) & 1023u;
                            value = (int)(v ^ 512u)-512;
                        }
                        s->angle[axis] = (uint16_t)(value+((flags & 1u) ? s->angle[axis] : 0));
                    }
                    s->known = 1;
                }
            }
        }
        p += size*4u;
    }
    return p == limit;
}
static void pose_packet(uint8_t* buffer, uint32_t at, unsigned id, const uint16_t* angles) {
    motion_put(buffer, at, 0x03310000u | id); /* relative, angles only, 3 words */
    motion_put(buffer, at+4u, (uint32_t)angles[0] | (uint32_t)angles[1] << 16);
    motion_put(buffer, at+8u, angles[2]);
}
/* Read the net relative angular update of each part in a whole group. An
 * absolute angle or any structural/camera/control operation excludes it. */
static uint64_t pose_relative(const uint8_t* data, uint32_t at, uint32_t end,
                              PoseAngles* delta) {
    uint64_t roots = 0, relative = 0, absolute = 0;
    int only = 1;
    memset(delta, 0, sizeof(PoseAngles)*POSE_PARTS);
    for (unsigned id = 0; id < POSE_PARTS; id++) delta[id].known = 1;
    if (!pose_group(data, at, end, delta, &roots, &only) || !only) return 0;
    const uint32_t limit = at+(motion_get(data, at) & 65535u)*4u;
    for (uint32_t p = at+8u; p < limit;) {
        const uint32_t h = motion_get(data, p), id = h & 65535u;
        if ((h & 0x00200000u) && id < POSE_PARTS) {
            if (h & 0x00100000u) relative |= UINT64_C(1) << id;
            else absolute |= UINT64_C(1) << id;
        }
        p += (h >> 24)*4u;
    }
    return relative & ~absolute;
}
/* Dense PS1 clips already have a sample every tick. Shape ONE inner sample
 * between original recovery anchors, rather than inventing empty time slots.
 * +correction / -correction uses the native modulo-16-bit additive semantics.
 * Returns unchanged end on an unrecognised clip; no partial output escapes. */
static uint32_t pose_refine(uint32_t destination, uint32_t end, uint32_t recovery,
                            uint64_t roots, unsigned* samples) {
    if (!roots || end <= destination+4u || end > MOTION_BYTES) return end;
    const uint8_t* input = s_motion_build+destination;
    const uint32_t size = end-destination, groups = motion_get(input, 0) >> 16;
    uint32_t offsets[4096], at = 4u, middle = UINT32_MAX, exit = 0;
    PoseAngles first[POSE_PARTS], second[POSE_PARTS];
    uint16_t correction[3] = {0}, inverse[3] = {0};
    unsigned part = 0;
    if (groups > 4096u || groups < 3u) return end;
    for (unsigned g = 0; g < groups; g++) {
        int only = 1;
        uint64_t ignored_roots = 0;
        memset(first, 0, sizeof first);
        if (!pose_group(input, at, size, first, &ignored_roots, &only)) return end;
        offsets[g] = at;
        at += (motion_get(input, at) & 65535u)*4u;
    }
    if (at != size || size+24u > POSE_BYTES || size+24u > MOTION_BYTES-destination) return end;
    for (unsigned g = 1; g+1u < groups && middle == UINT32_MAX; g++) {
        const uint32_t left = motion_get(input, offsets[g-1u]+4u);
        const uint32_t mid = motion_get(input, offsets[g]+4u);
        const uint32_t right = motion_get(input, offsets[g+1u]+4u);
        if (left < recovery || mid <= left || right <= mid || right-left > 6u) continue;
        const unsigned gap = right-left, t = mid-left, weight = gap*gap-(gap-t)*(gap-t);
        const uint64_t candidates = pose_relative(input, offsets[g], size, first) &
            pose_relative(input, offsets[g+1u], size, second) & ~roots;
        for (unsigned id = 1; id < POSE_PARTS; id++) if (candidates & (UINT64_C(1) << id)) {
            int small = 1, changed = 0;
            for (unsigned axis = 0; axis < 3; axis++) {
                const int u = (int16_t)first[id].angle[axis], v = (int16_t)second[id].angle[axis];
                if (u+v < -256 || u+v > 256) small = 0;
                int c = (u+v)*(int)weight/(int)(gap*gap)-u;
                if (c < -32) c = -32;
                if (c > 32) c = 32;
                correction[axis] = (uint16_t)c; inverse[axis] = (uint16_t)-c;
                changed |= c != 0;
            }
            if (small && changed) { middle = g; exit = g+1u; part = id; break; }
        }
    }
    if (middle == UINT32_MAX) return end;
    motion_put(s_pose_output, 0, motion_get(input, 0));
    uint32_t output = 4u;
    for (unsigned g = 0; g < groups; g++) {
        const uint32_t h = motion_get(input, offsets[g]), bytes = (h & 65535u)*4u;
        const int modify = g == middle || g == exit;
        if ((h & 65535u) > 65532u || h >> 16 == 65535u) return end;
        motion_put(s_pose_output, output, h+(modify ? 0x00010003u : 0u));
        motion_put(s_pose_output, output+4u, motion_get(input, offsets[g]+4u)); output += 8u;
        if (modify) { pose_packet(s_pose_output, output, part, g == middle ? correction : inverse); output += 12u; }
        memcpy(s_pose_output+output, input+offsets[g]+8u, bytes-8u); output += bytes-8u;
    }
    memcpy(s_motion_build+destination, s_pose_output, output);
    (*samples)++;
    return destination+output;
}
