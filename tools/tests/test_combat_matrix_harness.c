/* Integrated production rules against the user's private disc, all archive
 * records and both sides. Reuse the runtime test double, not a second combat
 * implementation. No game bytes or generated animations live in this file. */
#define main responsive_scenarios_main
#include "test_responsive_harness.c"
#undef main
#include "../../src/mods/dbfb_responsive.c"

static uint8_t character_data[0x50800];

static void mount_character(void) {
    put_half(0x80072A02u, 21); /* observed live Goku/Pan object stride */
    for (unsigned p = 0; p < 2; p++) {
        const uint32_t base = p ? 0x80147800u : 0x800CF000u;
        const uint32_t scripts = p ? 0x80190000u : 0x80117800u;
        memcpy(mem(base, sizeof character_data), character_data, sizeof character_data);
        const unsigned slots = psx_mod_read_half(base+2u);
        put(base, 0x826Bu | slots << 16);
        for (unsigned a = 0; a < slots; a++)
            put(base+4u*(a+1u), peek(base+4u*(a+1u))+base+4u*(slots+1u));
        put(0x8006F794u+p*4u, scripts);
        put(0x8007EF3Cu+p*4u, base);
    }
}

static void launch_ki(unsigned side, unsigned slot, int32_t x, int32_t y, int32_t z) {
    cpu.gpr[17] = side; cpu.gpr[20] = 14u+slot; cpu.gpr[18] = 0x72u;
    projectile_spawn(&cpu, PROJECTILE_SPAWN_SITE);
    assert(s_ki_flight[side][slot].live);
    put_half(projectile_flag(side, slot), 0x80u);
    put(combat_control(side), peek(combat_control(side)) | 0x100u);
    const unsigned index = projectile_index(side, slot);
    const uint32_t object = 0x8007B8BCu+index*40u;
    put(0x8007C3FCu+index*20u, 0);
    put(object+0x18u, (uint32_t)x); put(object+0x1Cu, (uint32_t)y); put(object+0x20u, (uint32_t)z);
}

static void check_projectiles(void) {
    combat_reset();
    for (unsigned p = 0; p < 2; p++) for (unsigned slot = 0; slot < 3; slot++) {
        launch_ki(p, slot, (p ? 6000 : -6000), (int32_t)slot*1000, 0);
        const unsigned index = projectile_index(p, slot);
        cpu.gpr[22] = p; cpu.gpr[18] = index*5u; cpu.gpr[16] = index*40u;
        cpu.gpr[2] = 4096; projectile_speed(&cpu, PROJECTILE_XZ_SITE);
        assert(cpu.gpr[2] == 5120);
        cpu.gpr[2] = (uint32_t)-4096; projectile_speed(&cpu, PROJECTILE_Y_SITE);
        assert((int32_t)cpu.gpr[2] == -5120);
        online = 1; cpu.gpr[2] = 4096; projectile_speed(&cpu, PROJECTILE_XZ_SITE);
        assert(cpu.gpr[2] == 4096); online = 0;
    }
    projectile_poll();
    const uint32_t born = s_standard_frame;
    s_standard_frame = born+PROJECTILE_LIFE-1u; projectile_poll();
    assert(s_ki_flight[0][0].live);
    s_standard_frame++; projectile_poll();
    for (unsigned p = 0; p < 2; p++) for (unsigned k = 0; k < 3; k++)
        assert(!s_ki_flight[p][k].live && !half(projectile_flag(p, k)));
    assert(count("dbfb.responsive.ki_expired") == 6);
    assert(!(peek(combat_control(0)) & 0x100u) && !(peek(combat_control(1)) & 0x100u));
    launch_ki(0, 0, -400, 0, 0); launch_ki(1, 0, 400, 0, 0);
    projectile_poll();
    put(0x8007B8BCu+projectile_index(0, 0)*40u+0x18u, 400);
    put(0x8007B8BCu+projectile_index(1, 0)*40u+0x18u, (uint32_t)-400);
    projectile_poll();
    assert(!half(projectile_flag(0, 0)) && !half(projectile_flag(1, 0)));
    assert(count("dbfb.responsive.ki_trade") == 1);
    launch_ki(0, 0, 0, -1000, 0); launch_ki(1, 0, 0, 1000, 0);
    projectile_poll(); /* same XZ but different height: no trade */
    assert(half(projectile_flag(0, 0)) && half(projectile_flag(1, 0)));
    const uint32_t birth = s_ki_flight[0][0].born;
    s_standard_frame += 8;
    launch_ki(0, 0, -1000, 0, 0); /* reused live slot gets a fresh lifetime */
    assert(s_ki_flight[0][0].born == birth+8u);
    standard_restore(); assert(!s_ki_flight[0][0].live);
}

