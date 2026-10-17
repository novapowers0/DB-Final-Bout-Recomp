/* Final Bout only. Verified seams and limits: COMBATE_EVIDENCIA.md.
 *
 * The framework builds a plan-gated hook table (mod_runtime.cpp). Each feature
 * owns ALL its callbacks: input works without trace, trace never enables input.
 * There are no cached "active" flags that could survive a plan replacement.
 * All-off executes no callback, reads/writes no guest memory, allocates nothing.
 * Input mode "original" is also inert, including when called directly.
 *
 * Buffer = capture a VBlank-sampled press missed between game polls, deliver it
 * ONCE at the next verified remap, with a bounded lifetime. It is NOT an
 * action-ready/recovery/command buffer: those game states are still unknown.
 * Hold = explicitly separate experiment, bounded from a raw poll rising edge;
 * holding a button for a long time cannot bank extra time after its release.
 * Neither mode buffers directions, START, SELECT, L3 or R3.
 *
 * Only gameplay write: one 32-bit caller stack slot, poll-entry $sp - 0x10,
 * before the stock remapper. No patch, fighter field or persistent guest state.
 * Pending host input is discarded on lost scope, pause/menu buttons, swap,
 * restore, activation and live option change. Offline only, also during resim.
 */
#include <stdint.h>
#include <string.h>

#include "cpu_state.h"
#include "mod_plugins.h"
#include "psx_netplay.h"
#include "sio.h"

#define ID_TRACE "dbfb.responsive.trace"
#define ID_BUFFER "dbfb.responsive.input-buffer"

#define ADDR_POLL 0x8003FCF0u
#define ADDR_REMAP 0x8003FE68u
#define ADDR_SWAP 0x8003BC7Eu
#define ADDR_PRESSED 0x800A9CE8u /* signed SW offset 0x9CE8 from LUI 0x800B */
#define ADDR_RELEASED 0x800AA198u /* signed SW offset 0xA198 from LUI 0x800B */
#define POLL_RETURN 0x8003FCBCu /* jal poll at 0x8003FCB4; not init at 0x539C8 */
#define REMAP_RETURN 0x8003FD64u
#define INPUT_CODE_BYTES 0x294u /* complete poll AND remapper through jr ra/nop */
#define INPUT_CODE_FNV 0x829BEBD2u
#define CALLER_CODE 0x800539A8u
#define CALLER_CODE_BYTES 0x28u
#define CALLER_CODE_FNV 0x2B7A4598u
#define PAD_READ_CODE 0x80010F40u
#define PAD_READ_BYTES 0x10Cu
#define PAD_READ_FNV 0xC4EF2A99u

#define RING_CAP 4096u
#define REC_WORDS 8u
#define HDR_WORDS 8u

enum { KIND_VBLANK = 1, KIND_POLL = 2, KIND_REMAP = 3 };
enum { MODE_ORIGINAL, MODE_BUFFER, MODE_HOLD };

/* The game's pad word is byte-swapped relative to the SIO word (verified live:
 * RIGHT+SQUARE reads 0x2080 at 0x8003FE68 entry): low byte = L2 R2 L1 R1
 * TRIANGLE CIRCLE CROSS SQUARE (bit0..7), high byte = SELECT L3 R3 START UP
 * RIGHT DOWN LEFT. Only the low byte (face + shoulders) is ever buffered. */
#define BUFFERABLE_MASK 0x00FFu
#define MENU_MASK 0x0900u /* SELECT / START, never synthetic */
#define MAX_POLL_GAP 2u   /* observed combat cadence: one poll per two VBlanks */

typedef struct CombatScope {
    uint32_t frame, poll_frame, poll_sp;
    int combat, open, swap;
} CombatScope;

static CombatScope s_trace_scope, s_input_scope;
static int s_trace_failed;
static uint32_t s_ring_base;
static uint32_t s_head;
static uint16_t s_prev_pad[2] = {0xFFFFu, 0xFFFFu};
static unsigned s_mode = MODE_ORIGINAL, s_window = 2;
static uint16_t s_sample[2], s_raw[2], s_output[2];
static uint8_t s_pending[2], s_hold[2];
static uint32_t s_birth[2][8], s_hold_birth[2][8];
/* No pause-state flag has been verified. A menu button conservatively suspends
 * assistance until this code context leaves (or a new activation). Never infer
 * that releasing START means the game resumed combat. */
static int s_menu_suspended;

static void scope_reset(CombatScope* scope) {
    scope->combat = scope->open = 0;
    scope->poll_sp = 0;
}

