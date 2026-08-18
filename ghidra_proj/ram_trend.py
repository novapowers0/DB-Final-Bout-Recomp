"""Muestreo temporal de un word especifico cada N segundos, para ver tendencia.
UNA conexion por comando (protocolo debug server)."""
import socket, json, time, sys

HOST, PORT = '127.0.0.1', 4370
def connect():
    for _ in range(60):
        try: return socket.create_connection((HOST,PORT),timeout=3)
        except OSError: time.sleep(0.5)
    return None
def read_words(addr, count):
    s = connect()
    if not s: return []
    try:
        s.settimeout(3)
        s.sendall((json.dumps({"cmd":"mem_words","addr":"0x%08X"%addr,"count":count})+'\n').encode('ascii'))
        data=b''; 
        while b'\n' not in data:
            c=s.recv(8192)
            if not c: break
            data+=c
        r=json.loads(data.split(b'\n')[0].decode('ascii','replace'))
        return r.get('words',[])
    except Exception:
        return []
    finally:
        try: s.close()
        except Exception: pass
def main():
    addr=int(sys.argv[1],16); iters=int(sys.argv[2]); dt=float(sys.argv[3])
    for i in range(iters):
        if i>0: time.sleep(dt)
        ws=read_words(addr,4)
        if ws:
            w=int(ws[0],16); hi=(w>>16)&0xFFFF; lo=w&0xFFFF
            print("t=%5.1fs  %08X: hi=%04X lo=%04X (dec hi=%5d lo=%5d)"%(i*dt,addr,hi,lo,hi,lo))
        else:
            print("t=%5.1fs  (sin respuesta)"%(i*dt))
main()
