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
 * Input gameplay write: one 32-bit caller stack slot, poll-entry $sp - 0x10,
 * before the stock remapper. Pending host input is discarded on lost scope,
 * pause/menu buttons, swap, restore, activation and live option change.
 * Offline only, also during resim.
 *
 * Tier 3 rules (ki-economy, speed-scale, chain-window) are a separate feature
 * family: default off, offline only, and every write is gated on the same
 * verified combat path plus a code-identity read. With all features off the
 * constructor registers callbacks only; no guest byte is read or written and
 * nothing is allocated. See COMBATE_MAPA.md for the address map and evidence.
 */
#include <stdint.h>
#include <string.h>

#include "cpu_state.h"
#include "mod_plugins.h"
#include "psx_netplay.h"
#include "sio.h"

#define ID_TRACE "dbfb.responsive.trace"
#define ID_BUFFER "dbfb.responsive.input-buffer"
#define ID_STANDARD "dbfb.responsive.standard"

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

enum { KIND_VBLANK = 1, KIND_POLL = 2, KIND_REMAP = 3, KIND_FIGHTER = 4 };
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
    /* Mechanical trace, not just pad timing. Raw fields deliberately retain
     * their measured layout instead of inventing animation names or hitstop.
     * kind low byte = 4, high byte = fighter index (0/1).
     * [action, flags2, script pointer, frame/opcode word, HP/KI, speed/gate]. */
    for (unsigned p = 0; p < 2; p++) {
        const uint32_t control = 0x80072800u + p * 0x7Cu;
        const uint32_t script = 0x800728F8u + p * 0x30u;
        rec[1] = KIND_FIGHTER | (p << 8);
        rec[2] = psx_mod_read_word(control + 8u);
        rec[3] = psx_mod_read_word(control + 4u);
        rec[4] = psx_mod_read_word(script);
        rec[5] = psx_mod_read_word(script + 4u);
        rec[6] = psx_mod_read_word(control + 0x40u);
        rec[7] = psx_mod_read_half(script + 0x0Cu) |
                 ((uint32_t)psx_mod_read_half(script + 0x22u) << 16);
        ring_store(rec);
    }
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

/* ------------------------------------------------------------------------ *
 * Tier 3 combat rules (COMBATE_MAPA.md). All default-off, offline-only.
 *
 * Unlike the input feature these DO touch fighter state, so every write is
 * gated on the same verified combat call path and on a code-identity read.
 * They run from the already-verified poll entry 0x8003FCF0, so no new hook
 * site (and no overlay recompile) is needed.
 *
 * - ki-economy: adds ki to both fighters on a period. The game clamps to 0xC4
 *   itself; we never write above it and never write a negative value.
 * - speed-scale: scales the script's stored velocity (script state +0x0C).
 *   A shadow detects the script's own writes, so the scale is applied once per
 *   value and never accumulates. Positions, collisions and hit tests untouched.
 * - chain-window: replaces ONE verified instruction with an equivalent that
 *   keeps the command instead of discarding it. Applied only when the site
 *   still holds the original word, and reverted when the option goes back to
 *   Original. The overlay reload wipes it, and it is re-applied on demand.
 * ------------------------------------------------------------------------ */

#define ID_KI "dbfb.responsive.ki-economy"
#define ID_SPEED "dbfb.responsive.speed-scale"
#define ID_CHAIN "dbfb.responsive.chain-window"

#define ADDR_VEL 0x80072904u /* script state +0x0C, actor 1; actor 2 +0x30 */
#define VEL_STRIDE 0x30u
#define ADDR_KI 0x80072842u /* control +0x42, fighter 1; fighter 2 +0x7C */
#define KI_STRIDE 0x7Cu
#define KI_TOP 0xC4u
#define ADDR_CHAIN 0x80054AD8u
#define CHAIN_ORIGINAL 0x2402FFFFu /* addiu v0,zero,0xffff (verified) */
#define CHAIN_PATCHED 0x00801021u  /* addu v0,a0,zero (keep the command) */

enum { SPEED_ORIGINAL, SPEED_75, SPEED_125, SPEED_150 };
enum { CHAIN_ORIGINAL_MODE, CHAIN_OPEN };

static unsigned s_ki_mode, s_ki_period = 2, s_ki_tick;
static unsigned s_speed_mode;
static unsigned s_chain_mode;
static uint8_t s_vel_primed;
static int16_t s_vel_shadow[2];
static int16_t s_vel_raw[2];
static unsigned s_vel_mode;
static int s_chain_owned;
static int s_rule_suspended[3];
static void chain_apply(unsigned mode);

