import zmq
from time import sleep
import msgpack

context = zmq.Context()

servidor_sub = context.socket(zmq.SUB)
servidor_sub.connect("tcp://servidor:5559")
servidor_sub.setsockopt_string(zmq.SUBSCRIBE, "")

proxy_pub = context.socket(zmq.PUB)
proxy_pub.connect("tcp://proxy:5557")

print("[PUB] Iniciado", flush=True)

while True:
    try:
        mensagem_data = servidor_sub.recv()
        mensagem = msgpack.unpackb(mensagem_data, raw=False)
        topic = mensagem.get("topic", "")
        
        if topic:
            proxy_pub.send_string(topic, zmq.SNDMORE)
            proxy_pub.send(msgpack.packb(mensagem))
        else:
            proxy_pub.send(msgpack.packb(mensagem))
    except:
        pass
    sleep(0.1)

proxy_pub.close()
servidor_sub.close()
context.close()
