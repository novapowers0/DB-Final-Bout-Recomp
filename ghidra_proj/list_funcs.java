// Analyze FinalBout: enumerate functions, find combat-relevant ones.
// @category Analysis
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.*;

public class list_funcs extends GhidraScript {
    @Override
    public void run() throws Exception {
        FunctionManager fm = currentProgram.getFunctionManager();
        SymbolTable st = currentProgram.getSymbolTable();

        println("==== FUNCTION COUNT ====");
        println(fm.getFunctionCount());

        println("==== FIRST 50 FUNCTIONS ====");
        int n = 0;
        for (Function f : fm.getFunctions(true)) {
            if (n++ >= 50) break;
            println(String.format("%08X  %5d  %s",
                f.getEntryPoint().getOffset(), f.getBody().getNumAddresses(), f.getName()));
        }

        println("==== FUNCTIONS REFERENCING 0x1F801040 (SIO0) ====");
        Address sio = toAddr(0x1F801040);
        ReferenceIterator refs = st.getReferences(sio);
        java.util.Set<Long> seen = new java.util.HashSet<Long>();
        while (refs.hasNext()) {
            Reference r = refs.next();
            Address a = r.getFromAddress();
            Function f = fm.getFunctionContaining(a);
            if (f != null && !seen.contains(f.getEntryPoint().getOffset())) {
                seen.add(f.getEntryPoint().getOffset());
                println(String.format("%08X  %s", f.getEntryPoint().getOffset(), f.getName()));
            }
        }
        println("SIO0 ref funcs: " + seen.size());

        println("==== FUNCTIONS REFERENCING 0x1F800000 (scratch) ====");
        Address scr = toAddr(0x1F800000);
        ReferenceIterator refs2 = st.getReferences(scr);
        java.util.Set<Long> seen2 = new java.util.HashSet<Long>();
        while (refs2.hasNext()) {
            Reference r = refs2.next();
            Address a = r.getFromAddress();
            Function f = fm.getFunctionContaining(a);
            if (f != null) seen2.add(f.getEntryPoint().getOffset());
        }
        println("scratch ref funcs: " + seen2.size());
    }
}