static void input_reset(void) {
    scope_reset(&s_input_scope);
    memset(s_sample, 0, sizeof s_sample);
    memset(s_raw, 0, sizeof s_raw);
    memset(s_output, 0, sizeof s_output);
    memset(s_pending, 0, sizeof s_pending);
    memset(s_hold, 0, sizeof s_hold);
    memset(s_birth, 0, sizeof s_birth);
    memset(s_hold_birth, 0, sizeof s_hold_birth);
}

static int offline_started(void) {
    return !psx_netplay_active() && !psx_netplay_is_resimulating() &&
           psx_mod_game_started();
}

static int ram_word(uint32_t ptr) {
    const uint32_t segment = ptr & 0xE0000000u;
    return !(ptr & 3u) && (ptr & 0x1FFFFFFFu) <= 0x1FFFFCu &&
           (segment == 0 || segment == 0x80000000u || segment == 0xA0000000u);
}

static uint32_t code_fnv(uint32_t addr, uint32_t bytes) {
    uint32_t hash = 2166136261u;
    for (uint32_t i = 0; i < bytes; i += 4u) {
        const uint32_t word = psx_mod_read_word(addr + i);
        for (unsigned b = 0; b < 4; b++) {
            hash ^= (word >> (8u * b)) & 0xFFu;
            hash *= 16777619u;
        }
    }
    return hash;
}

/* Code identity + the observed combat call path, never a guessed state flag.
 * Presence alone does not authorize a write: poll/remap CPU context must match.
 * FNV is an accidental-revision guard, not an authenticity/security boundary. */
static int combat_code(void) {
    if (code_fnv(ADDR_POLL, INPUT_CODE_BYTES) != INPUT_CODE_FNV ||
        code_fnv(PAD_READ_CODE, PAD_READ_BYTES) != PAD_READ_FNV ||
        code_fnv(CALLER_CODE, CALLER_CODE_BYTES) != CALLER_CODE_FNV ||
        psx_mod_read_word(POLL_RETURN - 8u) != 0x0C00FF3Cu ||
        psx_mod_read_word(POLL_RETURN - 4u) != 0x00002021u) {
        psx_mod_counter_add("dbfb.responsive.code_mismatch", 1);
        return 0;
    }
    return 1;
}

/* PadRead explicitly checks status == 0 and id >> 4 == 4 for this path.
 * Other device protocols are left entirely stock, not guessed. Logical port
 * mapping follows the game's half-word swap before remap. */
static int digital_pad_ready(int logical, int swap) {
    const uint32_t base = (logical ^ swap) ? 0x8003BC28u : 0x8003BC00u;
    return psx_mod_read_byte(base) == 0 && (psx_mod_read_byte(base + 1u) >> 4) == 4;
}

static uint32_t physical_pad(int swap) {
    uint32_t word = 0;
    for (int p = 0; p < 2; p++) {
        const uint16_t pressed = (uint16_t)~sio_get_pad_buttons_slot(p);
        const uint16_t game = (uint16_t)((pressed << 8) | (pressed >> 8));
        word |= (uint32_t)game << (16 * (p ^ swap));
    }
    return word;
}

static int menu_buttons(uint32_t word) {
    return (word & ((uint32_t)MENU_MASK | ((uint32_t)MENU_MASK << 16))) != 0;
}

static int begin_poll(CombatScope* scope, struct CPUState* cpu, uint32_t address) {
    if (!cpu || (address & 0x1FFFFFFFu) != (ADDR_POLL & 0x1FFFFFFFu) ||
        !offline_started() || !combat_code() ||
        cpu->gpr[4] != 0 ||
        (cpu->gpr[31] & 0x1FFFFFFFu) != (POLL_RETURN & 0x1FFFFFFFu) ||
        !ram_word(cpu->gpr[29]) || (cpu->gpr[29] & 0x1FFFFFFFu) < 0x20u) {
        scope_reset(scope);
        return 0;
    }
    scope->swap = psx_mod_read_byte(ADDR_SWAP) != 0;
    scope->combat = scope->open = 1;
    scope->poll_frame = scope->frame;
    scope->poll_sp = cpu->gpr[29];
    return 1;
}

static int remap_context(CombatScope* scope, struct CPUState* cpu, uint32_t address) {
    if (!cpu || !scope->combat || !scope->open || !offline_started() ||
        (address & 0x1FFFFFFFu) != (ADDR_REMAP & 0x1FFFFFFFu) ||
        scope->frame != scope->poll_frame || !combat_code() ||
        (cpu->gpr[31] & 0x1FFFFFFFu) != (REMAP_RETURN & 0x1FFFFFFFu) ||
        !ram_word(cpu->gpr[4]) || cpu->gpr[4] != scope->poll_sp - 0x10u ||
        cpu->gpr[29] != scope->poll_sp - 0x20u ||
        scope->swap != (psx_mod_read_byte(ADDR_SWAP) != 0)) {
        scope_reset(scope);
        return 0;
    }
    scope->open = 0; /* at most one write for this call, even if a hook repeats */
    return 1;
}

