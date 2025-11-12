import zmq from "zeromq";
import fs from "fs";
import { encode, decode } from "@msgpack/msgpack";

const socket = new zmq.Reply();
await socket.connect("tcp://broker:5556");
console.log("Socket Reply conectado ao broker: tcp://broker:5556");

// Pub socket para publicar mensagens no Pub/Sub
const pubSocket = new zmq.Publisher();
await pubSocket.connect("tcp://proxy:5558");

// Sockets separados para comunicação com servidor de referência
// (ZeroMQ REQ não permite múltiplas operações simultâneas)
const refSocketRank = new zmq.Request();
refSocketRank.connect("tcp://referencia:5559");

const refSocketList = new zmq.Request();
refSocketList.connect("tcp://referencia:5559");

const refSocketHeartbeat = new zmq.Request();
refSocketHeartbeat.connect("tcp://referencia:5559");

// Socket para comunicação entre servidores (REQ para outros servidores)
const serverSocket = new zmq.Request();

// Socket para receber mensagens de eleição (REP para outros servidores)
const electionSocket = new zmq.Reply();
const electionPort = process.env.ELECTION_PORT || 5560;
let isElectionSocketActive = true;
try {
  await electionSocket.bind(`tcp://*:${electionPort}`);
  console.log(`Socket de eleição aguardando em tcp://*:${electionPort}`);
} catch (err) {
  if (err.code === "EBUSY") {
    isElectionSocketActive = false;
    console.warn(
      `Porta de eleição ${electionPort} ocupada. Este servidor funcionará em modo passivo de eleição.`
    );
  } else {
    throw err;
  }
}

// Sub socket para receber notificações de eleição no tópico "servers"
const subSocket = new zmq.Subscriber();
subSocket.connect("tcp://proxy:5557");
subSocket.subscribe("servers");

// Sub socket para receber mensagens de replicação
const replicationSubSocket = new zmq.Subscriber();
replicationSubSocket.connect("tcp://proxy:5557");
replicationSubSocket.subscribe("replication");

let erro = "";

let tarefas = {};
let cont = 0;

// Relógio lógico
let logicalClock = 0;

// Relógio físico (ajustado pela sincronização Berkeley)
let physicalClockOffset = 0;

// Informações do servidor
const serverName = process.env.SERVER_NAME || process.env.HOSTNAME || `server_${Date.now()}`;
const containerName = process.env.HOSTNAME || serverName;
let serverRank = -1;
let coordinator = null;
let coordinatorContainer = null; // Nome do container do coordenador
let messageCount = 0; // Contador para sincronização a cada 10 mensagens
let serverList = []; // Lista de outros servidores
let isReplicating = false; // Flag para evitar loops de replicação

function updateLogicalClock(receivedClock) {
  logicalClock = Math.max(logicalClock, receivedClock) + 1;
}

function incrementLogicalClock() {
  logicalClock++;
  return logicalClock;
}

const DATA_FILE = "./data/data.json";
const MESSAGES_FILE = "./data/messages.json";
const PUBLICATIONS_FILE = "./data/publications.json";

function loadData() {
  if (!fs.existsSync(DATA_FILE)) {
    const initialData = { users: [], channels: [] };
    fs.writeFileSync(DATA_FILE, JSON.stringify(initialData, null, 2));
    return initialData;
  }
  return JSON.parse(fs.readFileSync(DATA_FILE));
}
function saveData(data) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

function loadMessages() {
  if (!fs.existsSync(MESSAGES_FILE)) {
    const initialData = [];
    fs.writeFileSync(MESSAGES_FILE, JSON.stringify(initialData, null, 2));
    return initialData;
  }
  return JSON.parse(fs.readFileSync(MESSAGES_FILE));
}

function saveMessage(message) {
  const messages = loadMessages();
  messages.push(message);
  fs.writeFileSync(MESSAGES_FILE, JSON.stringify(messages, null, 2));
}

