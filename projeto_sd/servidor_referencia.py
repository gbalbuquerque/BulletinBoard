import zmq
import msgpack
import time
import threading
from datetime import datetime

# Classe do relógio lógico
class RelogioLogico:
    def __init__(self):
        self.clock = 0
    
    def tick(self):
        self.clock += 1
        return self.clock
    
    def update(self, clock_recebido):
        self.clock = max(self.clock, clock_recebido)
        return self.clock
    
    def get(self):
        return self.clock

relogio = RelogioLogico()

# Estrutura para armazenar servidores
# {nome: {"rank": rank, "last_heartbeat": timestamp}}
servidores = {}
proximo_rank = 1
lock = threading.Lock()

# Timeout para heartbeat (em segundos)
HEARTBEAT_TIMEOUT = 30

def limpar_servidores_inativos():
    while True:
        time.sleep(10)
        tempo_atual = time.time()
        with lock:
            servidores_inativos = []
            for nome, info in servidores.items():
                if tempo_atual - info["last_heartbeat"] > HEARTBEAT_TIMEOUT:
                    servidores_inativos.append(nome)
            for nome in servidores_inativos:
                del servidores[nome]

threading.Thread(target=limpar_servidores_inativos, daemon=True).start()

def atribuir_rank(nome_servidor):
    global proximo_rank
    with lock:
        if nome_servidor not in servidores:
            rank = proximo_rank
            proximo_rank += 1
            servidores[nome_servidor] = {"rank": rank, "last_heartbeat": time.time()}
            print(f"[REF] Servidor {nome_servidor} rank {rank}", flush=True)
        else:
            rank = servidores[nome_servidor]["rank"]
            servidores[nome_servidor]["last_heartbeat"] = time.time()
    return rank

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5560")

print("[REF] Porta 5560", flush=True)

while True:
    try:
        request_data = socket.recv()
        request = msgpack.unpackb(request_data, raw=False)
        
        service = request.get("service")
        data = request.get("data", {})
        
        if "clock" in data:
            relogio.update(data["clock"])
        
        if service == "rank":
            # Atribuir rank ao servidor
            nome_servidor = data.get("user")
            rank = atribuir_rank(nome_servidor)
            
            reply = {
                "service": "rank",
                "data": {
                    "rank": rank,
                    "timestamp": time.time(),
                    "clock": relogio.tick()
                }
            }
        
        elif service == "list":
            with lock:
                lista_servidores = [{"name": nome, "rank": info["rank"]} for nome, info in servidores.items()]
            reply = {
                "service": "list",
                "data": {
                    "list": lista_servidores,
                    "timestamp": time.time(),
                    "clock": relogio.tick()
                }
            }
        
        elif service == "heartbeat":
            nome_servidor = data.get("user")
            with lock:
                if nome_servidor in servidores:
                    servidores[nome_servidor]["last_heartbeat"] = time.time()
                    status = "OK"
                else:
                    status = "unknown"
            reply = {
                "service": "heartbeat",
                "data": {
                    "status": status,
                    "timestamp": time.time(),
                    "clock": relogio.tick()
                }
            }
        
        else:
            reply = {
                "service": service,
                "data": {
                    "status": "erro",
                    "message": "Servico nao reconhecido",
                    "timestamp": time.time(),
                    "clock": relogio.tick()
                }
            }
        
        socket.send(msgpack.packb(reply))
    except:
        pass

