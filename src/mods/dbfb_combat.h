/* Final Bout combat extensions, included only by the standard plugin.
 *
 * Every field and seam below was read from the retail STEP40 overlay and is
 * re-checked through standard_code() before a write. Host-only state (meters,
 * timers) never touches the guest. The modules are:
 *
 * - defence: the native guard test (defender action 0x21/0x22/0x23 plus the
 *   attacker's +0x2900 mask) is reproduced before the engine applies its own
 *   half/quarter/zero reduction. A guard meter breaks on sustained pressure;
 *   a just-guard (observed guard entry) takes a quarter instead.
 * - impact: fighter script/pose calls are filtered for a few VBlanks and the
 *   defender is displaced a small, bounded distance along the hit vector.
 * - camera: the verified camera tween source at 0x800A8664 is shaken only in
 *   direct mode (0x800A8680 == 0), abandoning immediately if the game writes.
 * - attack: late recovery after the final attack clear, with damage-confirmed
 *   cancels for the exact published private script and its visual tail.
 * - AI: side 2 receives a real command through the game's own command slot
 *   before the native gate, so costs, busy states and handlers still apply.
 *   Only a native CPU opponent is assisted; its defensive choices win.
 */
#define CONTROL_BASE 0x80072800u
#define CONTROL_STRIDE 0x7Cu
#define SCRIPT_BASE 0x800728F8u
#define SCRIPT_STRIDE 0x30u
#define OBJECT_PTR_BASE 0x800A86A4u
#define CAMERA_SOURCE 0x800A8664u
#define CAMERA_DIRECT 0x800A8680u
#define AI_SITE 0x80054A60u
#define AI_ORIGINAL 0x84242856u /* lh a0,+0x2856(at) */
#define AI_STATE_BASE 0x80072960u
#define AI_STATE_STRIDE 0x24u
#define GUARD_BREAK_VBLANKS 30u
#define JUST_GUARD_VBLANKS 6u
#define COMBO_WINDOW 90u

static uint16_t s_guard_meter[2], s_guard_broken[2];
static uint32_t s_guard_entry[2];
static uint8_t s_prev_action[2] = {0xFFu, 0xFFu};
static uint32_t s_combo_hits[2], s_combo_frame[2];
static uint32_t s_hitstop;
static int s_hitstop_active;
static uint32_t s_confirm_action[2], s_confirm_pointer[2], s_last_pointer[2];
static uint32_t s_shake_frames, s_shake_total, s_shake_amp;
static int32_t s_shake_base[2], s_shake_last[2];
static int s_shake_live;
static unsigned s_ko_frames, s_ko_live;
static int32_t s_ko_camera[6], s_ko_last[6];
static uint32_t s_push_cool[2];
static uint32_t s_ai_cooldown, s_ai_step;
static int16_t s_round_hp[2] = {-1, -1};

static uint32_t combat_control(unsigned side) {
    return CONTROL_BASE + (uint32_t)side * CONTROL_STRIDE;
}
static uint32_t combat_script(unsigned side) {
    return SCRIPT_BASE + (uint32_t)side * SCRIPT_STRIDE;
}
static uint32_t combat_isqrt(uint32_t value) {
    uint32_t root = 0, bit = 1u << 30;
    while (bit > value) bit >>= 2;
    while (bit) {
        if (value >= root + bit) { value -= root + bit; root = (root >> 1) + bit; }
        else root >>= 1;
        bit >>= 2;
    }
    return root;
}
static int16_t combat_signed_half(uint32_t address) {
    return (int16_t)psx_mod_read_half(address);
}
static void combat_reset(void) {
    projectile_reset();
    locomotion_reset();
    memset(s_guard_meter, 0, sizeof s_guard_meter);
    memset(s_guard_broken, 0, sizeof s_guard_broken);
    s_guard_entry[0] = s_guard_entry[1] = UINT32_MAX;
    s_prev_action[0] = s_prev_action[1] = 0xFFu;
    s_combo_hits[0] = s_combo_hits[1] = 0;
    s_combo_frame[0] = s_combo_frame[1] = UINT32_MAX;
    s_hitstop = 0;
    s_hitstop_active = 0;
    s_confirm_action[0] = s_confirm_action[1] = UINT32_MAX;
    memset(s_confirm_pointer, 0, sizeof s_confirm_pointer);
    memset(s_last_pointer, 0, sizeof s_last_pointer);
    s_shake_frames = s_shake_total = s_shake_amp = 0;
    s_shake_live = 0;
    s_ko_frames = s_ko_live = 0;
    s_push_cool[0] = s_push_cool[1] = 0;
    s_ai_cooldown = s_ai_step = 0;
    s_round_hp[0] = s_round_hp[1] = -1;
}
/* A damaging action is any bounded action of a living fighter; the retimed
 * timeline is a separate condition used only by the damage/cancel rules. */
