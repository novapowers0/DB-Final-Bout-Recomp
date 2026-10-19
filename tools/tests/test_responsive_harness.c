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
#define EXP_SIZE 0x180000u

typedef struct Plugin {
    PSXModActivationCallback activate, restore;
    PSXModVBlankCallback vblank;
    PSXModFunctionEntryCallback poll, remap;
    PSXModOptionChangedCallback changed;
    int selected;
} Plugin;
#define PLUGIN_COUNT 7
static Plugin plugins[PLUGIN_COUNT];
static uint8_t ram[0x200000], original_ram[0x200000], expansion[EXP_SIZE];
static uint8_t reference_ram[0x200000], reference_expansion[EXP_SIZE];
static uint32_t output_stream[80], reference_stream[80];
static uint32_t scratch_pad;
static uint16_t pads[2];
static uint32_t reads, writes, ram_writes, allocs, sio_reads, last_write, exp_used;
static int started = 1, online, resim, alloc_fail, reverse_order;
static const char *mode_option, *window_option;
static CPUState cpu;
static PSXModFunctionEntryCallback command_hook, damage_hook, ai_hook, locomotion_hook, camera_hook;
static PSXModFunctionFilterCallback script_filter, animation_filter;
static struct { const char* name; uint32_t value; } counters[64];
static unsigned counter_count, tests;