static void ki_restore(void) { s_ki_tick = 0; s_rule_suspended[0] = 0; }
static void speed_restore(void) { s_vel_primed = 0; s_rule_suspended[1] = 0; }
static void chain_restore(void) {
    s_chain_owned = 0;
    s_rule_suspended[2] = 0;
    /* A save made in Open can carry patched RAM even when the current option
     * is Original. Reconcile it through the executable-memory API as well. */
    if (s_chain_mode == CHAIN_ORIGINAL_MODE && offline_started() && combat_code())
        chain_apply(CHAIN_ORIGINAL_MODE);
}

/* Same verified combat call path the input feature uses, minus any write. */
static int combat_tick(struct CPUState* cpu, uint32_t address, unsigned rule) {
    if (!cpu || !offline_started() ||
        (address & 0x1FFFFFFFu) != (ADDR_POLL & 0x1FFFFFFFu) ||
        cpu->gpr[4] != 0 ||
        (cpu->gpr[31] & 0x1FFFFFFFu) != (POLL_RETURN & 0x1FFFFFFFu)) return 0;
    if (!combat_code()) { s_rule_suspended[rule] = 0; return 0; }
    if (menu_buttons(physical_pad(0))) s_rule_suspended[rule] = 1;
    return !s_rule_suspended[rule];
}

static void ki_tick(struct CPUState* cpu, uint32_t address) {
    if (s_ki_mode == 0 || !combat_tick(cpu, address, 0)) return;
    if (psx_mod_read_word(0x8006D1D4u) != 0x94232842u ||
        psx_mod_read_word(0x8006D1DCu) != 0x2C6200C4u) return;
    if (++s_ki_tick % s_ki_period) return;
    for (int a = 0; a < 2; a++) {
        const uint32_t at = ADDR_KI + (uint32_t)a * KI_STRIDE;
        const int16_t ki = (int16_t)psx_mod_read_half(at);
        if (ki < 0 || (uint16_t)ki >= KI_TOP) continue;
        psx_mod_write_half(at, (uint16_t)(ki + 1));
        psx_mod_counter_add("dbfb.responsive.ki_gain", 1);
    }
}

static int16_t scale_velocity(int16_t v) {
    if (s_speed_mode == SPEED_ORIGINAL) return v;
    if (!v) return 0;
    const int num = s_speed_mode == SPEED_75 ? 3 : s_speed_mode == SPEED_125 ? 5 : 3;
    const int den = s_speed_mode == SPEED_150 ? 2 : 4;
    const int sign = v < 0 ? -1 : 1;
    int mag = v < 0 ? -v : v;
    mag = (mag * num + den / 2) / den;
    if (mag > 0x7FFF) mag = 0x7FFF;
    return (int16_t)(sign * mag);
}

static void speed_tick(struct CPUState* cpu, uint32_t address) {
    if (s_speed_mode == SPEED_ORIGINAL && !s_vel_primed) return;
    if (!combat_tick(cpu, address, 1)) return;
    if (psx_mod_read_word(0x800666ECu) != 0x94232904u ||
        psx_mod_read_word(0x8006672Cu) != 0x94232904u) return;
    for (int a = 0; a < 2; a++) {
        const uint32_t at = ADDR_VEL + (uint32_t)a * VEL_STRIDE;
        const int16_t cur = (int16_t)psx_mod_read_half(at);
        if (!(s_vel_primed & (1u << a))) {
            s_vel_raw[a] = s_vel_shadow[a] = cur;
            continue;
        }
        if (cur == s_vel_shadow[a] && s_vel_mode == s_speed_mode) continue;
        if (cur != s_vel_shadow[a]) s_vel_raw[a] = cur;
        const int16_t out = scale_velocity(s_vel_raw[a]);
        s_vel_shadow[a] = out;
        if (out != cur) {
            psx_mod_write_half(at, (uint16_t)out);
            psx_mod_counter_add("dbfb.responsive.speed_write", 1);
        }
    }
    s_vel_primed = s_speed_mode == SPEED_ORIGINAL ? 0 : 3u;
    s_vel_mode = s_speed_mode;
}