static void pose_at(unsigned p, unsigned a, uint32_t pointer) {
    const uint32_t context = 0x800A8624u+p*0x20u;
    put(combat_script(p), pointer);
    put_half(combat_script(p)+4u, 0);
    put(context, s_motion_visual[p][a]);
    put(context+4u, motion_total_ticks(p, a)-s_motion_visual_start[p][a]);
    put_half(combat_script(p)+0x22u, 20);
}

int main(void) {
#ifdef _WIN32
    assert(_setmode(_fileno(stdin), _O_BINARY) != -1);
#endif
    uint32_t blocks;
    assert(fread(&blocks, 4, 1, stdin) == 1 && blocks == 22);
    for (uint32_t i = 0; i < blocks; i++) {
        uint32_t address, size;
        assert(fread(&address, 4, 1, stdin) == 1 && fread(&size, 4, 1, stdin) == 1);
        assert(address < sizeof ram && size <= sizeof ram-address);
        assert(fread(ram+address, 1, size, stdin) == size);
    }
    memcpy(original_ram, ram, sizeof ram);
    unsigned variants = 0, recovery_cases = 0, no_recovery_cases = 0;
    for (unsigned record = 0; record < 18; record++) {
        assert(fread(character_data, 1, sizeof character_data, stdin) == sizeof character_data);
        standard_setup(); mount_character();
        combat_fighter(0, 0, 1000, 1000); combat_fighter(1, 0, 1000, 1000);
        poll(0);
        if (record < 17) check_projectiles();
        poll(0);
        for (unsigned p = 0; p < 2; p++) for (unsigned a = 0; a < MOTION_ACTIONS; a++) {
            if (!motion_clip_live(p, a)) continue;
            variants++;
            const uint32_t recovery = s_motion_recovery[p][a];
            combat_reset();
            combat_fighter(p, a, 1000, 1000); combat_fighter(p ^ 1u, 0x24, 1000, 1000);
            const uint32_t start = s_motion_start[p][a];
            pose_at(p, a, recovery ? recovery : start);
            put(combat_control(p), 0x10u); /* rush flag alone must NEVER confirm */
            combat_poll(&cpu, POLL);
            assert(half(combat_script(p)+0x22u) == 20);

            /* Blocking is not a hit confirm, even with a fully elapsed pose. */
            pose_at(p, a, start);
            combat_fighter(p ^ 1u, 0x22, 1000, 1000);
            cpu.gpr[16] = p; cpu.gpr[18] = p ^ 1u;
            cpu.gpr[17] = 10; cpu.gpr[5] = 0x40400000u;
            standard_damage(&cpu, 0x80066D28u);
            assert(s_confirm_action[p] == UINT32_MAX);

            combat_reset(); combat_fighter(p ^ 1u, 0x24, 1000, 1000);
            pose_at(p, a, start);
            cpu.gpr[16] = p; cpu.gpr[18] = p ^ 1u;
            cpu.gpr[17] = 10; cpu.gpr[5] = 0;
            standard_damage(&cpu, 0x80066D28u);
            assert(s_confirm_action[p] == a);
            assert(cpu.gpr[17] == (a >= 0x72u && a <= 0x77u ? 7u : 8u));
            for (unsigned n = 0; n < 5; n++) tick(0);
            poll(0);
            /* No startup/active cancellation, even after an actual hit. */
            combat_poll(&cpu, POLL);
            assert(half(combat_script(p)+0x22u) == 20);
            if (!recovery) { no_recovery_cases++; continue; }
            recovery_cases++;
            pose_at(p, a, recovery);
            combat_poll(&cpu, POLL);
            assert(half(combat_script(p)+0x22u) == 0);
            /* Repeating the same action rewinds its pointer: old confirmation
             * must not open recovery on a later whiff of the same move. */
            pose_at(p, a, start); combat_poll(&cpu, POLL);
            pose_at(p, a, recovery); combat_poll(&cpu, POLL);
            assert(half(combat_script(p)+0x22u) == 20);
            assert(s_confirm_action[p] == UINT32_MAX);
        }
        s_guard_broken[0] = 20; s_combo_hits[0] = 9; s_hitstop = 4;
        s_round_hp[0] = 0;
        combat_fighter(0, 0, 1000, 1000);
        combat_poll(&cpu, POLL);
        assert(!s_guard_broken[0] && !s_combo_hits[0] && !s_hitstop);
        printf("PASS archive record %u: both sides, whiff/block/hit/startup/recovery/repeated action\n", record);
    }
    assert(variants == 942 && recovery_cases > 0 && no_recovery_cases > 0);
    printf("PASS integrated matrix: %u variants, %u confirmed recoveries, %u conservative no-cancel variants\n",
           variants, recovery_cases, no_recovery_cases);
    return 0;
}
