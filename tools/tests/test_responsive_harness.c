/* Link the UNMODIFIED production C as a separate translation unit. Only the
 * runtime services are simulated. Private code fingerprints arrive on stdin
 * from local captures; no disc-derived bytes are distributed in this test. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cpu_state.h"
#include "mod_plugins.h"
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

#define POLL 0x8003FCF0u
#define REMAP 0x8003FE68u
#define SP 0x801FF000u
#define SLOT (SP - 0x10u)
#define EXP 0x1F000000u
#define EXP_SIZE 0x80000u

typedef struct Plugin {
    PSXModActivationCallback activate, restore;
    PSXModVBlankCallback vblank;
    PSXModFunctionEntryCallback poll, remap;
    PSXModOptionChangedCallback changed;
    int selected;
} Plugin;
static Plugin plugins[2];
static uint8_t ram[0x200000], original_ram[0x200000], expansion[EXP_SIZE];
static uint8_t reference_ram[0x200000], reference_expansion[EXP_SIZE];
static uint32_t output_stream[80], reference_stream[80];
static uint32_t scratch_pad;
static uint16_t pads[2];
static uint32_t reads, writes, ram_writes, allocs, sio_reads, last_write, exp_used;
static int started = 1, online, resim, alloc_fail, reverse_order;
static const char *mode_option, *window_option;
static CPUState cpu;
static struct { const char* name; uint32_t value; } counters[32];
static unsigned counter_count, tests;

static unsigned id_index(const char* id) {
    if (!strcmp(id, "dbfb.responsive.trace")) return 0;
    assert(!strcmp(id, "dbfb.responsive.input-buffer"));
    return 1;
}
int psx_mod_register_activation_plugin(const char* id, PSXModActivationCallback cb) {
    plugins[id_index(id)].activate = cb; return 1;
}
int psx_mod_register_vblank_plugin(const char* id, PSXModVBlankCallback cb) {
    plugins[id_index(id)].vblank = cb; return 1;
}
int psx_mod_register_savestate_plugin(const char* id, PSXModActivationCallback cb) {
    plugins[id_index(id)].restore = cb; return 1;
}
int psx_mod_register_option_changed_plugin(const char* id, PSXModOptionChangedCallback cb) {
    plugins[id_index(id)].changed = cb; return 1;
}
int psx_mod_register_function_entry_plugin(const char* id, uint32_t addr,
                                          PSXModFunctionEntryCallback cb) {
    Plugin* p = &plugins[id_index(id)];
    if (addr == POLL) { assert(!p->poll); p->poll = cb; }
    else { assert(addr == REMAP && !p->remap); p->remap = cb; }
    return 1;
}
int psx_mod_game_started(void) { return started; }
int psx_netplay_active(void) { return online; }
int psx_netplay_is_resimulating(void) { return resim; }
int psx_mod_option_value(const char* package, const char* feature, const char* option,
                         char* out, uint32_t size) {
    assert(!strcmp(package, "dbfb.responsive") && !strcmp(feature, "input-buffer"));
    const char* value = !strcmp(option, "mode") ? mode_option : window_option;
    if (!value) { if (size) out[0] = 0; return 0; }
    assert(strlen(value) < size);
    strcpy(out, value); return 1;
}
uint16_t sio_get_pad_buttons_slot(int p) {
    assert(p >= 0 && p < 2); sio_reads++; return pads[p];
}
void psx_mod_counter_add(const char* name, uint32_t delta) {
    for (unsigned i = 0; i < counter_count; i++) if (!strcmp(name, counters[i].name)) {
        counters[i].value += delta; return;
    }
    assert(counter_count < 32);
    counters[counter_count].name = name;
    counters[counter_count++].value = delta;
}
static uint32_t count(const char* name) {
    for (unsigned i = 0; i < counter_count; i++)
        if (!strcmp(name, counters[i].name)) return counters[i].value;
    return 0;
}
static uint8_t* mem(uint32_t addr, uint32_t size) {
    const uint32_t phys = addr & 0x1FFFFFFFu;
    if (phys < sizeof ram && size <= sizeof ram - phys) return ram + phys;
    if (phys >= EXP && phys - EXP <= EXP_SIZE - size) return expansion + phys - EXP;
    /* Only the verified previous-pad scratchpad word is read. */
    if (phys == 0x1F800004u && size == 4) return (uint8_t*)&scratch_pad;
    assert(!"Unexpected guest memory access"); return NULL;
}
static uint32_t peek(uint32_t addr) {
    uint32_t word; memcpy(&word, mem(addr, 4), 4); return word;
}
static void put(uint32_t addr, uint32_t word) { memcpy(mem(addr, 4), &word, 4); }
uint8_t psx_mod_read_byte(uint32_t addr) { reads++; return *mem(addr, 1); }
uint32_t psx_mod_read_word(uint32_t addr) { reads++; return peek(addr); }
void psx_mod_write_word(uint32_t addr, uint32_t word) {
    assert(!(addr & 3)); writes++; last_write = addr;
    if ((addr & 0x1FFFFFFFu) < sizeof ram) { ram_writes++; assert(addr == SLOT); }
    put(addr, word);
}
uint32_t psx_mod_alloc_guest_memory(uint32_t size, uint32_t alignment) {
    allocs++;
    if (alloc_fail) return 0;
    exp_used = (exp_used + alignment - 1) & ~(alignment - 1);
    assert(size <= EXP_SIZE - exp_used);
    const uint32_t result = EXP + exp_used;
    exp_used += size;
    return result;
}

