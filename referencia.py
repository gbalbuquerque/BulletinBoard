import zmq
import msgpack
from datetime import datetime

context = zmq.Context()

# Socket para responder requisições dos servidores
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5559")

# Relógio lógico
logical_clock = 0

def update_logical_clock(received_clock):
    global logical_clock
    logical_clock = max(logical_clock, received_clock) + 1

def increment_logical_clock():
    global logical_clock
    logical_clock += 1
    return logical_clock

# Armazena servidores: {nome: rank}
servers = {}
next_rank = 0

print("Servidor de referência iniciado em tcp://*:5559")

while True:
    # Recebe requisição
    msg = socket.recv()
    request = msgpack.unpackb(msg, raw=False)
    
    # Atualiza relógio lógico
    received_clock = request.get("data", {}).get("clock", 0)
    update_logical_clock(received_clock)
    
    service = request.get("service")
    data = request.get("data", {})
    
    increment_logical_clock()
    reply = {
        "service": service,
        "data": {
            "timestamp": datetime.now().timestamp(),
            "clock": logical_clock
        }
    }
    
    if service == "rank":
        # Serviço para obter rank do servidor
        server_name = data.get("user")
        if server_name:
            if server_name not in servers:
                # Novo servidor, atribui rank
                servers[server_name] = next_rank
                next_rank += 1
                print(f"Servidor '{server_name}' registrado com rank {servers[server_name]}", flush=True)
            
            reply["data"]["rank"] = servers[server_name]
        else:
            reply["data"]["rank"] = -1
    
    elif service == "list":
        # Serviço para listar todos os servidores
        server_list = [{"name": name, "rank": rank} for name, rank in servers.items()]
        reply["data"]["list"] = server_list
        print(f"Lista de servidores solicitada: {len(server_list)} servidores", flush=True)
    
    elif service == "heartbeat":
        # Serviço de heartbeat para manter servidor na lista
        server_name = data.get("user")
        if server_name:
            if server_name not in servers:
                # Se não existe, registra
                servers[server_name] = next_rank
                next_rank += 1
                print(f"Servidor '{server_name}' registrado via heartbeat com rank {servers[server_name]}", flush=True)
            else:
                print(f"Heartbeat recebido de '{server_name}' (rank {servers[server_name]})", flush=True)
        # Resposta OK
        reply["data"]["status"] = "OK"
    
    else:
        reply["data"]["error"] = "Serviço não reconhecido"
    
    # Envia resposta
    socket.send(msgpack.packb(reply))

