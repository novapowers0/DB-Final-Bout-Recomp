"""Busca words en una zona de globals (0x8003xxxx) que apunten dentro del
rango [target_start, target_end]. Estrategia: leer globals y chequear cada word.
"""
import socket, json, time, sys

HOST, PORT = '127.0.0.1', 4370
def connect():
    for _ in range(60):
        try: return socket.create_connection((HOST, PORT), timeout=3)
        except OSError: time.sleep(0.5)
    return None
def send(s,o): s.sendall((json.dumps(o)+'\n').encode('ascii'))
def read_resp(s):
    data=b''; s.settimeout(4)
    while b'\n' not in data:
        try: c=s.recv(8192)
        except socket.timeout: break
        if not c: break
        data+=c
    try: return json.loads(data.split(b'\n')[0].decode('ascii','replace'))
    except: return {}
def read_zone(s,start,nwords):
    out={}; B=500
    for off in range(0,nwords,B):
        for attempt in range(3):
            try:
                send(s,{"cmd":"mem_words","addr":"0x%08X"%(start+off*4),"count":min(B,nwords-off)})
                r=read_resp(s)
                if r.get('words'):
                    for i,w in enumerate(r['words']):
                        out[start+off*4+i*4]=int(w,16)
                    break
            except OSError:
                s.close(); s=connect()
    return out

def main():
    gstart=int(sys.argv[1],16); gwords=int(sys.argv[2])
    tstart=int(sys.argv[3],16); tend=int(sys.argv[4],16)
    # Una conexion por bloque para respetar el protocolo una-comando-por-conexion
    zone={}; s=None; B=500
    for off in range(0,gwords,B):
        s=connect()
        if s:
            zone.update(read_zone(s,gstart+off*4,min(B,gwords-off)))
            s.close()
    hits=[]
    for a,v in zone.items():
        if tstart<=v<=tend:
            hits.append((a,v))
    print("Globals 0x%08X (%d words) que apuntan a [0x%08X,0x%08X]:"%(gstart,gwords,tstart,tend))
    for a,v in sorted(hits):
        print("  %08X -> %08X"%(a,v))
    print("total hits: %d"%len(hits))
main()
