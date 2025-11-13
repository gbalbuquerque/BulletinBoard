import threading
import zmq
import msgpack
import time
import json
import os

# Diretório para persistência de dados
DATA_DIR = "/app/dados"
os.makedirs(DATA_DIR, exist_ok=True)

# Porta para receber replicações de outros servidores
REPLICATION_PORT = 5562

# Função para salvar mensagens no arquivo de log
def salvar_log(mensagem):
    try:
        with open("log.txt", "a", encoding="utf-8") as f:
            f.write(f"{mensagem}\n")
    except Exception as e:
        print(f"Erro ao salvar no log: {e}", flush=True)

# Função para carregar dados persistidos
def carregar_dados():
    usuarios = []
    canais = []
    
    usuarios_path = os.path.join(DATA_DIR, "usuarios.json")
    canais_path = os.path.join(DATA_DIR, "canais.json")
    
    # Carregar usuários
    if os.path.exists(usuarios_path):
        try:
            with open(usuarios_path, "r", encoding="utf-8") as f:
                usuarios = json.load(f)
        except:
            pass
    
    if os.path.exists(canais_path):
        try:
            with open(canais_path, "r", encoding="utf-8") as f:
                canais = json.load(f)
        except:
            pass
    
    return usuarios, canais

def salvar_usuarios(usuarios):
    try:
        usuarios_path = os.path.join(DATA_DIR, "usuarios.json")
        with open(usuarios_path, "w", encoding="utf-8") as f:
            json.dump(usuarios, f, indent=2, ensure_ascii=False)
    except:
        pass

def salvar_canais(canais):
    try:
        canais_path = os.path.join(DATA_DIR, "canais.json")
        with open(canais_path, "w", encoding="utf-8") as f:
            json.dump(canais, f, indent=2, ensure_ascii=False)
    except:
        pass

def salvar_publicacao(publicacao):
    try:
        publicacoes_path = os.path.join(DATA_DIR, "publicacoes.json")
        publicacoes = []
        if os.path.exists(publicacoes_path):
            with open(publicacoes_path, "r", encoding="utf-8") as f:
                publicacoes = json.load(f)
        publicacoes.append(publicacao)
        with open(publicacoes_path, "w", encoding="utf-8") as f:
            json.dump(publicacoes, f, indent=2, ensure_ascii=False)
    except:
        pass

def salvar_mensagem_privada(mensagem):
    try:
        mensagens_path = os.path.join(DATA_DIR, "mensagens.json")
        mensagens = []
        if os.path.exists(mensagens_path):
            with open(mensagens_path, "r", encoding="utf-8") as f:
                mensagens = json.load(f)
        mensagens.append(mensagem)
        with open(mensagens_path, "w", encoding="utf-8") as f:
            json.dump(mensagens, f, indent=2, ensure_ascii=False)
    except:
        pass

# Função para replicar mensagem para outros servidores
def replicar_para_outros_servidores(mensagem):
    def enviar_replicacao():
        try:
            mensagem_copy = mensagem.copy()
            mensagem_copy["replicated"] = True
            lista_servidores = obter_lista_servidores()
            
            for servidor in lista_servidores:
                nome_servidor = servidor.get("name")
                if nome_servidor == NOME_SERVIDOR:
                    continue
                
                try:
                    ctx = zmq.Context()
                    sock = ctx.socket(zmq.REQ)
                    sock.connect(f"tcp://{nome_servidor}:{REPLICATION_PORT}")
                    sock.setsockopt(zmq.RCVTIMEO, 2000)
                    sock.setsockopt(zmq.SNDTIMEO, 2000)
                    sock.send(msgpack.packb(mensagem_copy))
                    sock.recv()
                    sock.close()
                    ctx.term()
                except:
                    pass
        except:
            pass
    
    threading.Thread(target=enviar_replicacao, daemon=True).start()

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

# Variáveis para sincronização e eleição
import socket as sock
NOME_SERVIDOR = sock.gethostname()  # Nome único do servidor
rank_servidor = None
coordenador_atual = None
contador_mensagens = 0
ajuste_relogio = 0.0  # Ajuste do relógio físico (Berkeley)

# Socket para comunicação com servidor de referência
ref_context = zmq.Context()
ref_socket = ref_context.socket(zmq.REQ)
ref_socket.connect("tcp://referencia:5560")