static unsigned id_index(const char* id) {
    if (!strcmp(id, "dbfb.responsive.trace")) return 0;
    if (!strcmp(id, "dbfb.responsive.input-buffer")) return 1;
    if (!strcmp(id, "dbfb.responsive.ki-economy")) return 2;
    if (!strcmp(id, "dbfb.responsive.speed-scale")) return 3;
    if (!strcmp(id, "dbfb.responsive.chain-window")) return 4;
    if (!strcmp(id, "dbfb.responsive.standard")) return 5;
    assert(!strcmp(id, "dbfb.responsive.unlock-all"));
    return 6;
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
int psx_mod_register_instruction_plugin(const char* id, uint32_t addr, uint32_t expected,
                                       PSXModFunctionEntryCallback cb) {
    assert(!strcmp(id, "dbfb.responsive.standard"));
    if (addr == 0x80054A60u) { assert(expected == 0x84242856u); ai_hook = cb; }
    else if (addr == 0x80054AE8u) { assert(expected == 0x02C02021u); command_hook = cb; }
    else if (addr == 0x80067A68u) { assert(expected == 0x02020018u); locomotion_hook = cb; }
    else if (addr == 0x80054F88u) { assert(expected == 0x3C04800Bu); camera_hook = cb; }
    else if (addr == 0x8004F5A0u) { assert(expected == 0xA462FFE4u); }
    else if (addr == 0x800592A8u || addr == 0x800592FCu) { assert(expected == 0x00021200u); }
    else { assert(addr == 0x80066D28u && expected == 0x1C400002u); damage_hook = cb; }
    return 1;
}
int psx_mod_register_function_filter_plugin(const char* id, uint32_t addr,
                                           PSXModFunctionFilterCallback cb) {
    assert(!strcmp(id, "dbfb.responsive.standard"));
    if (addr == 0x8004E530u) script_filter = cb;
    else { assert(addr == 0x80042240u); animation_filter = cb; }
    return 1;
}
int psx_mod_game_started(void) { return started; }
int psx_netplay_active(void) { return online; }
int psx_netplay_is_resimulating(void) { return resim; }
int psx_mod_option_value(const char* package, const char* feature, const char* option,
                         char* out, uint32_t size) {
    assert(!strcmp(package, "dbfb.responsive"));
    if (strcmp(feature, "input-buffer")) { if (size) out[0] = 0; return 0; }
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
    assert(counter_count < 64);
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
uint16_t psx_mod_read_half(uint32_t addr) {
    uint16_t value; reads++; memcpy(&value, mem(addr, 2), 2); return value;
}
void psx_mod_write_half(uint32_t addr, uint16_t value) {
    assert(!(addr & 1));
    assert((addr >= 0x800A870Cu && addr < 0x800A8724u) ||
           addr == 0x80072842u || addr == 0x800728BEu ||
           addr == 0x80072904u || addr == 0x80072934u ||
           addr == 0x80072856u || addr == 0x800728D2u ||
           addr == 0x800728FCu || addr == 0x8007292Cu ||
           addr == 0x8007291Au || addr == 0x8007294Au);
    writes++; ram_writes++; last_write = addr;
    memcpy(mem(addr, 2), &value, 2);
}
void psx_mod_write_code_word(uint32_t addr, uint32_t value) {
    assert((addr == 0x80054AD8u && (value == 0x2402FFFFu || value == 0x00801021u)) ||
           (addr == 0x80054AC0u && value == 0x2C42000Cu));
    writes++; ram_writes++; last_write = addr; put(addr, value);
}
uint32_t psx_mod_read_word(uint32_t addr) { reads++; return peek(addr); }
void psx_mod_write_word(uint32_t addr, uint32_t word) {
    assert(!(addr & 3)); writes++; last_write = addr;
    if ((addr & 0x1FFFFFFFu) < sizeof ram) {
        ram_writes++;
        const uint32_t phys = addr & 0x1FFFFFFFu;
        assert(addr == SLOT || addr == SP+0x10u || addr == SP+0x14u ||
               (phys >= 0x07C3FCu && phys < 0x07C99Cu && (phys-0x07C3FCu)%20u == 0) ||
               phys == 0x06F794u || phys == 0x06F798u ||
               phys == 0x072800u || phys == 0x07287Cu ||
               phys == 0x07EF3Cu || phys == 0x07EF40u ||
               phys == 0x0A8664u || phys == 0x0A8668u || phys == 0x0A866Cu ||
               phys == 0x07281Cu || phys == 0x072824u ||
               phys == 0x07282Cu || phys == 0x072834u ||
               phys == 0x072898u || phys == 0x0728A0u ||
               phys == 0x0728A8u || phys == 0x0728B0u ||
               phys == 0x180018u || phys == 0x180020u ||
               phys == 0x180040u || phys == 0x180048u ||
               phys == 0x0A9FF0u || phys == 0x0A9FF4u || phys == 0x0A9FF8u ||
               phys == 0x03BCC4u); /* lui 8004 + signed -433c */
    }
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
    for (unsigned n = 0; n < PLUGIN_COUNT; n++) {
        Plugin* p = &plugins[reverse_order ? PLUGIN_COUNT - 1 - n : n];
        PSXModFunctionEntryCallback cb = addr == POLL ? p->poll : p->remap;
        if (p->selected && cb) cb(&cpu, addr);
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
    for (unsigned n = 0; n < PLUGIN_COUNT; n++) {
        Plugin* p = &plugins[reverse_order ? PLUGIN_COUNT - 1 - n : n];
        if (p->selected && p->vblank) p->vblank();
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
    for (unsigned n = 0; n < PLUGIN_COUNT; n++)
        if (plugins[n].selected && plugins[n].restore) plugins[n].restore();
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
    for (unsigned n = 2; n < PLUGIN_COUNT; n++) plugins[n].selected = 0;
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

static void rule_setup(unsigned rule, const char* mode) {
    setup(NULL, NULL, 0, 0);
    plugins[rule].selected = 1;
    plugins[rule].activate();
    assert(plugins[rule].changed("mode", mode));
}

static uint16_t half(uint32_t addr) {
    uint16_t value; memcpy(&value, mem(addr, 2), 2); return value;
}
static void put_half(uint32_t addr, uint16_t value) { memcpy(mem(addr, 2), &value, 2); }

static void test_rule_defaults(void) {
    setup(NULL, NULL, 0, 0);
    for (unsigned n = 2; n < 5; n++) {
        plugins[n].selected = 1; plugins[n].activate();
    }
    for (unsigned n = 0; n < 8; n++) { tick(0); poll(0); }
    assert(!reads && !writes && !allocs && !sio_reads);
    passed("all rule defaults: zero guest effects, independently registered callbacks");
}

static void test_ki_economy(void) {
    for (unsigned period = 1; period <= 8; period++) {
        rule_setup(2, "flow");
        char option[] = {(char)('0' + period), 0};
        assert(plugins[2].changed("period", option));
        put(0x80072840u, 0x00140055u); /* HP adjacent to ki must survive */
        put(0x800728BCu, 0x00C30066u);
        for (unsigned n = 1; n < period; n++) poll_start();
        assert(half(0x80072842u) == 20 && !writes);
        poll_start();
        assert(peek(0x80072840u) == 0x00150055u);
        assert(peek(0x800728BCu) == 0x00C40066u);
        for (unsigned n = 0; n < period; n++) poll_start();
        assert(half(0x800728BEu) == 196);
        put_half(0x80072842u, 0xFFFFu);
        put_half(0x800728BEu, 197);
        const uint32_t before = writes;
        for (unsigned n = 0; n < period * 2; n++) poll_start();
        assert(writes == before); /* negative sentinel and out-of-range untouched */
    }
    assert(!plugins[2].changed("period", "0"));
    assert(!plugins[2].changed("period", "9"));
    assert(!plugins[2].changed("period", "2junk"));
    assert(!plugins[2].changed("mode", "typo"));
    passed("ki periods 1..8, symmetric gains, cap, sentinels and adjacent HP preserved");
}

static void test_rule_guards(void) {
    const char* modes[] = {"flow", "150", "open"};
    for (unsigned rule = 2; rule < 5; rule++) {
        for (unsigned reason = 0; reason < 7; reason++) {
            rule_setup(rule, modes[rule - 2]);
            if (reason == 0) online = 1;
            if (reason == 1) resim = 1;
            if (reason == 2) started = 0;
            if (reason == 3) put(POLL + 0x28u, peek(POLL + 0x28u) ^ 1u);
            if (reason == 4) physical(0x0800);
            if (reason == 5) physical(0x01000000u);
            if (reason == 6) {
                put(rule == 2 ? 0x8006D1DCu : rule == 3 ? 0x800666ECu : 0x80054AD4u, 0);
            }
            for (unsigned n = 0; n < 4; n++) poll_start();
            assert(!writes);
            if (reason == 4 || reason == 5) {
                physical(0);
                for (unsigned n = 0; n < 4; n++) poll_start();
                assert(!writes); /* releasing START is not permission to resume */
            }
        }
        rule_setup(rule, modes[rule - 2]);
        memset(&cpu, 0, sizeof cpu); cpu.gpr[31] = 0x800539D0u;
        hook(POLL); assert(!writes);
        cpu.gpr[31] = 0x8003FCBCu; cpu.gpr[4] = 1;
        hook(POLL); assert(!writes);
        online = 1; assert(!plugins[rule].changed("mode", "original"));
        online = 0; resim = 1; assert(!plugins[rule].changed("mode", "original"));
    }
    passed("each rule refuses online/resim/pregame, wrong code/caller/flag and paused polls");
}

static void test_speed_scale(void) {
    rule_setup(3, "150");
    put(0x80072904u, 0xABCD0000u);
    put(0x80072934u, 0xDCBA0000u);
    poll_start(); /* baseline */
    put_half(0x80072904u, 100);
    put_half(0x80072934u, (uint16_t)-100);
    poll_start();
    assert(peek(0x80072904u) == 0xABCD0096u);
    assert(peek(0x80072934u) == 0xDCBAFF6Au);
    const uint32_t before = writes;
    for (unsigned n = 0; n < 20; n++) poll_start();
    assert(writes == before); /* no exponential accumulation */
    assert(plugins[3].changed("mode", "125")); poll_start();
    assert(half(0x80072904u) == 125 && (int16_t)half(0x80072934u) == -125);
    assert(plugins[3].changed("mode", "75")); poll_start();
    assert(half(0x80072904u) == 75 && (int16_t)half(0x80072934u) == -75);
    assert(plugins[3].changed("mode", "original")); poll_start();
    assert(half(0x80072904u) == 100 && (int16_t)half(0x80072934u) == -100);
    reads = writes = sio_reads = 0; poll_start();
    assert(!reads && !writes && !sio_reads);
    assert(plugins[3].changed("mode", "150")); poll_start();
    put_half(0x80072904u, 30000); put_half(0x80072934u, (uint16_t)-30000);
    poll_start();
    assert(half(0x80072904u) == 32767 && (int16_t)half(0x80072934u) == -32767);
    restore(); reads = writes = 0; poll_start();
    assert(!writes); /* restored RAM is re-baselined, never scaled twice */
    assert(!plugins[3].changed("mode", "200"));
    passed("speed signs, saturation, no accumulation, live rescale/Original and save restore");
}

static void test_chain_window(void) {
    rule_setup(4, "open");
    assert(!writes); /* live change waits for verified combat */
    poll_start(); assert(peek(0x80054AD8u) == 0x00801021u && writes == 1);
    poll_start(); assert(writes == 1);
    assert(plugins[4].changed("mode", "original"));
    assert(peek(0x80054AD8u) == 0x2402FFFFu && writes == 2);
    reads = writes = sio_reads = 0; poll_start();
    assert(!reads && !writes && !sio_reads);
    assert(plugins[4].changed("mode", "open")); poll_start();
    put(0x80054AD8u, 0x2402FFFFu); poll_start(); /* overlay reload */
    assert(peek(0x80054AD8u) == 0x00801021u);
    restore(); poll_start(); /* savestate retained patched word */
    assert(plugins[4].changed("mode", "original"));
    assert(peek(0x80054AD8u) == 0x2402FFFFu);
    put(0x80054AD8u, 0x00801021u); /* old save made in Open, now Original */
    restore(); assert(peek(0x80054AD8u) == 0x2402FFFFu);
    put(0x80054AD8u, 0xDEADBEEFu);
    assert(plugins[4].changed("mode", "open")); poll_start();
    assert(peek(0x80054AD8u) == 0xDEADBEEFu);
    assert(!plugins[4].changed("mode", "typo"));
    passed("chain deferred apply, idempotence, Original restore, reload and unknown-word refusal");
}

static void standard_setup(void) {
    setup(NULL, NULL, 0, 0);
    plugins[5].selected = 1;
    assert(plugins[5].activate && plugins[5].vblank && plugins[5].restore &&
           plugins[5].poll && plugins[5].remap && !plugins[5].changed);
    plugins[5].activate();
}

static void standard_step(void) { tick(0); tick(0); poll(0); }

static void test_standard_profile(void) {
    standard_setup();
    assert(!reads && !writes && !allocs); /* one activation, no option configuration */
    put_half(0x80072842u, 20); put_half(0x800728BEu, 20);
    poll(0);
    put_half(0x80072904u, 100); put_half(0x80072934u, (uint16_t)-100);
    standard_step();
    assert(half(0x80072904u) == 100 && (int16_t)half(0x80072934u) == -100);
    standard_step(); standard_step();
    assert(half(0x80072842u) == 21 && half(0x800728BEu) == 21);
    assert(peek(0x80054AC0u) == 0x2C42000Cu);
    assert(peek(0x80054AD8u) == 0x2402FFFFu); /* no unconditional cancel patch */
    assert(count("dbfb.responsive.standard_chain_patch") == 1);
    const uint32_t gains = count("dbfb.responsive.ki_gain");
    for (unsigned n = 0; n < 12; n++) poll(0); /* duplicate hooks in same frame */
    assert(count("dbfb.responsive.ki_gain") == gains);
    /* The original SLTIU gate still closes at 12; only ticks 9..11 differ. */
    for (unsigned age = 0; age < 40; age++) {
        const int stock = age < (0x2C420009u & 0xFFFFu);
        const int standard = age < (peek(0x80054AC0u) & 0xFFFFu);
        assert(age >= 9 && age < 12 ? standard && !stock : standard == stock);
    }
    standard_setup();
    pending_tap(); assert(poll(0) == 0x20); tick(0); tick(0); assert(poll(0) == 0);
    passed("one-click standard: tap capture, native reaction velocity, symmetric ki and bounded chain gate");
}

static void test_standard_pause(void) {
    standard_setup(); pending_tap();
    put(0x800A868Cu, 1); /* native game pause, not just held START */
    const uint32_t before = writes;
    for (unsigned n = 0; n < 8; n++) { tick(n == 0 ? 0x0800 : 0); poll(0); }
    assert(writes == before);
    put(0x800A868Cu, 0); /* game has actually resumed */
    tick(0); assert(poll(0) == 0); /* no queued attack crosses pause */
    tick(0x20); tick(0); assert(poll(0) == 0x20); /* assistance resumes automatically */
    const uint32_t gains = count("dbfb.responsive.ki_gain");
    for (unsigned n = 0; n < 8; n++) standard_step();
    assert(count("dbfb.responsive.ki_gain") > gains);
    restore(); tick(0); assert(poll(0) == 0);
    passed("standard native pause: no writes or queued attack while paused, automatic resume");
}

static void test_standard_guards(void) {
    const uint32_t sites[] = {POLL + 0x28u, 0x8006A178u, 0x8006A180u,
        0x8006A2F8u, 0x800666ECu, 0x8006672Cu, 0x8006D1DCu, 0x80054AC0u,
        0x80054AD8u, 0x80054A60u};
    for (unsigned n = 0; n < sizeof sites / sizeof *sites; n++) {
        standard_setup();
        put(sites[n], peek(sites[n]) ^ 1u);
        for (unsigned i = 0; i < 8; i++) standard_step();
        assert(!writes && !allocs);
    }
    for (unsigned gate = 0; gate < 3; gate++) {
        standard_setup();
        if (gate == 0) online = 1;
        if (gate == 1) resim = 1;
        if (gate == 2) started = 0;
        standard_step(); assert(!reads && !writes && !allocs && !sio_reads);
    }
    standard_setup(); poll(0); /* first battle */
    put(0x80054AC0u, 0x2C420009u); /* next battle reloads stock overlay */
    standard_step(); assert(peek(0x80054AC0u) == 0x2C42000Cu);
    standard_setup(); /* new plan without standard */
    plugins[5].selected = 0; reads = writes = sio_reads = 0;
    standard_step(); assert(!reads && !writes && !sio_reads);
    passed("standard fails as a whole on unknown code, refuses online/resim, reloads and leaves no active flag");
}

static void test_fighter_trace(void) {
    setup(NULL, NULL, 1, 0);
    put(0x80072808u, 0x80000053u); put(0x80072804u, 0x20u);
    put(0x800728F8u, 0x80117880u); put(0x800728FCu, 0x00250004u);
    put(0x80072840u, 0x006400C8u); put_half(0x80072904u, (uint16_t)-100);
    put_half(0x8007291Au, 9);
    poll_start();
    const uint32_t record = EXP + 32u + 32u; /* after the input poll record */
    assert(peek(record + 4u) == 4);
    assert(peek(record + 8u) == 0x80000053u && peek(record + 12u) == 0x20u);
    assert(peek(record + 16u) == 0x80117880u && peek(record + 20u) == 0x00250004u);
    assert(peek(record + 24u) == 0x006400C8u && peek(record + 28u) == 0x0009FF9Cu);
    assert(peek(record + 32u + 4u) == 0x104u && !ram_writes);
    passed("read-only mechanical trace captures both fighters, action/script clocks, HP/ki and speed/gate");
}

static void command_call(unsigned side, int recognized) {
    cpu.gpr[22] = side; cpu.gpr[23] = side*0x7Cu; cpu.gpr[4] = (uint32_t)recognized;
    const CPUState before = cpu;
    command_hook(&cpu, 0x80054AE8u);
    assert(!memcmp(&cpu, &before, sizeof cpu));
}
static void command_fighter(unsigned p, unsigned action) {
    const uint32_t c = 0x80072800u+p*0x7Cu;
    put(c+8u, 0x80000000u | action); put(c+4u, 0x20);
    put_half(c+0x40u, 100); put_half(c+0x42u, 100); put_half(c+0x56u, 0xFFFFu);
    put_half(0x8007291Au+p*0x30u, 20);
}
static void test_command_recovery(void) {
    assert(command_hook && damage_hook && ai_hook);
    for (unsigned p = 0; p < 2; p++) {
        standard_setup(); poll(0); command_fighter(p, 0x64);
        const uint32_t c = 0x80072800u+p*0x7Cu;
        command_call(p, 0x22); assert(half(c+0x56u) == 0xFFFFu);
        standard_step(); command_call(p, -1); assert(half(c+0x56u) == 0xFFFFu);
        put(c+4u, 0); command_call(p, -1); assert(half(c+0x56u) == 0x22);
        put_half(c+0x56u, 0xFFFFu); command_call(p, -1);
        assert(half(c+0x56u) == 0xFFFFu); /* once only */
        put(c+4u, 0x20); command_call(p, 0x22);
        put(c+8u, 0x80000024u); command_call(p, -1); /* hit reaction cancels intent */
        put(c+8u, 0x80000064u); put(c+4u, 0); command_call(p, -1);
        assert(half(c+0x56u) == 0xFFFFu);
        put(c+4u, 0x20); command_call(p, 0x22); restore(); put(c+4u, 0);
        poll(0); command_call(p, -1); assert(half(c+0x56u) == 0xFFFFu);
        put(c+4u, 0x20); command_call(p, 0x22);
        for (unsigned n = 0; n < 3; n++) standard_step();
        put(c+4u, 0); command_call(p, -1); assert(half(c+0x56u) == 0xFFFFu);
        assert(count("dbfb.responsive.command_recovered") == 1);
    }
    passed("recognized-command recovery: both sides, bounded six-frame life, native busy gate, no stun escape or replay");
}
static void test_followup_window(void) {
    for (unsigned p = 0; p < 2; p++) {
        const uint32_t c = 0x80072800u+p*0x7Cu;
        /* Recorded failure: cmd25 in neutral falls through to CIRCLE/6A,
         * whose busy bit8 prevents the native UP producer during LIFE16.
         * Replace call inputs only, leaving native action/flags untouched. */
        standard_setup(); poll(0); command_fighter(p, 6);
        put(c+4u, 0); put(c, 0); put(c-4u, 0); put(c+0x10u, 0);
        put_half(c+0x56u, 0x25); cpu.gpr[29] = SP;
        put(SP+0x10u, 0x20); put(SP+0x14u, 0x20);
        command_call(p, 0x25);
        assert(peek(SP+0x10u) == 0x1000 && peek(SP+0x14u) == 0x1000);
        assert(peek(c+8u) == 0x80000006u && peek(c+4u) == 0 && peek(c) == 0);
        assert(count("dbfb.responsive.followup_lift") == 1);
        /* Native lift result, followed by single delivery through the slot. */
        put(c+8u, 0x8000001Du); put(c+4u, 0x20); put(c, 8);
        put_half(c+0x56u, 0xFFFFu); standard_step(); command_call(p, -1);
        assert(half(c+0x56u) == 0x25);
        assert(count("dbfb.responsive.followup_inject") == 1);
        /* Refuse busy/stun/air-context/unsupported ID/competing input/bad
         * stack and changed argument code. Never cancel an existing attack. */
        for (unsigned reason = 0; reason < 10; reason++) {
            standard_setup(); poll(0); command_fighter(p, 0);
            put(c+4u, 0); put(c, 0); put(c-4u, 0); put(c+0x10u, 0);
            put_half(c+0x56u, 0x25); cpu.gpr[29] = SP;
            put(SP+0x10u, 0x20); put(SP+0x14u, 0x20);
            if (reason == 0) put(c, 8);
            if (reason == 1) put(c+8u, 0x8000006Au);
            if (reason == 2) put(c+0x10u, 0x80000000u);
            if (reason == 3) put(c-4u, 3);
            if (reason == 4) put(SP+0x10u, 0x1020);
            if (reason == 5) put(SP+0x14u, 0x40);
            if (reason == 6) cpu.gpr[29] = 0x801FFFFCu;
            if (reason == 7) put(0x80054AECu, 0);
            if (reason == 8) put(c+8u, 0x80000024u);
            if (reason == 9) put_half(c+0x42u, 0xFFFFu);
            command_call(p, 0x25);
            assert(count("dbfb.responsive.followup_lift") == 0);
            assert(peek(SP+0x10u) == (reason == 4 ? 0x1020u : 0x20u));
            assert(peek(SP+0x14u) == (reason == 5 ? 0x40u : 0x20u));
        }
        /* A grounded gesture is retained, not queued, then injected once the
         * native airborne flag arms the handler. */
        standard_setup(); poll(0); command_fighter(p, 0x1D);
        put(c+4u, 0); command_call(p, 0x25);
        assert(half(c+0x56u) == 0xFFFFu); /* not queued while grounded */
        assert(count("dbfb.responsive.followup_wait") == 1);
        standard_step();
        put(c+4u, 0x20); command_call(p, -1);
        assert(half(c+0x56u) == 0x25u);    /* native slot gets the follow-up */
        assert(count("dbfb.responsive.followup_inject") == 1);
        put_half(c+0x56u, 0xFFFFu); command_call(p, -1);
        assert(half(c+0x56u) == 0xFFFFu);  /* delivered once only */
        /* Any other recognised command cancels the pending follow-up. */
        standard_setup(); poll(0); command_fighter(p, 0x1D);
        put(c+4u, 0); command_call(p, 0x25);
        command_call(p, 0x22);
        put(c+4u, 0x20); command_call(p, -1);
        assert(half(c+0x56u) == 0xFFFFu);
        assert(count("dbfb.responsive.followup_inject") == 0);
        /* A continuation action clears it. */
        standard_setup(); poll(0); command_fighter(p, 0x1D);
        put(c+4u, 0); command_call(p, 0x29);
        put(c+8u, 0x80000098u); command_call(p, -1);
        put(c+8u, 0x8000001Du); put(c+4u, 0x20); command_call(p, -1);
        assert(half(c+0x56u) == 0xFFFFu);
        /* Bounded life: expires if the airborne window never opens. */
        standard_setup(); poll(0); command_fighter(p, 0x1D);
        put(c+4u, 0); command_call(p, 0x25);
        for (unsigned n = 0; n < 8; n++) standard_step();
        put(c+4u, 0x20); command_call(p, -1);
        assert(half(c+0x56u) == 0xFFFFu);
        /* Native pause suspends and clears the pending follow-up. */
        standard_setup(); poll(0); command_fighter(p, 0x1D);
        put(c+4u, 0); command_call(p, 0x25);
        put(0x800A868Cu, 1);
        tick(0); tick(0); poll(0);
        put(c+4u, 0x20); command_call(p, -1);
        assert(half(c+0x56u) == 0xFFFFu);
        /* Online/resim never retains or injects. */
        standard_setup(); poll(0); command_fighter(p, 0x1D);
        online = 1;
        put(c+4u, 0); command_call(p, 0x25);
        put(c+4u, 0x20); command_call(p, -1);
        assert(half(c+0x56u) == 0xFFFFu);
        online = 0;
        /* Restore drops any pending follow-up. */
        standard_setup(); poll(0); command_fighter(p, 0x1D);
        put(c+4u, 0); command_call(p, 0x25);
        restore(); put(c+4u, 0x20); command_call(p, -1);
        assert(half(c+0x56u) == 0xFFFFu);
    }
    passed("aerial follow-up: grounded gesture retained and injected once when "
           "airborne, cancelled by another command/continuation, bounded, both "
           "sides, pause/online/restore guarded");
}
static void test_standard_damage(void) {
    for (unsigned p = 0; p < 2; p++) {
        standard_setup(); poll(0); command_fighter(p, 0x64);
        cpu.gpr[16] = p; cpu.gpr[18] = p ^ 1u; cpu.gpr[17] = 100;
        damage_hook(&cpu, 0x80066D28u);
        assert(cpu.gpr[17] == 100 && cpu.gpr[2] == (100u << 16));
        put(0x80072808u+p*0x7Cu, 0x80000072u); cpu.gpr[17] = 100;
        damage_hook(&cpu, 0x80066D28u); assert(cpu.gpr[17] == 100);
        cpu.gpr[17] = 1; damage_hook(&cpu, 0x80066D28u); assert(cpu.gpr[17] == 1);
        put(0x80072808u+p*0x7Cu, 0x80000078u); cpu.gpr[17] = 100;
        damage_hook(&cpu, 0x80066D28u); assert(cpu.gpr[17] == 100);
        put(0x80072808u+p*0x7Cu, 0x80000064u); online = 1;
        reads = writes = 0; damage_hook(&cpu, 0x80066D28u);
        assert(cpu.gpr[17] == 100 && !reads && !writes);
    }
    passed("damage before motion publication stays stock: both sides, normals/ki, native minimum, cinematics, online inert");
}

static void combat_fighter(unsigned p, unsigned action, int hp, int maxhp) {
    const uint32_t c = 0x80072800u+p*0x7Cu;
    put(c+8u, 0x80000000u | action); put(c+4u, 0);
    put_half(c+0x3Eu, (uint16_t)maxhp); put_half(c+0x40u, (uint16_t)hp);
    put_half(c+0x42u, 100); put_half(c+0x56u, 0xFFFFu);
    put_half(0x8007291Au+p*0x30u, 20);
}
static void combat_place(int32_t ax, int32_t az, int32_t dx, int32_t dz) {
    put(0x8007281Cu, (uint32_t)ax); put(0x80072824u, (uint32_t)az);
    put(0x8007282Cu, (uint32_t)ax); put(0x80072834u, (uint32_t)az);
    put(0x80072898u, (uint32_t)dx); put(0x800728A0u, (uint32_t)dz);
    put(0x800728A8u, (uint32_t)dx); put(0x800728B0u, (uint32_t)dz);
    put(0x800A86A4u, 0x80180000u); put(0x800A86A8u, 0x80180028u);
    put(0x80180018u, (uint32_t)ax); put(0x80180020u, (uint32_t)az);
    put(0x80180040u, (uint32_t)dx); put(0x80180048u, (uint32_t)dz);
}
static void hit(int damage, uint32_t params) {
    cpu.gpr[16] = 0; cpu.gpr[18] = 1; cpu.gpr[17] = (uint32_t)damage; cpu.gpr[5] = params;
    damage_hook(&cpu, 0x80066D28u);
}
static int32_t locomote(unsigned side, int32_t delta) {
    cpu.gpr[18] = side; cpu.gpr[16] = (uint32_t)delta;
    CPUState expected = cpu;
    const unsigned before = writes;
    locomotion_hook(&cpu, 0x80067A68u);
    expected.gpr[16] = cpu.gpr[16];
    assert(!memcmp(&cpu, &expected, sizeof cpu) && writes == before);
    return (int32_t)cpu.gpr[16];
}
static void test_locomotion(void) {
    assert(locomotion_hook);
    for (unsigned side = 0; side < 2; side++) {
        for (int sign = -1; sign <= 1; sign += 2) {
            standard_setup();
            combat_fighter(0, 3, 100, 100); combat_fighter(1, 3, 100, 100);
            poll(0);
            assert(locomote(side, sign*100) == sign*40);
            assert(locomote(side, sign*100) == sign*40); /* same VBlank */
            tick(0); poll(0); assert(locomote(side, sign*100) == sign*80);
            tick(0); poll(0); assert(locomote(side, sign*100) == sign*120);
            tick(0); poll(0); assert(locomote(side, sign*100) == sign*125);
            /* Neutral brakes in two active VBlanks, then stays still. */
            combat_fighter(side, 0, 100, 100);
            tick(0); poll(0); assert(locomote(side, 0) == sign*61);
            tick(0); poll(0); assert(locomote(side, 0) == 0);
            tick(0); poll(0); assert(locomote(side, 0) == 0);
            combat_fighter(side, 3, 100, 100);
            tick(0); poll(0); assert(locomote(side, sign*100) == sign*40);
            /* Pause, state restore, reactions, KO and discontinuities never
             * carry a stored velocity into another action or timeline. */
            put(0x800A868Cu, 1); assert(locomote(side, sign*100) == sign*100);
            put(0x800A868Cu, 0); tick(0); poll(0);
            assert(locomote(side, sign*100) == sign*40);
            combat_fighter(side, 0x24, 100, 100); tick(0); poll(0);
            assert(locomote(side, sign*100) == sign*100);
            combat_fighter(side, 3, 0, 100); tick(0); poll(0);
            assert(locomote(side, sign*100) == sign*100);
            combat_fighter(side, 3, 100, 100); tick(0); poll(0);
            assert(locomote(side, sign*1000) == sign*1000);
            restore(); poll(0);
            assert(locomote(side, sign*100) == sign*40);
            online = 1; reads = 0;
            assert(locomote(side, sign*100) == sign*100 && !reads);
        }
    }
    passed("self-locomotion: signed/both sides, VBlank acceleration, braking, native projection only, pause/KO/restore guards");
}
static void camera_setup(void) {
    standard_setup();
    combat_fighter(0, 3, 100, 100); combat_fighter(1, 3, 100, 100);
    poll(0);
    put(0x80054F88u, 0x3C04800Bu);
    put(0x800A9D0Cu, 0x800A9FA0u);
    put(0x800AA194u, 1u);
    put(0x800A868Cu, 0u);
    put(0x800A9FA0u, 0u);
    for (unsigned i = 0; i < 6u; i++) put(0x800A9FA0u+0xB0u+i*4u, 0u);
    /* eye = target - (100, 0, 0): the native offset is scaled 17/16. */
    put(0x800A9FA0u+0x50u, 0u); put(0x800A9FA0u+0x54u, 0u); put(0x800A9FA0u+0x58u, 0u);
    put(0x800A9FA0u+0x5Cu, 100u); put(0x800A9FA0u+0x60u, 0u); put(0x800A9FA0u+0x64u, 0u);
}
static void test_camera_framing(void) {
    assert(camera_hook);
    camera_setup();
    const unsigned before = count("dbfb.responsive.camera_framing");
    camera_hook(&cpu, 0x80054F88u);
    assert(peek(0x800A9FA0u+0x50u) == (uint32_t)-6); /* 100 - 106 */
    assert(peek(0x800A9FA0u+0x54u) == 0u && peek(0x800A9FA0u+0x58u) == 0u);
    assert(peek(0x800A9FA0u+0x5Cu) == 100u); /* target untouched */
    assert(count("dbfb.responsive.camera_framing") == before+1u);
    /* Every gate rejects BEFORE any guest write. */
    const unsigned writes_before = writes;
    put(0x800AA194u, 2u); camera_hook(&cpu, 0x80054F88u); assert(writes == writes_before);
    put(0x800AA194u, 1u); put(0x800A868Cu, 1u); camera_hook(&cpu, 0x80054F88u);
    assert(writes == writes_before);
    put(0x800A868Cu, 0u); put(0x800A9FA0u, 1u); camera_hook(&cpu, 0x80054F88u);
    assert(writes == writes_before);
    put(0x800A9FA0u, 0u); put(0x800A9FA0u+0xB0u, 4u); camera_hook(&cpu, 0x80054F88u);
    assert(writes == writes_before);
    put(0x800A9FA0u+0xB0u, 0u); put(0x80054F88u, 0u); camera_hook(&cpu, 0x80054F88u);
    assert(writes == writes_before);
    put(0x80054F88u, 0x3C04800Bu);
    online = 1; camera_hook(&cpu, 0x80054F88u);
    assert(writes == writes_before); online = 0;
    put(0x800A9FA0u+0x5Cu, 0x7FFFFFFFu); camera_hook(&cpu, 0x80054F88u);
    assert(writes == writes_before && peek(0x800A9FA0u+0x50u) == (uint32_t)-6);
    put(0x800A9FA0u+0x5Cu, 100u);
    assert(count("dbfb.responsive.camera_framing") == before+1u);
    passed("camera framing: native delivery seam, offset-only scale, target intact, mode/lock/transition/KO/pause/online/out-of-bounds reject");
}
static void test_defence(void) {
    standard_setup(); combat_fighter(0, 0x78, 100, 1000); poll(0);
    combat_fighter(1, 0x22, 1000, 1000); combat_place(0, 0, 1000, 0);
    hit(10, 0x40400000u);
    assert(cpu.gpr[17] == 10 && count("dbfb.responsive.guard_block") == 1);
    assert(count("dbfb.responsive.guard_break") == 0);
    /* Just guard: the guard action was already visible at the verified poll. */
    standard_setup(); combat_fighter(0, 0x78, 100, 1000);
    combat_fighter(1, 0x22, 1000, 1000); combat_place(0, 0, 1000, 0); poll(0);
    hit(10, 0x40400000u);
    assert(cpu.gpr[17] == 5 && count("dbfb.responsive.just_guard") == 1);
    assert(half(0x800728BEu) == 102); /* symmetric ki reward, capped */
    /* A perfect-guard stance (native zero divisor) never invents damage. */
    standard_setup(); combat_fighter(0, 0x78, 100, 1000);
    combat_fighter(1, 0x22, 1000, 1000); combat_place(0, 0, 1000, 0); poll(0);
    hit(10, 0x00400000u);
    assert(cpu.gpr[17] == 10 && count("dbfb.responsive.guard_perfect") == 1);
    /* Low bit 14 is unrelated to native half-damage (LUI 0x4000 = bit 30). */
    standard_setup(); combat_fighter(0, 0x78, 100, 1000);
    combat_fighter(1, 0x22, 1000, 1000); poll(0);
    hit(10, 0x00404000u);
    assert(cpu.gpr[17] == 10 && count("dbfb.responsive.guard_perfect") == 1);
    /* The signed parameter branch divides by four, not two. */
    standard_setup(); combat_fighter(0, 0x78, 100, 1000);
    combat_fighter(1, 0x22, 1000, 1000); poll(0);
    hit(12, 0x80400000u);
    assert(cpu.gpr[17] == 12 && count("dbfb.responsive.just_guard") == 1);
    /* Guard break: full damage and the native zero branch is opened. */
    standard_setup(); combat_fighter(0, 0x78, 100, 100);
    combat_fighter(1, 0x22, 100, 100); combat_place(0, 0, 1000, 0); poll(0);
    for (unsigned n = 0; n < 8; n++) tick(0);
    poll(0);
    hit(30, 0x00400000u);
    assert(cpu.gpr[17] == 60 && (cpu.gpr[5] & 0x40000000u));
    assert(count("dbfb.responsive.guard_break") == 1);
    /* Sustained pressure breaks after the guard meter threshold. */
    standard_setup(); combat_fighter(0, 0x78, 100, 1000);
    combat_fighter(1, 0x22, 1000, 1000); combat_place(0, 0, 1000, 0); poll(0);
    for (unsigned n = 0; n < 8; n++) tick(0);
    poll(0);
    for (unsigned n = 0; n < 3; n++) { hit(100, 0x40400000u); standard_step(); }
    assert(count("dbfb.responsive.guard_break") == 1);
    /* Timed defence must survive pressure that would break an ordinary block. */
    standard_setup(); combat_fighter(0, 0x78, 100, 100);
    combat_fighter(1, 0x22, 100, 100); combat_place(0, 0, 1000, 0); poll(0);
    hit(30, 0x00400000u);
    assert(cpu.gpr[17] == 30 && count("dbfb.responsive.guard_perfect") == 1);
    assert(count("dbfb.responsive.guard_break") == 0);
    passed("defence: native block, just-guard quarter, perfect zero, guard meter and break");
}
static void test_impact_camera_push(void) {
    /* Hit-stop skips the interpreter and visual calls, never rewinds a countdown. */
    standard_setup(); combat_fighter(0, 0x64, 100, 1000);
    combat_fighter(1, 0x24, 1000, 1000); combat_place(0, 0, 1000, 0);
    put(0x800728F8u, 0x80110000u); put_half(0x800728FCu, 5);
    put(0x80072928u, 0x80110020u); put_half(0x8007292Cu, 5);
    put(0x800A8680u, 1); /* tween mode: no camera writes in this scenario */
    poll(0); hit(10, 0x00400000u);
    for (unsigned n = 0; n < 2; n++) {
        tick(0);
        for (unsigned p = 0; p < 2; p++) {
            cpu.gpr[4] = p;
            assert(script_filter(&cpu, 0x8004E530u));
            cpu.gpr[4] = 0x800A8624u+p*0x20u;
            assert(animation_filter(&cpu, 0x80042240u) && cpu.gpr[2] == 0);
        }
        assert(half(0x800728FCu) == 5 && half(0x8007292Cu) == 5);
    }
    tick(0); cpu.gpr[4] = 0;
    assert(!script_filter(&cpu, 0x8004E530u));
    /* Camera shake is bounded and restores the exact original pair. */
    standard_setup(); combat_fighter(0, 0x64, 100, 1000);
    combat_fighter(1, 0x24, 1000, 1000); combat_place(0, 0, 1000, 0);
    put(0x800A8680u, 0); put(0x800A8664u, 1000); put(0x800A8668u, 2000);
    poll(0); hit(10, 0x00400000u);
    tick(0); assert(peek(0x800A8664u) != 1000 || peek(0x800A8668u) != 2000);
    for (unsigned n = 0; n < 16; n++) tick(0);
    assert(peek(0x800A8664u) == 1000 && peek(0x800A8668u) == 2000);
    assert(count("dbfb.responsive.camera_shake") > 0);
    /* Pushback follows the hit vector and updates both position copies. */
    standard_setup(); combat_fighter(0, 0x64, 100, 1000);
    combat_fighter(1, 0x24, 1000, 1000); combat_place(0, 0, 1000, 0);
    poll(0); hit(10, 0x00400000u);
    assert(peek(0x800728A8u) == 1064 && peek(0x80072898u) == 1064);
    assert(peek(0x80180040u) == 1064);
    /* KO punch-in uses the direct shot's eye/target, returning exactly. */
    standard_setup(); combat_fighter(0, 0x78, 100, 1000);
    combat_fighter(1, 0x24, 5, 1000); poll(0);
    put(0x800A866Cu, (uint32_t)-1000); hit(10, 0);
    tick(0); assert((int32_t)peek(0x800A866Cu) > -1000);
    for (unsigned n = 1; n < 24; n++) tick(0);
    assert((int32_t)peek(0x800A866Cu) == -1000);
    assert(count("dbfb.responsive.ko_camera") == 24);
    /* A new native shot wins immediately, without restoring over it. */
    poll(0); hit(10, 0); tick(0); put(0x800A866Cu, (uint32_t)-2000);
    tick(0); assert((int32_t)peek(0x800A866Cu) == -2000);
    passed("impact: bounded hit-stop on both sides, camera shake restores, vector pushback");
}
static void test_freeze_scope(void) {
    standard_setup(); combat_fighter(0, 0x64, 100, 1000);
    combat_fighter(1, 0x24, 1000, 1000); poll(0); hit(10, 0);
    cpu.gpr[4] = 2; assert(!script_filter(&cpu, 0x8004E530u));
    cpu.gpr[4] = 0x800A8604u;
    assert(!animation_filter(&cpu, 0x80042240u)); /* effect/UI context */
    cpu.gpr[4] = 0;
    put(0x800A868Cu, 1); assert(!script_filter(&cpu, 0x8004E530u));
    for (unsigned n = 0; n < 20; n++) tick(0);
    put(0x800A868Cu, 0); poll(0); cpu.gpr[4] = 0;
    assert(script_filter(&cpu, 0x8004E530u));
    online = 1; assert(!script_filter(&cpu, 0x8004E530u)); online = 0;
    resim = 1; assert(!script_filter(&cpu, 0x8004E530u)); resim = 0;
    put(0x8004EE84u, 0); assert(!script_filter(&cpu, 0x8004E530u));
    put(0x8004EE84u, 0x2694FFFFu);
    restore(); poll(0); cpu.gpr[4] = 0;
    assert(!script_filter(&cpu, 0x8004E530u));
    passed("hit-stop scope: fighter calls only, pause preserves remaining time, online/resim/unknown/restore inert");
}
static void test_cancel_and_ai(void) {
    /* Without a published retimed timeline the cancel rule never guesses. */
    standard_setup(); combat_fighter(0, 0x64, 100, 1000); poll(0);
    put_half(0x800728FCu, 100); put(0x80072800u, 0x10u);
    put_half(0x8007291Au, 20);
    poll(0); assert(half(0x8007291Au) == 20);
    assert(count("dbfb.responsive.cancel_window") == 0);
    /* CPU ownership and effective per-side difficulty, not device presence. */
    static const unsigned cadence[3] = {150, 120, 90};
    for (unsigned difficulty = 0; difficulty < 3; difficulty++) {
        standard_setup(); combat_fighter(0, 0x00, 100, 1000);
        combat_fighter(1, 0x00, 100, 1000); combat_place(0, 0, 400, 0);
        put(0x80072800u, 0); put(0x8007287Cu, 1);
        put_half(0x80072984u, (uint16_t)difficulty);
        put(0x8007298Cu, 0); put(0x80072990u, 0); put_half(0x80072994u, 0);
        put(0x800729A0u, 0xFFFFFFFFu); put(SP+0x10u, 0); put(SP+0x14u, 0);
        poll(0);
        memset(&cpu, 0, sizeof cpu); cpu.gpr[22] = 1; cpu.gpr[23] = 0x7Cu; cpu.gpr[29] = SP;
        const CPUState before = cpu;
        ai_hook(&cpu, 0x80054A60u);
        assert(!memcmp(&cpu, &before, sizeof cpu));
        assert(half(0x800728D2u) == 0);
        put_half(0x800728D2u, 0xFFFFu);
        for (unsigned n = 0; n < 500; n++) ai_hook(&cpu, 0x80054A60u);
        assert(half(0x800728D2u) == 0xFFFFu); /* duplicate calls do not age it */
        put(0x800A868Cu, 1);
        for (unsigned n = 0; n < 200; n++) tick(0);
        put(0x800A868Cu, 0); poll(0);
        cpu.gpr[22] = 1; cpu.gpr[23] = 0x7Cu; cpu.gpr[29] = SP;
        for (unsigned n = 1; n < cadence[difficulty]; n++) { tick(0); poll(0); }
        cpu.gpr[22] = 1; cpu.gpr[23] = 0x7Cu; cpu.gpr[29] = SP;
        ai_hook(&cpu, 0x80054A60u); assert(half(0x800728D2u) == 0xFFFFu);
        tick(0); ai_hook(&cpu, 0x80054A60u);
        assert(half(0x800728D2u) == 1);
        assert(count("dbfb.responsive.ai_command") == 2);
    }
    for (unsigned n = 0; n < 90; n++) { tick(0); poll(0); }
    cpu.gpr[22] = 1; cpu.gpr[23] = 0x7Cu; cpu.gpr[29] = SP;
    put_half(0x800728D2u, 0xFFFFu);
    /* Each native defensive decision and a human assignment wins immediately. */
    const uint32_t veto_address[] = {0x8007287Cu, 0x80072800u, 0x80072884u,
        0x8007287Cu, 0x8007298Cu, 0x80072990u, 0x80072994u,
        0x80072808u, 0x80072800u, 0x80072984u, 0x800728D2u,
        SP+0x10u, SP+0x14u, 0x800729A0u};
    const uint32_t veto_value[] = {0, 1, 0x80000021u, 0x08000001u,
        0x40u, 0x4040u, 12, 0x80000064u, 0x100u, 3, 0x22u,
        0x40u, 0x4040u, 0xC8u};
    for (unsigned n = 0; n < sizeof veto_address/sizeof *veto_address; n++) {
        const uint32_t stock = peek(veto_address[n]);
        put(veto_address[n], veto_value[n]);
        const uint32_t before = writes;
        ai_hook(&cpu, 0x80054A60u); assert(writes == before);
        put(veto_address[n], stock);
    }
    /* Side 1 is never hijacked, including CPU-vs-CPU. */
    put_half(0x80072856u, 0xFFFFu); cpu.gpr[22] = 0; cpu.gpr[23] = 0;
    ai_hook(&cpu, 0x80054A60u); assert(half(0x80072856u) == 0xFFFFu);
    cpu.gpr[22] = 1; cpu.gpr[23] = 0x7Cu; put_half(0x800728D2u, 0xFFFFu);
    put(0x800728A8u, 5000); ai_hook(&cpu, 0x80054A60u);
    assert(half(0x800728D2u) == 0xFFFFu);
    put(0x800728A8u, 400); put(0x80072808u+0x7Cu, 0x80000030u);
    ai_hook(&cpu, 0x80054A60u); assert(half(0x800728D2u) == 0xFFFFu);
    put(0x80072808u+0x7Cu, 0x80000000u); online = 1;
    const uint32_t before = writes; ai_hook(&cpu, 0x80054A60u);
    assert(writes == before); online = 0;
    passed("attack/AI: CPU ownership, 3 difficulties, VBlank cadence, pause, native defence and human priority");
}
static void unlock_setup(void) {
    setup(NULL, NULL, 0, 0);
    plugins[6].selected = 1;
    assert(plugins[6].vblank && !plugins[6].activate && !plugins[6].restore);
}

static void test_unlock_all(void) {
    /* The shipped title code stores the starting set and the cheat set; both
     * are upgraded to the full roster. Anything else is left untouched so an
     * overlay whose code lives at that address is never clobbered. */
    unlock_setup();
    put(0x8003BCC4u, 0x000007DFu);
    tick(0);
    assert(peek(0x8003BCC4u) == 0x0001FFFFu);
    assert(count("dbfb.responsive.unlock_all") == 1);
    tick(0);
    assert(count("dbfb.responsive.unlock_all") == 1); /* already full */
    put(0x8003BCC4u, 0x0001BFFFu);
    tick(0);
    assert(peek(0x8003BCC4u) == 0x0001FFFFu);
    assert(count("dbfb.responsive.unlock_all") == 2);
    put(0x8003BCC4u, 0x24020001u); /* unknown data must be preserved */
    tick(0);
    assert(peek(0x8003BCC4u) == 0x24020001u);
    assert(count("dbfb.responsive.unlock_all") == 2);
    put(0x8003BCC4u, 0x000007DFu); online = 1;
    tick(0);
    assert(peek(0x8003BCC4u) == 0x000007DFu);
    online = 0;
    put(0x8003BCC4u, 0x000007DFu); resim = 1;
    tick(0);
    assert(peek(0x8003BCC4u) == 0x000007DFu);
    resim = 0;
    passed("unlock all: full roster from the two known sets, code untouched, offline only");
}

int main(void) {
#ifdef _WIN32
    assert(_setmode(_fileno(stdin), _O_BINARY) != -1);
#endif
    /* Private fixture stream: count, then (physical addr, byte count, bytes). */
    uint32_t blocks;
    assert(fread(&blocks, 4, 1, stdin) == 1 && blocks == 22);
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
    test_rule_defaults(); test_ki_economy(); test_rule_guards(); test_speed_scale(); test_chain_window();
    test_standard_profile(); test_standard_pause(); test_standard_guards(); test_fighter_trace();
    test_command_recovery(); test_followup_window(); test_standard_damage();
    test_defence(); test_impact_camera_push(); test_freeze_scope(); test_cancel_and_ai(); test_unlock_all();
    test_locomotion();
    test_camera_framing();
    printf("%u C scenario groups passed\n", tests);
    return 0;
}
