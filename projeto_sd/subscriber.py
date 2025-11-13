import zmq
from time import sleep
import msgpack
import os

usuario = os.environ.get("SUBSCRIBER_USER", "sub_default")
canais_inscritos = os.environ.get("SUBSCRIBER_CHANNELS", "").split(",")
canais_inscritos = [c.strip() for c in canais_inscritos if c.strip()]

context = zmq.Context()
sub = context.socket(zmq.SUB)
sub.connect("tcp://proxy:5558")

sub.setsockopt_string(zmq.SUBSCRIBE, usuario)
for canal in canais_inscritos:
    sub.setsockopt_string(zmq.SUBSCRIBE, canal)

print(f"[SUB {usuario}] Iniciado", flush=True)

while True:
    try:
        topic = sub.recv_string()
        mensagem_data = sub.recv()
        mensagem = msgpack.unpackb(mensagem_data, raw=False)
        
        msg_type = mensagem.get("type")
        if msg_type == "user":
            src = mensagem.get("src")
            message = mensagem.get("message")
            print(f"[SUB {usuario}] De {src}: {message}", flush=True)
        elif msg_type == "channel":
            user = mensagem.get("user")
            channel = mensagem.get("channel")
            message = mensagem.get("message")
            print(f"[SUB {usuario}] #{channel} {user}: {message}", flush=True)
    except:
        pass
    sleep(0.1)

sub.close()
context.close()
