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


def log_io(direction: str, payload: dict):
    label = "enviada" if direction == "send" else "recebida"
    print(f"Mensagem {label}: {payload}")


def prompt(message: str) -> str:
    return input(f"{CLIENT_TAG} {message}")


def mostrar_menu():
    """Exibe o menu de opções de forma amigável"""
    print("\n" + "="*60)
    print("  BULLETIN BOARD - Sistema de Mensagens")
    print("="*60)
    print("  1. Login (Fazer login no sistema)")
    print("  2. Listar Usuários (Ver todos os usuários conectados)")
    print("  3. Criar/Entrar em Canal (Criar ou entrar em um canal)")
    print("  4. Listar Canais (Ver todos os canais disponíveis)")
    print("  5. Publicar Mensagem (Enviar mensagem para um canal)")
    print("  6. Enviar Mensagem Privada (Enviar mensagem para um usuário)")
    print("  7. Sair (Encerrar o cliente)")
    print("="*60)


def formatar_resposta(reply):
    """Formata a resposta do servidor de forma mais legível"""
    if not reply:
        return "Nenhuma resposta recebida"
    
    status = reply.get("status", "desconhecido")
    data = reply.get("data", {})
    
    if status == "success":
        mensagem = f"✓ Sucesso: {reply.get('message', 'Operação realizada com sucesso')}"
        if data:
            # Formata dados específicos de forma mais legível
            if "users" in data:
                users = data["users"]
                if isinstance(users, list) and users:
                    mensagem += f"\n  Usuários conectados ({len(users)}):"
                    for user in users:
                        mensagem += f"\n    - {user}"
                else:
                    mensagem += "\n  Nenhum usuário conectado no momento"
            elif "channels" in data:
                channels = data["channels"]
                if isinstance(channels, list) and channels:
                    mensagem += f"\n  Canais disponíveis ({len(channels)}):"
                    for channel in channels:
                        mensagem += f"\n    - {channel}"
                else:
                    mensagem += "\n  Nenhum canal disponível no momento"
        return mensagem
    elif status == "error":
        return f"✗ Erro: {reply.get('message', 'Ocorreu um erro desconhecido')}"
    else:
        return f"Resposta: {reply}"


# Mensagem de boas-vindas
print("\n" + "="*60)
print("  Bem-vindo ao Bulletin Board!")
print("  Sistema de Mensagens e Publicações")
print("="*60)

mostrar_menu()
opcao = prompt("\nEscolha uma opção (1-7): ").strip().lower()

while opcao not in ["7", "sair", "exit", "quit"]:
    timestamp = datetime.now().timestamp()

    match opcao:
        case "1" | "login":
            print("\n--- Login no Sistema ---")
            login = prompt("Digite seu nome de usuário: ").strip()
            
            if not login:
                print("✗ Erro: Nome de usuário não pode estar vazio!")
            else:
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
                    reply_bytes = socket.recv()
                    reply = msgpack.unpackb(reply_bytes, raw=False)
                    if reply.get("data", {}).get("clock") is not None:
                        update_logical_clock(reply["data"]["clock"])
                    print(formatar_resposta(reply))
                except zmq.Again:
                    print("✗ Erro: Timeout ao aguardar resposta do servidor. Tente novamente.")
                except Exception as e:
                    print(f"✗ Erro ao processar resposta: {e}")

        case "2" | "users":
            print("\n--- Listando Usuários ---")
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
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(formatar_resposta(reply))
            except zmq.Again:
                print("✗ Erro: Timeout ao aguardar resposta do servidor. Tente novamente.")
            except Exception as e:
                print(f"✗ Erro ao processar resposta: {e}")

        case "3" | "channel":
            print("\n--- Criar/Entrar em Canal ---")
            nome_canal = prompt("Digite o nome do canal: ").strip()
            
            if not nome_canal:
                print("✗ Erro: Nome do canal não pode estar vazio!")
            else:
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
                    reply_bytes = socket.recv()
                    reply = msgpack.unpackb(reply_bytes, raw=False)
                    if reply.get("data", {}).get("clock") is not None:
                        update_logical_clock(reply["data"]["clock"])
                    print(formatar_resposta(reply))
                except zmq.Again:
                    print("✗ Erro: Timeout ao aguardar resposta do servidor. Tente novamente.")
                except Exception as e:
                    print(f"✗ Erro ao processar resposta: {e}")

        case "4" | "channels":
            print("\n--- Listando Canais ---")
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
                reply_bytes = socket.recv()
                reply = msgpack.unpackb(reply_bytes, raw=False)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])
                print(formatar_resposta(reply))
            except zmq.Again:
                print("✗ Erro: Timeout ao aguardar resposta do servidor. Tente novamente.")
            except Exception as e:
                print(f"✗ Erro ao processar resposta: {e}")

        case "5" | "publish":
            print("\n--- Publicar Mensagem em Canal ---")
            user = prompt("Digite seu nome de usuário: ").strip()
            canal = prompt("Digite o nome do canal: ").strip()
            mensagem = prompt("Digite sua mensagem: ").strip()
            
            if not user or not canal or not mensagem:
                print("✗ Erro: Todos os campos são obrigatórios!")
            else:
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
                    reply_bytes = socket.recv()
                    reply = msgpack.unpackb(reply_bytes, raw=False)
                    if reply.get("data", {}).get("clock") is not None:
                        update_logical_clock(reply["data"]["clock"])
                    print(formatar_resposta(reply))
                except zmq.Again:
                    print("✗ Erro: Timeout ao aguardar resposta do servidor. Tente novamente.")
                except Exception as e:
                    print(f"✗ Erro ao processar resposta: {e}")

        case "6" | "message":
            print("\n--- Enviar Mensagem Privada ---")
            src = prompt("Digite seu nome de usuário: ").strip()
            dst = prompt("Digite o nome do destinatário: ").strip()
            mensagem = prompt("Digite sua mensagem: ").strip()
            
            if not src or not dst or not mensagem:
                print("✗ Erro: Todos os campos são obrigatórios!")
            else:
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
                    reply_bytes = socket.recv()
                    reply = msgpack.unpackb(reply_bytes, raw=False)
                    if reply.get("data", {}).get("clock") is not None:
                        update_logical_clock(reply["data"]["clock"])
                    print(formatar_resposta(reply))
                except zmq.Again:
                    print("✗ Erro: Timeout ao aguardar resposta do servidor. Tente novamente.")
                except Exception as e:
                    print(f"✗ Erro ao processar resposta: {e}")

        case _:
            print("\n✗ Opção inválida! Por favor, escolha uma opção entre 1 e 7.")

    mostrar_menu()
    opcao = prompt("\nEscolha uma opção (1-7): ").strip().lower()

print("\n" + "="*60)
print("  Obrigado por usar o Bulletin Board!")
print("  Até logo!")
print("="*60)