static void hook(uint32_t addr) {
    const CPUState before = cpu;
    for (unsigned n = 0; n < 2; n++) {
        Plugin* p = &plugins[n ^ (unsigned)reverse_order];
        if (p->selected) (addr == POLL ? p->poll : p->remap)(&cpu, addr);
    }
    assert(!memcmp(&cpu, &before, sizeof cpu));
}
static void physical(uint32_t game_word) {
    for (unsigned p = 0; p < 2; p++) {
        const uint16_t half = (uint16_t)(game_word >> (16 * p));
        pads[p] = (uint16_t)~(uint16_t)((half << 8) | (half >> 8));
    }
}
static void tick(uint32_t physical_word) {
    physical(physical_word);
    for (unsigned n = 0; n < 2; n++) {
        Plugin* p = &plugins[n ^ (unsigned)reverse_order];
        if (p->selected) p->vblank();
    }
}
static void poll_start(void) {
    memset(&cpu, 0, sizeof cpu);
    cpu.gpr[29] = SP; cpu.gpr[31] = 0x8003FCBCu;
    hook(POLL);
}
static uint32_t remap_end(uint32_t raw) {
    cpu.gpr[4] = SLOT; cpu.gpr[29] = SP - 0x20u; cpu.gpr[31] = 0x8003FD64u;
    put(SLOT, raw); hook(REMAP); return peek(SLOT);
}
static uint32_t poll(uint32_t raw) {
    poll_start(); return remap_end(raw);
}
static void restore(void) {
    for (unsigned n = 0; n < 2; n++) if (plugins[n].selected) plugins[n].restore();
}
static void setup(const char* mode, const char* window, int trace, int input) {
    memcpy(ram, original_ram, sizeof ram);
    memset(expansion, 0xA5, sizeof expansion);
    scratch_pad = 0;
    reads = writes = ram_writes = allocs = sio_reads = exp_used = last_write = 0;
    started = 1; online = resim = alloc_fail = reverse_order = 0;
    mode_option = mode; window_option = window; counter_count = 0;
    physical(0);
    *mem(0x8003BC00u, 1) = *mem(0x8003BC28u, 1) = 0;
    *mem(0x8003BC01u, 1) = *mem(0x8003BC29u, 1) = 0x41;
    *mem(0x8003BC7Eu, 1) = 0;
    plugins[0].selected = trace; plugins[1].selected = input;
    for (unsigned n = 0; n < 2; n++) if (plugins[n].selected) plugins[n].activate();
}
static void passed(const char* name) { tests++; printf("PASS %s\n", name); }
static void pending_tap(void) {
    assert(poll(0) == 0); tick(0x20); tick(0);
}

