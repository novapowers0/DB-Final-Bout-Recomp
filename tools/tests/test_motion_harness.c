/* Executes the production motion compiler against private local-disc fixtures.
 * Fixtures arrive on stdin and are never written by this harness. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
#include "mod_plugins.h"
static uint8_t ram[0x200000], expansion[0x100000], original[0x50800];
static uint8_t action_engine[0xAE4], animation_engine[0xC24];
static uint32_t used, writes, published, variants, rejected, pose_samples, techniques;
static uint8_t* memory(uint32_t a, uint32_t size) {
    a &= 0x1FFFFFFFu;
    if (a < sizeof ram && size <= sizeof ram-a) return ram+a;
    assert(a >= 0x1F000000u && a-0x1F000000u <= sizeof expansion-size);
    return expansion+a-0x1F000000u;
}
uint8_t psx_mod_read_byte(uint32_t a) { return *memory(a, 1); }
uint16_t psx_mod_read_half(uint32_t a) {
    uint16_t v; memcpy(&v, memory(a, 2), 2); return v;
}
uint32_t psx_mod_read_word(uint32_t a) {
    uint32_t v; memcpy(&v, memory(a, 4), 4); return v;
}
static void put(uint32_t a, uint32_t v) { memcpy(memory(a, 4), &v, 4); }
void psx_mod_write_word(uint32_t a, uint32_t v) {
    assert(!(a & 3u)); writes++;
    if ((a & 0x1FFFFFFFu) < sizeof ram) {
        assert(a == 0x8006F794u || a == 0x8006F798u || a == 0x8007EF3Cu || a == 0x8007EF40u);
        published++;
    }
    put(a, v);
}
uint32_t psx_mod_alloc_guest_memory(uint32_t size, uint32_t alignment) {
    used = (used+alignment-1u) & ~(alignment-1u);
    assert(size <= sizeof expansion-used);
    const uint32_t result = 0x9F000000u+used;
    used += size; return result;
}
void psx_mod_counter_add(const char* name, uint32_t n) {
    if (!strcmp(name, "dbfb.responsive.motion_variants")) variants += n;
    else if (!strcmp(name, "dbfb.responsive.pose_transitions")) pose_samples += n;
    else if (!strcmp(name, "dbfb.responsive.technique_variants")) techniques += n;
    else { assert(!strcmp(name, "dbfb.responsive.motion_rejected")); rejected += n; }
}
static uint32_t code_fnv(uint32_t address, uint32_t size) {
    uint32_t h = 2166136261u;
    for (uint32_t i = 0; i < size; i++) { h ^= psx_mod_read_byte(address+i); h *= 16777619u; }
    return h;
}
#include "../../src/mods/dbfb_motion.h"

static void init(const uint8_t* data) {
    memset(ram, 0, sizeof ram); memset(expansion, 0, sizeof expansion);
    used = writes = published = variants = rejected = pose_samples = techniques = 0; motion_reset();
    memcpy(memory(0x8004E530u, sizeof action_engine), action_engine, sizeof action_engine);
    memcpy(memory(0x800420ECu, sizeof animation_engine), animation_engine, sizeof animation_engine);
    for (unsigned p = 0; p < 2; p++) {
        const uint32_t base = p ? 0x80147800u : 0x800CF000u;
        const uint32_t scripts = p ? 0x80190000u : 0x80117800u;
        memcpy(memory(base, sizeof original), data, sizeof original);
        const unsigned count = psx_mod_read_half(base+2u);
        assert(count >= 216u && count <= 219u);
        put(base, 0x826Bu | count << 16);
        for (unsigned i = 0; i < count; i++)
            put(base+4u*(i+1u), psx_mod_read_word(base+4u*(i+1u))+base+4u*(count+1u));
        put(0x8006F794u+4u*p, scripts); put(0x8007EF3Cu+4u*p, base);
    }
}

static void check_variant(unsigned p, unsigned action) {
    const uint32_t stock = p ? 0x80190000u : 0x80117800u;
    const uint32_t table = psx_mod_read_word(0x8006F794u+4u*p);
    const uint32_t anim = psx_mod_read_word(0x8007EF3Cu+4u*p);
    assert(table == s_motion_arena[p]+16u && anim == s_motion_arena[p]+712u);
    const uint32_t offset = psx_mod_read_word(table+4u*(action+1u));
    if (offset == UINT32_MAX) return;
    uint32_t script = table+4u*(MOTION_ACTIONS+1u)+offset*4u;
    if ((script & 0x1FFFFFFFu) < sizeof ram) return; /* absent/aliased boss moves */
    int saw_variant = 0;
    uint32_t original_script = stock+4u*(MOTION_ACTIONS+1u)+
        psx_mod_read_word(stock+4u*(action+1u))*4u;
    for (unsigned n = 0; n < 256; n++) {
        const uint32_t word = psx_mod_read_word(script);
        const unsigned op = (word >> 16) & 255u;
        const unsigned words = motion_words(op);
        assert(words);
        if (op == 0x84u && action >= 0x72u && action <= 0x77u) {
            const uint32_t operand = psx_mod_read_word(original_script+4u);
            const unsigned old_cost = operand >> 24;
            unsigned expected_cost = old_cost;
            if (old_cost && old_cost < 128u) {
                expected_cost = old_cost*3u/4u;
                if (!expected_cost) expected_cost = 1;
            }
            const uint32_t new_operand = psx_mod_read_word(script+4u);
            assert((new_operand & 0xFFFFFFu) == (operand & 0xFFFFFFu));
            assert(new_operand >> 24 == expected_cost);
        }
        if (op == 0x20u && (word & 0xFFFFu) >=
            psx_mod_read_half((p ? 0x80147800u : 0x800CF000u)+2u)) {
            const uint32_t ptr = psx_mod_read_word(anim+4u*((word & 0xFFFFu)+1u));
            assert(psx_mod_read_half(ptr) == 0x4Fu);
            assert(psx_mod_read_half(ptr+2u) > 0);
            saw_variant = 1;
        }
        script += words*4u;
        original_script += words*4u;
        if (!word) break;
        assert(n != 255);
    }
    assert(saw_variant);
    const uint32_t context = 0x800A8624u+p*0x20u;
    put(context, s_motion_visual[p][action]);
    put(context+4u, motion_total_ticks(p, action)-s_motion_visual_start[p][action]);
    assert(!motion_recovery_ready(p, action, s_motion_start[p][action], 0));
    assert(!motion_recovery_ready(p, action, s_motion_end[p][action], 0));
    if (s_motion_recovery[p][action]) {
        assert(motion_recovery_ready(p, action, s_motion_recovery[p][action], 0));
        assert(!motion_recovery_ready(p, action, s_motion_recovery[p][action], 255));
        put(context, 0); /* another animation cannot donate its elapsed time */
    }
    assert(psx_mod_read_word(stock) == 0x00AD4244u);
}

