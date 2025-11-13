import zmq
import threading

def proxy_channels():
    context = zmq.Context()
    xsub = context.socket(zmq.XSUB)
    xsub.bind("tcp://*:5557")
    xpub = context.socket(zmq.XPUB)
    xpub.bind("tcp://*:5558")
    print("[PROXY] Channels 5557/5558", flush=True)
    zmq.proxy(xsub, xpub)
    xsub.close()
    xpub.close()
    context.close()

def proxy_replication():
    context = zmq.Context()
    xsub = context.socket(zmq.XSUB)
    xsub.bind("tcp://*:5570")
    xpub = context.socket(zmq.XPUB)
    xpub.bind("tcp://*:5571")
    print("[PROXY] Replication 5570/5571", flush=True)
    zmq.proxy(xsub, xpub)
    xsub.close()
    xpub.close()
    context.close()

threading.Thread(target=proxy_channels, daemon=True).start()
threading.Thread(target=proxy_replication, daemon=True).start()

try:
    while True:
        threading.Event().wait(1)
except KeyboardInterrupt:
    pass
