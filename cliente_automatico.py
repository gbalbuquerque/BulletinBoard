import zmq
import random
import time
import msgpack
from datetime import datetime

context = zmq.Context()


def create_req_socket():
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.RCVTIMEO, 10000)  # Timeout de 10 segundos por tentativa
    socket.setsockopt(zmq.SNDTIMEO, 10000)
    socket.connect("tcp://broker:5555")
    return socket


def reset_req_socket():
    global req_socket
    try:
        req_socket.close(0)
    except Exception:
        pass
    req_socket = create_req_socket()
    print("Socket REQ recriado e reconectado ao broker", flush=True)


req_socket = create_req_socket()
print("Socket conectado ao broker: tcp://broker:5555", flush=True)

# Socket para receber mensagens Pub/Sub
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://proxy:5557")

# Gera um nome de usuário aleatório
username = f"user_{random.randint(1000, 9999)}"
print(f"Cliente automático iniciado com usuário: {username}", flush=True)

# Relógio lógico
logical_clock = 0


def update_logical_clock(received_clock):
    global logical_clock
    logical_clock = max(logical_clock, received_clock) + 1


def increment_logical_clock():
    global logical_clock
    logical_clock += 1
    return logical_clock


def send_request(request, descricao, max_attempts=3, max_wait_attempts=6):
    global req_socket

    for attempt in range(1, max_attempts + 1):
        try:
            req_socket.send(msgpack.packb(request))
        except zmq.Again:
            print(f"Timeout ao enviar requisição de {descricao} (tentativa {attempt}/{max_attempts})", flush=True)
            reset_req_socket()
            time.sleep(1)
            continue
        except Exception as e:
            print(f"Erro ao enviar requisição de {descricao}: {e}", flush=True)
            import traceback
            traceback.print_exc()
            reset_req_socket()
            time.sleep(1)
            continue

        for wait in range(1, max_wait_attempts + 1):
            try:
                reply_raw = req_socket.recv()
                reply = msgpack.unpackb(reply_raw, raw=False)
                return reply
            except zmq.Again:
                print(
                    f"Ainda aguardando resposta de {descricao} (tentativa {wait}/{max_wait_attempts})",
                    flush=True,
                )
            except Exception as e:
                print(f"Erro ao receber resposta de {descricao}: {e}", flush=True)
                import traceback
                traceback.print_exc()
                break

        print(
            f"Nenhuma resposta para {descricao}. Recriando socket e tentando novamente...",
            flush=True,
        )
        reset_req_socket()
        time.sleep(1)

    print(f"Falha ao concluir {descricao} após {max_attempts} tentativas.", flush=True)
    return None


# Faz login
while True:
    timestamp = datetime.now().timestamp()
    increment_logical_clock()
    login_request = {
        "opcao": "login",
        "data": {
            "user": username,
            "timestamp": timestamp,
            "clock": logical_clock,
        },
    }

    reply = send_request(login_request, "login")
    if reply:
        if reply.get("data", {}).get("clock") is not None:
            update_logical_clock(reply["data"]["clock"])
        print(f"Login realizado: {reply}", flush=True)
        break

    print("ERRO: Falha ao fazer login, tentando novamente em 3 segundos...", flush=True)
    time.sleep(3)

# Aguarda um pouco para garantir que o servidor está pronto
time.sleep(2)

# Inscreve-se no próprio tópico para receber mensagens diretas
sub_socket.setsockopt_string(zmq.SUBSCRIBE, username)
print(f"Inscrito no tópico: {username}", flush=True)

# Lista de mensagens pré-definidas
mensagens = [
    "Olá, esta é uma mensagem de teste!",
    "Sistema funcionando corretamente.",
    "Teste de publicação em canal.",
    "Mensagem automática gerada pelo cliente.",
    "Verificando funcionalidade de Pub/Sub.",
    "Esta é a mensagem número 6.",
    "Teste de persistência de mensagens.",
    "Mensagem enviada automaticamente.",
    "Verificando comunicação entre clientes.",
    "Última mensagem do conjunto de testes.",
]


def obter_canais():
    """Obtém a lista de canais disponíveis"""
    try:
        timestamp = datetime.now().timestamp()
        increment_logical_clock()
        request = {
            "opcao": "channels",
            "data": {
                "timestamp": timestamp,
                "clock": logical_clock,
            },
        }
        reply = send_request(request, "channels")
        if not reply:
            print("Resposta ausente ao obter canais", flush=True)
            return []

        print(f"Resposta de canais recebida: {reply}", flush=True)
        if reply.get("data", {}).get("clock") is not None:
            update_logical_clock(reply["data"]["clock"])
        if reply.get("service") == "channels" and "channels" in reply.get("data", {}):
            canais = reply["data"]["channels"]
            print(f"Canais obtidos: {canais}", flush=True)
            return canais
        print(f"Resposta inesperada ao obter canais: {reply}", flush=True)
        return []
    except Exception as e:
        print(f"Erro ao obter canais: {e}", flush=True)
        import traceback
        traceback.print_exc()
        reset_req_socket()
        return []


