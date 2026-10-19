/* Pure emitter test process, never the game's runtime. Private poses on stdin. */
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
#include "../../src/mods/dbfb_rig_bridge.h"

static uint32_t get32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static int readpose(DbfbBridgePose *p) {
    uint8_t b[22];
    if (fread(b, 1, sizeof b, stdin) != sizeof b) return 0;
    for (unsigned i = 0; i < 3; ++i) {
        p->angle[i] = (int16_t)((unsigned)b[2*i] | (unsigned)b[2*i+1]<<8);
        p->translation[i] = (int16_t)((unsigned)b[6+2*i] | (unsigned)b[7+2*i]<<8);
        p->scale[i] = (uint16_t)((unsigned)b[12+2*i] | (unsigned)b[13+2*i]<<8);
    }
    p->known = get32(b+18);
    return 1;
}
int main(void) {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    uint8_t header[20], output[43000], original[43000], length[4];
    DbfbBridgePose a[64] = {0}, b[64] = {0};
    if (dbfb_bridge_arc(4090, 6) != 12 || dbfb_bridge_arc(6, 4090) != -12 ||
        dbfb_bridge_arc(0, 2048) != -2048) return 2;
    while (fread(header, 1, sizeof header, stdin) == sizeof header) {
        const uint64_t mask = get32(header) | (uint64_t)get32(header+4)<<32;
        const uint64_t protected_parts = get32(header+8) | (uint64_t)get32(header+12)<<32;
        const unsigned ticks = get32(header+16);
        for (unsigned i = 0; i < 64; ++i) if (!readpose(a+i)) return 3;
        for (unsigned i = 0; i < 64; ++i) if (!readpose(b+i)) return 4;
        memset(output, 0xCD, sizeof output);
        memcpy(original, output, sizeof output);
        if (dbfb_bridge_build(output, 1, a, b, mask, protected_parts, ticks) ||
            memcmp(output, original, sizeof output)) return 5;
        if (dbfb_bridge_build(output, sizeof output, a, b, mask | protected_parts,
                protected_parts, ticks) || memcmp(output, original, sizeof output)) return 6;
        unsigned first = 0;
        while (first < 64 && !((mask >> first) & 1u)) ++first;
        if (first == 64) return 10;
        const unsigned known = a[first].known;
        a[first].known = 0;
        if (dbfb_bridge_build(output, sizeof output, a, b, mask, protected_parts, ticks) ||
            memcmp(output, original, sizeof output)) return 11;
        a[first].known = known;
        const uint16_t scale = a[first].scale[0];
        a[first].scale[0] ^= 1;
        if (dbfb_bridge_build(output, sizeof output, a, b, mask, protected_parts, ticks) ||
            memcmp(output, original, sizeof output)) return 12;
        a[first].scale[0] = scale;
        const size_t size = dbfb_bridge_build(output, sizeof output, a, b, mask, protected_parts, ticks);
        if (!size || size > sizeof output) return 7;
        dbfb_bridge_put(length, (uint32_t)size);
        if (fwrite(length, 1, 4, stdout) != 4 || fwrite(output, 1, size, stdout) != size) return 8;
    }
    return ferror(stdin) ? 9 : 0;
}
