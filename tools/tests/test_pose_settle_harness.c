/* Reuse the existing motion memory fixture, not its assertions about a new
 * feature. No shared responsive harness changes. */
#define main original_motion_test_main
#include "test_motion_harness.c"
#undef main

int main(void) {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    assert(fread(action_engine, 1, sizeof action_engine, stdin) == sizeof action_engine);
    assert(fread(animation_engine, 1, sizeof animation_engine, stdin) == sizeof animation_engine);
    for (unsigned character = 0; character < 18; ++character) {
        assert(fread(original, 1, sizeof original, stdin) == sizeof original);
        init(original); motion_tick();
        assert(!rejected);
        for (unsigned side = 0; side < 2; ++side) {
            const uint32_t stock = side ? 0x80190000u : 0x80117800u;
            const uint32_t table = psx_mod_read_word(0x8006F794u+4u*side);
            const uint32_t ptr = table+4u*(MOTION_ACTIONS+1u)+psx_mod_read_word(table+28u)*4u;
            const uint32_t original_ptr = stock+4u*(MOTION_ACTIONS+1u)+psx_mod_read_word(stock+28u)*4u;
            if (character != 0) { assert(ptr == original_ptr); continue; }
            assert(ptr != original_ptr);
            assert(psx_mod_read_word(ptr) == 0x01200002u);
            const unsigned slot = psx_mod_read_word(ptr+4u) & 65535u;
            const uint32_t animations = psx_mod_read_word(0x8007EF3Cu+side*4u);
            const uint32_t target = psx_mod_read_word(animations+4u*(slot+1u));
            assert((psx_mod_read_word(ptr+4u) & 0xFFFF0000u) == 0x00200000u);
            assert(!psx_mod_read_word(ptr+8u));
            assert(slot >= 218u);
            assert(!motion_selected(6) && !motion_clip_live(side, 6));
            assert(!motion_damage_scales(side, 6) && !motion_total_ticks(side, 6));
            uint8_t snapshot[SETTLE_OUTPUT_BYTES];
            memcpy(snapshot, memory(target, sizeof snapshot), sizeof snapshot);
            const uint32_t context = 0x800A8624u+side*0x20u;
            put(context, target); put(context+4u, 3); put(context+8u, target+4u);
            const uint32_t node_context = psx_mod_read_word(context+8u);
            motion_restore(); motion_tick();
            assert(psx_mod_read_word(context) == target && psx_mod_read_word(context+4u) == 3);
            assert(psx_mod_read_word(context+8u) == node_context);
            assert(!memcmp(snapshot, memory(target, sizeof snapshot), sizeof snapshot));
            if (side == 0) assert(fwrite(snapshot, 1, sizeof snapshot, stdout) == sizeof snapshot);
        }
    }
    return 0;
}