static void chain_apply(unsigned mode) {
    if (psx_mod_read_word(ADDR_CHAIN - 4u) != 0x10820004u ||
        psx_mod_read_word(ADDR_CHAIN + 12u) != 0xA4222856u) return;
    const uint32_t word = psx_mod_read_word(ADDR_CHAIN);
    if (mode == 0) {
        if (word != CHAIN_PATCHED) return;
        psx_mod_write_code_word(ADDR_CHAIN, CHAIN_ORIGINAL);
        s_chain_owned = 0;
        psx_mod_counter_add("dbfb.responsive.chain_restore", 1);
        return;
    }
    if (word == CHAIN_PATCHED) { s_chain_owned = 1; return; }
    if (word != CHAIN_ORIGINAL) return; /* not the verified body: do nothing */
    psx_mod_write_code_word(ADDR_CHAIN, CHAIN_PATCHED);
    s_chain_owned = 1;
    psx_mod_counter_add("dbfb.responsive.chain_patch", 1);
}

static void chain_tick(struct CPUState* cpu, uint32_t address) {
    if (s_chain_mode == CHAIN_ORIGINAL_MODE && !s_chain_owned) return;
    if (!combat_tick(cpu, address, 2)) return;
    chain_apply(s_chain_mode);
}

static int parse_speed(const char* value, unsigned* mode) {
    if (!strcmp(value, "original")) *mode = SPEED_ORIGINAL;
    else if (!strcmp(value, "75")) *mode = SPEED_75;
    else if (!strcmp(value, "125")) *mode = SPEED_125;
    else if (!strcmp(value, "150")) *mode = SPEED_150;
    else return 0;
    return 1;
}

static int parse_chain(const char* value, unsigned* mode) {
    if (!strcmp(value, "original")) *mode = CHAIN_ORIGINAL_MODE;
    else if (!strcmp(value, "open")) *mode = CHAIN_OPEN;
    else return 0;
    return 1;
}

static int parse_ki_mode(const char* value, unsigned* mode) {
    if (!strcmp(value, "original")) *mode = 0;
    else if (!strcmp(value, "flow")) *mode = 1;
    else return 0;
    return 1;
}

static int parse_period(const char* value, unsigned* period) {
    if (value[0] < '1' || value[0] > '8' || value[1]) return 0;
    *period = (unsigned)(value[0] - '0');
    return 1;
}

static void ki_activate(void) {
    char value[16];
    s_ki_mode = 0;
    s_ki_period = 2;
    s_ki_tick = 0;
    ki_restore();
    if ((psx_mod_option_value("dbfb.responsive", "ki-economy", "mode", value, sizeof value) &&
         !parse_ki_mode(value, &s_ki_mode)) ||
        (psx_mod_option_value("dbfb.responsive", "ki-economy", "period", value, sizeof value) &&
         !parse_period(value, &s_ki_period))) {
        s_ki_mode = 0;
        psx_mod_counter_add("dbfb.responsive.invalid_option", 1);
    }
}

static void speed_activate(void) {
    char value[16];
    s_speed_mode = SPEED_ORIGINAL;
    s_vel_primed = 0;
    s_vel_shadow[0] = s_vel_shadow[1] = 0;
    speed_restore();
    if (psx_mod_option_value("dbfb.responsive", "speed-scale", "mode", value, sizeof value) &&
        !parse_speed(value, &s_speed_mode)) {
        s_speed_mode = SPEED_ORIGINAL;
        psx_mod_counter_add("dbfb.responsive.invalid_option", 1);
    }
}

static void chain_activate(void) {
    char value[16];
    s_chain_mode = CHAIN_ORIGINAL_MODE;
    s_chain_owned = 0;
    s_rule_suspended[2] = 0;
    if (psx_mod_option_value("dbfb.responsive", "chain-window", "mode", value, sizeof value) &&
        !parse_chain(value, &s_chain_mode)) {
        s_chain_mode = CHAIN_ORIGINAL_MODE;
        psx_mod_counter_add("dbfb.responsive.invalid_option", 1);
    }
}

static int ki_option_changed(const char* id, const char* value) {
    unsigned mode = s_ki_mode, period = s_ki_period;
    if (psx_netplay_active() || psx_netplay_is_resimulating()) return 0;
    if (!strcmp(id, "mode")) { if (!parse_ki_mode(value, &mode)) return 0; }
    else if (!strcmp(id, "period")) { if (!parse_period(value, &period)) return 0; }
    else return 0;
    s_ki_mode = mode;
    s_ki_period = period;
    return 1;
}

