/* General-camera framing, applied at the native delivery point.
 * STEP40 80054F80..94: jal 8004477C, then lui/lw a0 = [0x800A9D0C],
 * jal 80044824 with a0+0x50 in the delay slot. Writing context+0x50 there is
 * read by the native matrix builder 80024850 in the SAME frame.
 * 80024850 consumes eye = +0x50/+54/+58 and target = +0x5C/+60/+64 (8 words).
 * This scales ONLY the native eye->target offset (zoom out), never invents
 * geometry, never touches the target, the update lock, shot flags or the
 * transition delta. Root cause of the earlier rejected seam (80054F34):
 * 800442A8/8004778C rewrite +0x50 after that point, so a write there is lost.
 * Opt-out for A/B comparison: DBFB_CAMERA_FRAMING=0. Default on.
 */
#ifndef DBFB_CAMERA_FRAME_H
#define DBFB_CAMERA_FRAME_H

#include <stdint.h>
#include <stdlib.h>
#include "dbfb_camera.h"

#define DBFB_CAMERA_FRAME_SITE 0x80054F88u
#define DBFB_CAMERA_FRAME_WORD 0x3C04800Bu /* lui a0,0x800b */
#define DBFB_CAMERA_FRAME_NUM 17
#define DBFB_CAMERA_FRAME_DEN 16
#define DBFB_CAMERA_FRAME_LIMIT 0x01000000

/* Pure: 1 when the native offset was scaled, 0 when any coordinate is outside
 * the accepted bound (no partial write is performed). */
static inline int dbfb_camera_framing(int32_t eye[3], const int32_t target[3]) {
    for (unsigned i = 0; i < 3u; i++) {
        if (eye[i] < -DBFB_CAMERA_FRAME_LIMIT || eye[i] > DBFB_CAMERA_FRAME_LIMIT ||
            target[i] < -DBFB_CAMERA_FRAME_LIMIT || target[i] > DBFB_CAMERA_FRAME_LIMIT)
            return 0;
        const int32_t delta = target[i]-eye[i];
        if (delta < -DBFB_CAMERA_FRAME_LIMIT || delta > DBFB_CAMERA_FRAME_LIMIT) return 0;
    }
    for (unsigned i = 0; i < 3u; i++) {
        const int64_t delta = (int64_t)(target[i]-eye[i])*DBFB_CAMERA_FRAME_NUM;
        eye[i] = target[i]-(int32_t)(delta/DBFB_CAMERA_FRAME_DEN);
    }
    return 1;
}

static int s_camera_framing_off = -1;

static int camera_framing_enabled(void) {
    if (s_camera_framing_off < 0) {
        const char* value = getenv("DBFB_CAMERA_FRAMING");
        s_camera_framing_off = value && value[0] == '0' && value[1] == '\0';
    }
    return !s_camera_framing_off;
}

/* Native delivery only. Every gate below rejects before any guest write:
 * disabled, out of scope, pause, KO, non-general mode, another context, an
 * update lock, or an in-flight camera transition (any of the six +0xB0 words).
 * The six-word transition delta is the same signal the KO camera path uses. */
static void camera_frame_step(struct CPUState* cpu, uint32_t address) {
    if (!cpu || (address & 0x1FFFFFFFu) != (DBFB_CAMERA_FRAME_SITE & 0x1FFFFFFFu)) return;
    if (!camera_framing_enabled() || !offline_started() || !standard_code() ||
        !s_input_scope.combat || s_menu_suspended ||
        psx_mod_read_word(DBFB_CAMERA_FRAME_SITE) != DBFB_CAMERA_FRAME_WORD) return;
    if (psx_mod_read_word(0x800A868Cu)) return;          /* paused */
    if (psx_mod_read_word(0x800AA194u) != 1u) return;    /* general branch only */
    const uint32_t context = psx_mod_read_word(0x800A9D0Cu);
    if (context != DBFB_CAMERA_CONTEXT) return;
    if (psx_mod_read_word(context) != 0u) return;        /* native update lock */
    if (s_ko_frames) return;                             /* KO shot owns +0x50 */
    for (unsigned i = 0; i < 6u; i++)
        if (psx_mod_read_word(context + 0xB0u + i*4u) != 0u) return;
    int32_t eye[3], target[3];
    for (unsigned i = 0; i < 3u; i++) {
        eye[i] = (int32_t)psx_mod_read_word(context + 0x50u + i*4u);
        target[i] = (int32_t)psx_mod_read_word(context + 0x5Cu + i*4u);
    }
    if (!dbfb_camera_framing(eye, target)) return;
    for (unsigned i = 0; i < 3u; i++)
        psx_mod_write_word(context + 0x50u + i*4u, (uint32_t)eye[i]);
    psx_mod_counter_add("dbfb.responsive.camera_framing", 1);
}

#endif /* DBFB_CAMERA_FRAME_H */
