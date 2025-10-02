import zmq
from datetime import datetime

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://broker:5555")

opcao = input("Entre com a opção: ")
while opcao != "sair":
    match opcao:
        # case "cadastrar":
        #     login = input("Entre com o login: ")
        #     timestamp = datetime.now().timestamp() 

        #     request = {
        #         "opcao": "cadastrar",
        #         "dados": {
        #             "user": login,
        #             "time": timestamp
        #         }
        #     }

        #     socket.send_json(request)
        #     reply = socket.recv_string()
        #     if reply.split(":")[0] == "ERRO":
        #         print(reply, flush=True)
        
        case "login":
            login = input("Entre com o login: ")
            timestamp = datetime.now().timestamp() 

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
                
        case "users":
            request = {
                "opcao": "users",
                "data": {
                    "timestamp": timestamp
                }
            }
        case _:
            print("Opção não encontrada")

    opcao = input("Entre com a opção: ")
