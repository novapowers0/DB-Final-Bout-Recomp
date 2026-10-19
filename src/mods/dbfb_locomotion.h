/* Self-locomotion, BEFORE the native rotation/separation/arena resolution.
 * STEP40 80067A60..68 sign-extends the animated root delta in s0 and multiplies
 * it by the native facing sine; the second projection uses the same s0.
 * This does not touch script+0x0C (opponent displacement) or fighter positions.
 */
#define LOCOMOTION_SITE 0x80067A68u
#define LOCOMOTION_ORIGINAL 0x02020018u /* mult s0,v0 */
static int32_t s_locomotion_velocity[2];
static uint32_t s_locomotion_frame[2];

static void locomotion_reset(void) {
    s_locomotion_velocity[0] = s_locomotion_velocity[1] = 0;
    s_locomotion_frame[0] = s_locomotion_frame[1] = UINT32_MAX;
}

static void locomotion_step(struct CPUState* cpu, uint32_t address) {
    if (!cpu || (address & 0x1FFFFFFFu) != (LOCOMOTION_SITE & 0x1FFFFFFFu)) return;
    if (!offline_started() || !standard_code() || !s_input_scope.combat ||
        s_menu_suspended || psx_mod_read_word(LOCOMOTION_SITE) != LOCOMOTION_ORIGINAL) {
        locomotion_reset(); return;
    }
    const unsigned side = cpu->gpr[18]; /* s2, copied from native side argument */
    if (side > 1u) return;
    const uint32_t control = combat_control(side);
    const unsigned action = psx_mod_read_byte(control+8u);
    const int32_t delta = (int32_t)cpu->gpr[16];
    /* Neutral + bounded native movement family only. Reactions, attacks,
     * guard, scripted flight and discontinuities retain their original delta. */
    if (action > 0x16u || !combat_attacker_ready(side, action) ||
        delta < -256 || delta > 256 || s_hitstop_active) {
        s_locomotion_velocity[side] = 0;
        s_locomotion_frame[side] = UINT32_MAX;
        return;
    }
    const uint32_t elapsed = s_standard_frame-s_locomotion_frame[side];
    unsigned ticks = elapsed;
    if (s_locomotion_frame[side] == UINT32_MAX || elapsed > 6u) {
        s_locomotion_velocity[side] = 0;
        ticks = 1u;
    }
    const int32_t target = action == 0u ? 0 : delta*5/4;
    int32_t velocity = s_locomotion_velocity[side];
    /* At most 4 active VBlanks to reach 125 units from a 100-unit native
     * stride; braking is faster. Repeated calls in one VBlank do not ramp. */
    const int32_t rate = (target == 0 ? 64 : 40)*(int32_t)ticks;
    int32_t change = target-velocity;
    if (change > rate) change = rate;
    if (change < -rate) change = -rate;
    velocity += change;
    s_locomotion_velocity[side] = velocity;
    s_locomotion_frame[side] = s_standard_frame;
    cpu->gpr[16] = (uint32_t)velocity;
    if (velocity != delta) psx_mod_counter_add("dbfb.responsive.locomotion", 1);
}
