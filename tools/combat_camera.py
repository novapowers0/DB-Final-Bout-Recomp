"""R4 camera ownership metadata and private-image checks; no runtime or writes.

Uses combat_map's ISO reader and capture-verified relocation. JSON output contains
addresses, hashes and findings, not extracted retail code. --check also checks
the C probe's guards against the image. No build, installation or network.

R4 projection/recorte finding (offline disasm, no runtime):
- The general branch hands context+0x50 to 0x80044824 -> 0x80024850, which
  builds a Q12 view matrix (rotation from eye/target + translation -eye) with
  sin/cos tables (0x80020100/0x800201CC, table 0x8003DDA4) and writes 8 words
  to 0x8003BE78 (scratch, also read by 0x8002457C) and 0x8003B920.
- GTE projection consumers: 0x80020578 RTPS, 0x80021CD4 RTPT, fed via
  0x800227FC/0x8002282C (0x8003BB48 x node -> L matrix). Projection constants
  are set at 0x8002399C..0x800239E8 (DQB=0x155, ZSF3=0x100, OFY=0x3E8,
  H=0xEF9E, DQA=0x140, OFX/BFC=0).
- The PRE seam 0x80054F34 is NOT a safe writer: native 0x800442A8 runs after it
  and rewrites context+0x50 (target words snapped from destination at
  0x800443E0-0x800443E8; eye words at 0x800444B8-0x800444C4; dest+delta
  paths at 0x800446EC-0x80044748). 0x8004778C later adds shake to +0x54/+0x60
  (0x80047974/0x80047990). No writer is implemented; see write_seam_decision.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from combat_exe import ExeImage
from combat_map import BattleImage, ROOT, sha, step40

SHA256 = "001adcdc2e129d3bd715c29b64e393fa8c2901a7ef39c2347874b321aae6b9dd"
HEADER = ROOT / "src/mods/dbfb_camera.h"
# These are complete windows actually read with combat_map.py disasm START END.
WINDOWS = (
    (0x80047F68, 0x800480C8, "fd0d74a6b7fe6a77206aab0d37a01a3effc24291be7fec19e67b8077166a466b"),
    (0x80054E90, 0x80054F38, "6c19d550463d5cf982bc533c8c396a3ac901ad7735c238a4c995115d39c71caa"),
    (0x80054F10, 0x80055460, "30a9f1f68185b927b9cd8beb1878a522252daa28516d4dd58052653545617078"),
    (0x80043CA8, 0x80043FC0, "6cb1b4ab425e29e7f28478474c65db66ae93b4bdcdb09dccf2575de0706a640e"),
    (0x80044084, 0x800442A8, "343c64f8e56a3869ec6e93ae49217aa1f7f246b0aad2bb226b9ec18c3a64516d"),
    (0x800442A8, 0x8004477C, "ea4ab6f36c1fba4948879491b7bfdb959324555a028ffb8840b31595014b5619"),
    (0x8004E938, 0x8004EAA0, "7bc287fb838e4517c7bd22ce2792bdcccb0ba8ea42a9a8cb9af1c5e051c7fa0a"),
    (0x800506C8, 0x80050900, "ab33e932d53e4fbe202cd61fb80d3e77b8dd60e96b2e3807375033a9e6beebff"),
    (0x8004EDFC, 0x8004EEB0, "4b658feca1e9e791d190f945b816995d0f000a1560904156efe0d0c11bf23651"),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(image, header):
    require(sha(image.data) == SHA256 and image.base == 0x8003DFA0,
            "Unsupported STEP40 hash/base; no camera claim applies")
    for start, end, digest in WINDOWS:
        require(sha(image.data[start-image.base:end-image.base]) == digest,
                f"Camera evidence window changed: {start:08X}..{end:08X}")
    defines = dict(re.findall(r"^#define (DBFB_CAMERA_\w+)\s+(0x[0-9A-Fa-f]+)u", header, re.M))
    block = header.split("static const uint32_t anchors[][2] = {", 1)[1].split("};", 1)[0]
    anchors = re.findall(r"\{(\w+),\s*(\w+)\}", block)
    require(len(anchors) == 18, "Unexpected probe identity guard count")
    for address, expected in anchors:
        pc = int(defines.get(address, address).removesuffix("u"), 0)
        word = int(defines.get(expected, expected).removesuffix("u"), 0)
        require(image.word(pc) == word, f"Probe guard mismatch at {pc:08X}")
    for prefix in ("PRE", "POST", "END"):
        pc = int(defines[f"DBFB_CAMERA_{prefix}_SITE"], 0)
        require(pc in image.executed, f"Proposed seam has no matching execution evidence: {pc:08X}")
    # Native opcode dispatch, not a historical opcode name guess.
    require(image.word(0x8003E78C + 0x21*4) == 0x8004E960, "Opcode21 handler changed")
    require(image.word(0x8003E78C + 0x22*4) == 0x8004E988, "Opcode22 handler changed")
    # Direct-reference search is bounded and deliberately not advertised as a
    # whole-program alias analysis. Other overlays/DMA/indirect stores are unknown.
    stores = {}
    refs = list(image.xrefs())
    for target, expected in ((0x800AA194, [0x8004E96C, 0x80054384]),
                             (0x800A9D0C, [0x80047FA4])):
        actual = sorted({pc for pc, dst, kind, _ in refs if dst == target and kind == "sw"})
        require(actual == expected, f"Direct camera writers changed: {target:08X}")
        stores[f"0x{target:08X}"] = [f"0x{pc:08X}" for pc in actual]
    require(not re.search(r"\bpsx_mod_(?:write\w*|counter_add)\s*\(", header),
            "Investigation probe unexpectedly writes guest/telemetry")
    # Why the PRE seam must not be used as a writer: 0x800442A8 and 0x8004778C
    # run after 0x80054F34 and rewrite parts of context+0x50 before 0x80044824.
    overwrite = (
        (0x80054F90, 0x0C011209), (0x80054F94, 0x24840050),  # delivery call
        (0x8004433C, 0x1040007F), (0x80044344, 0x31426000),  # context+8 selects path
        (0x800443E0, 0x8CA20000), (0x800443E8, 0xAC820000),  # target <- dest
        (0x80044328, 0xAD230070), (0x80044340, 0xAD280084),  # prev <- cur
        (0x800444B8, 0x8C820000), (0x800444C4, 0xAC820000),  # eye step/snap
        (0x800446EC, 0xAD220050), (0x80044748, 0xAC820000),  # dest+delta
        (0x80047974, 0xACE20004), (0x80047990, 0xACE20010),  # shake +0x54/+0x60
        (0x800476F8, 0x8CC20050), (0x80047704, 0xACC200B0),  # transition delta
    )
    for pc, word in overwrite:
        require(image.word(pc) == word, f"PRE-seam overwrite evidence changed: {pc:08X}")
    return {"identity_guards": len(anchors), "hashed_windows": len(WINDOWS),
            "executed_seams": 3, "direct_writers_in_STEP40": stores,
            "pre_seam_overwrite_words": len(overwrite)}


def verify_exe(exe):
    """Pin the EXE side of the camera chain against the verified main binary."""
    words = {
        0x80024850: 0x27BDFF48, 0x80024858: 0x00809021, 0x800248BC: 0x8E450018,
        0x800248C0: 0x0C00904F, 0x80024D10: 0x02202021, 0x80024D48: 0x8E44001C,
        0x80024DF0: 0x3C058004, 0x80024DF4: 0x24A5B920, 0x80024E34: 0xACA3001C,
        0x80024E54: 0x03E00008, 0x8002413C: 0x27BDFFC0, 0x800241F4: 0x00804821,
        0x80022DAC: 0x8C880000, 0x80022C4C: 0x8C880000, 0x80022A14: 0x27BDFFD0,
        0x8002282C: 0x27BDFFC0, 0x800227FC: 0x27BDFFE8, 0x8002457C: 0x27BDFFE0,
        0x80024824: 0x3C048004, 0x8002482C: 0x0C008A64,
        0x80020578: 0x4A180001, 0x80021CD4: 0x4A280030, 0x80021C58: 0x8C880000,
        0x8002399C: 0x24080155, 0x800239A8: 0x24080100, 0x800239B4: 0x240803E8,
        0x800239C0: 0x2408EF9E, 0x800239CC: 0x3C080140, 0x800239D8: 0x48C0C000,
        0x800239DC: 0x48C0C800,
    }
    for pc, word in words.items():
        require(exe.word(pc) == word, f"Main EXE camera chain changed: {pc:08X}")
    return {"exe_checked_words": len(words),
            "delivery": "0x80054F90 jal 0x80044824 (a0=+0x50) -> 0x8004482C jal 0x80024850",
            "builder_stores": "0x8003BE78..+0x1C scratch; 0x8003B920..+0x1C at 0x80024DF0..",
            "gte": "RTPS 0x80020578; RTPT 0x80021CD4; constants at 0x8002399C..",
            "note": "0x80024850 also reads +0x68/-[+0x68] into 0x8002413C and gates on +0x6C"}


def report(checks):
    return {
        "task": "R4", "status": ("CLOSED as analysis: framing NOT implemented. The mandated "
                                 "PRE seam 0x80054F34 is overwritten by native 0x800442A8/"
                                 "0x8004778C before 0x80044824 consumes context+0x50, so a "
                                 "write there cannot reach the matrix deterministically."),
        "source_sha256": SHA256, "base": "0x8003DFA0", "checks": checks,
        "projection_chain": {
            "delivery": ("0x80054F8C lw a0,[0x800A9D0C]; 0x80054F94 addiu a0,a0,0x50; "
                         "0x80054F90 jal 0x80044824; 0x8004482C jal 0x80024850 (a0=context+0x50)"),
            "builder_inputs": ("0x80024858 s2=a0; eye +0x00/+0x04/+0x08, at +0x0C/+0x10/+0x14; "
                               "0x800248BC lw a1,+0x18(s2)=context+0x68 -> 0x8002413C(-w7); "
                               "0x80024D48 lw a0,+0x1C(s2)=context+0x6C gates 0x800242B8/"
                               "0x800240EC/0x80022990. Block is 8 words, not 6."),
            "math": ("sq distance 0x800248D4-0x80024914; yaw/pitch via LZCR divides "
                     "0x80024930-0x80024C00; rotation matrices 0x800241F4(a3=0x78/0x79, "
                     "sin/cos 0x80020100/0x800201CC, table 0x8003DDA4); matrix multiply via "
                     "GTE MVMVA 0x80022DAC; translation = R*(-eye) via 0x80022C4C at 0x80024D10"),
            "writes": ("0x8003BE78..0x8003BE97 scratch (also consumed by 0x8002457C for scene "
                       "objects); final 8 words copied to 0x8003B920..0x8003B93F at "
                       "0x80024DF0-0x80024E38. No direct reader of 0x8003B920 was found in "
                       "any disc code; runtime-computed aliases are not excluded."),
            "gte_projection": ("RTPS 0x80020578 and RTPT 0x80021CD4 with H/OFX/OFY; RT/TR loaded "
                               "by 0x80021C58/0x80021C88 from the node; 0x8002282C multiplies "
                               "0x8003BB48 x node into the L matrix; 0x800227FC loads node RT/TR"),
            "clip_and_limits": ("Constants set at 0x8002399C-0x800239E8: DQB=0x0155, ZSF3=0x0100, "
                                "OFY=0x03E8, H=0xEF9E (61342 as uint16), DQA=0x0140, OFX=0, "
                                "BFC=0. Projection is GTE RTPS/RTPT (EXE 0x80020578/0x80021CD4; "
                                "STEP40 renderer 0x80040340+). Recorte: STEP40 runs RTPT then "
                                "NCLIP (0x80040368, executed, MAC0 stored) and conditionally "
                                "skips the primitive (blez 0x80040388) = native backface cull. "
                                "The only near guard is the GTE division overflow (2*SZ3 <= H "
                                "saturates, FLAG.DIV_OVF); no far clip. Depth ordering via OTZ "
                                "(AVSZ3/4 0x8002515C/0x80025180) and SZ3>>2 from 0x80020594."),
            "write_seam_decision": {
                "pre_54F34": "REJECTED: native writers run after it (see checks)",
                "post_54F4C": ("after 0x800442A8 but before 0x8004778C; only additive shake on "
                               "+0x54/+0x60 remains, so it is the viable future seam"),
                "eve_of_delivery_54F88": ("last safe instruction slot (lui a0) before the "
                                          "context load and jal 0x80044824"),
                "action": ("no psx_mod writes and no dbfb.responsive.camera_framing counter "
                           "added; such a seam needs a new registered instruction site and "
                           "overlay regeneration, decided outside this task"),}},
        "projection_limits_note": ("H=0xEF9E is consumed by the hardware divide as unsigned "
                                   "16-bit; near guard triggers when 2*SZ3 <= 61342. SZ3 is "
                                   "Q12 (>>12) so a writer changing only +0x50 changes the "
                                   "matrix, never these constants."),
        "owner": {
            "pointer": "0x800A9D0C", "initialized_context": "0x800A9FA0",
            "initializer": "0x80047F78: zero 0x1F0 bytes, then publish pointer at 0x80047FA4",
            "initializer_caller": "0x80054334 (round setup)",
            "global_mode": "0x800AA194: opcode21 stores operand byte at 0x8004E96C; setup stores s1 at 0x80054384",
            "setup_value": "Not inferred from s1 at an interior setup window",
            "branch": "0x80054EC4: mode==1; delay slot ALWAYS publishes mode at context+0x158",
            "update_lock": "context+0 checked at 0x80054ED4; nonzero skips to 0x8005512C",
            "important": "0x800A8680==0 only describes direct source coordinates; it does NOT select the general branch",
        },
        "fields": {
            "0x00": "update suppression gate, not a fully mapped state enum",
            "0x04/0x08/0x0C": "camera control/internal-shot/event flags; not fully classified",
            "0x40..0x48": "fighter midpoint from control+0x0C..0x14 (43DD4/43DF4/43E1C)",
            "0x50..0x64": "current eye XYZ / target XYZ inputs",
            "0x70..0x84": "previous current shot, copied at 44328..44340",
            "0x90..0xA4": "destination eye/target, selected by 43CA8 and adjusted by 54444",
            "0xB0..0xC4": "current minus destination, established by 476C0; replayed by interpolation",
            "0x158": "published global mode; not a second independent camera selector",
            "0x168/0x16A/0x184": "interpolation clock/limit and held-shot countdown",
        },
        "general_order": [
            "54F08 -> 46E08: classify camera events for both fighters",
            "54F18 -> 47408: reconcile internal shot flags",
            "54F24 -> 43CA8: copy fighter data/midpoint, dispatch destination by context+8",
            "44228/44240/4425C/44274 -> 44B50/44FE8/45200/433BC: internal shot/default destination",
            "54F2C -> 54444: conditional destination offset for action95..9F and height guards",
            "54F44 -> 442A8: previous=current, interpolate current toward destination or add transition delta",
            "54F54 -> 4778C, conditional 54F80 -> 4477C: later native shot effects",
            "54F90 -> 44824 -> 24850: native matrix routine receives context+50",
            "54FA8 -> 47FE8, 54FB0 -> 48464, 54FB8 -> 486AC: turn/orbit/background state",
            "5512C: common rendering boundary; some incoming paths skipped camera updates",
        ],
        "scripted_order": [
            "mode!=1 branches to 54FE8, NOT to the general camera",
            "44824(source8664), 448A8, copy current to destination, preserve background state",
            "8680==0: copy 8 source words to context+50 at 55070..550AC",
            "8680!=0: node-relative transform 506C8 at 550E4",
            "550FC -> 4DEFC, 55104 -> 4E0BC, 5510C -> 4E258",
        ],
        "restoration": [
            "Opcode21 value1 clears context+6C at 4E984; other values join the common interpreter tail at 4EE00. No camera restore store occurs in the examined 4EDFC..4EEB0 tail; it advances the interpreter and publishes the action.",
            "Opcode22 replaces source8664..867C and direct-node8680, independently of the mode selector.",
            "476C0 saves current-destination as transition delta; 442A8 consumes it. This is native transition preservation, not proof of a mod restoration contract.",
            "Read-only probe: reset/discard host sample on activation, restore, disable, offline loss or code change; no RAM rollback.",
            "Future writer: do not copy back all context arrays after native handoff or save/load. Value equality alone cannot prove no native writer intervened.",
        ],
        "integration_proposal": {
            "include": 'src/mods/dbfb_responsive.c after psx_mod declarations: #include "dbfb_camera.h"',
            "instruction_sites": [
                {"pc": "0x80054F34", "original": "0x3C05800B", "phase": "before interpolation",
                 "writer": "REJECTED: 0x800442A8 runs after this PC and rewrites context+0x50"},
                {"pc": "0x80054F4C", "original": "0x3C04800B", "phase": "after interpolation, before effects",
                 "writer": "candidate: only additive shake (+0x54/+0x60) follows before 0x80044824"},
                {"pc": "0x80054F88", "original": "0x3C04800B", "phase": "eve of the matrix call",
                 "writer": "candidate: last slot before the context load feeding 0x80044824"},
                {"pc": "0x8005512C", "original": "0x3C048008", "phase": "common render boundary"},
            ],
            "callback": "dbfb_camera_capture(&sample, address, guest_frame, offline_started(), s_input_scope.combat)",
            "gates": "Call only while owning plugin is enabled; offline_started must exclude netplay/resimulation. Probe checks native pause, code, context and object pointers.",
            "export": "Parent must publish structured samples through existing instrumentation; no printf, no new private ring silently assumed.",
            "restore": "dbfb_camera_reset(&sample) on activation/save-load/disable/context loss; do not cache identity across restores",
            "build": "Parent must declare instruction sites in source config and regenerate overlays before expecting callbacks; no integration made here.",
        },
        "pending": [
            "Choose the future writer seam (0x80054F4C or 0x80054F88) with a new registered instruction site; the mandatory PRE 0x80054F34 seam is disproven as a writer.",
            "Complete all destination builders and context+4/+8 producers/cleanup: distinguish ordinary flight from internal cinematic shots while mode remains1.",
            "Trace script producers that return mode to1 and round setup s1 reaching 54384; bounded direct writers are not complete alias/DMA ownership.",
            "No reader of 0x8003B920 exists in any disc code; confirm the live handoff (0x8003BE78 -> 0x8002457C objects) with a runtime sample before any framing change.",
            "Establish visible model extents, not just fighter roots; demonstrate both complete fighters fit before selecting a framing correction and restoration seam.",
        ],
        "limits": ["Static bytes and historical executed-PC matches only; no new play session.",
                   "No runtime/build performed; C probe has not been compiled.",
                   "No camera writes implemented; the mandated PRE seam is disproven, so no framing and no dbfb.responsive.camera_framing counter exist."]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disc", type=Path, default=ROOT / "disc/Dragon Ball GT - Final Bout (USA).bin")
    parser.add_argument("--captures", type=Path, default=ROOT / "build-release/vault/overlay_captures.json")
    parser.add_argument("--exe", type=Path, default=ROOT / "disc/SLUS_004.93")
    parser.add_argument("--check", action="store_true", help="Validate identity/guards without printing the full report")
    args = parser.parse_args()
    data, _ = step40(args.disc)
    require(sha(data) == SHA256, "Unsupported STEP40 hash; refusing camera analysis")
    image = BattleImage(data, args.captures)
    checks = verify(image, HEADER.read_text(encoding="utf-8"))
    checks.update(verify_exe(ExeImage(args.exe)))
    print(json.dumps({"camera_static_checks": "PASS", **checks} if args.check else report(checks), indent=2))


if __name__ == "__main__":
    main()