# Socket PUB para eleições (tópico "servers")
election_pub_socket = ref_context.socket(zmq.PUB)
election_pub_socket.connect("tcp://proxy:5557")

# Socket SUB para eleições
election_sub_socket = ref_context.socket(zmq.SUB)
election_sub_socket.connect("tcp://proxy:5558")
election_sub_socket.setsockopt_string(zmq.SUBSCRIBE, "servers")

def registrar_no_servidor_referencia():
    """Registra o servidor e obtém seu rank"""
    global rank_servidor
    try:
        ref_socket.setsockopt(zmq.RCVTIMEO, 5000)
        ref_socket.setsockopt(zmq.SNDTIMEO, 5000)
        
        request = {
            "service": "rank",
            "data": {
                "user": NOME_SERVIDOR,
                "timestamp": time.time(),
                "clock": relogio.tick()
            }
        }
        ref_socket.send(msgpack.packb(request))
        reply_data = ref_socket.recv()
        reply = msgpack.unpackb(reply_data, raw=False)
        
        if "data" in reply and "clock" in reply["data"]:
            relogio.update(reply["data"]["clock"])
        
        rank_servidor = reply.get("data", {}).get("rank")
        print(f"[S] Servidor {NOME_SERVIDOR} registrado com rank {rank_servidor}", flush=True)
    except:
        rank_servidor = None

def enviar_heartbeat():
    """Envia heartbeat periodicamente ao servidor de referência"""
    while True:
        time.sleep(10)  # Enviar a cada 10 segundos
        try:
            ctx = zmq.Context()
            sock = ctx.socket(zmq.REQ)
            sock.connect("tcp://referencia:5560")
            
            request = {
                "service": "heartbeat",
                "data": {
                    "user": NOME_SERVIDOR,
                    "timestamp": time.time(),
                    "clock": relogio.tick()
                }
            }
            sock.send(msgpack.packb(request))
            reply_data = sock.recv()
            reply = msgpack.unpackb(reply_data, raw=False)
            
            if "data" in reply and "clock" in reply["data"]:
                relogio.update(reply["data"]["clock"])
            
            sock.close()
            ctx.term()
        except:
            pass

def obter_lista_servidores():
    """Obtém a lista de servidores do servidor de referência"""
    try:
        ctx = zmq.Context()
        sock = ctx.socket(zmq.REQ)
        sock.connect("tcp://referencia:5560")
        
        request = {
            "service": "list",
            "data": {
                "timestamp": time.time(),
                "clock": relogio.tick()
            }
        }
        sock.send(msgpack.packb(request))
        reply_data = sock.recv()
        reply = msgpack.unpackb(reply_data, raw=False)
        
        if "data" in reply and "clock" in reply["data"]:
            relogio.update(reply["data"]["clock"])
        
        lista = reply.get("data", {}).get("list", [])
        
        sock.close()
        ctx.term()
        
        return lista
    except:
        return []

def sincronizar_relogio():
    """Sincroniza o relógio com o coordenador usando algoritmo de Berkeley"""
    global ajuste_relogio, contador_mensagens
    
    while True:
        time.sleep(30)  # Sincronizar a cada 30 segundos
        
        if coordenador_atual and coordenador_atual != NOME_SERVIDOR:
            try:
                # Solicitar horário do coordenador
                ctx = zmq.Context()
                sock = ctx.socket(zmq.REQ)
                
                # Encontrar endereço do coordenador
                lista_servidores = obter_lista_servidores()
                endereco_coord = None
                
                for servidor in lista_servidores:
                    if servidor.get("name") == coordenador_atual:
                        # Usar nome do container
                        endereco_coord = f"tcp://{coordenador_atual}:5561"
                        break
                
                if not endereco_coord:
                    continue
                
                sock.connect(endereco_coord)
                sock.setsockopt(zmq.RCVTIMEO, 5000)
                
                t1 = time.time()
                request = {
                    "service": "clock",
                    "data": {
                        "timestamp": t1,
                        "clock": relogio.tick()
                    }
                }
                sock.send(msgpack.packb(request))
                reply_data = sock.recv()
                t2 = time.time()
                
                reply = msgpack.unpackb(reply_data, raw=False)
                
                if "data" in reply and "clock" in reply["data"]:
                    relogio.update(reply["data"]["clock"])
                
                tempo_coord = reply.get("data", {}).get("time")
                
                if tempo_coord:
                    # Calcular ajuste (Berkeley simplificado)
                    rtt = t2 - t1
                    tempo_estimado_coord = tempo_coord + (rtt / 2)
                    ajuste_relogio = tempo_estimado_coord - time.time()
                
                sock.close()
                ctx.term()
                
            except zmq.Again:
                # Iniciar eleição silenciosamente
                iniciar_eleicao()
            except:
                pass