static int scope_tick(CombatScope* scope) {
    scope->frame++;
    if (!offline_started() || !scope->combat ||
        scope->frame - scope->poll_frame > MAX_POLL_GAP || !combat_code() ||
        scope->swap != (psx_mod_read_byte(ADDR_SWAP) != 0)) {
        scope_reset(scope);
        return 0;
    }
    return 1;
}

static void ring_store(const uint32_t rec[REC_WORDS]) {
    const uint32_t slot = s_head % RING_CAP;
    const uint32_t at = s_ring_base + (HDR_WORDS + slot * REC_WORDS) * 4u;
    for (uint32_t i = 0; i < REC_WORDS; i++) psx_mod_write_word(at + i * 4u, rec[i]);
    s_head++;
    psx_mod_write_word(s_ring_base + 16u, s_head);
    psx_mod_write_word(s_ring_base + 20u, s_trace_scope.frame);
}

static int ring_init(void) {
    if (s_ring_base) return 1;
    s_ring_base = psx_mod_alloc_guest_memory((HDR_WORDS + RING_CAP * REC_WORDS) * 4u, 16u);
    if (!s_ring_base) return 0;
    const uint32_t header[HDR_WORDS] = {0x42464244u, 2u, RING_CAP, REC_WORDS * 4u,
                                      0u, s_trace_scope.frame, 1u, 0u};
    for (unsigned i = 0; i < HDR_WORDS; i++)
        psx_mod_write_word(s_ring_base + i * 4u, header[i]);
    return 1;
}

static void trace_activate(void) {
    memset(&s_trace_scope, 0, sizeof s_trace_scope);
    s_trace_failed = 0;
    s_ring_base = s_head = 0;
    s_prev_pad[0] = s_prev_pad[1] = 0xFFFFu;
    /* Allocate lazily only after a verified offline combat poll. */
}

static void trace_restore(void) {
    scope_reset(&s_trace_scope);
    s_trace_failed = 0;
    s_prev_pad[0] = s_prev_pad[1] = 0xFFFFu;
    /* The ring is guest memory and may have been rolled back too. Rebind its
     * head/clock without allocating on every restore or writing stale indices.
     * A state without this allocation gets a fresh ring lazily, if available. */
    if (s_ring_base && offline_started() &&
        psx_mod_read_word(s_ring_base) == 0x42464244u &&
        psx_mod_read_word(s_ring_base + 4u) == 2u &&
        psx_mod_read_word(s_ring_base + 8u) == RING_CAP &&
        psx_mod_read_word(s_ring_base + 12u) == REC_WORDS * 4u) {
        s_head = psx_mod_read_word(s_ring_base + 16u);
        s_trace_scope.frame = psx_mod_read_word(s_ring_base + 20u);
    } else {
        s_ring_base = s_head = s_trace_scope.frame = 0;
    }
}

static int parse_mode(const char* value, unsigned* mode) {
    if (!strcmp(value, "original")) *mode = MODE_ORIGINAL;
    else if (!strcmp(value, "buffer")) *mode = MODE_BUFFER;
    else if (!strcmp(value, "hold")) *mode = MODE_HOLD;
    else return 0;
    return 1;
}

static int parse_window(const char* value, unsigned* window) {
    if (value[0] < '1' || value[0] > '6' || value[1]) return 0;
    *window = (unsigned)(value[0] - '0');
    return 1;
}

static void buffer_activate(void) {
    char value[16];
    input_reset();
    s_menu_suspended = 0;
    s_input_scope.frame = 0;
    s_mode = MODE_BUFFER;
    s_window = 2;
    if ((psx_mod_option_value("dbfb.responsive", "input-buffer", "mode", value, sizeof value) &&
         !parse_mode(value, &s_mode)) ||
        (psx_mod_option_value("dbfb.responsive", "input-buffer", "window", value, sizeof value) &&
         !parse_window(value, &s_window))) {
        s_mode = MODE_ORIGINAL;
        psx_mod_counter_add("dbfb.responsive.invalid_option", 1);
    }
}

