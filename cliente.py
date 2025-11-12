import zmq
import msgpack
from datetime import datetime

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.setsockopt(zmq.RCVTIMEO, 30000)  # Timeout de 30 segundos
socket.setsockopt(zmq.SNDTIMEO, 30000)  # Timeout de 30 segundos
socket.connect("tcp://broker:5555")

# Relógio lógico
logical_clock = 0

def update_logical_clock(received_clock):
    global logical_clock
    logical_clock = max(logical_clock, received_clock) + 1

def increment_logical_clock():
    global logical_clock
    logical_clock += 1
    return logical_clock 

opcao = input("Entre com a opção (login, users, channel, channels, publish, message, sair): ")
while opcao != "sair":
    timestamp = datetime.now().timestamp()

    match opcao:
        case "login":
            login = input("Entre com o login: ")

            increment_logical_clock()
            request = {
                "opcao": "login",
                "data": {
                    "user": login,
                    "timestamp": timestamp,
                    "clock": logical_clock
                }
            }
            try:
                socket.send(msgpack.packb(request))
                print(f"Mensagem enviada: {request}", flush=True)
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(f"Mensagem recebida: {reply}", flush=True)
            except zmq.Again:
                print("ERRO: Timeout ao aguardar resposta do servidor", flush=True)
            except Exception as e:
                print(f"ERRO ao processar resposta: {e}", flush=True)
                import traceback
                traceback.print_exc()

        case "users":
            increment_logical_clock()
            request = {
                "opcao": "users",
                "data": {
                    "timestamp": timestamp,
                    "clock": logical_clock
                }
            }
            try:
                socket.send(msgpack.packb(request))
                print(f"Mensagem enviada: {request}", flush=True)
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(f"Mensagem recebida: {reply}", flush=True)
            except zmq.Again:
                print("ERRO: Timeout ao aguardar resposta do servidor", flush=True)
            except Exception as e:
                print(f"ERRO ao processar resposta: {e}", flush=True)
                import traceback
                traceback.print_exc()

        case "channel":
            nome_canal = input("Entre com o nome do canal: ")

            increment_logical_clock()
            request = {
                "opcao": "channel",
                "data": {
                    "channel": nome_canal,
                    "timestamp": timestamp,
                    "clock": logical_clock
                }
            }
            try:
                socket.send(msgpack.packb(request))
                print(f"Mensagem enviada: {request}", flush=True)
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(f"Mensagem recebida: {reply}", flush=True)
            except zmq.Again:
                print("ERRO: Timeout ao aguardar resposta do servidor", flush=True)
            except Exception as e:
                print(f"ERRO ao processar resposta: {e}", flush=True)
                import traceback
                traceback.print_exc()

        case "channels":
            increment_logical_clock()
            request = {
                "opcao": "channels",
                "data": {
                    "timestamp": timestamp,
                    "clock": logical_clock
                }
            }
            try:
                socket.send(msgpack.packb(request))
                print(f"Mensagem enviada: {request}", flush=True)
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(f"Mensagem recebida: {reply}", flush=True)
            except zmq.Again:
                print("ERRO: Timeout ao aguardar resposta do servidor", flush=True)
            except Exception as e:
                print(f"ERRO ao processar resposta: {e}", flush=True)
                import traceback
                traceback.print_exc()

        case "publish":
            user = input("Entre com o nome do usuário: ")
            canal = input("Entre com o nome do canal: ")
            mensagem = input("Entre com a mensagem: ")

            increment_logical_clock()
            request = {
                "service": "publish",
                "data": {
                    "user": user,
                    "channel": canal,
                    "message": mensagem,
                    "timestamp": timestamp,
                    "clock": logical_clock
                }
            }
            try:
                socket.send(msgpack.packb(request))
                print(f"Mensagem enviada: {request}", flush=True)
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(f"Mensagem recebida: {reply}", flush=True)
            except zmq.Again:
                print("ERRO: Timeout ao aguardar resposta do servidor", flush=True)
            except Exception as e:
                print(f"ERRO ao processar resposta: {e}", flush=True)
                import traceback
                traceback.print_exc()

        case "message":
            src = input("Entre com o nome do usuário de origem: ")
            dst = input("Entre com o nome do usuário de destino: ")
            mensagem = input("Entre com a mensagem: ")

            increment_logical_clock()
            request = {
                "service": "message",
                "data": {
                    "src": src,
                    "dst": dst,
                    "message": mensagem,
                    "timestamp": timestamp,
                    "clock": logical_clock
                }
            }
            try:
                socket.send(msgpack.packb(request))
                print(f"Mensagem enviada: {request}", flush=True)
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(f"Mensagem recebida: {reply}", flush=True)
            except zmq.Again:
                print("ERRO: Timeout ao aguardar resposta do servidor", flush=True)
            except Exception as e:
                print(f"ERRO ao processar resposta: {e}", flush=True)
                import traceback
                traceback.print_exc()

        case _:
            print("Opção não encontrada")

    opcao = input("\nEntre com a opção (login, users, channel, channels, publish, message, sair): ")