static void coalescing(void) {
    /* Five original frames, four retimed ticks: all five payloads survive. */
    motion_put(s_motion_clip, 0, 0x0005004Fu);
    for (unsigned g = 0; g < 5; g++) {
        motion_put(s_motion_clip, 4u+12u*g, 0x00010003u);
        motion_put(s_motion_clip, 8u+12u*g, g+1u);
        motion_put(s_motion_clip, 12u+12u*g, 100u+g);
    }
    const MotionKnot knot = {0, 0};
    const uint32_t end = motion_retime(64u, 0, &knot, 1, 3, 4);
    assert(end == 56u && motion_get(s_motion_build, 0) == 0x0004004Fu);
    uint32_t at = 4, payload = 100;
    for (unsigned g = 0; g < 4; g++) {
        const uint32_t header = motion_get(s_motion_build, at), words = header & 0xFFFFu;
        for (unsigned w = 2; w < words; w++) assert(motion_get(s_motion_build, at+4u*w) == payload++);
        at += 4u*words;
    }
    assert(payload == 105u && at == end);
    motion_put(s_motion_clip, 0, 0x0001004Fu);
    motion_put(s_motion_clip, 4, 0x0001FFFFu);
    assert(!motion_retime(16, 0, &knot, 1, 4, 5));
}