static int combat_attacker_ready(unsigned side, unsigned action) {
    const uint32_t c = combat_control(side);
    return action < MOTION_ACTIONS && combat_signed_half(c + 0x40u) > 0 &&
           combat_signed_half(c + 0x42u) >= 0;
}
/* Exactly the engine's own block predicate: the defender must be in one of the
 * three guard actions and the attacker's +0x2900 word must carry that action's
 * mask. Returns -1 when the hit is not blocked, otherwise the native divisor
 * (0 means the stock body zeroes the damage). */
static int combat_guard_divisor(unsigned defender_action, int32_t params) {
    if (defender_action != 0x21u && defender_action != 0x22u &&
        defender_action != 0x23u) return -1;
    const uint32_t mask = defender_action == 0x22u ? 0x00400000u : 0x05000000u;
    if (((uint32_t)params & mask) == 0) return -1;
    if (params < 0) return 4;
    return (params & 0x40000000) ? 2 : 0;
}
static void combat_ki_reward(unsigned side, unsigned amount) {
    const uint32_t c = combat_control(side);
    const int16_t ki = combat_signed_half(c + 0x42u);
    if (ki < 0 || (uint16_t)ki >= 0xC4u) return;
    uint16_t next = (uint16_t)(ki + amount);
    if (next > 0xC4u) next = 0xC4u;
    psx_mod_write_half(c + 0x42u, next);
}
static void combat_shake(unsigned amplitude, unsigned frames) {
    if (s_shake_live && s_shake_frames >= frames) return;
    s_shake_amp = amplitude;
    s_shake_total = frames;
    s_shake_frames = frames;
}
static void combat_hitstop(unsigned frames) {
    if (s_hitstop < frames) s_hitstop = frames;
    s_hitstop_active = 1;
}
/* STEP40 counts event duration DOWN. Editing that countdown cannot freeze the
 * visual stream and can skip/duplicate events. Consume the two void/incomplete
 * calls instead, leaving pointers, clocks and relative pose packets untouched.
 * Only the two fighter contexts are filtered; UI/effects keep updating. */
