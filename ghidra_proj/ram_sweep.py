"""Muestreo continuo de una zona de RAM: lee N muestras (con delay) y reporta
para cada direccion cuantas veces cambio y el rango de valores.
Protocolo debug server: UNA conexion por comando. Cada bloque usa su conexion.
"""
import socket, json, time, sys

HOST, PORT = '127.0.0.1', 4370
BLOCK = 500

def connect():
    for _ in range(60):
        try:
            return socket.create_connection((HOST, PORT), timeout=3)
        except OSError:
            time.sleep(0.5)
    return None

def mem_block(start, nwords):
    s = connect()
    if not s: return {}
    out = {}
    try:
        s.settimeout(3)
        s.sendall((json.dumps({"cmd":"mem_words","addr":"0x%08X"%start,"count":nwords})+'\n').encode('ascii'))
        data = b''
        while b'\n' not in data:
            c = s.recv(8192)
            if not c: break
            data += c
        r = json.loads(data.split(b'\n')[0].decode('ascii','replace'))
        for i,w in enumerate(r.get('words',[])):
            out[start + i*4] = int(w,16)
    except Exception:
        pass
    finally:
        try: s.close()
        except Exception: pass
    return out

def read_zone(start, nwords):
    out = {}
    for off in range(0, nwords, BLOCK):
        out.update(mem_block(start + off*4, min(BLOCK, nwords-off)))
    return out

def main():
    start = int(sys.argv[1],16); n = int(sys.argv[2],10)
    iters = int(sys.argv[3]); delay = float(sys.argv[4])
    samples = []
    for i in range(iters):
        if i > 0: time.sleep(delay)
        z = read_zone(start, n)
        if not z:
            print("muestra %d FALLO lectura"%(i+1)); continue
        samples.append(z)
        print("muestra %d leida (%d words)"%(i+1,len(z)))
    if not samples: print("sin datos"); sys.exit(1)
    print("=== direcciones que cambiaron entre muestras ===")
    count = 0
    for a in sorted(samples[0]):
        vals = [sm.get(a) for sm in samples]
        if len(set(vals)) > 1:
            count += 1
            print("  %08X: %s"%(a, ' '.join('%08X'%v if v is not None else '--------' for v in vals)))
    print("total cambios: %d"%count)

main()