def iniciar_eleicao():
    """Inicia o processo de eleição (Bully Algorithm)"""
    global coordenador_atual
    
    print(f"[S] Iniciando eleição...", flush=True)
    
    lista_servidores = obter_lista_servidores()
    meu_rank = rank_servidor
    
    # Enviar election para servidores com rank maior
    servidores_maiores = [s for s in lista_servidores if s.get("rank", 0) > meu_rank]
    
    recebeu_ok = False
    
    for servidor in servidores_maiores:
        try:
            ctx = zmq.Context()
            sock = ctx.socket(zmq.REQ)
            sock.connect(f"tcp://{servidor['name']}:5561")
            sock.setsockopt(zmq.RCVTIMEO, 2000)
            
            request = {
                "service": "election",
                "data": {
                    "timestamp": time.time(),
                    "clock": relogio.tick()
                }
            }
            sock.send(msgpack.packb(request))
            reply_data = sock.recv()
            reply = msgpack.unpackb(reply_data, raw=False)
            
            if reply.get("data", {}).get("election") == "OK":
                recebeu_ok = True
            
            sock.close()
            ctx.term()
        except:
            pass
    
    if not recebeu_ok:
        coordenador_atual = NOME_SERVIDOR
        pub_msg = {
            "type": "election",
            "topic": "servers",
            "service": "election",
            "data": {
                "coordinator": NOME_SERVIDOR,
                "timestamp": time.time(),
                "clock": relogio.tick()
            }
        }
        election_pub_socket.send_string("servers", zmq.SNDMORE)
        election_pub_socket.send(msgpack.packb(pub_msg))

def monitor_eleicoes():
    global coordenador_atual
    while True:
        try:
            topic = election_sub_socket.recv_string()
            msg_data = election_sub_socket.recv()
            msg = msgpack.unpackb(msg_data, raw=False)
            
            if msg.get("type") == "election":
                novo_coord = msg.get("data", {}).get("coordinator")
                if novo_coord:
                    coordenador_atual = novo_coord
                    if "clock" in msg.get("data", {}):
                        relogio.update(msg["data"]["clock"])
        except:
            pass

time.sleep(3)
registrar_no_servidor_referencia()

if rank_servidor is not None:
    threading.Thread(target=enviar_heartbeat, daemon=True).start()
    threading.Thread(target=sincronizar_relogio, daemon=True).start()
    threading.Thread(target=monitor_eleicoes, daemon=True).start()
    if rank_servidor == 1:
        coordenador_atual = NOME_SERVIDOR

PUB_PORT = 5559  # Porta para publisher

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.connect("tcp://broker:5556")

# Socket para responder requisições de sincronização e eleição
sync_socket = context.socket(zmq.REP)
sync_socket.bind("tcp://*:5561")

replication_socket = context.socket(zmq.REP)
replication_socket.bind(f"tcp://*:{REPLICATION_PORT}")

pub_socket = context.socket(zmq.PUB)
pub_socket.bind(f"tcp://*:{PUB_PORT}")

# Carregar dados persistidos
usuarios, canais = carregar_dados()

def recarregar_dados_periodicamente():
    global usuarios, canais
    while True:
        time.sleep(2)
        try:
            usuarios_novos, canais_novos = carregar_dados()
            usuarios = usuarios_novos
            canais = canais_novos
        except:
            pass

threading.Thread(target=recarregar_dados_periodicamente, daemon=True).start()

poller = zmq.Poller()
poller.register(socket, zmq.POLLIN)
poller.register(sync_socket, zmq.POLLIN)
poller.register(replication_socket, zmq.POLLIN)

print(f"[S] {NOME_SERVIDOR} pronto", flush=True)