static void check_technique(unsigned side, unsigned action) {
    const uint32_t stock = side ? 0x80190000u : 0x80117800u;
    const uint32_t table = psx_mod_read_word(0x8006F794u+4u*side);
    const uint32_t offset = psx_mod_read_word(stock+4u*(action+1u));
    if (offset == UINT32_MAX) return;
    uint32_t original_at = stock+4u*(MOTION_ACTIONS+1u)+offset*4u;
    uint32_t at = table+4u*(MOTION_ACTIONS+1u)+psx_mod_read_word(table+4u*(action+1u))*4u;
    assert((at & 0x1FFFFFFFu) >= sizeof ram);
    assert(!motion_clip_live(side, action) && !motion_damage_scales(side, action));
    assert(!motion_recovery_ready(side, action, at, 0));
    for (unsigned event = 0; event < 256; event++) {
        const uint32_t word = psx_mod_read_word(original_at);
        const unsigned op = (word >> 16) & 255u, words = motion_words(op);
        assert(words);
        for (unsigned i = 0; i < words; i++) {
            uint32_t expected = psx_mod_read_word(original_at+i*4u);
            if (op == 0x84u && i == 1u) {
                const unsigned cost = expected >> 24;
                if (cost && cost < 128u) {
                    unsigned adjusted = cost*4u/5u;
                    if (!adjusted) adjusted = 1;
                    expected = (expected & 0xFFFFFFu) | adjusted << 24;
                }
            }
            assert(psx_mod_read_word(at+i*4u) == expected);
        }
        if (!word) return;
        at += words*4u; original_at += words*4u;
    }
    assert(!"unterminated technique");
}

static void authored_recovery(void) {
    /* Dense native relative stream: shape the middle pose, then cancel the
     * correction. This must work for arbitrary incoming poses, including wrap. */
    motion_put(s_motion_build, 0, 0x0003004Fu);
    const uint16_t u[3] = {(uint16_t)-80, 110, 34}, v[3] = {(uint16_t)-44, 53, 22};
    for (unsigned g = 0; g < 3; g++) {
        const unsigned at = 4u+32u*g;
        motion_put(s_motion_build, at, 0x00020008u);
        motion_put(s_motion_build, at+4u, 8u+g);
        pose_packet(s_motion_build, at+8u, 1, g == 2 ? v : u);
        pose_packet(s_motion_build, at+20u, 6, g == 2 ? v : u);
    }
    uint8_t source[100]; memcpy(source, s_motion_build, sizeof source);
    unsigned samples = 0;
    assert(pose_refine(0, sizeof source, 9, UINT64_C(2), &samples) == sizeof source);
    assert(!samples && !memcmp(source, s_motion_build, sizeof source));
    const uint32_t end = pose_refine(0, sizeof source, 8, UINT64_C(2), &samples);
    assert(samples == 1 && end == sizeof source+24u && motion_get(s_motion_build, 0) >> 16 == 3);
    for (unsigned seed = 0; seed < 3; seed++) {
        PoseAngles state[POSE_PARTS] = {{{0,0,0},0}}, original_state[POSE_PARTS];
        for (unsigned id = 0; id < POSE_PARTS; id++) {
            state[id].known = 1;
            for (unsigned axis = 0; axis < 3; axis++) state[id].angle[axis] = (uint16_t)(seed*32000u+axis*17u);
        }
        memcpy(original_state, state, sizeof state);
        uint64_t roots = 0;
        uint32_t at = 4, stock = 4;
        for (unsigned g = 0; g < 3; g++) {
            int only = 1;
            assert(pose_group(s_motion_build, at, end, state, &roots, &only));
            assert(pose_group(source, stock, sizeof source, original_state, &roots, &only));
            assert(!memcmp(state[1].angle, original_state[1].angle, sizeof state[1].angle));
            if (g == 1) assert(memcmp(state[6].angle, original_state[6].angle, sizeof state[6].angle));
            else assert(!memcmp(state, original_state, sizeof state));
            at += (motion_get(s_motion_build, at) & 65535u)*4u;
            stock += (motion_get(source, stock) & 65535u)*4u;
        }
        assert(at == end);
    }
}

