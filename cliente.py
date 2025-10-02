import zmq
from datetime import datetime

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://broker:5556")  # porta igual à do servidor

opcao = input("Entre com a opção (login, users, channel, channels, sair): ")
while opcao != "sair":
    timestamp = datetime.now().timestamp()

    match opcao:
        # =========================
        # LOGIN
        # =========================
        case "login":
            login = input("Entre com o login: ")

            request = {
                "opcao": "login",
                "data": {
                    "user": login,
                    "timestamp": timestamp
                }
            }
            socket.send_json(request)
            print(f"Mensagem enviada: {request}", flush=True)
            reply = socket.recv_string()
            print(f"Mensagem recebida: {reply}", flush=True)

        # =========================
        # LISTAR USUÁRIOS
        # =========================
        case "users":
            request = {
                "opcao": "users",
                "data": {
                    "timestamp": timestamp
                }
            }
            socket.send_json(request)
            print(f"Mensagem enviada: {request}", flush=True)
            reply = socket.recv_string()
            print(f"Mensagem recebida: {reply}", flush=True)

        # =========================
        # CRIAR CANAL
        # =========================
        case "channel":
            nome_canal = input("Entre com o nome do canal: ")

            request = {
                "opcao": "channel",
                "data": {
                    "channel": nome_canal,
                    "timestamp": timestamp
                }
            }
            socket.send_json(request)
            print(f"Mensagem enviada: {request}", flush=True)
            reply = socket.recv_string()
            print(f"Mensagem recebida: {reply}", flush=True)

        # =========================
        # LISTAR CANAIS
        # =========================
        case "channels":
            request = {
                "opcao": "channels",
                "data": {
                    "timestamp": timestamp
                }
            }
            socket.send_json(request)
            print(f"Mensagem enviada: {request}", flush=True)
            reply = socket.recv_string()
            print(f"Mensagem recebida: {reply}", flush=True)

        # =========================
        # DEFAULT
        # =========================
        case _:
            print("Opção não encontrada")

    opcao = input("\nEntre com a opção (login, users, channel, channels, sair): ")