static int combat_freeze_ready(void) {
    return offline_started() && standard_code() && s_input_scope.combat &&
           s_hitstop_active && !s_menu_suspended &&
           psx_mod_read_word(0x8004E530u) == 0x27BDFFC8u &&
           psx_mod_read_word(0x8004EE84u) == 0x2694FFFFu &&
           psx_mod_read_word(0x80042240u) == 0x27BDFFE0u &&
           psx_mod_read_word(0x80042278u) == 0xAE020004u;
}
static int combat_script_filter(struct CPUState* cpu, uint32_t address) {
    if (!cpu || (address & 0x1FFFFFFFu) != 0x4E530u ||
        cpu->gpr[4] > 1u || !combat_freeze_ready()) return 0;
    psx_mod_counter_add("dbfb.responsive.hitstop_script", 1);
    return 1;
}
static int combat_animation_filter(struct CPUState* cpu, uint32_t address) {
    if (!cpu || (address & 0x1FFFFFFFu) != 0x42240u) return 0;
    const uint32_t context = cpu->gpr[4] & 0x1FFFFFFFu;
    if ((context != 0xA8624u && context != 0xA8644u) || !combat_freeze_ready()) return 0;
    cpu->gpr[2] = 0; /* native return: animation has not completed */
    psx_mod_counter_add("dbfb.responsive.hitstop_pose", 1);
    return 1;
}
static void combat_position(uint32_t control, uint32_t object, int32_t dx, int32_t dz) {
    const uint32_t offsets[4] = {0x1Cu, 0x24u, 0x2Cu, 0x34u};
    const int32_t delta[4] = {dx, dz, dx, dz};
    for (unsigned i = 0; i < 4; i++) {
        int64_t value = (int64_t)(int32_t)psx_mod_read_word(control + offsets[i]) + delta[i];
        if (value > 7000) value = 7000;
        if (value < -7000) value = -7000;
        psx_mod_write_word(control + offsets[i], (uint32_t)value);
    }
    if (object >= 0x80000000u && object <= 0x801FFFDCu && !(object & 3u)) {
        int64_t x = (int64_t)(int32_t)psx_mod_read_word(object + 0x18u) + dx;
        int64_t z = (int64_t)(int32_t)psx_mod_read_word(object + 0x20u) + dz;
        if (x > 7000) x = 7000;
        if (x < -7000) x = -7000;
        if (z > 7000) z = 7000;
        if (z < -7000) z = -7000;
        psx_mod_write_word(object + 0x18u, (uint32_t)x);
        psx_mod_write_word(object + 0x20u, (uint32_t)z);
    }
}
static void combat_push(unsigned attacker, unsigned defender, int amount) {
    if (s_push_cool[defender]) return;
    const uint32_t ac = combat_control(attacker), dc = combat_control(defender);
    const int32_t ax = (int32_t)psx_mod_read_word(ac + 0x2Cu);
    const int32_t az = (int32_t)psx_mod_read_word(ac + 0x34u);
    const int32_t bx = (int32_t)psx_mod_read_word(dc + 0x2Cu);
    const int32_t bz = (int32_t)psx_mod_read_word(dc + 0x34u);
    if (ax < -7000 || ax > 7000 || az < -7000 || az > 7000 ||
        bx < -7000 || bx > 7000 || bz < -7000 || bz > 7000) return;
    const int32_t vx = bx-ax, vz = bz-az;
    const uint32_t distance = combat_isqrt((uint32_t)((int64_t)vx * vx + (int64_t)vz * vz));
    if (!distance) return;
    const int32_t dx = (int32_t)((int64_t)vx * amount / (int32_t)distance);
    const int32_t dz = (int32_t)((int64_t)vz * amount / (int32_t)distance);
    if (!dx && !dz) return;
    const uint32_t object = psx_mod_read_word(OBJECT_PTR_BASE + defender * 4u);
    combat_position(dc, object, dx, dz);
    s_push_cool[defender] = 4;
    psx_mod_counter_add("dbfb.responsive.pushback", 1);
}
static void combat_shake_tick(void) {
    if (!s_shake_frames) return;
    if (psx_mod_read_word(CAMERA_DIRECT) != 0) {
        s_shake_frames = 0;
        s_shake_live = 0;
        return;
    }
    if (!s_shake_live) {
        for (unsigned i = 0; i < 2; i++) {
            s_shake_base[i] = (int32_t)psx_mod_read_word(CAMERA_SOURCE + i * 4u);
            s_shake_last[i] = s_shake_base[i];
        }
        s_shake_live = 1;
    } else {
        for (unsigned i = 0; i < 2; i++)
            if ((int32_t)psx_mod_read_word(CAMERA_SOURCE + i * 4u) != s_shake_last[i]) {
                s_shake_frames = 0;
                s_shake_live = 0;
                return; /* the game issued a new camera command: do not clobber it */
            }
    }
    const unsigned amplitude = s_shake_total
        ? (s_shake_amp * s_shake_frames + s_shake_total - 1u) / s_shake_total : 0;
    const int32_t sign = (s_shake_frames & 1u) ? 1 : -1;
    for (unsigned i = 0; i < 2; i++) {
        const int32_t offset = sign * (int32_t)(i ? amplitude / 2u : amplitude);
        const int32_t value = s_shake_base[i] + offset;
        psx_mod_write_word(CAMERA_SOURCE + i * 4u, (uint32_t)value);
        s_shake_last[i] = value;
    }
    s_shake_frames--;
    if (!s_shake_frames) {
        for (unsigned i = 0; i < 2; i++)
            psx_mod_write_word(CAMERA_SOURCE + i * 4u, (uint32_t)s_shake_base[i]);
        s_shake_live = 0;
    }
    psx_mod_counter_add("dbfb.responsive.camera_shake", 1);
}
/* The direct camera is eye XYZ + target XYZ (opcode 0x22; 0x8004DEFC
 * consumes their difference). A small 24-VBlank KO punch-in returns exactly to
 * that shot. Node-relative/scripted cinematics retain their own framing. */
