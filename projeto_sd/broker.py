import zmq

context = zmq.Context()

client_socket = context.socket(zmq.ROUTER)
client_socket.bind("tcp://*:5555")
print("[BROKER] ROUTER porta 5555", flush=True)

server_socket = context.socket(zmq.DEALER)
server_socket.bind("tcp://*:5556")
print("[BROKER] DEALER porta 5556", flush=True)

try:
    zmq.proxy(client_socket, server_socket)
except KeyboardInterrupt:
    pass
finally:
    client_socket.close()
    server_socket.close()
    context.term()