while True:
    try:
        socks = dict(poller.poll())
        
        if socket in socks:
            request_data = socket.recv()
            print(f"[S] Recebido {len(request_data)} bytes", flush=True)
            
            # Detectar formato: MessagePack ou JSON
            formato_json = False
            try:
                request = msgpack.unpackb(request_data, raw=False)
                print(f"[S] Formato: MessagePack", flush=True)
            except:
                try:
                    request = json.loads(request_data.decode('utf-8'))
                    formato_json = True
                    print(f"[S] Formato: JSON", flush=True)
                    print(f"[S] Request: {request}", flush=True)
                except Exception as e:
                    print(f"[S] Erro ao parsear: {e}", flush=True)
                    continue
            
            service = request.get("service", request.get("opcao"))
            data = request.get("data", request.get("dados"))
            
            salvar_log(f"[{time.time()}] {service}")
            
            if data and "clock" in data:
                relogio.update(data["clock"])
            
            contador_mensagens += 1
            
            match service:
                case "login":
                    user = data.get("user")
                    timestamp = data.get("timestamp")
                    
                    # Verificar se o usuário já existe
                    usuario_existe = any(u.get("user") == user for u in usuarios)
                    
                    if usuario_existe:
                        reply = {
                            "service": "login",
                            "data": {
                                "status": "erro",
                                "timestamp": time.time(),
                                "description": "Usuário já cadastrado",
                                "clock": relogio.tick()
                            }
                        }
                        print(f"[S] - Tentativa de login com usuário existente: {user}", flush=True)
                    else:
                        # Adicionar novo usuário
                        usuarios.append({
                            "user": user,
                            "timestamp": timestamp
                        })
                        salvar_usuarios(usuarios)  # Persistir em disco
                        
                        reply = {
                            "service": "login",
                            "data": {
                                "status": "sucesso",
                                "timestamp": time.time(),
                                "clock": relogio.tick()
                            }
                        }
                        print(f"[S] Login: {user}", flush=True)
                        replicar_para_outros_servidores({"service": "login", "data": data})

                case "users" | "listar":
                    lista_usuarios = [u.get("user") for u in usuarios]
                    print(f"[S] Listando usuarios: {len(usuarios)}", flush=True)
                    
                    reply = {
                        "service": "users",
                        "data": {
                            "timestamp": time.time(),
                            "users": lista_usuarios,
                            "clock": relogio.tick()
                        }
                    }
            
                case "channel" | "cadastrarCanal":
                    channel = data.get("channel", data.get("canal"))
                    timestamp = data.get("timestamp")
                    canal_existe = any(c.get("channel") == channel for c in canais)
                    
                    if canal_existe:
                        reply = {
                            "service": "channel",
                            "data": {
                                "status": "erro",
                                "timestamp": time.time(),
                                "description": "Canal ja existe",
                                "clock": relogio.tick()
                            }
                        }
                    else:
                        canais.append({"channel": channel, "timestamp": timestamp})
                        salvar_canais(canais)
                        reply = {
                            "service": "channel",
                            "data": {
                                "status": "sucesso",
                                "timestamp": time.time(),
                                "clock": relogio.tick()
                            }
                        }
                        print(f"[S] Canal: {channel}", flush=True)
                        replicar_para_outros_servidores({"service": "channel", "data": data})

                case "channels" | "listarCanal":
                    lista_canais = [c.get("channel") for c in canais]
                    print(f"[S] Listando canais: {len(canais)}", flush=True)
                    
                    reply = {
                        "service": "channels",
                        "data": {
                            "timestamp": time.time(),
                            "channels": lista_canais,
                            "clock": relogio.tick()
                        }
                    }

                case "publish":
                    user = data.get("user")
                    channel = data.get("channel")
                    message = data.get("message")
                    timestamp = data.get("timestamp")
                    canal_existe = any(c.get("channel") == channel for c in canais)
                    
                    if not canal_existe:
                        reply = {
                            "service": "publish",
                            "data": {
                                "status": "erro",
                                "message": f"Canal nao existe",
                                "timestamp": time.time(),
                                "clock": relogio.tick()
                            }
                        }
                    else:
                        pub_msg = {
                            "type": "channel",
                            "topic": channel,
                            "user": user,
                            "channel": channel,
                            "message": message,
                            "timestamp": timestamp,
                            "clock": relogio.get()
                        }
                        pub_socket.send(msgpack.packb(pub_msg))
                        salvar_publicacao({"user": user, "channel": channel, "message": message, "timestamp": timestamp})
                        
                        reply = {
                            "service": "publish",
                            "data": {
                                "status": "OK",
                                "timestamp": time.time(),
                                "clock": relogio.tick()
                            }
                        }
                        print(f"[S] Publicado: {channel}", flush=True)
                        replicar_para_outros_servidores({"service": "publish", "data": data})

                case "message":
                    src = data.get("src")
                    dst = data.get("dst")
                    message = data.get("message")
                    timestamp = data.get("timestamp")
                    usuario_existe = any(u.get("user") == dst for u in usuarios)
                    
                    if not usuario_existe:
                        reply = {
                            "service": "message",
                            "data": {
                                "status": "erro",
                                "message": f"Usuario nao existe",
                                "timestamp": time.time(),
                                "clock": relogio.tick()
                            }
                        }
                    else:
                        pub_msg = {
                            "type": "user",
                            "topic": dst,
                            "src": src,
                            "dst": dst,
                            "message": message,
                            "timestamp": timestamp,
                            "clock": relogio.get()
                        }
                        pub_socket.send(msgpack.packb(pub_msg))
                        salvar_mensagem_privada({"src": src, "dst": dst, "message": message, "timestamp": timestamp})
                        
                        reply = {
                            "service": "message",
                            "data": {
                                "status": "OK",
                                "timestamp": time.time(),
                                "clock": relogio.tick()
                            }
                        }
                        print(f"[S] Mensagem: {src} -> {dst}", flush=True)
                        replicar_para_outros_servidores({"service": "message", "data": data})
            
                case _ :
                    reply = {
                        "service": service if service else "unknown",
                        "data": {
                            "status": "erro",
                            "timestamp": time.time(),
                            "description": "Serviço não encontrado",
                            "clock": relogio.tick()
                        }
                    }

            # Responder no mesmo formato que recebeu
            if formato_json:
                socket.send(json.dumps(reply).encode('utf-8'))
            else:
                socket.send(msgpack.packb(reply))
        
        if sync_socket in socks:
            try:
                request_data = sync_socket.recv()
                request = msgpack.unpackb(request_data, raw=False)
                service = request.get("service")
                data = request.get("data", {})
                
                if "clock" in data:
                    relogio.update(data["clock"])
                
                if service == "clock":
                    reply = {
                        "service": "clock",
                        "data": {
                            "time": time.time() + ajuste_relogio,
                            "timestamp": time.time(),
                            "clock": relogio.tick()
                        }
                    }
                elif service == "election":
                    reply = {
                        "service": "election",
                        "data": {
                            "election": "OK",
                            "timestamp": time.time(),
                            "clock": relogio.tick()
                        }
                    }
                    threading.Thread(target=iniciar_eleicao, daemon=True).start()
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
                
                sync_socket.send(msgpack.packb(reply))
            except:
                pass
        
        if replication_socket in socks:
            try:
                request_data = replication_socket.recv()
                request = msgpack.unpackb(request_data, raw=False)
                
                if request.get("replicated"):
                    service = request.get("service")
                    data = request.get("data", {})
                    
                    if "clock" in data:
                        relogio.update(data["clock"])
                    
                    if service == "login":
                        user = data.get("user")
                        if not any(u.get("user") == user for u in usuarios):
                            usuarios.append({"user": user, "timestamp": data.get("timestamp")})
                            salvar_usuarios(usuarios)
                            print(f"[S] Replicado usuario: {user}", flush=True)
                    
                    elif service == "channel":
                        channel = data.get("channel", data.get("canal"))
                        if not any(c.get("channel") == channel for c in canais):
                            canais.append({"channel": channel, "timestamp": data.get("timestamp")})
                            salvar_canais(canais)
                            print(f"[S] Replicado canal: {channel}", flush=True)
                    
                    elif service == "publish":
                        salvar_publicacao({
                            "user": data.get("user"),
                            "channel": data.get("channel"),
                            "message": data.get("message"),
                            "timestamp": data.get("timestamp")
                        })
                    
                    elif service == "message":
                        salvar_mensagem_privada({
                            "src": data.get("src"),
                            "dst": data.get("dst"),
                            "message": data.get("message"),
                            "timestamp": data.get("timestamp")
                        })
                    
                    ack = {"status": "OK", "clock": relogio.tick()}
                    replication_socket.send(msgpack.packb(ack))
                else:
                    ack = {"status": "ignored"}
                    replication_socket.send(msgpack.packb(ack))
            except:
                pass
    
    except KeyboardInterrupt:
        break
    except:
        time.sleep(0.1)