static int speed_option_changed(const char* id, const char* value) {
    unsigned mode = s_speed_mode;
    if (psx_netplay_active() || psx_netplay_is_resimulating()) return 0;
    if (strcmp(id, "mode") || !parse_speed(value, &mode)) return 0;
    s_speed_mode = mode;
    /* Retain raw/shadow so the next verified tick rescales from raw, or
     * restores it for Original, rather than multiplying an already scaled value. */
    return 1;
}

static int chain_option_changed(const char* id, const char* value) {
    unsigned mode = s_chain_mode;
    if (psx_netplay_active() || psx_netplay_is_resimulating()) return 0;
    if (strcmp(id, "mode") || !parse_chain(value, &mode)) return 0;
    s_chain_mode = mode;
    /* Opening is deferred to a verified poll. Closing may restore our patch
     * immediately (also while paused), but only in the verified code image. */
    if (mode == CHAIN_ORIGINAL_MODE && s_chain_owned && offline_started() && combat_code())
        chain_apply(mode);
    return 1;
}

/* Player-facing mode. No tuning dependency, no live plan flags and no legacy
 * experiment plugins in its manifest. These callbacks alone own the profile.
 * This is a measured-site starting ruleset, not a completed animation redesign.
 *
 * Pause evidence: 0x8006A178/180 and 0x8006A220/22C toggle 0x800A868C;
 * 0x8006A2F8/300 checks it before drawing the paused UI. Unlike the old lab
 * latch, resuming is authorized by the game's flag, not by releasing START.
 */
#define ADDR_PAUSE 0x800A868Cu
#define ADDR_CHAIN_LIMIT 0x80054AC0u
#define CHAIN_LIMIT_STOCK 0x2C420009u /* sltiu v0,v0,9 */
#define CHAIN_LIMIT_STANDARD 0x2C42000Cu /* sltiu v0,v0,12 */
static uint32_t s_standard_frame, s_standard_rule_frame;
static int16_t s_command[2] = {-1, -1};
static uint32_t s_command_birth[2];
/* Aerial follow-up retention (R1, 2026-10-18). Commands 0x25 (RIGHT,DOWN,
 * CIRCLE) and 0x29 (DOWN,RIGHT,CIRCLE) are the producers of the aerial
 * continuation candidates 0x98/0xAA that 0x800576BC refines to 0x99/0x9B/0x9A;
 * their handlers 0x800607A0/0x800609C0 select by control+4 bits 0x20/0x40 and
 * store no action while the fighter is still grounded. The native gate already
 * accepts both while busy, so the gesture is otherwise consumed with no effect.
 * Hold a recognised follow-up and re-inject it through the SAME native slot
 * control+0x56 once the native airborne flag appears; nothing is written to
 * control+4/control+8, so the gate, handler, ki cost and busy-state still
 * decide. Bounded, and cleared by any other command, a continuation action,
 * lost context, pause or restore. */
#define FOLLOWUP_BUSY 0x60u /* control+4 airborne/busy bits that arm the handler */
#define FOLLOWUP_LIFE 16u   /* guest frames the pending follow-up survives */
static int16_t s_followup[2] = {-1, -1};
static uint32_t s_followup_birth[2];
static int followup_action(unsigned action) {
    return action == 0x98u || action == 0xAAu || action == 0x99u ||
           action == 0x9Au || action == 0x9Bu;
}

#include "dbfb_motion.h"

static int standard_unpaused(void) {
    if (psx_mod_read_word(0x8006A178u) != 0x38420001u ||
        psx_mod_read_word(0x8006A180u) != 0xAC22868Cu ||
        psx_mod_read_word(0x8006A2F8u) != 0x8C63868Cu) return 0;
    return psx_mod_read_word(ADDR_PAUSE) == 0;
}

