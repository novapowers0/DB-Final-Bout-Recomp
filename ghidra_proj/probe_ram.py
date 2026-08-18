"""Instrumentación en vivo — lee la RAM del juego vía el debug server TCP (4370).
Protocolo: lineas JSON. Comando: {"cmd":"mem_words","addr":"0x...","count":N}
Respuesta: {"id":N,"ok":true,"addr":"0x...","words":["0x..."]}
"""
import socket, json, sys, time

HOST = '127.0.0.1'
PORT = 4370

def connect():
    for _ in range(30):
        try:
            s = socket.create_connection((HOST, PORT), timeout=2)
            return s
        except OSError:
            time.sleep(0.5)
    return None

def send(s, cmd_obj):
    s.sendall((json.dumps(cmd_obj) + '\n').encode('ascii'))

def read_resp(s):
    # read until newline
    data = b''
    s.settimeout(3)
    while b'\n' not in data:
        chunk = s.recv(8192)
        if not chunk:
            break
        data += chunk
    line = data.split(b'\n')[0].decode('ascii', 'replace')
    try:
        return json.loads(line)
    except Exception as e:
        return {'raw': line, 'err': str(e)}

def mem_words(s, addr, count=16):
    send(s, {"cmd":"mem_words", "addr": "0x%08X" % addr, "count": count})
    r = read_resp(s)
    return r.get('words', [])

def main():
    addr = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x80030000
    count = int(sys.argv[2], 10) if len(sys.argv) > 2 else 32
    s = connect()
    if not s:
        print("NO PUEDO CONECTAR al puerto 4370. El juego debe estar corriendo.")
        sys.exit(1)
    print("Conectado. Leyendo 0x%08X (%d words)..." % (addr, count))
    words = mem_words(s, addr, count)
    for i, w in enumerate(words):
        a = addr + i*4
        print("  %08X: %s" % (a, w))
    s.close()

if __name__ == '__main__':
    main()
