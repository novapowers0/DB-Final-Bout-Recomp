/* R4 investigation probe, NOT a general framing implementation.
 * Include after the psx_mod_read_* declarations. No registration, guest writes,
 * CPU edits, retained shot, counters or allocation. The caller owns the sample.
 *
 * Verified USA STEP40: 001adcdc2e129d3bd715c29b64e393fa8c2901a7ef39c2347874b321aae6b9dd.
 * tools/combat_camera.py checks these seams against the private disc/capture.
 *
 * General branch: 54EC4, mode == 1; context+0 can still suppress updates.
 * 46E08 -> 47408 -> 43CA8 -> 54444 -> 442A8 -> 4778C -> 44824
 * -> 47FE8 -> 48464 -> 486AC. 44824 calls native 24850.
 * Context+50/+70/+90/+B0 are current/previous/destination/transition delta,
 * six words each. Their first/second triples are the eye/target inputs, but
 * this is NOT enough to establish final screen-space model bounds or culling.
 * Context+8 selects internal shots even with mode == 1: never interpret that
 * global alone as permission to override cinematics.
 *
 * R4 offline disasm (tools/combat_camera.py verify/verify_exe):
 * - 0x80024850 receives context+0x50 and reads EIGHT words: eye +0x00/+04/+08,
 *   at +0x0C/+10/+14, plus +0x18 (negated into 0x8002413C) and +0x1C (gates
 *   0x800242B8/0x800240EC/0x80022990). It builds the Q12 view rotation from
 *   eye/at (sin/cos 0x80020100/0x800201CC, table 0x8003DDA4; MVMVA multiply
 *   0x80022DAC) plus translation R*(-eye) via 0x80022C4C, writing 0x8003BE78
 *   (scratch, read by 0x8002457C for scene objects) and 0x8003B920.
 * - Projection: RTPS 0x80020578 / RTPT 0x80021CD4; GTE RT/TR from the node via
 *   0x800227FC; 0x8002282C combines 0x8003BB48 x node into the L matrix.
 *   Constants at 0x8002399C..0x800239E8: H=0xEF9E, OFY=0x03E8, DQA=0x0140,
 *   DQB=0x0155, ZSF3=0x0100, OFX=0, BFC=0.
 * - Recorte: the STEP40 polygon renderer runs RTPT then NCLIP (e.g. 0x80040340
 *   and 0x80040368, executed) and conditionally skips the primitive (blez at
 *   0x80040388): native backface cull. The near guard is the GTE divide
 *   overflow (2*SZ3 <= H); no far clip; ordering via OTZ/AVSZ3-4.
 *
 * WRITER SAFETY — the PRE seam 0x80054F34 is NOT a write point: native
 * 0x800442A8 executes after it and rewrites context+0x50. Target words (3..5)
 * are copied from destination each frame at 0x800443E0-0x800443E8 and via the
 * dest+delta paths at 0x800446EC-0x80044748; eye words (0..2) step/snap at
 * 0x800444B8-0x800444C4 whenever the interpolation clock (+0x168/+0x16A)
 * permits. 0x8004778C then adds shake to +0x54/+0x60 at 0x80047974/0x80047990.
 * A host write there is erased (target) or state-dependent (eye), so it cannot
 * reach 0x80044824 deterministically. NO writer, NO counter and no
 * dbfb.responsive.camera_framing is implemented. Future safe candidates are
 * 0x80054F4C (before the additive shake) or 0x80054F88 (immediately before the
 * context load feeding 0x80044824); both require a newly registered
 * instruction site and overlay regeneration, decided outside this task.
 *
 * Proposed instruction observations (before original instruction executes):
 * 54F34: after destination generation, before interpolation. OBSERVE ONLY.
 * 54F4C: after interpolation, before subsequent shot effects/matrix update.
 * 5512C: common rendering boundary, ALSO reached on pause/update-lock paths;
 *         not proof that the camera updated, nor a paired post for every pre.
 *
 * Restore/disable/overlay change: discard the host sample. There is no guest
 * restoration for this probe. A future writer must not restore old context
 * arrays: native transitions use previous/destination/delta, and same-valued
 * native writes cannot be detected with value comparisons alone.
 */
#ifndef DBFB_CAMERA_H
#define DBFB_CAMERA_H

#include <stdint.h>

#define DBFB_CAMERA_PRE_SITE  0x80054F34u
#define DBFB_CAMERA_PRE_WORD  0x3C05800Bu
#define DBFB_CAMERA_POST_SITE 0x80054F4Cu
#define DBFB_CAMERA_POST_WORD 0x3C04800Bu
#define DBFB_CAMERA_END_SITE  0x8005512Cu
#define DBFB_CAMERA_END_WORD  0x3C048008u
#define DBFB_CAMERA_CONTEXT   0x800A9FA0u

enum dbfb_camera_result {
    DBFB_CAMERA_DISABLED = 0,
    DBFB_CAMERA_SAMPLED = 1,
    DBFB_CAMERA_BAD_SITE = 2,
    DBFB_CAMERA_BAD_CODE = 3,
    DBFB_CAMERA_PAUSED = 4,
    DBFB_CAMERA_BAD_CONTEXT = 5,
    DBFB_CAMERA_BAD_OBJECT = 6
};