static int standard_code(void) {
    if (!combat_code() || !standard_unpaused()) return 0;
    const uint32_t limit = psx_mod_read_word(ADDR_CHAIN_LIMIT);
    return (limit == CHAIN_LIMIT_STOCK || limit == CHAIN_LIMIT_STANDARD) &&
           psx_mod_read_word(ADDR_CHAIN_LIMIT - 4u) == 0 &&
           psx_mod_read_word(ADDR_CHAIN_LIMIT + 4u) == 0x14400008u &&
           psx_mod_read_word(ADDR_CHAIN) == CHAIN_ORIGINAL &&
           psx_mod_read_word(ADDR_CHAIN + 12u) == 0xA4222856u &&
           psx_mod_read_word(0x800666ECu) == 0x94232904u &&
           psx_mod_read_word(0x8006672Cu) == 0x94232904u &&
           psx_mod_read_word(0x8006D1D4u) == 0x94232842u &&
           psx_mod_read_word(0x8006D1DCu) == 0x2C6200C4u &&
           psx_mod_read_word(0x80054A60u) == 0x84242856u &&
           psx_mod_read_word(0x80054AE8u) == 0x02C02021u &&
           psx_mod_read_word(0x80066D24u) == 0x00111400u &&
           psx_mod_read_word(0x80066D28u) == 0x1C400002u;
}

static void command_reset(void) {
    s_command[0] = s_command[1] = -1;
    s_followup[0] = s_followup[1] = -1;
}

/* A grounded cmd25 otherwise falls through to the raw CIRCLE normal (6A),
 * whose control+0 bit8 prevents the UP producer at 5D830 from ever arming20
 * during LIFE16. Make the recognised gesture a native lift-and-follow-up:
 * replace only its unmodified final CIRCLE input in the call arguments.
 * 54AEC/54AF0 load these two words; 56E64/56E6C keep them in s3/s4;
 * 57238 passes s3 to 5D264, whose 5D314 branch selects the native UP path.
 * Never change flags/actions, invent recovery, or assist an unsupported ID.
 * The native handler still owns the lift, refusal, contact and continuation. */
static void followup_lift(struct CPUState* cpu, unsigned p, int16_t accepted,
                          unsigned action) {
    const uint32_t c = 0x80072800u+p*0x7Cu;
    const unsigned id = psx_mod_read_byte(c-4u);
    const uint32_t ids = 0x0000EE75u; /* 0,2,4,5,6,9,10,11,13,14,15: cmd25 */
    const uint32_t sp = cpu->gpr[29];
    if (accepted != 0x25 || action > 6u || id > 15u || !(ids & (1u << id)) ||
        (psx_mod_read_word(c) & 0x04000208u) ||
        (int32_t)psx_mod_read_word(c+0x10u) < 0 ||
        (sp & 3u) || sp < 0x80000100u || sp > 0x801FFFE8u ||
        psx_mod_read_word(0x80054AECu) != 0x8FA50010u ||
        psx_mod_read_word(0x80054AF0u) != 0x8FA60014u ||
        psx_mod_read_word(0x80056E64u) != 0x00A09821u ||
        psx_mod_read_word(0x80056E6Cu) != 0x00C0A021u ||
        psx_mod_read_word(0x80057238u) != 0x0C017499u ||
        psx_mod_read_word(0x8005D314u) != 0x10820146u ||
        psx_mod_read_word(0x8005D910u) != 0xAC222804u) return;
    const uint32_t held = psx_mod_read_word(sp+0x10u);
    const uint32_t pressed = psx_mod_read_word(sp+0x14u);
    if (held != 0x20u || (pressed & ~0x20u)) return;
    psx_mod_write_word(sp+0x10u, 0x1000u);
    psx_mod_write_word(sp+0x14u, 0x1000u);
    psx_mod_counter_add("dbfb.responsive.followup_lift", 1);
}

/* Only neutral/movement/guard and known normal attacks may carry intent.
 * A hit reaction, cinematic, KO or unknown action discards it immediately. */
static int command_state(unsigned p) {
    const uint32_t control = 0x80072800u+p*0x7Cu;
    const unsigned action = psx_mod_read_word(control+8u) & 255u;
    return (int16_t)psx_mod_read_half(control+0x40u) > 0 &&
           (int16_t)psx_mod_read_half(control+0x42u) >= 0 &&
           (action <= 0x23u || motion_selected(action));
}

static void projectile_reset(void);
static void locomotion_reset(void);
#include "dbfb_combat.h"
#include "dbfb_projectiles.h"
#include "dbfb_locomotion.h"
#include "dbfb_camera_frame.h"

/* Runs at the verified post-gate instruction, including the accepted path that
 * skips the reject store. Buffer recognized commands, not gesture fragments.
 * Never skip the native busy gate, costs, dispatcher or recovery state. */
