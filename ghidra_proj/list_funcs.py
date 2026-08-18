# Analyze FinalBout: enumerate functions, find combat-relevant ones.
# Run via analyzeHeadless -postScript
import ghidra.program.model.listing as listing
from ghidra.program.model.address import Address
from ghidra.program.model.symbol import RefType
from ghidra.program.model.lang import OperandType

fm = currentProgram.getFunctionManager()
lm = currentProgram.getListing()
st = currentProgram.getSymbolTable()

print("==== FUNCTION COUNT ====")
print(fm.getFunctionCount())

# Collect all functions
funcs = []
it = fm.getFunctions(True)
while it.hasNext():
    f = it.next()
    funcs.append(f)

print("==== FIRST 40 FUNCTIONS ====")
for f in funcs[:40]:
    body = f.getBody()
    print("%08X  %5d  %s" % (f.getEntryPoint().getOffset(), body.getNumAddresses(), f.getName()))

# Find functions referencing SIO0 (0x1F801040) and pad constants
print("==== FUNCTIONS REFERENCING 0x1F801040 (SIO0) ====")
sio = toAddr(0x1F801040)
refs = st.getReferences(sio)
seen = set()
for r in refs:
    a = r.getFromAddress()
    f = fm.getFunctionContaining(a)
    if f and f.getEntryPoint().getOffset() not in seen:
        seen.add(f.getEntryPoint().getOffset())
        print("%08X  %s" % (f.getEntryPoint().getOffset(), f.getName()))

# Find references to 0x800 (common scratch / VRAM offsets) - look for large global struct
print("==== FUNCTIONS REFERENCING 0x1F800000 scratch ====")
scr = toAddr(0x1F800000)
refs = st.getReferences(scr)
seen = set()
cnt = 0
for r in refs:
    a = r.getFromAddress()
    f = fm.getFunctionContaining(a)
    if f and f.getEntryPoint().getOffset() not in seen:
        seen.add(f.getEntryPoint().getOffset())
        cnt += 1
print("count:", cnt)
for f_off in list(seen)[:20]:
    print("%08X" % f_off)