static void combat_ko_begin(void) {
    if (psx_mod_read_word(CAMERA_DIRECT)) return;
    if (s_shake_live) {
        if ((int32_t)psx_mod_read_word(CAMERA_SOURCE) == s_shake_last[0] &&
            (int32_t)psx_mod_read_word(CAMERA_SOURCE+4u) == s_shake_last[1])
            for (unsigned i = 0; i < 2; i++)
                psx_mod_write_word(CAMERA_SOURCE+i*4u, (uint32_t)s_shake_base[i]);
    }
    s_shake_live = 0; s_shake_frames = 0;
    if (!s_ko_frames) { s_ko_frames = 24; s_ko_live = 0; }
}
static int combat_ko_tick(void) {
    if (!s_ko_frames) return 0;
    if (psx_mod_read_word(CAMERA_DIRECT)) { s_ko_frames = s_ko_live = 0; return 0; }
    for (unsigned i = 0; i < 6; i++) {
        const int32_t value = (int32_t)psx_mod_read_word(CAMERA_SOURCE+i*4u);
        if (value < -32768 || value > 32767 || (s_ko_live && value != s_ko_last[i])) {
            s_ko_frames = s_ko_live = 0; return 0; /* game owns a newer shot */
        }
        if (!s_ko_live) s_ko_camera[i] = s_ko_last[i] = value;
    }
    s_ko_live = 1;
    const unsigned age = 25u-s_ko_frames;
    const unsigned phase = age <= 12u ? age : 24u-age;
    const unsigned ease = phase*(24u-phase); /* 0..144, ease in/out, 8% peak */
    for (unsigned axis = 0; axis < 3; axis++) {
        const int64_t vector = (int64_t)s_ko_camera[axis+3u]-s_ko_camera[axis];
        const int32_t value = s_ko_camera[axis]+(int32_t)(vector*ease*8/(144*100));
        psx_mod_write_word(CAMERA_SOURCE+axis*4u, (uint32_t)value);
        s_ko_last[axis] = value;
    }
    s_ko_frames--;
    if (!s_ko_frames) s_ko_live = 0;
    psx_mod_counter_add("dbfb.responsive.ko_camera", 1);
    return 1;
}
static void combat_vblank(void) {
    if (s_ai_cooldown && !s_hitstop_active) s_ai_cooldown--;
    for (unsigned side = 0; side < 2; side++) {
        if (s_push_cool[side]) s_push_cool[side]--;
        if (s_guard_broken[side]) s_guard_broken[side]--;
        if (s_guard_meter[side] && !(s_standard_frame & 1u)) s_guard_meter[side]--;
    }
    s_hitstop_active = s_hitstop != 0;
    if (s_hitstop_active) {
        s_hitstop--;
        psx_mod_counter_add("dbfb.responsive.hitstop_frame", 1);
    }
    if (!combat_ko_tick()) combat_shake_tick();
}
static void combat_poll(struct CPUState* cpu, uint32_t address) {
    (void)address;
    if (!cpu || !s_input_scope.combat) return;
    const int16_t hp0 = combat_signed_half(combat_control(0)+0x40u);
    const int16_t hp1 = combat_signed_half(combat_control(1)+0x40u);
    if ((s_round_hp[0] == 0 && hp0 > 0) || (s_round_hp[1] == 0 && hp1 > 0))
        combat_reset(); /* rematch/next fight must not inherit a broken guard */
    s_round_hp[0] = hp0; s_round_hp[1] = hp1;
    psx_mod_counter_add("dbfb.responsive.combat_poll", 1);
    for (unsigned side = 0; side < 2; side++) {
        const uint32_t c = combat_control(side), script = combat_script(side);
        const unsigned action = psx_mod_read_word(c + 8u) & 255u;
        const uint32_t pointer = psx_mod_read_word(script);
        if (s_confirm_action[side] != action || pointer < s_confirm_pointer[side] ||
            pointer < s_last_pointer[side] || combat_signed_half(c+0x40u) <= 0)
            s_confirm_action[side] = UINT32_MAX;
        s_last_pointer[side] = pointer;
        /* A neutral/guard defender has recovered: nearby separate attacks are
         * not a combo just because they land within ninety VBlanks. */
        if (action <= 0x23u || combat_signed_half(c+0x40u) <= 0) {
            s_combo_hits[side ^ 1u] = 0;
            s_combo_frame[side ^ 1u] = UINT32_MAX;
        }
        const int guarding = action == 0x21u || action == 0x22u || action == 0x23u;
        const uint8_t was = s_prev_action[side];
        const int was_guarding = was == 0x21u || was == 0x22u || was == 0x23u;
        if (guarding && !was_guarding) {
            s_guard_entry[side] = s_standard_frame;
            psx_mod_counter_add("dbfb.responsive.guard_entry", 1);
        }
        if (!guarding) s_guard_entry[side] = UINT32_MAX;
        s_prev_action[side] = (uint8_t)action;
        /* Late recovery starts AFTER the final attack clear, using the exact
         * script pointer/countdown and visual tail, never +4 as elapsed time.
         * Confirmation comes from the damage seam, not the stock rush-only bit. */
        if (s_hitstop_active || s_confirm_action[side] != action) continue;
        const uint16_t tick = psx_mod_read_half(script + 4u);
        if (!motion_recovery_ready(side, action, pointer, tick)) continue;
        if (psx_mod_read_half(script + 0x22u) < 9u) continue;
        psx_mod_write_half(script + 0x22u, 0);
        psx_mod_counter_add("dbfb.responsive.cancel_window", 1);
    }
}
/* Returns the new pre-guard damage (s1). The native body still applies its
 * own half/quarter/zero reduction, HP clamp, reaction and accumulation. */