static void test_original(void) {
    setup("original", "6", 0, 1);
    const uint32_t slot_before = peek(SLOT);
    for (unsigned i = 0; i < 20; i++) {
        tick((i * 76543u) ^ 0x12345678u);
        memset(&cpu, 0xC3, sizeof cpu);
        const CPUState before = cpu;
        hook(POLL); hook(REMAP);
        assert(!memcmp(&cpu, &before, sizeof cpu));
    }
    assert(peek(SLOT) == slot_before && !reads && !writes && !allocs && !sio_reads);
    setup(NULL, NULL, 0, 0);
    tick(0xFFFFFFFFu); hook(POLL); hook(REMAP);
    assert(!reads && !writes && !allocs && !sio_reads);
    passed("Original and all-off: zero guest reads/writes/allocations/SIO effects");
}
static void test_capture_once(void) {
    setup("buffer", "2", 0, 1);
    pending_tap();
    assert(poll(0) == 0x20 && ram_writes == 1 && allocs == 0);
    assert(count("dbfb.responsive.delivered_button") == 1);
    assert(count("dbfb.responsive.delivery_age_vblanks") == 1);
    assert(last_write == SLOT);
    /* Duplicate hook cannot consume or inject twice. */
    hook(REMAP); assert(ram_writes == 1);
    assert(poll(0) == 0 && ram_writes == 1);
    passed("input without trace: missed tap delivered once, next poll released");
}
static void test_no_duplicate(void) {
    setup("buffer", "6", 0, 1);
    assert(poll(0) == 0); tick(0x20);
    assert(poll(0x20) == 0x20); tick(0);
    assert(poll(0) == 0 && !ram_writes);
    setup("buffer", "6", 0, 1);
    assert(poll(0) == 0); assert(poll(0x20) == 0x20);
    assert(poll(0) == 0 && !ram_writes);
    passed("visible raw presses consumed naturally; buffer does not extend a hold");
}
static void test_mask_ports_swap(void) {
    for (unsigned port = 0; port < 2; port++) for (unsigned bit = 0; bit < 16; bit++) {
        setup("buffer", "2", 0, 1);
        const uint32_t press = 1u << (16 * port + bit);
        assert(poll(0) == 0); tick(press); tick(0);
        assert(poll(0) == (bit < 8 ? press : 0));
    }
    setup("buffer", "2", 0, 1);
    assert(poll(0) == 0); tick(0x00200080u); tick(0);
    assert(poll(0x40002000u) == 0x40202080u);
    setup("buffer", "2", 0, 1);
    *mem(0x8003BC7Eu, 1) = 1;
    assert(poll(0) == 0); tick(0x20); tick(0);
    assert(poll(0) == 0x00200000u);
    passed("all 32 pad bits, simultaneous ports, live directions and port swap");
}
static void test_lifetime(void) {
    for (unsigned w = 1; w <= 6; w++) {
        const char text[] = {(char)('0' + w), 0};
        setup("buffer", text, 0, 1); pending_tap();
        assert(poll(0) == (w == 1 ? 0 : 0x20));
    }
    passed("VBlank lifetime boundaries 1..6 (not extra polls)");
}
static void test_release_before_retrigger(void) {
    setup("buffer", "6", 0, 1);
    assert(poll(0) == 0); assert(poll(0x20) == 0x20);
    tick(0); tick(0x20);
    assert(poll(0) == 0); /* release must be visible before a new rising edge */
    tick(0);
    assert(poll(0) == 0x20); assert(poll(0) == 0);
    passed("no synthetic retrigger until a release poll has been visible");
}
static void test_hold(void) {
    setup("hold", "3", 0, 1);
    assert(poll(0) == 0); assert(poll(0x20) == 0x20);
    tick(0); tick(0);
    assert(poll(0) == 0x20); tick(0);
    assert(poll(0) == 0);
    setup("hold", "3", 0, 1);
    assert(poll(0) == 0);
    for (unsigned i = 0; i < 10; i++) { assert(poll(0x20) == 0x20); tick(0x20); }
    tick(0); assert(poll(0) == 0 && !ram_writes);
    setup("hold", "6", 0, 1); pending_tap();
    assert(poll(0) == 0); /* hold mode cannot catch a tap that raw polls missed */
    passed("hold is separate, finite from press, never banked by a long hold");
}
static void test_scope_loss(void) {
    setup("buffer", "6", 0, 1); pending_tap();
    tick(0); assert(poll(0) == 0); /* >2 VBlanks since last poll */
    setup("buffer", "6", 0, 1); pending_tap();
    poll_start(); cpu.gpr[31] = 0x800539D0u; cpu.gpr[29] = SP;
    hook(POLL); assert(remap_end(0) == 0); assert(poll(0) == 0);
    setup("buffer", "6", 0, 1); pending_tap();
    poll_start(); cpu.gpr[4] = 1; cpu.gpr[29] = SP; hook(POLL);
    assert(remap_end(0) == 0);
    passed("timeout, initialization/noncombat caller and unknown poll flag reset scope");
}
static void test_code_guards(void) {
    const uint32_t addresses[] = {POLL + 0x28u, REMAP + 0x10u,
                                 0x80010FC0u, 0x800539B8u, 0x8003FCB8u};
    for (unsigned i = 0; i < sizeof addresses / sizeof *addresses; i++) {
        setup("buffer", "6", 0, 1); pending_tap();
        const uint32_t old = peek(addresses[i]);
        put(addresses[i], old ^ 1u);
        assert(poll(0) == 0 && !ram_writes);
        put(addresses[i], old);
        assert(poll(0) == 0); /* correct code returns, old input does not */
    }
    setup("buffer", "6", 0, 1); pending_tap();
    const uint32_t old = peek(REMAP + 0x10u);
    poll_start(); put(REMAP + 0x10u, old ^ 1u);
    assert(remap_end(0) == 0 && !ram_writes);
    passed("complete poll/remap/PadRead and combat caller guards reject changed code");
}
static void test_context_guards(void) {
    const uint32_t pointers[] = {0x801FFFFDu, 0x80200000u, 0x80800000u, 0xA0200000u,
                                 0x1F800004u, EXP, 0x80001000u, SLOT + 4u};
    for (unsigned i = 0; i < sizeof pointers / sizeof *pointers; i++) {
        setup("buffer", "6", 0, 1); pending_tap(); poll_start();
        cpu.gpr[4] = pointers[i]; cpu.gpr[29] = SP - 0x20u; cpu.gpr[31] = 0x8003FD64u;
        hook(REMAP); assert(!ram_writes && poll(0) == 0);
    }
    setup("buffer", "6", 0, 1); pending_tap(); poll_start(); tick(0);
    assert(remap_end(0) == 0);
    setup("buffer", "6", 0, 1); pending_tap(); poll_start();
    cpu.gpr[4] = SLOT; cpu.gpr[29] = SP - 0x20u; cpu.gpr[31] = 0x8003FD68u;
    hook(REMAP); assert(!ram_writes);
    setup("buffer", "6", 0, 1); assert(remap_end(0) == 0 && !ram_writes);
    passed("bad RAM/alignment/stack/caller/late/standalone remap fail closed");
}
static void test_session_gates(void) {
    for (unsigned gate = 0; gate < 3; gate++) {
        setup("buffer", "6", 1, 1);
        if (gate == 0) online = 1;
        if (gate == 1) resim = 1;
        if (gate == 2) started = 0;
        tick(0x20); assert(poll(0) == 0);
        assert(!reads && !writes && !allocs && !sio_reads);
        online = resim = 0; started = 1;
        assert(poll(0) == 0);
        tick(0x20); tick(0);
        if (gate == 0) online = 1;
        if (gate == 1) resim = 1;
        if (gate == 2) started = 0;
        tick(0);
        online = resim = 0; started = 1;
        assert(poll(0) == 0 && !ram_writes);
    }
    passed("online, resimulation and pregame are inert and discard pending input");
}
static void test_transitions(void) {
    for (unsigned reason = 0; reason < 5; reason++) {
        setup("buffer", "6", 0, 1); pending_tap();
        if (reason == 0) tick(0x0800); /* START */
        if (reason == 1) tick(0x01000000u); /* SELECT p2 */
        if (reason == 2) { *mem(0x8003BC7Eu, 1) = 1; tick(0); }
        if (reason == 3) restore();
        if (reason == 4) {
            plugins[1].selected = 0; tick(0x20); tick(0);
            plugins[1].selected = 1; plugins[1].activate();
        }
        physical(0); assert(poll(0) == 0 && !ram_writes);
    }
    /* Releasing a menu button is NOT proof of leaving pause. Stay suspended
     * even if that screen keeps the combat input helper alive. */
    setup("buffer", "6", 0, 1); pending_tap(); tick(0x0800);
    physical(0); assert(poll(0) == 0); tick(0x20); tick(0);
    assert(poll(0) == 0 && !ram_writes);
    const uint32_t code = peek(REMAP + 0x10u);
    put(REMAP + 0x10u, code ^ 1u); tick(0); put(REMAP + 0x10u, code);
    pending_tap(); assert(poll(0) == 0x20);
    passed("START/SELECT, swap, restore and deactivation/reactivation discard queue");
}
static void test_pad_disconnect(void) {
    for (unsigned reason = 0; reason < 2; reason++) {
        setup("buffer", "6", 0, 1); pending_tap();
        if (reason == 0) *mem(0x8003BC00u, 1) = 0xFF;
        else *mem(0x8003BC01u, 1) = 0x73;
        assert(poll(0) == 0 && !ram_writes);
        *mem(0x8003BC00u, 1) = 0; *mem(0x8003BC01u, 1) = 0x41;
        assert(poll(0) == 0);
    }
    passed("unready/disconnected and unsupported pad protocols stay stock");
}
static void test_options(void) {
    const char* invalid[] = {"", "0", "7", "-1", "2junk", "999999999999"};
    for (unsigned i = 0; i < sizeof invalid / sizeof *invalid; i++) {
        setup("buffer", invalid[i], 0, 1); pending_tap();
        assert(poll(0) == 0 && !reads && !writes && !sio_reads);
    }
    setup("invalid", "2", 0, 1); pending_tap();
    assert(!reads && !writes);
    setup("buffer", "6", 0, 1); pending_tap();
    assert(plugins[1].changed("mode", "original") == 1);
    reads = writes = sio_reads = 0;
    tick(0x20); assert(poll(0) == 0);
    assert(!reads && !writes && !sio_reads);
    assert(plugins[1].changed("mode", "buffer") == 1);
    physical(0); assert(poll(0) == 0);
    for (unsigned i = 0; i < sizeof invalid / sizeof *invalid; i++)
        assert(!plugins[1].changed("window", invalid[i]));
    assert(!plugins[1].changed("mode", "typo"));
    online = 1; assert(!plugins[1].changed("mode", "hold")); online = 0;
    tick(0x20); tick(0); assert(poll(0) == 0x20); /* refused changes did not apply */
    setup("hold", "6", 0, 1); mode_option = window_option = NULL;
    plugins[1].activate(); pending_tap(); assert(poll(0) == 0x20); /* default buffer */
    passed("strict options, live Original, rejected live edits, fresh activation defaults");
}
static void test_trace(void) {
    setup(NULL, NULL, 1, 0);
    tick(0x20); assert(!allocs && !reads && !writes);
    put(0x800A9CE8u, 0x00000020u); put(0x800AA198u, 0x00400000u);
    assert(poll(0) == 0); assert(allocs == 1 && !ram_writes);
    assert(peek(EXP) == 0x42464244u && peek(EXP+4) == 2);
    assert(peek(EXP+8) == 4096 && peek(EXP+12) == 32);
    assert(peek(EXP+24) == 1 && peek(EXP+28) == 0);
    assert(peek(EXP + 32u + 6u*4u) == 0x20u);
    assert(peek(EXP + 32u + 7u*4u) == 0x00400000u);
    for (unsigned i = 0; i < 10; i++) { restore(); assert(poll(0) == 0); }
    assert(allocs == 1); /* restoring an existing ring does not leak allocations */
    for (unsigned i = 0; i < 2200; i++) { tick(i & 1 ? 0 : 0x20); assert(poll(0) == 0); }
    assert(peek(EXP+16) > 4096 && !ram_writes);
    setup("buffer", "2", 1, 1); alloc_fail = 1;
    pending_tap(); assert(poll(0) == 0x20 && ram_writes == 1);
    assert(allocs == 1); /* trace failure latched, input independent */
    passed("trace lazily allocates, initializes/wraps ring, failure isolated from input");
}
static void sequence(const char* mode, int trace, int input, int reversed) {
    setup(mode, "2", trace, input); reverse_order = reversed;
    uint32_t rng = 0x12345678u;
    for (unsigned frame = 0; frame < 160; frame++) {
        rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
        const uint32_t raw = rng & 0x00FF00FFu;
        tick(raw);
        if (!(frame & 1)) {
            scratch_pad = peek(SLOT);
            const uint32_t result = poll(raw);
            output_stream[frame / 2] = result;
        }
    }
}
static void test_parity_and_determinism(void) {
    sequence("original", 0, 0, 0);
    memcpy(reference_ram, ram, sizeof ram);
    memcpy(reference_stream, output_stream, sizeof output_stream);
    sequence("original", 0, 1, 0);
    assert(!memcmp(reference_ram, ram, sizeof ram));
    assert(!memcmp(reference_stream, output_stream, sizeof output_stream));
    assert(!reads && !writes && !allocs);
    sequence("buffer", 1, 1, 0);
    memcpy(reference_ram, ram, sizeof ram);
    memcpy(reference_stream, output_stream, sizeof output_stream);
    memcpy(reference_expansion, expansion, sizeof expansion);
    const uint32_t delivered = count("dbfb.responsive.delivered_button");
    assert(delivered > 0);
    sequence("buffer", 1, 1, 0);
    assert(!memcmp(reference_ram, ram, sizeof ram));
    assert(!memcmp(reference_stream, output_stream, sizeof output_stream));
    assert(!memcmp(reference_expansion, expansion, sizeof expansion));
    assert(delivered == count("dbfb.responsive.delivered_button"));
    sequence("buffer", 1, 1, 1);
    assert(!memcmp(reference_ram, ram, sizeof ram));
    assert(!memcmp(reference_stream, output_stream, sizeof output_stream));
    sequence("buffer", 0, 1, 0);
    assert(!memcmp(reference_ram, ram, sizeof ram));
    assert(!memcmp(reference_stream, output_stream, sizeof output_stream));
    passed("160-frame A/B Original byte parity, repeated trace parity, hook-order independence");
}