struct dbfb_camera_snapshot {
    uint32_t valid, frame, site;
    uint32_t context, mode, published_mode, update_lock;
    uint32_t flags, shot_flags, events, direct_node, matrix_pointer;
    uint32_t object[2], action[2];
    int16_t hp[2];
    int32_t position[2][3];
    int32_t current[6], previous[6], destination[6], transition_delta[6];
    int32_t source[7];
    uint32_t transition_clock, transition_limit, shot_hold;
};

/* Small identity guards, not a substitute for the tool's full hash pin. */
static inline int dbfb_camera_code(void) {
    static const uint32_t anchors[][2] = {
        {0x80047F9Cu, 0x24429FA0u},
        {0x80047FA4u, 0xAC229D0Cu},
        {0x80054EB4u, 0x8CC69D0Cu},
        {0x80054EBCu, 0x8C63A194u},
        {0x80054EC4u, 0x14620048u},
        {0x80054EC8u, 0xACC30158u},
        {0x80054ED4u, 0x14400095u},
        {0x80054F08u, 0x0C011B82u},
        {0x80054F24u, 0x0C010F2Au},
        {DBFB_CAMERA_PRE_SITE, DBFB_CAMERA_PRE_WORD},
        {0x80054F44u, 0x0C0110AAu},
        {DBFB_CAMERA_POST_SITE, DBFB_CAMERA_POST_WORD},
        {0x80054F90u, 0x0C011209u},
        {0x8004482Cu, 0x0C009214u},
        {DBFB_CAMERA_END_SITE, DBFB_CAMERA_END_WORD},
        {0x8006A178u, 0x38420001u},
        {0x8006A180u, 0xAC22868Cu},
        {0x8006A2F8u, 0x8C63868Cu}
    };
    for (unsigned i = 0; i < sizeof anchors / sizeof anchors[0]; i++)
        if (psx_mod_read_word(anchors[i][0]) != anchors[i][1]) return 0;
    return 1;
}

static inline void dbfb_camera_reset(struct dbfb_camera_snapshot* sample) {
    if (sample) *sample = (struct dbfb_camera_snapshot){0};
}

/* Call synchronously on the emulation thread; gates come from the owning
 * plugin, including enabled/offline/netplay/resimulation and combat scope.
 * A successful sample is diagnostic data, NEVER an override eligibility flag.
 * No host pointer into guest memory survives a call or a save-state restore. */
static inline enum dbfb_camera_result dbfb_camera_capture(
    struct dbfb_camera_snapshot* sample, uint32_t site, uint32_t frame,
    int offline_enabled, int combat_scope) {
    dbfb_camera_reset(sample);
    if (!sample || !offline_enabled || !combat_scope) return DBFB_CAMERA_DISABLED;
    site = (site & 0x1FFFFFFFu) | 0x80000000u;
    if (site != DBFB_CAMERA_PRE_SITE && site != DBFB_CAMERA_POST_SITE &&
        site != DBFB_CAMERA_END_SITE) return DBFB_CAMERA_BAD_SITE;
    if (!dbfb_camera_code()) return DBFB_CAMERA_BAD_CODE;
    if (psx_mod_read_word(0x800A868Cu)) return DBFB_CAMERA_PAUSED;
    const uint32_t context = psx_mod_read_word(0x800A9D0Cu);
    if (context != DBFB_CAMERA_CONTEXT) return DBFB_CAMERA_BAD_CONTEXT;
    struct dbfb_camera_snapshot next = {0};
    next.frame = frame;
    next.site = site;
    next.context = context;
    next.mode = psx_mod_read_word(0x800AA194u);
    next.published_mode = psx_mod_read_word(context + 0x158u);
    next.update_lock = psx_mod_read_word(context);
    next.flags = psx_mod_read_word(context + 4u);
    next.shot_flags = psx_mod_read_word(context + 8u);
    next.events = psx_mod_read_word(context + 12u);
    next.direct_node = psx_mod_read_word(0x800A8680u);
    next.matrix_pointer = psx_mod_read_word(0x800A8694u);
    next.transition_clock = psx_mod_read_half(context + 0x168u);
    next.transition_limit = psx_mod_read_half(context + 0x16Au);
    next.shot_hold = psx_mod_read_word(context + 0x184u);
    for (unsigned i = 0; i < 6; i++) {
        next.current[i] = (int32_t)psx_mod_read_word(context + 0x50u + i*4u);
        next.previous[i] = (int32_t)psx_mod_read_word(context + 0x70u + i*4u);
        next.destination[i] = (int32_t)psx_mod_read_word(context + 0x90u + i*4u);
        next.transition_delta[i] = (int32_t)psx_mod_read_word(context + 0xB0u + i*4u);
    }
    for (unsigned i = 0; i < 7; i++)
        next.source[i] = (int32_t)psx_mod_read_word(0x800A8664u + i*4u);
    for (unsigned side = 0; side < 2; side++) {
        const uint32_t control = 0x80072800u + side*0x7Cu;
        const uint32_t object = psx_mod_read_word(0x800A86A4u + side*4u);
        if (object < 0x80000000u || object > 0x801FFFDCu || (object & 3u))
            return DBFB_CAMERA_BAD_OBJECT;
        next.object[side] = object;
        next.action[side] = psx_mod_read_word(control + 8u);
        next.hp[side] = (int16_t)psx_mod_read_half(control + 0x40u);
        for (unsigned axis = 0; axis < 3; axis++)
            next.position[side][axis] = (int32_t)psx_mod_read_word(object + 0x18u + axis*4u);
    }
    next.valid = 1;
    *sample = next;
    return DBFB_CAMERA_SAMPLED;
}

#endif /* DBFB_CAMERA_H */