static int buffer_option_changed(const char* id, const char* value) {
    unsigned mode = s_mode, window = s_window;
    if (psx_netplay_active() || psx_netplay_is_resimulating()) return 0;
    if (!strcmp(id, "mode")) { if (!parse_mode(value, &mode)) return 0; }
    else if (!strcmp(id, "window")) { if (!parse_window(value, &window)) return 0; }
    else return 0;
    input_reset(); /* changing to Original touches host state only */
    s_mode = mode;
    s_window = window;
    return 1;
}

static void trace_vblank(void) {
    uint32_t rec[REC_WORDS] = {0};
    if (s_trace_failed || !scope_tick(&s_trace_scope)) return;
    rec[0] = s_trace_scope.frame;
    rec[1] = KIND_VBLANK;
    for (int p = 0; p < 2; p++) {
        const uint16_t cur = sio_get_pad_buttons_slot(p);
        const uint16_t edges = (uint16_t)(s_prev_pad[p] & (uint16_t)~cur);
        rec[p + 2] = (uint32_t)cur | ((uint32_t)edges << 16);
        s_prev_pad[p] = cur;
    }
    ring_store(rec);
}

static void trace_poll(struct CPUState* cpu, uint32_t address) {
    uint32_t rec[REC_WORDS] = {0};
    const int was_combat = s_trace_scope.combat;
    if (s_trace_failed || !begin_poll(&s_trace_scope, cpu, address)) return;
    if (!was_combat) for (int p = 0; p < 2; p++)
        s_prev_pad[p] = sio_get_pad_buttons_slot(p);
    if (!ring_init()) {
        s_trace_failed = 1;
        psx_mod_counter_add("dbfb.responsive.trace_allocation_failed", 1);
        return;
    }
    rec[0] = s_trace_scope.frame;
    rec[1] = KIND_POLL;
    rec[2] = address;
    rec[3] = cpu->gpr[31];
    rec[4] = cpu->gpr[4];
    rec[5] = cpu->gpr[29];
    /* Previous poll's edge outputs, before this original poll runs. Not state,
     * health, animation, or proof that an action was accepted by a fighter. */
    rec[6] = psx_mod_read_word(ADDR_PRESSED);
    rec[7] = psx_mod_read_word(ADDR_RELEASED);
    ring_store(rec);
}

static void trace_remap(struct CPUState* cpu, uint32_t address) {
    uint32_t rec[REC_WORDS] = {0};
    if (s_trace_failed || !remap_context(&s_trace_scope, cpu, address)) return;
    rec[0] = s_trace_scope.frame;
    rec[1] = KIND_REMAP;
    rec[2] = address;
    rec[3] = cpu->gpr[31];
    rec[4] = cpu->gpr[4];
    rec[5] = psx_mod_read_word(cpu->gpr[4]);
    /* Verified stock edge consumer's previous pad, not a fighter state. */
    rec[6] = psx_mod_read_word(0x1F800004u);
    rec[7] = rec[5] & ~rec[6];
    ring_store(rec);
}

static void buffer_poll(struct CPUState* cpu, uint32_t address) {
    const int was_combat = s_input_scope.combat;
    const uint32_t last = s_input_scope.poll_frame;
    const int swap = s_input_scope.swap;
    if (s_mode == MODE_ORIGINAL) { input_reset(); return; }
    if (s_menu_suspended) {
        if (offline_started() && !combat_code()) s_menu_suspended = 0;
        input_reset();
        return;
    }
    if (!begin_poll(&s_input_scope, cpu, address)) { input_reset(); return; }
    if (!was_combat || s_input_scope.frame - last > MAX_POLL_GAP ||
        swap != s_input_scope.swap) {
        const uint32_t pad = physical_pad(s_input_scope.swap);
        memset(s_pending, 0, sizeof s_pending);
        memset(s_hold, 0, sizeof s_hold);
        for (int p = 0; p < 2; p++)
            s_sample[p] = s_raw[p] = s_output[p] = (uint16_t)(pad >> (16 * p));
    }
}

static void buffer_vblank(void) {
    if (s_mode == MODE_ORIGINAL) { input_reset(); return; }
    if (s_menu_suspended) {
        s_input_scope.frame++;
        if (offline_started() && !combat_code()) s_menu_suspended = 0;
        input_reset();
        return;
    }
    const int was_combat = s_input_scope.combat;
    if (!scope_tick(&s_input_scope)) {
        /* START may itself coincide with the first missed poll (e.g. pause).
         * Do not treat that gap as permission to rearm a paused input loop. */
        if (was_combat && offline_started() && combat_code() &&
            menu_buttons(physical_pad(s_input_scope.swap))) s_menu_suspended = 1;
        input_reset();
        return;
    }
    const uint32_t word = physical_pad(s_input_scope.swap);
    if (menu_buttons(word)) { s_menu_suspended = 1; input_reset(); return; }
    for (int p = 0; p < 2; p++) {
        const uint16_t raw = (uint16_t)(word >> (16 * p));
        const uint16_t edges = raw & (uint16_t)~s_sample[p] & BUFFERABLE_MASK;
        if (!digital_pad_ready(p, s_input_scope.swap)) {
            s_pending[p] = s_hold[p] = 0;
            s_sample[p] = raw;
            continue;
        }
        if (s_mode == MODE_BUFFER) for (unsigned b = 0; b < 8; b++) {
            if (edges & (1u << b)) {
                s_pending[p] |= (uint8_t)(1u << b);
                s_birth[p][b] = s_input_scope.frame;
                psx_mod_counter_add("dbfb.responsive.captured_button", 1);
            }
        }
        s_sample[p] = raw;
    }
}

