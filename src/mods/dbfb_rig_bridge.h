/* Standalone PS1 multipart pose bridge. No guest writes, hooks or retail data.
 * Caller supplies DECODED local poses and a geometry-verified part mask.
 * This is not root motion, a skeleton mapper, or a complete full-body clip.
 * Absolute op1 angles+translation are consumed by STEP40 80042398..8004252C.
 * Scale/hierarchy/geometry stay with the existing initialized native context.
 * Integration proposal: construct in a PRIVATE arena after decoding snapshots;
 * append a fresh 0x826B slot and publish only after full validation. Root and
 * protected carriers must still follow the native destination trajectory.
 * Do not replace an entire action with this partial clip, prepend six ticks to
 * attack scripts, or feed it to pose_refine (that expects relative packets).
 * A host owner must cancel/discard on pause/restore/reload/KO/online, synchronize
 * script/pose clocks, and hand back to the destination without double-applying
 * its relative deltas. No such owner or state machine is implemented here.
 */
#ifndef DBFB_RIG_BRIDGE_H
#define DBFB_RIG_BRIDGE_H
#include <stddef.h>
#include <stdint.h>

typedef struct DbfbBridgePose {
    int16_t angle[3], translation[3];
    uint16_t scale[3];
    unsigned known; /* bits 1/2/4: angle/translation/scale */
} DbfbBridgePose;

static inline void dbfb_bridge_put(uint8_t *p, uint32_t v) {
    for (unsigned i = 0; i < 4; ++i) p[i] = (uint8_t)(v >> (i*8));
}
static inline int32_t dbfb_bridge_arc(int32_t a, int32_t b) {
    /* RotMatrix consumes a 4096-unit turn. Not a 65536-unit turn.
     * Exactly half a turn deterministically uses the negative arc. */
    return (int32_t)((uint32_t)(b-a+2048) & 4095u)-2048;
}
static inline size_t dbfb_bridge_size(uint64_t mask, unsigned ticks) {
    unsigned count = 0;
    if (ticks < 2 || ticks > 32 || !mask) return 0;
    for (unsigned i = 0; i < 64; ++i) count += (unsigned)((mask >> i) & 1u);
    return 8u+(ticks+1u)*(8u+count*20u); /* includes native end packet */
}
/* Returns zero WITHOUT changing output on invalid inputs. Input/output must not
 * overlap. Mask excludes root AND its immediate carrier children; this policy
 * is verified by the disc-side tool, never guessed by this pure emitter.
 * All selected endpoints must have the same scale; no scale is emitted. */
static inline size_t dbfb_bridge_build(uint8_t *out, size_t capacity,
        const DbfbBridgePose from[64], const DbfbBridgePose to[64],
        uint64_t mask, uint64_t protected_parts, unsigned ticks) {
    const size_t size = dbfb_bridge_size(mask, ticks);
    unsigned count = 0;
    if (!out || !from || !to || !size || capacity < size ||
        (mask & protected_parts) || (mask & 1u) || !protected_parts) return 0;
    for (unsigned id = 0; id < 64; ++id) if ((mask >> id) & 1u) {
        if ((from[id].known & 7u) != 7u || (to[id].known & 7u) != 7u) return 0;
        for (unsigned axis = 0; axis < 3; ++axis)
            if (from[id].scale[axis] != to[id].scale[axis]) return 0;
        ++count;
    }
    dbfb_bridge_put(out, 0x4Fu | (ticks+1u) << 16);
    size_t at = 4;
    const int32_t denominator = (int32_t)(ticks*ticks*ticks);
    for (unsigned tick = 0; tick <= ticks; ++tick) {
        const int32_t weight = (int32_t)(tick*tick*(3u*ticks-2u*tick));
        const unsigned final = tick == ticks;
        dbfb_bridge_put(out+at, (2u+5u*count+final) | (count+final) << 16);
        dbfb_bridge_put(out+at+4, tick);
        at += 8;
        for (unsigned id = 0; id < 64; ++id) if ((mask >> id) & 1u) {
            int16_t a[3], t[3];
            for (unsigned axis = 0; axis < 3; ++axis) {
                const int32_t start = from[id].angle[axis];
                const int32_t arc = dbfb_bridge_arc(start, to[id].angle[axis]);
                a[axis] = tick == ticks ? to[id].angle[axis] :
                    (int16_t)(start+arc*weight/denominator);
                const int32_t v = from[id].translation[axis];
                const int32_t delta = (int32_t)to[id].translation[axis]-v;
                t[axis] = (int16_t)(v+delta*weight/denominator);
            }
            dbfb_bridge_put(out+at, 0x05A10000u | id);
            dbfb_bridge_put(out+at+4, (uint16_t)a[0] | (uint32_t)(uint16_t)a[1] << 16);
            dbfb_bridge_put(out+at+8, (uint16_t)a[2]);
            dbfb_bridge_put(out+at+12, (uint16_t)t[0] | (uint32_t)(uint16_t)t[1] << 16);
            dbfb_bridge_put(out+at+16, (uint16_t)t[2]);
            at += 20;
        }
        /* 80042240 does not stop at the declared group count. op9/flag0
         * returns NULL, clearing context+8; without it playback reads past end. */
        if (final) { dbfb_bridge_put(out+at, 0x01090000u); at += 4; }
    }
    return at;
}
#endif
