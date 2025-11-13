const zmq = require('zeromq');
const msgpack = require('msgpack5')();

class RelogioLogico {
    constructor() {
        this.clock = 0;
    }
    
    tick() {
        this.clock++;
        return this.clock;
    }
    
    update(clockRecebido) {
        if (clockRecebido > this.clock) {
            this.clock = clockRecebido;
        }
    }
    
    get() {
        return this.clock;
    }
}

async function main() {
    const sock = new zmq.Request();
    sock.connect("tcp://broker:5555");
    sock.sendTimeout = 10000;
    sock.receiveTimeout = 10000;
    
    const relogio = new RelogioLogico();
    
    const usuario = process.env.CLIENT_NAME || `bot_${Math.floor(Math.random() * 9000) + 1000}`;
    console.log(`[BOT ${usuario}] Iniciado`);
    
    // Login
    let request = {
        service: "login",
        data: {
            user: usuario,
            timestamp: Date.now() / 1000,
            clock: relogio.tick()
        }
    };
    
    await sock.send(msgpack.encode(request));
    let reply = msgpack.decode(await sock.receive());
    
    if (reply.data && reply.data.clock) {
        relogio.update(reply.data.clock);
    }
    
    // Listar canais inicial
    request = {
        service: "channels",
        data: {
            timestamp: Date.now() / 1000,
            clock: relogio.tick()
        }
    };
    
    await sock.send(msgpack.encode(request));
    reply = msgpack.decode(await sock.receive());
    
    if (reply.data && reply.data.clock) {
        relogio.update(reply.data.clock);
    }
    
    const mensagensDisponiveis = [
        "Ola a todos!",
        "Mensagem automatica.",
        "Testando o canal.",
        "Mensagem de exemplo.",
        "Pub/Sub funcionando.",
        "Mais uma mensagem.",
        "JavaScript e legal.",
        "Distribuido e melhor.",
        "ZeroMQ test.",
        "Fim das mensagens."
    ];
    
    const canaisPadrao = ["geral", "noticias"];
    
    // Loop infinito
    while (true) {
        try {
            // Obter lista de canais
            request = {
                service: "channels",
                data: {
                    timestamp: Date.now() / 1000,
                    clock: relogio.tick()
                }
            };
            
            await sock.send(msgpack.encode(request));
            reply = msgpack.decode(await sock.receive());
            
            if (reply.data && reply.data.clock) {
                relogio.update(reply.data.clock);
            }
            
            let canais = reply.data?.channels || canaisPadrao;
            if (canais.length === 0) {
                canais = canaisPadrao;
            }
            
            const canalEscolhido = canais[Math.floor(Math.random() * canais.length)];
            
            // Enviar 10 mensagens
            for (let i = 0; i < 10; i++) {
                const mensagem = mensagensDisponiveis[Math.floor(Math.random() * mensagensDisponiveis.length)];
                
                request = {
                    service: "publish",
                    data: {
                        user: usuario,
                        channel: canalEscolhido,
                        message: mensagem,
                        timestamp: Date.now() / 1000,
                        clock: relogio.tick()
                    }
                };
                
                await sock.send(msgpack.encode(request));
                reply = msgpack.decode(await sock.receive());
                
                if (reply.data && reply.data.clock) {
                    relogio.update(reply.data.clock);
                }
                
                console.log(`[BOT ${usuario}] ${canalEscolhido}: ${mensagem}`);
                
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            
            await new Promise(resolve => setTimeout(resolve, 2000));
            
        } catch (error) {
            console.error(`[BOT ${usuario}] Erro: ${error.message}`);
            await new Promise(resolve => setTimeout(resolve, 5000));
        }
    }
}

main().catch(console.error);