def criar_canal_se_necessario():
    """Cria um canal se não houver nenhum"""
    canais = obter_canais()
    if not canais:
        # Cria um canal padrão
        canal = "geral"
        timestamp = datetime.now().timestamp()
        increment_logical_clock()
        request = {
            "opcao": "channel",
            "data": {
                "channel": canal,
                "timestamp": timestamp,
                "clock": logical_clock,
            },
        }
        try:
            print(f"Tentando criar canal '{canal}'...", flush=True)
            reply = send_request(request, "criação de canal")
            if not reply:
                print(f"Falha ao criar canal '{canal}'", flush=True)
                return []

            print(f"Resposta de criação de canal recebida: {reply}", flush=True)
            if reply.get("data", {}).get("clock") is not None:
                update_logical_clock(reply["data"]["clock"])
            status = reply.get("data", {}).get("status", "erro")
            if status == "sucesso":
                print(f"Canal '{canal}' criado com sucesso", flush=True)
                return [canal]
            else:
                error_msg = reply.get("data", {}).get("description", "Erro desconhecido")
                print(f"Erro ao criar canal '{canal}': {error_msg}", flush=True)
                return []
        except Exception as e:
            print(f"Exceção ao criar canal: {e}", flush=True)
            import traceback
            traceback.print_exc()
            reset_req_socket()
            return []
    return canais


# Loop principal
print("Iniciando loop principal...", flush=True)
try:
    while True:
        # Obtém ou cria canais
        print("Obtendo lista de canais...", flush=True)
        canais = criar_canal_se_necessario()

        if not canais:
            print("Aguardando criação de canais...", flush=True)
            time.sleep(5)
            continue

        print(f"Canais disponíveis: {canais}", flush=True)
        # Escolhe um canal aleatório
        canal_escolhido = random.choice(canais)
        print(f"\n=== Enviando 10 mensagens para o canal '{canal_escolhido}' ===", flush=True)

        # Envia 10 mensagens
        for i in range(10):
            mensagem = mensagens[i % len(mensagens)]
            timestamp = datetime.now().timestamp()

            increment_logical_clock()
            request = {
                "service": "publish",
                "data": {
                    "user": username,
                    "channel": canal_escolhido,
                    "message": mensagem,
                    "timestamp": timestamp,
                    "clock": logical_clock,
                },
            }

            try:
                print(f"  [{i+1}/10] Enviando mensagem: {mensagem[:30]}...", flush=True)
                reply = send_request(request, "publicação")
                if not reply:
                    print(f"  [{i+1}/10] ✗ Sem resposta ao publicar", flush=True)
                    continue

                print(f"  [{i+1}/10] Resposta recebida: {reply}", flush=True)
                if reply.get("data", {}).get("clock") is not None:
                    update_logical_clock(reply["data"]["clock"])

                if reply.get("data", {}).get("status") == "OK":
                    print(f"  [{i+1}/10] ✓ Mensagem publicada com sucesso: {mensagem[:50]}...", flush=True)
                else:
                    error_msg = reply.get("data", {}).get("message", "Erro desconhecido")
                    print(f"  [{i+1}/10] ✗ Erro ao publicar: {error_msg}", flush=True)
                    print(f"  Resposta completa: {reply}", flush=True)
            except Exception as e:
                print(f"  [{i+1}/10] ✗ Exceção ao publicar: {e}", flush=True)
                import traceback
                traceback.print_exc()
                reset_req_socket()

            time.sleep(0.5)  # Pequeno delay entre mensagens

        print(f"=== Concluído envio de 10 mensagens para '{canal_escolhido}' ===\n", flush=True)

        # Verifica se há mensagens recebidas (não bloqueante)
        try:
            sub_socket.setsockopt(zmq.RCVTIMEO, 100)  # Timeout de 100ms
            topic = sub_socket.recv_string()
            message = sub_socket.recv()
            data = msgpack.unpackb(message, raw=False)
            # Atualiza relógio lógico ao receber mensagem Pub/Sub
            if data.get("clock") is not None:
                update_logical_clock(data["clock"])
            print(f"📨 Mensagem recebida no tópico '{topic}': {data}", flush=True)
        except zmq.Again:
            pass  # Nenhuma mensagem recebida

        # Aguarda antes de começar o próximo ciclo
        time.sleep(2)

except KeyboardInterrupt:
    print(f"\nCliente automático {username} encerrado.", flush=True)
finally:
    try:
        req_socket.close()
    except Exception:
        pass
    sub_socket.close()
    context.term()