function loadPublications() {
  if (!fs.existsSync(PUBLICATIONS_FILE)) {
    const initialData = [];
    fs.writeFileSync(PUBLICATIONS_FILE, JSON.stringify(initialData, null, 2));
    return initialData;
  }
  try {
    return JSON.parse(fs.readFileSync(PUBLICATIONS_FILE));
  } catch (err) {
    console.error("Erro ao carregar publicações:", err);
    return [];
  }
}

function savePublication(publication) {
  const publications = loadPublications();
  publications.push(publication);
  fs.writeFileSync(PUBLICATIONS_FILE, JSON.stringify(publications, null, 2));
}

let db = loadData();

// Função para obter rank do servidor de referência
async function getRank() {
  try {
    incrementLogicalClock();
    const request = {
      service: "rank",
      data: {
        user: serverName,
        timestamp: Date.now(),
        clock: logicalClock
      }
    };
    await refSocketRank.send(encode(request));
    const reply = decode(await refSocketRank.receive());
    updateLogicalClock(reply.data?.clock || 0);
    serverRank = reply.data?.rank || -1;
    console.log(`Servidor '${serverName}' obteve rank ${serverRank}`);
    return serverRank;
  } catch (err) {
    console.error(`Erro ao obter rank do servidor de referência: ${err.message}`);
    // Atribui um rank temporário baseado no timestamp
    serverRank = Date.now() % 1000;
    console.log(`Usando rank temporário ${serverRank}`);
    return serverRank;
  }
}

// Função para enviar heartbeat
async function sendHeartbeat() {
  incrementLogicalClock();
  const request = {
    service: "heartbeat",
    data: {
      user: serverName,
      timestamp: Date.now(),
      clock: logicalClock
    }
  };
  try {
    await refSocketHeartbeat.send(encode(request));
    const reply = decode(await refSocketHeartbeat.receive());
    updateLogicalClock(reply.data?.clock || 0);
  } catch (err) {
    // Ignora erros de heartbeat silenciosamente para não poluir logs
    if (err.code !== 'EBUSY') {
      console.error("Erro ao enviar heartbeat:", err.message);
    }
  }
}

// Função para obter lista de servidores
async function getServerList() {
  try {
    incrementLogicalClock();
    const request = {
      service: "list",
      data: {
        timestamp: Date.now(),
        clock: logicalClock
      }
    };
    await refSocketList.send(encode(request));
    const reply = decode(await refSocketList.receive());
    updateLogicalClock(reply.data?.clock || 0);
    serverList = reply.data?.list || [];
    // Filtra o próprio servidor da lista
    serverList = serverList.filter(s => s.name !== serverName);
    return serverList;
  } catch (err) {
    // Ignora erros EBUSY silenciosamente
    if (err.code !== 'EBUSY') {
      console.error("Erro ao obter lista de servidores:", err.message);
    }
    return [];
  }
}

// Função para sincronizar relógio físico (Berkeley)
async function synchronizePhysicalClock() {
  if (!coordinator || coordinator === serverName) {
    return; // Não precisa sincronizar se é o coordenador
  }
  
  if (!coordinatorContainer) {
    return; // Não sabemos o container do coordenador ainda
  }
  
  try {
    // Conecta ao coordenador usando o nome do container
    const coordSocket = new zmq.Request();
    await coordSocket.connect(`tcp://${coordinatorContainer}:5560`);
    
    incrementLogicalClock();
    const request = {
      service: "clock",
      data: {
        timestamp: Date.now(),
        clock: logicalClock
      }
    };
    
    await coordSocket.send(encode(request));
    const reply = decode(await coordSocket.receive());
    updateLogicalClock(reply.data?.clock || 0);
    
    const coordinatorTime = reply.data?.time || Date.now();
    const localTime = Date.now();
    physicalClockOffset = coordinatorTime - localTime;
    
    console.log(`Relógio sincronizado: offset = ${physicalClockOffset}ms`);
    
    coordSocket.close();
  } catch (err) {
    console.error(`Erro ao sincronizar com coordenador ${coordinator}:`, err);
    // Se coordenador não está disponível, inicia eleição
    startElection();
  }
}