static void standard_command(struct CPUState* cpu, uint32_t address) {
    if (!cpu || (address & 0x1FFFFFFFu) != 0x54AE8u || !offline_started() ||
        !standard_code() || !s_input_scope.combat ||
        s_input_scope.frame-s_input_scope.poll_frame > MAX_POLL_GAP) {
        command_reset(); return;
    }
    const unsigned p = cpu->gpr[22]; /* s6 = side; s7 = side*0x7c */
    if (p > 1 || cpu->gpr[23] != p*0x7Cu) return;
    const uint32_t control = 0x80072800u+p*0x7Cu;
    const unsigned action_now = psx_mod_read_word(control+8u) & 255u;
    if (!command_state(p)) {
        if (s_followup[p] >= 0)
            psx_mod_counter_add(followup_action(action_now) ?
                "dbfb.responsive.followup_native" :
                "dbfb.responsive.followup_interrupted", 1);
        s_command[p] = -1; s_followup[p] = -1; return;
    }
    const int16_t accepted = (int16_t)psx_mod_read_half(control+0x56u);
    const int16_t recognized = (int16_t)cpu->gpr[4];
    /* Aerial follow-up retention. A follow-up recognised before the airborne
     * flag is armed is held instead of being queued as an ordinary command, and
     * re-injected through control+0x56 once the handler can act. Never queue a
     * second command while a follow-up is pending. */
    const uint32_t follow_flags = psx_mod_read_word(control+4u);
    if (followup_action(action_now) ||
        (recognized >= 0 && recognized != 0x25 && recognized != 0x29)) {
        if (s_followup[p] >= 0)
            psx_mod_counter_add(followup_action(action_now) ?
                "dbfb.responsive.followup_native" :
                "dbfb.responsive.followup_superseded", 1);
        s_followup[p] = -1;
    } else if (recognized == 0x25 || recognized == 0x29) {
        s_command[p] = -1;
        if (!(follow_flags & FOLLOWUP_BUSY)) {
            s_followup[p] = recognized;
            s_followup_birth[p] = s_standard_frame;
            psx_mod_counter_add("dbfb.responsive.followup_wait", 1);
            if (recognized == 0x25)
                followup_lift(cpu, p, accepted, action_now);
        } else {
            s_followup[p] = -1;
        }
    }
    if (s_followup[p] >= 0) {
        if (s_standard_frame-s_followup_birth[p] >= FOLLOWUP_LIFE) {
            s_followup[p] = -1;
            psx_mod_counter_add("dbfb.responsive.followup_expired", 1);
        } else if ((follow_flags & FOLLOWUP_BUSY) && accepted < 0) {
            psx_mod_write_half(control+0x56u, (uint16_t)s_followup[p]);
            s_followup[p] = -1;
            psx_mod_counter_add("dbfb.responsive.followup_inject", 1);
            return;
        } else {
            return; /* still grounded: keep the follow-up pending, queue nothing */
        }
    }
    if (accepted >= 0) { s_command[p] = -1; return; }
    if (recognized >= 0 && recognized <= 0x44) {
        s_command[p] = recognized;
        s_command_birth[p] = s_standard_frame;
        psx_mod_counter_add("dbfb.responsive.command_queued", 1);
        return;
    }
    if (s_command[p] < 0) return;
    if (s_standard_frame-s_command_birth[p] >= 6u) { s_command[p] = -1; return; }
    const uint32_t flags = psx_mod_read_word(control+4u);
    const uint16_t age = psx_mod_read_half(0x8007291Au+p*0x30u);
    if ((flags & 0x60u) && age >= 12u && s_command[p] != 0x25 && s_command[p] != 0x29)
        return;
    psx_mod_write_half(control+0x56u, (uint16_t)s_command[p]);
    s_command[p] = -1;
    psx_mod_counter_add("dbfb.responsive.command_recovered", 1);
}

/* Normal pressure/ki fire get damage proportional to their faster clock.
 * This is the final pre-guard sum (s1), not one guessed component. The native
 * minimum, block formula, HP clamp, hit reaction and accumulated damage remain
 * in the original body. Both human and CPU fighters use this same path. */