static int combat_damage(unsigned attacker, unsigned defender, unsigned action,
                         int damage, struct CPUState* cpu) {
    const uint32_t dc = combat_control(defender);
    const unsigned defender_action = psx_mod_read_word(dc + 8u) & 255u;
    const int32_t params = (int32_t)cpu->gpr[5];
    const int divisor = combat_guard_divisor(defender_action, params);
    const int projectile = action >= 0x72u && action <= 0x77u;
    int scaled = damage;
    int final = damage;
    if (divisor >= 0) {
        const uint16_t maxhp = psx_mod_read_half(dc + 0x3Eu);
        unsigned threshold = maxhp ? (unsigned)maxhp / 4u : 50u;
        if (threshold < 16u) threshold = 16u;
        const int just = s_guard_entry[defender] != UINT32_MAX &&
            s_standard_frame - s_guard_entry[defender] <= JUST_GUARD_VBLANKS;
        /* A timed defence relieves pressure instead of breaking guard on the
         * very hit the player defended correctly. An existing break still wins. */
        uint32_t meter = s_guard_meter[defender];
        if (just) meter = meter > (uint32_t)damage ? meter-(uint32_t)damage : 0;
        else meter += (uint32_t)damage;
        if (meter > 0xFFFFu) meter = 0xFFFFu;
        s_guard_meter[defender] = (uint16_t)meter;
        const int broken = s_guard_broken[defender] || meter >= threshold;
        psx_mod_counter_add("dbfb.responsive.guard_block", 1);
        if (broken) {
            if (divisor == 0) cpu->gpr[5] |= 0x40000000u;
            const int native = divisor ? divisor : 2;
            scaled = damage * native;
            if (scaled > 0x7FFF) scaled = 0x7FFF;
            final = damage;
            s_guard_meter[defender] = 0;
            s_guard_broken[defender] = GUARD_BREAK_VBLANKS;
            combat_hitstop(4);
            combat_shake(96, 14);
            combat_push(attacker, defender, 160);
            psx_mod_counter_add("dbfb.responsive.guard_break", 1);
        } else if (just) {
            if (divisor == 0) {
                final = 0;
                psx_mod_counter_add("dbfb.responsive.guard_perfect", 1);
            } else {
                scaled = (damage * divisor + 3) / 4;
                final = damage / 4;
                psx_mod_counter_add("dbfb.responsive.just_guard", 1);
            }
            combat_ki_reward(defender, 2);
            combat_hitstop(3);
            combat_shake(72, 10);
            combat_push(attacker, defender, 32);
        } else {
            final = divisor ? damage / divisor : 0;
            combat_hitstop(3);
            combat_shake(56, 8);
            combat_push(attacker, defender, 40);
        }
    } else {
        if (motion_clip_live(attacker, action)) {
            s_confirm_action[attacker] = action;
            s_confirm_pointer[attacker] = psx_mod_read_word(combat_script(attacker));
        }
        int multiplier = 100;
        if (s_combo_frame[attacker] != s_standard_frame) {
            if (s_combo_frame[attacker] != UINT32_MAX &&
                s_standard_frame - s_combo_frame[attacker] <= COMBO_WINDOW)
                s_combo_hits[attacker]++;
            else
                s_combo_hits[attacker] = 1;
            s_combo_frame[attacker] = s_standard_frame;
        }
        const uint32_t hits = s_combo_hits[attacker];
        if (hits > 1u) multiplier -= (int)((hits > 9u ? 9u : hits) - 1u) * 5;
        if (multiplier < 60) multiplier = 60;
        scaled = damage * multiplier / 100;
        if (scaled < 1) scaled = 1;
        final = scaled;
        if (multiplier < 100) psx_mod_counter_add("dbfb.responsive.combo_scaled", 1);
        combat_hitstop(projectile ? 4u : 2u);
        combat_shake(projectile ? 80u : 64u, projectile ? 10u : 8u);
        combat_push(attacker, defender, projectile ? 128 : 64);
    }
    if (final > 0) {
        const int16_t hp = combat_signed_half(dc + 0x40u);
        if (hp > 0 && final >= hp) {
            combat_ko_begin();
            psx_mod_counter_add("dbfb.responsive.ko_impact", 1);
        }
    }
    return scaled;
}
/* STEP40 copies the menu difficulty to AI_STATE_BASE + side*0x24 (53DE4/
 * 53EFC), and chooses the CPU path with control bit 0 (549C8). Physical pad
 * presence is not player ownership. The native AI runs BEFORE this hook;
 * never replace its command, held output or defensive decision with a special.
 * The extra cadence is a design choice in VBlanks, not hook invocation counts.
 * Stock difficulty-dependent defence and the final command/cost gate remain. */