static uint32_t buffer_apply(uint32_t word) {
    uint32_t out = word;
    for (int p = 0; p < 2; p++) {
        const uint16_t raw = (uint16_t)(word >> (16 * p));
        if (!digital_pad_ready(p, s_input_scope.swap)) {
            s_pending[p] = s_hold[p] = 0;
            s_raw[p] = s_output[p] = raw;
            continue;
        }
        for (unsigned b = 0; b < 8; b++) {
            const uint8_t bit = (uint8_t)(1u << b);
            if (s_mode == MODE_BUFFER) {
                if (s_input_scope.frame - s_birth[p][b] >= s_window || (raw & bit))
                    s_pending[p] &= (uint8_t)~bit;
                if ((s_pending[p] & bit) && !(s_output[p] & bit)) {
                    out |= (uint32_t)bit << (16 * p);
                    s_pending[p] &= (uint8_t)~bit;
                    psx_mod_counter_add("dbfb.responsive.delivered_button", 1);
                    psx_mod_counter_add("dbfb.responsive.delivery_age_vblanks",
                                        s_input_scope.frame - s_birth[p][b]);
                }
            } else {
                if ((raw & bit) && !(s_raw[p] & bit)) {
                    s_hold[p] |= bit;
                    s_hold_birth[p][b] = s_input_scope.frame;
                }
                if (s_input_scope.frame - s_hold_birth[p][b] >= s_window)
                    s_hold[p] &= (uint8_t)~bit;
                if (!(raw & bit) && (s_hold[p] & bit))
                    out |= (uint32_t)bit << (16 * p);
            }
        }
        s_raw[p] = raw;
        s_output[p] = (uint16_t)(out >> (16 * p));
    }
    return out;
}

static void buffer_remap(struct CPUState* cpu, uint32_t address) {
    if (s_mode == MODE_ORIGINAL || s_menu_suspended) { input_reset(); return; }
    if (!remap_context(&s_input_scope, cpu, address)) {
        input_reset();
        psx_mod_counter_add("dbfb.responsive.rejected_remap", 1);
        return;
    }
    const uint32_t before = psx_mod_read_word(cpu->gpr[4]);
    if (menu_buttons(before) || menu_buttons(physical_pad(s_input_scope.swap))) {
        s_menu_suspended = 1;
        input_reset();
        return;
    }
    const uint32_t after = buffer_apply(before);
    if (after != before) {
        psx_mod_write_word(cpu->gpr[4], after);
        psx_mod_counter_add(s_mode == MODE_BUFFER ? "dbfb.responsive.buffer_write" :
                                                  "dbfb.responsive.hold_write", 1);
    }
}

PSX_MOD_CONSTRUCTOR(dbfb_register_responsive) {
    (void)psx_mod_register_activation_plugin(ID_TRACE, trace_activate);
    (void)psx_mod_register_vblank_plugin(ID_TRACE, trace_vblank);
    (void)psx_mod_register_savestate_plugin(ID_TRACE, trace_restore);
    (void)psx_mod_register_function_entry_plugin(ID_TRACE, ADDR_POLL, trace_poll);
    (void)psx_mod_register_function_entry_plugin(ID_TRACE, ADDR_REMAP, trace_remap);
    (void)psx_mod_register_activation_plugin(ID_BUFFER, buffer_activate);
    (void)psx_mod_register_vblank_plugin(ID_BUFFER, buffer_vblank);
    (void)psx_mod_register_savestate_plugin(ID_BUFFER, input_reset);
    (void)psx_mod_register_function_entry_plugin(ID_BUFFER, ADDR_POLL, buffer_poll);
    (void)psx_mod_register_function_entry_plugin(ID_BUFFER, ADDR_REMAP, buffer_remap);
    (void)psx_mod_register_option_changed_plugin(ID_BUFFER, buffer_option_changed);
}