// Função para iniciar eleição
async function startElection() {
  console.log(`Iniciando eleição...`);
  const list = await getServerList();
  
  // Filtra servidores com rank maior (menor número = maior prioridade)
  const higherRankServers = list.filter(s => s.rank < serverRank);
  
  if (higherRankServers.length === 0) {
    // Este servidor é o coordenador
    coordinator = serverName;
    coordinatorContainer = containerName;
    console.log(`Servidor '${serverName}' (${containerName}) eleito como coordenador`);
    
    // Publica no tópico "servers"
    incrementLogicalClock();
    const electionData = {
      service: "election",
      data: {
        coordinator: serverName,
        coordinatorContainer: containerName,
        timestamp: Date.now(),
        clock: logicalClock
      }
    };
    await pubSocket.send(["servers", encode(electionData)]);
  } else {
    // Envia requisição de eleição para servidores com rank maior
    // Nota: Com Docker Compose replicas, todos os containers compartilham o mesmo nome de serviço
    // A conexão será feita através do load balancer interno do Docker
    // Por simplicidade, vamos assumir que pelo menos um servidor responderá
    let electionSuccess = false;
    
    // Tenta conectar ao serviço "servidor" (Docker Compose faz o balanceamento)
    try {
      const electionSocket = new zmq.Request();
      // Usa o nome do serviço do Docker Compose
      await electionSocket.connect("tcp://servidor:5560");
      
      incrementLogicalClock();
      const request = {
        service: "election",
        data: {
          timestamp: Date.now(),
          clock: logicalClock
        }
      };
      
      await electionSocket.send(encode(request));
      const reply = decode(await electionSocket.receive());
      updateLogicalClock(reply.data?.clock || 0);
      
      if (reply.data?.election === "OK") {
        electionSuccess = true;
      }
      
      electionSocket.close();
    } catch (err) {
      // Nenhum servidor respondeu
      console.log(`Nenhum servidor com rank maior respondeu: ${err.message}`);
    }
    
    if (!electionSuccess) {
      // Nenhum servidor respondeu, este servidor é o coordenador
      coordinator = serverName;
      coordinatorContainer = containerName;
      console.log(`Servidor '${serverName}' (${containerName}) eleito como coordenador`);
      
      incrementLogicalClock();
      const electionData = {
        service: "election",
        data: {
          coordinator: serverName,
          coordinatorContainer: containerName,
          timestamp: Date.now(),
          clock: logicalClock
        }
      };
      await pubSocket.send(["servers", encode(electionData)]);
    }
  }
}

console.log(`Servidor '${serverName}' iniciado`);
console.log("Servidor JS conectado ao broker: tcp://broker:5556");
console.log("Servidor JS conectado ao proxy Pub/Sub: tcp://proxy:5558");
console.log("Servidor JS conectado ao servidor de referência: tcp://referencia:5559");
console.log("=== SERVIDOR PRONTO PARA RECEBER MENSAGENS DOS CLIENTES ===");

// Inicialização (não bloqueante - executa em background após o loop principal começar)
setTimeout(async () => {
  try {
    await getRank();
    await getServerList();
    await startElection();
    console.log("Inicialização do servidor concluída");
  } catch (err) {
    console.error("Erro na inicialização:", err);
  }
}, 2000);

// Heartbeat periódico (a cada 5 segundos)
setInterval(() => {
  sendHeartbeat().catch(err => {
    if (err.code !== 'EBUSY') {
      console.error("Erro no heartbeat:", err.message);
    }
  });
}, 5000);