static void combat_ai(struct CPUState* cpu, uint32_t address) {
    if (!cpu || (address & 0x1FFFFFFFu) != (AI_SITE & 0x1FFFFFFFu)) return;
    if (!offline_started() || !standard_code() || !s_input_scope.combat ||
        s_menu_suspended || s_hitstop_active) return;
    const unsigned side = cpu->gpr[22];
    if (side != 1u || cpu->gpr[23] != side * 0x7Cu) return;
    if (s_ai_cooldown) return;
    const uint32_t c = combat_control(side), o = combat_control(side ^ 1u);
    if (!(psx_mod_read_word(c) & 1u) || (psx_mod_read_word(o) & 1u)) return;
    const uint32_t ai = AI_STATE_BASE + side * AI_STATE_STRIDE;
    const unsigned difficulty = psx_mod_read_half(ai);
    if (difficulty > 2u) return;
    const uint32_t sp = cpu->gpr[29];
    if (!ram_word(sp) || (sp & 0x1FFFFFFFu) > 0x1FFFE8u) return;
    /* Native AI outputs are staged at sp+10/+14 before this exact site. */
    if (psx_mod_read_word(sp+0x10u) || psx_mod_read_word(sp+0x14u)) return;
    if (combat_signed_half(c + 0x56u) != -1) return;
    if ((psx_mod_read_word(c + 8u) & 255u) >= 0x21u) return;
    if (psx_mod_read_word(c) & 0x08000000u) return;
    if (psx_mod_read_word(ai+8u) || psx_mod_read_word(ai+12u) ||
        psx_mod_read_half(ai+16u)) return;
    const uint32_t decision = psx_mod_read_word(ai+28u);
    if (decision == 0xC8u || decision == 0xC9u) return;
    if ((psx_mod_read_word(o+8u) & 255u) >= 0x64u ||
        (psx_mod_read_word(o) & 0x100u)) return;
    if (psx_mod_read_word(c + 4u) & 0x60u) return;
    if (combat_signed_half(c + 0x40u) <= 0 || combat_signed_half(c + 0x42u) < 0) return;
    if (combat_signed_half(o + 0x40u) <= 0) return;
    const int64_t dx = (int64_t)(int32_t)psx_mod_read_word(o + 0x2Cu) - (int32_t)psx_mod_read_word(c + 0x2Cu);
    const int64_t dz = (int64_t)(int32_t)psx_mod_read_word(o + 0x34u) - (int32_t)psx_mod_read_word(c + 0x34u);
    if (dx < -1800 || dx > 1800 || dz < -1800 || dz > 1800 ||
        dx * dx + dz * dz > 1800ll * 1800ll) return;
    static const uint16_t commands[2] = {0x00u, 0x01u};
    psx_mod_write_half(c + 0x56u, commands[s_ai_step & 1u]);
    s_ai_step++;
    static const unsigned cadence[3] = {150, 120, 90};
    s_ai_cooldown = cadence[difficulty];
    psx_mod_counter_add("dbfb.responsive.ai_command", 1);
}
