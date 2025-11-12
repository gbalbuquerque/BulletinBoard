import zmq
import msgpack
from datetime import datetime

CLIENT_TAG = "[cliente]"
_original_print = print


def print(*args, **kwargs):  # noqa: A001 - shadowing built-in intencional
    kwargs.setdefault("flush", True)
    if not args:
        return _original_print(CLIENT_TAG, **kwargs)

    first, *rest = args
    if isinstance(first, str) and first.startswith(CLIENT_TAG):
        return _original_print(first, *rest, **kwargs)

    return _original_print(f"{CLIENT_TAG} {first}", *rest, **kwargs)


context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.setsockopt(zmq.RCVTIMEO, 15000)  # Timeout reduzido para respostas mais ágeis
socket.setsockopt(zmq.SNDTIMEO, 15000)
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

def prompt(message: str) -> str:
    return input(f"{CLIENT_TAG} {message}")


opcao = prompt("Entre com a opção (login, users, channel, channels, publish, message, sair): ")
while opcao != "sair":
    timestamp = datetime.now().timestamp()

    match opcao:
        case "login":
            login = prompt("Entre com o login: ")

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
                print(f"Mensagem enviada: {request}")
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(f"Mensagem recebida: {reply}")
            except zmq.Again:
                print("ERRO: Timeout ao aguardar resposta do servidor")
            except Exception as e:
                print(f"ERRO ao processar resposta: {e}")
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
                print(f"Mensagem enviada: {request}")
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(f"Mensagem recebida: {reply}")
            except zmq.Again:
                print("ERRO: Timeout ao aguardar resposta do servidor")
            except Exception as e:
                print(f"ERRO ao processar resposta: {e}")
                import traceback
                traceback.print_exc()

        case "channel":
            nome_canal = prompt("Entre com o nome do canal: ")

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
                print(f"Mensagem enviada: {request}")
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(f"Mensagem recebida: {reply}")
            except zmq.Again:
                print("ERRO: Timeout ao aguardar resposta do servidor")
            except Exception as e:
                print(f"ERRO ao processar resposta: {e}")
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
                print(f"Mensagem enviada: {request}")
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(f"Mensagem recebida: {reply}")
            except zmq.Again:
                print("ERRO: Timeout ao aguardar resposta do servidor")
            except Exception as e:
                print(f"ERRO ao processar resposta: {e}")
                import traceback
                traceback.print_exc()

        case "publish":
            user = prompt("Entre com o nome do usuário: ")
            canal = prompt("Entre com o nome do canal: ")
            mensagem = prompt("Entre com a mensagem: ")

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
                print(f"Mensagem enviada: {request}")
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(f"Mensagem recebida: {reply}")
            except zmq.Again:
                print("ERRO: Timeout ao aguardar resposta do servidor")
            except Exception as e:
                print(f"ERRO ao processar resposta: {e}")
                import traceback
                traceback.print_exc()

        case "message":
            src = prompt("Entre com o nome do usuário de origem: ")
            dst = prompt("Entre com o nome do usuário de destino: ")
            mensagem = prompt("Entre com a mensagem: ")

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
                print(f"Mensagem enviada: {request}")
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(f"Mensagem recebida: {reply}")
            except zmq.Again:
                print("ERRO: Timeout ao aguardar resposta do servidor")
            except Exception as e:
                print(f"ERRO ao processar resposta: {e}")
                import traceback
                traceback.print_exc()

        case _:
            print("Opção não encontrada")

    opcao = prompt("\nEntre com a opção (login, users, channel, channels, publish, message, sair): ")