static void standard_damage(struct CPUState* cpu, uint32_t address) {
    if (!cpu || (address & 0x1FFFFFFFu) != 0x66D28u || !offline_started() ||
        !standard_code() || !s_input_scope.combat) return;
    const unsigned attacker = cpu->gpr[16], defender = cpu->gpr[18];
    if (attacker > 1 || defender != (attacker ^ 1u)) return;
    const uint32_t control = 0x80072800u+attacker*0x7Cu;
    const unsigned action = psx_mod_read_word(control+8u) & 255u;
    const int damage = (int16_t)cpu->gpr[17];
    if (damage <= 0 || !combat_attacker_ready(attacker, action)) return;
    const int projectile = action >= 0x72u && action <= 0x77u;
    int scaled = damage;
    if (motion_damage_scales(attacker, action) && command_state(attacker))
        scaled = damage*(projectile ? 3 : 4)/(projectile ? 4 : 5);
    scaled = combat_damage(attacker, defender, action, scaled, cpu);
    if (scaled < 1) scaled = 1;
    cpu->gpr[17] = (uint32_t)scaled;
    cpu->gpr[2] = (uint32_t)scaled << 16; /* value consumed by the guarded bgtz */
    psx_mod_counter_add("dbfb.responsive.damage_scaled", 1);
}

/* ---- Unlock all (verified 2026-10-18) -----------------------------------
 * The title screen keeps the unlocked-character bitfield in one 32-bit word.
 * STEP00 initialises it to the ten starting characters; the shipped title code
 * rewrites it when the button code completes. Verified live: the title overlay
 * compares an 18-slot direction ring at 0x80060B10 against the 8-slot table at
 * 0x800562AC (Up, Down, Left, Right twice = Right, Left, Down, Up twice read
 * back to front), stores 0x0001BFFF, then matches the 14-slot table at
 * 0x800562CC and stores 0x0001FFFF (all seventeen fighters).
 *
 * STEP00 +0x328/+0x32c: lui 0x8004; sw -0x433c. The signed address is
 * 0x8003BCC4 (shared data), NOT 0x8004BCC4. We write only the two known roster
 * states, retaining every unknown value. Offline only. */
#define ID_UNLOCK "dbfb.responsive.unlock-all"

#define ADDR_UNLOCK_SET 0x8003BCC4u /* lui 0x8004 + signed -0x433c */
#define UNLOCK_STARTING 0x000007DFu
#define UNLOCK_CHEAT 0x0001BFFFu
#define UNLOCK_ALL 0x0001FFFFu

static void unlock_vblank(void) {
    if (!offline_started()) return;
    const uint32_t value = psx_mod_read_word(ADDR_UNLOCK_SET);
    if (value != UNLOCK_STARTING && value != UNLOCK_CHEAT) return;
    psx_mod_write_word(ADDR_UNLOCK_SET, UNLOCK_ALL);
    psx_mod_counter_add("dbfb.responsive.unlock_all", 1);
}

static void standard_activate(void) {
    motion_reset();
    command_reset();
    combat_reset();
    input_reset();
    s_menu_suspended = 0;
    s_input_scope.frame = 0;
    s_mode = MODE_BUFFER;
    s_window = 2;
    s_ki_mode = 1;
    s_ki_period = 4; /* +1 per eight guest frames; not unlimited ki */
    ki_restore();
    /* script+0x0C is consumed by 0x8006639C to displace the OPPONENT,
     * not demonstrated self-locomotion. Action/pose retiming owns tempo;
     * keep this reaction speed native in the public standard profile. */
    s_speed_mode = SPEED_ORIGINAL;
    speed_restore();
    s_standard_frame = 0;
    s_standard_rule_frame = UINT32_MAX;
}

static void standard_restore(void) {
    motion_restore();
    command_reset();
    combat_reset();
    input_reset();
    s_menu_suspended = 0;
    ki_restore();
    speed_restore();
    s_standard_rule_frame = UINT32_MAX;
}

static void standard_vblank(void) {
    if (!offline_started()) { input_reset(); command_reset(); return; }
    if (!combat_code()) {
        standard_restore();
        return;
    }
    if (!standard_code()) { input_reset(); command_reset(); return; }
    s_standard_frame++;
    s_menu_suspended = 0;
    combat_vblank();
    buffer_vblank();
}