// Atualiza lista de servidores periodicamente (a cada 10 segundos)
setInterval(async () => {
  try {
    await getServerList();
  } catch (err) {
    if (err.code !== 'EBUSY') {
      console.error("Erro ao atualizar lista de servidores:", err.message);
    }
  }
}, 10000);

// Processa mensagens de eleição recebidas via Pub/Sub
(async () => {
  for await (const [topic, msg] of subSocket) {
    if (topic.toString() === "servers") {
      const data = decode(msg);
      updateLogicalClock(data.data?.clock || 0);
      if (data.service === "election" && data.data?.coordinator) {
        coordinator = data.data.coordinator;
        coordinatorContainer = data.data.coordinatorContainer || coordinator;
        console.log(`Novo coordenador eleito: ${coordinator} (${coordinatorContainer})`);
      }
    }
  }
})();

// Função para replicar operação para outros servidores
async function replicateOperation(operation, operationData) {
  if (isReplicating) {
    return; // Evita loops de replicação
  }
  
  incrementLogicalClock();
  const replicationMessage = {
    service: "replication",
    data: {
      operation: operation,
      operationData: operationData,
      serverName: serverName,
      timestamp: Date.now(),
      clock: logicalClock
    }
  };
  
  await pubSocket.send(["replication", encode(replicationMessage)]);
  console.log(`Operação '${operation}' replicada para outros servidores`);
}

// Função para aplicar replicação recebida
function applyReplication(operation, operationData) {
  isReplicating = true;
  
  try {
    switch (operation) {
      case "login": {
        const { user, timestamp } = operationData;
        if (user) {
          const exists = db.users.find(u => u.user === user);
          if (!exists) {
            db.users.push({ user, timestamp });
            saveData(db);
          }
        }
        break;
      }
      
      case "channel": {
        const { channel, timestamp } = operationData;
        if (channel) {
          const exists = db.channels.find(c => c.channel === channel);
          if (!exists) {
            db.channels.push({ channel, timestamp });
            saveData(db);
          }
        }
        break;
      }
      
      case "publish": {
        const { channel, user, message, timestamp } = operationData;
        savePublication({
          channel: channel,
          user: user,
          message: message,
          timestamp: timestamp,
          savedAt: Date.now()
        });
        break;
      }
      
      case "message": {
        const { src, dst, message, timestamp } = operationData;
        saveMessage({
          src: src,
          dst: dst,
          message: message,
          timestamp: timestamp,
          savedAt: Date.now()
        });
        break;
      }
    }
    
    console.log(`Replicação aplicada: operação '${operation}'`);
  } catch (err) {
    console.error(`Erro ao aplicar replicação '${operation}':`, err);
  } finally {
    isReplicating = false;
  }
}

// Processa mensagens de replicação recebidas
(async () => {
  for await (const [topic, msg] of replicationSubSocket) {
    if (topic.toString() === "replication") {
      const data = decode(msg);
      updateLogicalClock(data.data?.clock || 0);
      
      // Ignora replicações do próprio servidor
      if (data.data?.serverName === serverName) {
        continue;
      }
      
      const operation = data.data?.operation;
      const operationData = data.data?.operationData;
      
      if (operation && operationData) {
        applyReplication(operation, operationData);
      }
    }
  }
})();

if (isElectionSocketActive) {
  (async () => {
    for await (const [msg] of electionSocket) {
      const request = decode(msg);
      updateLogicalClock(request.data?.clock || 0);
  
      if (request.service === "election") {
        incrementLogicalClock();
        const reply = {
          service: "election",
          data: {
            election: "OK",
            timestamp: Date.now(),
            clock: logicalClock
          }
        };
        await electionSocket.send(encode(reply));
      } else if (request.service === "clock") {
        // Responde com o horário atual (ajustado pelo offset)
        incrementLogicalClock();
        const reply = {
          service: "clock",
          data: {
            time: Date.now() + physicalClockOffset,
            timestamp: Date.now(),
            clock: logicalClock
          }
        };
        await electionSocket.send(encode(reply));
      }
    }
  })();
} else {
  console.log("Socket de eleição inativo; ignorando requisições de eleição neste servidor.");
}

