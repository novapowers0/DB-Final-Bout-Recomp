"""Escanea RAM buscando campos del luchador: lee una zona dos veces (con delay)
y reporta qué words cambiaron. Protocolo debug server: UNA conexion por comando
(una linea JSON), el servidor cierra la conexion tras responder. Por eso cada
bloque usa su propia conexion.
"""
import socket, json, time, sys

HOST, PORT = '127.0.0.1', 4370
BLOCK = 500   # words por comando (~cabe en la respuesta de 8192 bytes)

def connect():
    for _ in range(60):
        try:
            return socket.create_connection((HOST, PORT), timeout=3)
        except OSError:
            time.sleep(0.5)
    return None

def mem_block(start, nwords):
    """Un comando mem_words -> una conexion. Devuelve {addr: value} o {}."""
    s = connect()
    if not s:
        return {}
    out = {}
    try:
        s.settimeout(3)
        s.sendall((json.dumps({"cmd":"mem_words","addr":"0x%08X"%start,"count":nwords})+'\n').encode('ascii'))
        data = b''
        while b'\n' not in data:
            c = s.recv(8192)
            if not c: break
            data += c
        line = data.split(b'\n')[0].decode('ascii','replace')
        r = json.loads(line)
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
    start = int(sys.argv[1],16)
    n = int(sys.argv[2],10)
    delay = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
    a = read_zone(start, n)
    if not a:
        print("Fallo leyendo muestra 1 (juego no responde?)"); sys.exit(1)
    print("Muestra 1 leida (%d words). Muevete/lucha ahora... esperando %.1fs"%(len(a),delay))
    time.sleep(delay)
    b = read_zone(start, n)
    changed = [(addr, a.get(addr,0), b.get(addr,0)) for addr in sorted(a)
               if a.get(addr,0) != b.get(addr,0)]
    print("=== words que cambiaron (%d) ==="%len(changed))
    for addr,x,y in changed[:80]:
        print("  %08X: %08X -> %08X"%(addr,x,y))

main()