int main(void) {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
#endif
    coalescing(); authored_recovery();
    assert(fread(action_engine, 1, sizeof action_engine, stdin) == sizeof action_engine);
    assert(fread(animation_engine, 1, sizeof animation_engine, stdin) == sizeof animation_engine);
    for (unsigned character = 0; character < 18; character++) {
        assert(fread(original, 1, sizeof original, stdin) == sizeof original);
        init(original); motion_tick();
        if (rejected || !variants) {
            printf("REJECTED character %u variants %u rejected %u\n", character, variants, rejected);
            return 1;
        }
        assert(published == 4u);
        for (unsigned p = 0; p < 2; p++)
            for (unsigned a = 0; a < MOTION_ACTIONS; a++) if (motion_selected(a)) check_variant(p, a);
        assert(techniques == 24u);
        for (unsigned p = 0; p < 2; p++)
            for (unsigned a = 0x78u; a <= 0x83u; a++) check_technique(p, a);
        if (character == 0) {
            /* Damage follows the faster clock only while the private table is
             * published; a retimed clip that never installed keeps stock damage. */
            assert(motion_damage_scales(0, 0x64u) && motion_damage_scales(1, 0x64u));
            assert(!motion_damage_scales(0, 0x21u) && !motion_damage_scales(0, MOTION_ACTIONS));
            assert(motion_clip_live(0, 0x64u) && motion_clip_live(1, 0x64u));
            assert(!motion_clip_live(0, 0x21u) && !motion_clip_live(0, MOTION_ACTIONS));
            assert(motion_total_ticks(0, 0x64u) > 0 && motion_total_ticks(1, 0x72u) > 0);
            assert(motion_total_ticks(0, 0x21u) == 0 && motion_total_ticks(0, MOTION_ACTIONS) == 0);
            const uint32_t magic = psx_mod_read_word(s_motion_arena[0]);
            put(s_motion_arena[0], 0);
            assert(!motion_damage_scales(0, 0x64u));
            put(s_motion_arena[0], magic);
            assert(motion_damage_scales(0, 0x64u));
        }
        const uint32_t before = writes, count = variants;
        motion_tick(); assert(writes == before && variants == count);
        motion_restore();
        assert(motion_total_ticks(0, 0x64u) == 0); /* restore drops the timeline */
        motion_tick(); assert(variants == count*2u);
        assert(motion_total_ticks(0, 0x64u) > 0);
        /* Overlay re-publishing of original pointers must rebind the private
         * tables without allocating or multiplying the timing again. */
        put(0x8006F794u, 0x80117800u); put(0x8007EF3Cu, 0x800CF000u);
        const uint32_t allocated = used;
        motion_tick(); assert(used == allocated && variants == count*2u);
        assert(psx_mod_read_word(0x8006F794u) == s_motion_arena[0]+16u);
        printf("PASS roster %u: %u private variants, %u authored recovery samples, both sides, idempotence, restore, reload\n", character, count, pose_samples);
        /* Malformed original data never publishes a replacement. */
        init(original); put(0x80117AB8u+psx_mod_read_word(0x80117994u)*4u, 0x007F0000u);
        motion_tick(); /* side 2 can still build independently */
        assert(psx_mod_read_word(0x8006F794u) == 0x80117800u);
        init(original); put(0x800420ECu, 0); motion_tick();
        assert(!published && !used && !writes);
    }
    puts("PASS coalesced frames retain ordered transform payloads; invalid groups bounded; recovery resolves exact event/countdown and private pose on both sides");
    return 0;
}