int main(void) {
#ifdef _WIN32
    assert(_setmode(_fileno(stdin), _O_BINARY) != -1);
#endif
    /* Private fixture stream: count, then (physical addr, byte count, bytes). */
    uint32_t blocks;
    assert(fread(&blocks, 4, 1, stdin) == 1 && blocks == 4);
    for (uint32_t i = 0; i < blocks; i++) {
        uint32_t addr, size;
        assert(fread(&addr, 4, 1, stdin) == 1 && fread(&size, 4, 1, stdin) == 1);
        assert(addr < sizeof ram && size <= sizeof ram - addr);
        assert(fread(ram + addr, 1, size, stdin) == size);
    }
    memcpy(original_ram, ram, sizeof ram);
    assert(plugins[0].activate && plugins[0].restore && plugins[0].poll && plugins[0].remap);
    assert(plugins[1].activate && plugins[1].restore && plugins[1].poll && plugins[1].remap);
    assert(plugins[0].vblank && plugins[1].vblank && plugins[1].changed);
    assert(!reads && !writes && !allocs);
    passed("constructor registers independent plan-owned callbacks without guest effects");
    test_original(); test_capture_once(); test_no_duplicate(); test_mask_ports_swap();
    test_lifetime(); test_release_before_retrigger(); test_hold(); test_scope_loss();
    test_code_guards(); test_context_guards(); test_session_gates(); test_transitions();
    test_pad_disconnect(); test_options(); test_trace(); test_parity_and_determinism();
    printf("%u C scenario groups passed\n", tests);
    return 0;
}