static void standard_poll(struct CPUState* cpu, uint32_t address) {
    if (!cpu || !offline_started() || !standard_code() ||
        menu_buttons(physical_pad(0))) { input_reset(); return; }
    s_menu_suspended = 0;
    buffer_poll(cpu, address);
    if (!s_input_scope.open || s_standard_rule_frame == s_standard_frame) return;
    s_standard_rule_frame = s_standard_frame;
    /* Native pause is known here: the legacy menu latches are not needed. */
    s_rule_suspended[0] = s_rule_suspended[1] = 0;
    ki_tick(cpu, address);
    speed_tick(cpu, address);
    motion_tick();
    combat_poll(cpu, address);
    projectile_poll();
    /* Extend the stock acceptance window by three interpreter ticks, keeping
     * its deadline, busy-state checks, special exceptions and all other gates.
     * Deliberately do NOT use the lab's unconditional Open instruction. */
    if (psx_mod_read_word(ADDR_CHAIN_LIMIT - 4u) == 0 &&
        psx_mod_read_word(ADDR_CHAIN_LIMIT + 4u) == 0x14400008u &&
        psx_mod_read_word(ADDR_CHAIN) == CHAIN_ORIGINAL &&
        psx_mod_read_word(ADDR_CHAIN_LIMIT) == CHAIN_LIMIT_STOCK) {
        psx_mod_write_code_word(ADDR_CHAIN_LIMIT, CHAIN_LIMIT_STANDARD);
        psx_mod_counter_add("dbfb.responsive.standard_chain_patch", 1);
    }
}

static void standard_remap(struct CPUState* cpu, uint32_t address) {
    if (!offline_started() || !standard_code()) {
        input_reset(); return;
    }
    buffer_remap(cpu, address);
}

PSX_MOD_CONSTRUCTOR(dbfb_register_responsive) {
    (void)psx_mod_register_activation_plugin(ID_STANDARD, standard_activate);
    (void)psx_mod_register_vblank_plugin(ID_STANDARD, standard_vblank);
    (void)psx_mod_register_savestate_plugin(ID_STANDARD, standard_restore);
    (void)psx_mod_register_function_entry_plugin(ID_STANDARD, ADDR_POLL, standard_poll);
    (void)psx_mod_register_function_entry_plugin(ID_STANDARD, ADDR_REMAP, standard_remap);
    (void)psx_mod_register_function_filter_plugin(ID_STANDARD, 0x8004E530u, combat_script_filter);
    (void)psx_mod_register_function_filter_plugin(ID_STANDARD, 0x80042240u, combat_animation_filter);
    (void)psx_mod_register_instruction_plugin(ID_STANDARD, 0x80054A60u, AI_ORIGINAL, combat_ai);
    (void)psx_mod_register_instruction_plugin(ID_STANDARD, 0x80054AE8u, 0x02C02021u, standard_command);
    (void)psx_mod_register_instruction_plugin(ID_STANDARD, 0x80066D28u, 0x1C400002u, standard_damage);
    (void)psx_mod_register_instruction_plugin(ID_STANDARD, LOCOMOTION_SITE, LOCOMOTION_ORIGINAL, locomotion_step);
    (void)psx_mod_register_instruction_plugin(ID_STANDARD, DBFB_CAMERA_FRAME_SITE, DBFB_CAMERA_FRAME_WORD, camera_frame_step);
    (void)psx_mod_register_instruction_plugin(ID_STANDARD, PROJECTILE_SPAWN_SITE, 0xA462FFE4u, projectile_spawn);
    (void)psx_mod_register_instruction_plugin(ID_STANDARD, PROJECTILE_XZ_SITE, 0x00021200u, projectile_speed);
    (void)psx_mod_register_instruction_plugin(ID_STANDARD, PROJECTILE_Y_SITE, 0x00021200u, projectile_speed);
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
    (void)psx_mod_register_activation_plugin(ID_KI, ki_activate);
    (void)psx_mod_register_savestate_plugin(ID_KI, ki_restore);
    (void)psx_mod_register_function_entry_plugin(ID_KI, ADDR_POLL, ki_tick);
    (void)psx_mod_register_option_changed_plugin(ID_KI, ki_option_changed);
    (void)psx_mod_register_activation_plugin(ID_SPEED, speed_activate);
    (void)psx_mod_register_savestate_plugin(ID_SPEED, speed_restore);
    (void)psx_mod_register_function_entry_plugin(ID_SPEED, ADDR_POLL, speed_tick);
    (void)psx_mod_register_option_changed_plugin(ID_SPEED, speed_option_changed);
    (void)psx_mod_register_activation_plugin(ID_CHAIN, chain_activate);
    (void)psx_mod_register_savestate_plugin(ID_CHAIN, chain_restore);
    (void)psx_mod_register_function_entry_plugin(ID_CHAIN, ADDR_POLL, chain_tick);
    (void)psx_mod_register_option_changed_plugin(ID_CHAIN, chain_option_changed);
    (void)psx_mod_register_vblank_plugin(ID_UNLOCK, unlock_vblank);
}
