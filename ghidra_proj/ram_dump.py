"""Volcado de RAM a archivo para análisis offline. UNA conexion por bloque.
Uso: python ram_dump.py <addr_hex> <num_words> <archivo_salida>
Cada word se guarda como 4 bytes little-endian (8 MB de RAM ~ 2M words).
"""
import socket, json, time, sys

HOST, PORT = '127.0.0.1', 4370
BLOCK = 500

def connect():
    for _ in range(60):
        try: return socket.create_connection((HOST, PORT), timeout=3)
        except OSError: time.sleep(0.5)
    return None

def mem_block(start, nwords):
    s = connect()
    if not s: return None
    try:
        s.settimeout(4)
        s.sendall((json.dumps({"cmd":"mem_words","addr":"0x%08X"%start,"count":nwords})+'\n').encode('ascii'))
        data = b''
        while b'\n' not in data:
            c = s.recv(8192)
            if not c: break
            data += c
        r = json.loads(data.split(b'\n')[0].decode('ascii','replace'))
        return [int(w,16) for w in r.get('words',[])]
    except Exception:
        return None
    finally:
        try: s.close()
        except Exception: pass

def main():
    start = int(sys.argv[1],16); n = int(sys.argv[2],10); path = sys.argv[3]
    out = bytearray()
    ok = 0
    for off in range(0, n, BLOCK):
        cnt = min(BLOCK, n-off)
        ws = mem_block(start + off*4, cnt)
        if ws is None:
            print("fallo en bloque 0x%08X"%(start+off*4)); continue
        for w in ws:
            out += w.to_bytes(4,'little')
        ok += len(ws)
        print("volcado %d/%d words"%(ok, n))
    with open(path,'wb') as f:
        f.write(bytes(out))
    print("==> %d words -> %s"%(ok, path))

main()
