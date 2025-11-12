import zmq

context = zmq.Context()

# XSUB socket (recebe subscriptions)
xsub_socket = context.socket(zmq.XSUB)
xsub_socket.bind("tcp://*:5557")

# XPUB socket (publica mensagens)
xpub_socket = context.socket(zmq.XPUB)
xpub_socket.bind("tcp://*:5558")

print("Proxy Pub/Sub iniciado:")
print("  XSUB (subscribers) em tcp://*:5557")
print("  XPUB (publishers) em tcp://*:5558")

# Proxy conecta XSUB e XPUB
zmq.proxy(xsub_socket, xpub_socket)

xsub_socket.close()
xpub_socket.close()
context.term()

