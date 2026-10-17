"""One STEP40 native-coverage iteration against a LIVE game (debug port 4370).

Run it while a fight is on screen. It never guesses a function start: a new
entry is accepted only when the interpreter observed a dispatch into it whose
return address follows a real `jal`/`jalr` (so it is a call target) and the
code bytes come from the live fight RAM. It appends those entries to the
matching [[overlays]] block of game.toml (0x8003E000 below the 0x80060000
member, 0x80060000 above), builds synthetic full-region captures from the live
RAM (kept in the temp dir: they contain disc bytes and must never be committed
or published) and recompiles both regions with psxrecomp/tools/compile_overlays.py.

Afterwards: close the game, delete superseded 0003E000_*/00060000_* DLL
generations from build-release/cache/** (keep the newest), start a new fight and
compare dispatch_native / dirty_ram_insns.
"""
import json, re, tomllib, struct, glob, base64, subprocess, os, sys, binascii, socket

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.environ.get("TEMP", ROOT)
PORT = 4370
_id = [1]


def _recv_obj(s):
    buf = bytearray()
    depth = 0
    in_str = False
    esc = False
    started = False
    pos = 0
    while True:
        chunk = s.recv(1 << 20)
        if not chunk:
            break
        buf.extend(chunk)
        n = len(buf)
        while pos < n:
            c = buf[pos]
            if in_str:
                if esc:
                    esc = False
                elif c == 0x5C:
                    esc = True
                elif c == 0x22:
                    in_str = False
            else:
                if c == 0x22:
                    in_str = True
                elif c == 0x7B:
                    depth += 1
                    started = True
                elif c == 0x7D:
                    depth -= 1
                    if started and depth == 0:
                        return json.loads(buf[:pos + 1].decode())
            pos += 1
    return json.loads(buf.decode().strip())


_id = [1]


def cmd(name, timeout=15.0, **params):
    req = {"cmd": name, "id": _id[0]}
    _id[0] += 1
    req.update(params)
    s = socket.create_connection(("127.0.0.1", PORT), timeout=timeout)
    try:
        s.sendall((json.dumps(req) + "\n").encode())
        return _recv_obj(s)
    finally:
        s.close()


SC = SCRATCH
# 1) live RAM + per_pc
r = cmd("read_ram", addr="0x0", len=0x200000, timeout=60)
ram = binascii.unhexlify(r["hex"]); open(os.path.join(SC, "ram_cov.bin"), "wb").write(ram)
W = lambda a: struct.unpack_from("<I", ram, a & 0x1FFFFF)[0]
d = cmd("dirty_ram_stats", timeout=60)
live = set(); targets = {}
for x in d["per_pc"]:
    pc = int(x["pc"], 16) | 0x80000000; ra = int(x["ext_ra"], 16)
    live.add(pc)
    if not (0x8003E000 <= pc < 0x80073000) or ra == 0 or ra & 3 or ra == pc: continue
    site = ra - 8
    if not (0x80010000 <= site < 0x80080000): continue
    w = W(site)
    if ((w >> 26) == 0 and (w & 0x3F) == 9) or (w >> 26) == 3: targets[pc] = (x["insns"], hex(ra))
raw = open(os.path.join(ROOT, "game.toml"), "rb").read().decode("utf-8")
cur = tomllib.loads(raw)
decl = {o["load_addr"]: set(int(v, 16) for v in o["function_entry_pcs"]) for o in cur["overlays"]}
alld = set().union(*decl.values())
lo = sorted(a for a in targets if a < 0x80060000 and a not in decl["0x8003E000"])
hi = sorted(a for a in targets if a >= 0x80060000 and a not in decl["0x80060000"])
print("new low", [hex(a) for a in lo]); print("new high", [hex(a) for a in hi])
if not lo and not hi: print("NOTHING NEW"); sys.exit(0)
def rewrite(raw, base, adds):
    if not adds: return raw
    m = re.search(r'(load_addr = "%s"\r?\nfunction_entry_pcs = \[\r?\n)(.*?)(\r?\n\])' % base, raw, re.S)
    ents = sorted(set(int(x, 16) for x in re.findall(r'0x8[0-9A-Fa-f]{7}', m.group(2))) | set(adds))
    nl = "\r\n" if "\r\n" in raw else "\n"
    rows = nl.join("  " + " ".join('"0x%08X",' % a for a in ents[i:i+5]) for i in range(0, len(ents), 5))
    return raw[:m.start(2)] + rows + raw[m.end(2):]
raw = rewrite(rewrite(raw, "0x8003E000", lo), "0x80060000", hi)
open(os.path.join(ROOT, "game.toml"), "wb").write(raw.encode("utf-8")); tomllib.loads(raw)
# 2) captures + compile
def build(BASE, END, out):
    ex = set(p for p in live if BASE <= p < END)
    for f in glob.glob(ROOT + r"\build-release\overlay_captures.json.d\*.json"):
        try: j = json.load(open(f))
        except Exception: continue
        for rr in (j if isinstance(j, list) else [j]):
            la = int(rr["load_addr"], 16); b = base64.b64decode(rr["bytes_b64"])
            for p in rr["executed_pcs"]:
                p = int(p, 16)
                if BASE <= p < END and la <= p < la + len(b) - 4 and b[p-la:p-la+4] == ram[p & 0x1FFFFF:(p & 0x1FFFFF)+4]: ex.add(p)
    SZ = END - BASE
    rec = {"schema": "psxrecomp overlay capture v2", "load_addr": "0x%08X" % BASE, "size": SZ + 4, "guard_bytes": 4,
           "bytes_b64": base64.b64encode(ram[BASE & 0x1FFFFF:(BASE & 0x1FFFFF) + SZ + 4]).decode(),
           "executed_pcs": ["0x%08X" % p for p in sorted(ex)], "dispatch_entry_pcs": [], "function_entry_pcs": [], "seeds": []}
    json.dump([rec], open(os.path.join(SC, out), "w"))
build(0x8003E000, 0x80060000, "cap_low3.json"); build(0x80060000, 0x80072358, "cap_high3.json")
env = dict(os.environ); env["PATH"] = r"C:\msys64\mingw64\bin;" + env["PATH"]
for c, touched in (("cap_low3.json", lo), ("cap_high3.json", hi)):
    if not touched: continue
    out = subprocess.run(["python", os.path.join(ROOT, "psxrecomp", "tools", "compile_overlays.py"), "--captures", os.path.join(SC, c),
        "--game-toml", os.path.join(ROOT, "game.toml"), "--recompiler", os.path.join(ROOT, "build-recompiler", "psxrecomp-game.exe"),
        "--runtime-include", os.path.join(ROOT, "psxrecomp", "runtime", "include"), "--project-root", os.path.join(ROOT, "psxrecomp"),
        "--out-dir", os.path.join(ROOT, "build-release", "cache"), "--gcc", r"C:\msys64\mingw64\bin\gcc.exe"], capture_output=True, text=True, env=env, cwd=ROOT)
    print("\n".join(l for l in out.stdout.splitlines() if re.search(r"^Overlay |Function definitions|FAILED|PSX_SHARD", l)), out.returncode)
