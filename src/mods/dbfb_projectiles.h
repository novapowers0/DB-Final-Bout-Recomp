/* Basic ki volleys only. STEP40 0x8004F57C publishes slots 14/15/16 in the
 * six-halfword owner list. 0x80059194 integrates their angles at speed 256,
 * then performs the native bounds/contact tests. Never move a sampled object
 * after collision: scale the two sine/cosine results BEFORE native integration.
 * The spawn seam gives an exact lifetime origin, including reused slots. */
#define PROJECTILE_SPAWN_SITE 0x8004F5A0u
#define PROJECTILE_XZ_SITE 0x800592A8u
#define PROJECTILE_Y_SITE 0x800592FCu
#define PROJECTILE_LIFE 64u
typedef struct KiFlight {
    uint32_t born;
    int32_t previous[3];
    unsigned live, previous_valid;
} KiFlight;
static KiFlight s_ki_flight[2][3];

static void projectile_reset(void) { memset(s_ki_flight, 0, sizeof s_ki_flight); }
static unsigned projectile_stride(void) {
    /* Object pool: 72 records of 40 bytes before the next array. */
    const unsigned stride = psx_mod_read_half(0x80072A02u);
    return stride >= 17u && stride <= 36u ? stride : 0;
}
static int projectile_code(void) {
    return standard_code() && projectile_stride() &&
        psx_mod_read_word(PROJECTILE_SPAWN_SITE) == 0xA462FFE4u &&
        psx_mod_read_word(PROJECTILE_XZ_SITE) == 0x00021200u &&
        psx_mod_read_word(PROJECTILE_Y_SITE) == 0x00021200u &&
        psx_mod_read_word(0x80071CC0u) == 0x000F000Eu &&
        (psx_mod_read_word(0x80071CC4u) & 0xFFFFu) == 16u;
}
static uint32_t projectile_flag(unsigned side, unsigned slot) {
    return 0x800A870Cu+side*12u+slot*2u;
}
static unsigned projectile_index(unsigned side, unsigned slot) {
    return side*projectile_stride()+14u+slot;
}
static void projectile_spawn(struct CPUState* cpu, uint32_t address) {
    if (!cpu || (address & 0x1FFFFFFFu) != (PROJECTILE_SPAWN_SITE & 0x1FFFFFFFu) ||
        !offline_started() || !s_input_scope.combat || s_menu_suspended || !projectile_code()) return;
    const unsigned side = cpu->gpr[17], type = cpu->gpr[20], action = cpu->gpr[18];
    if (side > 1u || type < 14u || type > 16u || action < 0x72u || action > 0x77u ||
        !motion_clip_live(side, action)) return;
    KiFlight* flight = &s_ki_flight[side][type-14u];
    memset(flight, 0, sizeof *flight);
    flight->live = 1; flight->born = s_standard_frame;
    psx_mod_counter_add("dbfb.responsive.ki_spawn", 1);
}
static void projectile_speed(struct CPUState* cpu, uint32_t address) {
    const uint32_t site = address & 0x1FFFFFFFu;
    if (!cpu || (site != (PROJECTILE_XZ_SITE & 0x1FFFFFFFu) &&
                 site != (PROJECTILE_Y_SITE & 0x1FFFFFFFu)) || !offline_started() ||
        !s_input_scope.combat || s_menu_suspended || !projectile_code()) return;
    const unsigned side = cpu->gpr[22];
    if (side > 1u) return;
    const unsigned index = cpu->gpr[18]/5u, first = projectile_index(side, 0);
    if (index < first || index > first+2u || cpu->gpr[18] != index*5u ||
        cpu->gpr[16] != index*40u || !s_ki_flight[side][index-first].live) return;
    const int32_t value = (int32_t)cpu->gpr[2];
    if (value < -4096 || value > 4096) return;
    cpu->gpr[2] = (uint32_t)(value*5/4); /* 320 nominal units, same pitch/facing */
    psx_mod_counter_add("dbfb.responsive.ki_speed", 1);
}
static void projectile_retire(unsigned side, unsigned slot) {
    const unsigned index = projectile_index(side, slot);
    const uint32_t flags = 0x8007C3FCu+index*20u;
    psx_mod_write_word(flags, psx_mod_read_word(flags) | 0x80000000u);
    psx_mod_write_half(projectile_flag(side, slot), 0);
    memset(&s_ki_flight[side][slot], 0, sizeof(KiFlight));
    unsigned any_active = 0;
    for (unsigned k = 0; k < 6; k++)
        any_active |= psx_mod_read_half(projectile_flag(side, k)) & 0x80u;
    if (!any_active) {
        const uint32_t control = combat_control(side);
        psx_mod_write_word(control, psx_mod_read_word(control) & ~0x100u);
    }
}
static void projectile_poll(void) {
    if (!s_input_scope.combat || !projectile_code()) { projectile_reset(); return; }
    if (s_hitstop_active) return;
    int32_t position[2][3][3];
    unsigned active[2][3] = {{0}};
    for (unsigned p = 0; p < 2; p++) for (unsigned k = 0; k < 3; k++) {
        KiFlight* flight = &s_ki_flight[p][k];
        if (!(psx_mod_read_half(projectile_flag(p, k)) & 0x80u)) {
            memset(flight, 0, sizeof *flight); continue;
        }
        if (!flight->live) continue; /* stock/savestate/special projectile */
        if (s_standard_frame-flight->born >= PROJECTILE_LIFE) {
            projectile_retire(p, k);
            psx_mod_counter_add("dbfb.responsive.ki_expired", 1);
            continue;
        }
        const uint32_t object = 0x8007B8BCu+projectile_index(p, k)*40u;
        active[p][k] = 1;
        for (unsigned axis = 0; axis < 3; axis++) {
            position[p][k][axis] = (int32_t)psx_mod_read_word(object+0x18u+axis*4u);
            if (position[p][k][axis] < -20000 || position[p][k][axis] > 20000)
                active[p][k] = 0;
        }
    }
    /* Relative swept distance catches opposing shots crossing between polls,
     * including height. Integer-only, deterministic, each shot retires once. */
    for (unsigned a = 0; a < 3; a++) for (unsigned b = 0; b < 3; b++) {
        if (!active[0][a] || !active[1][b]) continue;
        int64_t d[3], v[3], dot = 0, length = 0;
        for (unsigned axis = 0; axis < 3; axis++) {
            const KiFlight *x = &s_ki_flight[0][a], *y = &s_ki_flight[1][b];
            const int32_t now = position[0][a][axis]-position[1][b][axis];
            d[axis] = x->previous_valid && y->previous_valid
                ? (int64_t)x->previous[axis]-y->previous[axis] : now;
            v[axis] = now-d[axis]; dot += d[axis]*v[axis]; length += v[axis]*v[axis];
        }
        int64_t t = length ? -dot*1024/length : 0;
        if (t < 0) t = 0;
        if (t > 1024) t = 1024;
        int64_t distance = 0;
        for (unsigned axis = 0; axis < 3; axis++) {
            const int64_t nearest = d[axis]+v[axis]*t/1024;
            distance += nearest*nearest;
        }
        if (distance <= 128ll*128ll) {
            projectile_retire(0, a); projectile_retire(1, b);
            active[0][a] = active[1][b] = 0;
            combat_shake(40, 4);
            psx_mod_counter_add("dbfb.responsive.ki_trade", 1);
        }
    }
    for (unsigned p = 0; p < 2; p++) for (unsigned k = 0; k < 3; k++)
        if (active[p][k]) {
            memcpy(s_ki_flight[p][k].previous, position[p][k], sizeof position[p][k]);
            s_ki_flight[p][k].previous_valid = 1;
        }
}