console.log(`[${serverName}] Iniciando loop principal de processamento de mensagens...`);
for await (const [msg] of socket) {
  console.log(`[${serverName}] Mensagem recebida do broker (tamanho: ${msg.length} bytes)`); 
  let request;
  try {
    request = decode(msg);
    console.log(`[${serverName}] Mensagem decodificada com sucesso`);
  } catch (err) {
    console.error(`[${serverName}] Erro ao parsear MessagePack:`, err);
    incrementLogicalClock();
    const errorReply = {
      service: "error",
      data: {
        message: "ERRO: MessagePack inválido",
        clock: logicalClock
      }
    };
    await socket.send(encode(errorReply));
    erro = "ERRO: MessagePack inválido";
    continue;
  }

  // Atualiza relógio lógico ao receber mensagem
  const receivedClock = request.data?.clock || 0;
  updateLogicalClock(receivedClock);
  
  // Incrementa contador de mensagens e sincroniza relógio a cada 10 mensagens
  messageCount++;
  if (messageCount >= 10) {
    messageCount = 0;
    synchronizePhysicalClock();
  }

  const opcao = request.service || request.opcao; // Suporta ambos os formatos
  console.log(`[${serverName}] Recebida requisição: ${opcao}`, JSON.stringify(request));
  const data = request.data;
  let reply = {
    service: "error",
    data: {
      message: "ERRO: função não escolhida",
      clock: logicalClock
    }
  };

  switch (opcao) {
    case "login":
      console.log(`Mensagem recebida ${JSON.stringify(request)}`)
      if (!erro) {
        tarefas[cont] = data;
        cont++;
        const { user, timestamp } = data;
        if (user) {
          const exists = db.users.find(u => u.user === user);
          if (!exists) {
            db.users.push({ user, timestamp });
            saveData(db);
            // Replica a operação
            await replicateOperation("login", { user, timestamp });
          }
        }

        incrementLogicalClock();
        reply = {
          service: "login",
          data: {
            status: "sucesso",
            timestamp: Date.now(),
            clock: logicalClock,
          },
        };
        console.log("Tarefas pós login:", tarefas); 
        break;
      } else {
        incrementLogicalClock();
        reply = {
          service: "login",
          data: {
            status: "erro",
            timestamp: Date.now(),
            description: erro,
            clock: logicalClock,
          },
        };
        break;
      }

    case "users":
      incrementLogicalClock();
      reply = {
        service: "users",
        data: {
          timestamp: Date.now(),
          users: db.users.map(u => u.user),
          clock: logicalClock
        }
      };
      break;

    case "channel": {
      const { channel, timestamp } = data;
      if (!channel) {
        incrementLogicalClock();
        reply = {
          service: "channel",
          data: {
            status: "erro",
            description: "Nome do canal não informado",
            timestamp: Date.now(),
            clock: logicalClock
          }
        };
        break;
      }

      const exists = db.channels.find(c => c.channel === channel);
      if (!exists) {
        db.channels.push({ channel, timestamp });
        saveData(db);
        // Replica a operação
        await replicateOperation("channel", { channel, timestamp });
      }

      incrementLogicalClock();
      reply = {
        service: "channel",
        data: {
          status: "sucesso",
          timestamp: Date.now(),
          clock: logicalClock
        }
      };
      break;
    }

    case "channels":
      incrementLogicalClock();
      reply = {
        service: "channels",
        data: {
          timestamp: Date.now(),
          channels: db.channels.map(c => c.channel),
          clock: logicalClock
        }
      };
      break;
    
    case "publish": {
      const { user, channel, message, timestamp } = data;
      
      if (!channel || !message || !user) {
        incrementLogicalClock();
        reply = {
          service: "publish",
          data: {
            status: "erro",
            message: "Canal, mensagem ou usuário não informado",
            timestamp: Date.now(),
            clock: logicalClock
          }
        };
        break;
      }

      // Verifica se o canal existe
      const channelExists = db.channels.find(c => c.channel === channel);
      if (!channelExists) {
        incrementLogicalClock();
        reply = {
          service: "publish",
          data: {
            status: "erro",
            message: "Canal não existe",
            timestamp: Date.now(),
            clock: logicalClock
          }
        };
        break;
      }

      // Publica no tópico do canal
      incrementLogicalClock();
      const publicationData = {
        user: user,
        message: message,
        timestamp: timestamp || Date.now(),
        clock: logicalClock
      };
      
      await pubSocket.send([channel, encode(publicationData)]);
      
      // Persiste a publicação
      savePublication({
        channel: channel,
        ...publicationData,
        savedAt: Date.now()
      });
      
      // Replica a operação
      await replicateOperation("publish", {
        channel: channel,
        user: user,
        message: message,
        timestamp: timestamp || Date.now()
      });

      incrementLogicalClock();
      reply = {
        service: "publish",
        data: {
          status: "OK",
          timestamp: Date.now(),
          clock: logicalClock
        }
      };
      break;
    }

    case "message": {
      const { src, dst, message, timestamp } = data;
      
      if (!src || !dst || !message) {
        incrementLogicalClock();
        reply = {
          service: "message",
          data: {
            status: "erro",
            message: "Origem, destino ou mensagem não informado",
            timestamp: Date.now(),
            clock: logicalClock
          }
        };
        break;
      }

      // Verifica se o usuário destino existe
      const userExists = db.users.find(u => u.user === dst);
      if (!userExists) {
        incrementLogicalClock();
        reply = {
          service: "message",
          data: {
            status: "erro",
            message: "Usuário destino não existe",
            timestamp: Date.now(),
            clock: logicalClock
          }
        };
        break;
      }

      // Publica no tópico do usuário destino
      incrementLogicalClock();
      const messageData = {
        src: src,
        message: message,
        timestamp: timestamp || Date.now(),
        clock: logicalClock
      };
      
      await pubSocket.send([dst, encode(messageData)]);
      
      // Persiste a mensagem
      saveMessage({
        src: src,
        dst: dst,
        message: message,
        timestamp: timestamp || Date.now(),
        savedAt: Date.now()
      });
      
      // Replica a operação
      await replicateOperation("message", {
        src: src,
        dst: dst,
        message: message,
        timestamp: timestamp || Date.now()
      });

      incrementLogicalClock();
      reply = {
        service: "message",
        data: {
          status: "OK",
          timestamp: Date.now(),
          clock: logicalClock
        }
      };
      break;
    }

    default:
      incrementLogicalClock();
      reply = {
        service: "error",
        data: {
          message: "ERRO: função não encontrada",
          clock: logicalClock
        }
      };
    
  }

  try {
    if (typeof reply === "object") {
      console.log(`[${serverName}] Enviando resposta:`, JSON.stringify(reply));
      await socket.send(encode(reply));
    } else {
      incrementLogicalClock();
      const errorReply = {
        service: "error",
        data: {
          message: reply,
          clock: logicalClock
        }
      };
      console.log(`[${serverName}] Enviando resposta de erro:`, JSON.stringify(errorReply));
      await socket.send(encode(errorReply));
    }
  } catch (err) {
    console.error(`[${serverName}] Erro ao enviar resposta:`, err);
    try {
      incrementLogicalClock();
      const errorReply = {
        service: "error",
        data: {
          message: `Erro interno: ${err.message}`,
          clock: logicalClock
        }
      };
      await socket.send(encode(errorReply));
    } catch (sendErr) {
      console.error(`[${serverName}] Erro crítico ao enviar resposta de erro:`, sendErr);
    }
  }
}
