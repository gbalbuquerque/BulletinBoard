import zmq from "zeromq";
import fs from "fs";
const { promises: fsp } = fs;
import { encode, decode } from "@msgpack/msgpack";

const containerName = process.env.HOSTNAME || `server_${Date.now()}`;
const serverName = process.env.SERVER_NAME || containerName;
const serverId = containerName;

const originalLog = console.log.bind(console);
const originalWarn = console.warn.bind(console);
const originalError = console.error.bind(console);

function logWithTag(originalFn, args) {
  const prefix = `[${serverName}]`;
  if (args.length === 0) {
    return originalFn(prefix);
  }

  const [first, ...rest] = args;
  if (typeof first === "string") {
    if (first.startsWith(prefix)) {
      return originalFn(first, ...rest);
    }
    return originalFn(`${prefix} ${first}`, ...rest);
  }

  return originalFn(prefix, first, ...rest);
}

console.log = (...args) => logWithTag(originalLog, args);
console.warn = (...args) => logWithTag(originalWarn, args);
console.error = (...args) => logWithTag(originalError, args);

const socket = new zmq.Reply();
await socket.connect("tcp://broker:5556");
console.log("Socket Reply conectado ao broker: tcp://broker:5556");

// Pub socket para publicar mensagens no Pub/Sub
const pubSocket = new zmq.Publisher();
await pubSocket.connect("tcp://proxy:5557");

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
subSocket.connect("tcp://proxy:5558");
subSocket.subscribe("servers");

// Sub socket para receber mensagens de replicação
const replicationSubSocket = new zmq.Subscriber();
replicationSubSocket.connect("tcp://proxy:5558");
replicationSubSocket.subscribe("replication");

let erro = "";

let tarefas = {};
let cont = 0;

// Relógio lógico
let logicalClock = 0;

// Relógio físico (ajustado pela sincronização Berkeley)
let physicalClockOffset = 0;

let serverRank = -1;
let coordinator = null; // Identificador único (hostname) do coordenador
let coordinatorContainer = null; // Hostname do coordenador (mantido por compatibilidade)
let coordinatorDisplayName = null;
let messageCount = 0; // Contador para sincronização a cada 10 mensagens
let serverList = []; // Lista de outros servidores
let isReplicating = false; // Flag para evitar loops de replicação
let clockSyncInProgress = false;

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
  if (data) {
    db = data;
  }
  dataDirty = true;
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
  messagesCache.push(message);
  messagesDirty = true;
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
  publicationsCache.push(publication);
  publicationsDirty = true;
}

let db = loadData();
let messagesCache = loadMessages();
let publicationsCache = loadPublications();
let dataDirty = false;
let messagesDirty = false;
let publicationsDirty = false;
let flushingData = false;
let flushingMessages = false;
let flushingPublications = false;

const FLUSH_INTERVAL = parseInt(process.env.FLUSH_INTERVAL_MS || "500", 10);

async function flushDataIfNeeded() {
  if (!dataDirty || flushingData) {
    return;
  }
  flushingData = true;
  const snapshot = JSON.stringify(db, null, 2);
  try {
    await fsp.writeFile(DATA_FILE, snapshot);
    dataDirty = false;
  } catch (err) {
    console.error(`Erro ao persistir dados:`, err.message);
  } finally {
    flushingData = false;
  }
}

async function flushMessagesIfNeeded() {
  if (!messagesDirty || flushingMessages) {
    return;
  }
  flushingMessages = true;
  const snapshot = JSON.stringify(messagesCache, null, 2);
  try {
    await fsp.writeFile(MESSAGES_FILE, snapshot);
    messagesDirty = false;
  } catch (err) {
    console.error(`Erro ao persistir mensagens:`, err.message);
  } finally {
    flushingMessages = false;
  }
}

async function flushPublicationsIfNeeded() {
  if (!publicationsDirty || flushingPublications) {
    return;
  }
  flushingPublications = true;
  const snapshot = JSON.stringify(publicationsCache, null, 2);
  try {
    await fsp.writeFile(PUBLICATIONS_FILE, snapshot);
    publicationsDirty = false;
  } catch (err) {
    console.error(`Erro ao persistir publicações:`, err.message);
  } finally {
    flushingPublications = false;
  }
}

setInterval(() => {
  flushDataIfNeeded();
  flushMessagesIfNeeded();
  flushPublicationsIfNeeded();
}, FLUSH_INTERVAL);

// Função para obter rank do servidor de referência
async function getRank() {
  try {
    incrementLogicalClock();
    const request = {
      service: "rank",
      data: {
        user: serverId,
        timestamp: Date.now(),
        clock: logicalClock
      }
    };
    await refSocketRank.send(encode(request));
    const reply = decode(await refSocketRank.receive());
    updateLogicalClock(reply.data?.clock || 0);
    serverRank = reply.data?.rank || -1;
    console.log(`Servidor '${serverName}' (${serverId}) obteve rank ${serverRank}`);
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
        user: serverId,
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
    serverList = serverList.filter(s => s.name !== serverId);
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
  if (!coordinator) {
    return;
  }

  if (coordinator === serverId) {
    await performCoordinatorClockSync();
    return;
  }

  const coordinatorHost = coordinatorContainer || coordinator;
  if (!coordinatorHost) {
    return;
  }

  try {
    const coordSocket = new zmq.Request();
    await coordSocket.connect(`tcp://${coordinatorHost}:5560`);

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

    console.log(`Relógio sincronizado com coordenador ${coordinatorDisplayName || coordinator}: offset = ${physicalClockOffset}ms`);

    coordSocket.close();
  } catch (err) {
    console.error(`Erro ao sincronizar com coordenador ${coordinator}:`, err);
    startElection();
  }
}

async function performCoordinatorClockSync() {
  if (clockSyncInProgress) {
    return;
  }

  clockSyncInProgress = true;
  try {
    const participants = [];
    const baseTime = Date.now() + physicalClockOffset;
    participants.push({ id: serverId, delta: 0 });

    const list = await getServerList();
    for (const entry of list) {
      const targetId = entry.name;
      if (targetId === serverId) {
        continue;
      }

      const sampleSocket = new zmq.Request();
      try {
        await sampleSocket.connect(`tcp://${targetId}:5560`);

        incrementLogicalClock();
        const sendTime = Date.now();
        const sampleRequest = {
          service: "clock",
          data: {
            timestamp: sendTime,
            clock: logicalClock
          }
        };

        await sampleSocket.send(encode(sampleRequest));
        const reply = decode(await sampleSocket.receive());
        updateLogicalClock(reply.data?.clock || 0);

        const receiveTime = Date.now();
        const remoteTime = reply.data?.time ?? sendTime;
        const rtt = receiveTime - sendTime;
        const estimatedRemote = remoteTime + rtt / 2;
        const delta = estimatedRemote - baseTime;
        participants.push({ id: targetId, delta });
      } catch (err) {
        console.warn(`Falha ao obter amostra de relógio de ${targetId}:`, err.message);
      } finally {
        sampleSocket.close();
      }
    }

    if (participants.length <= 1) {
      return;
    }

    const avgDelta =
      participants.reduce((acc, participant) => acc + participant.delta, 0) /
      participants.length;

    // Ajusta o relógio local (coordenador)
    physicalClockOffset += avgDelta;

    // Envia ajustes para os demais servidores
    await Promise.all(
      participants
        .filter(participant => participant.id !== serverId)
        .map(async participant => {
          const adjustment = avgDelta - participant.delta;
          await sendClockAdjustment(participant.id, adjustment);
        })
    );
  } catch (err) {
    console.error("Erro na sincronização Berkeley (coordenador):", err);
  } finally {
    clockSyncInProgress = false;
  }
}

async function sendClockAdjustment(targetId, adjustment) {
  const adjustSocket = new zmq.Request();
  try {
    await adjustSocket.connect(`tcp://${targetId}:5560`);

    incrementLogicalClock();
    const request = {
      service: "clockAdjust",
      data: {
        adjustment,
        timestamp: Date.now(),
        clock: logicalClock
      }
    };

    await adjustSocket.send(encode(request));
    const reply = decode(await adjustSocket.receive());
    updateLogicalClock(reply.data?.clock || 0);
  } catch (err) {
    console.warn(`Falha ao enviar ajuste de relógio para ${targetId}:`, err.message);
  } finally {
    adjustSocket.close();
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
    coordinator = serverId;
    coordinatorContainer = serverId;
    coordinatorDisplayName = serverName;
    console.log(`Servidor '${serverName}' (${serverId}) eleito como coordenador`);
    
    // Publica no tópico "servers"
    incrementLogicalClock();
    const electionData = {
      service: "election",
      data: {
        coordinator: serverId,
        coordinatorContainer: serverId,
        coordinatorDisplayName: serverName,
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
    
    for (const target of higherRankServers) {
      const targetId = target.name;
      if (!targetId) {
        continue;
      }

      try {
        const electionSocket = new zmq.Request();
        await electionSocket.connect(`tcp://${targetId}:5560`);
        
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
          electionSocket.close();
          break;
        }
        
        electionSocket.close();
      } catch (err) {
        console.log(`Servidor ${targetId} não respondeu à eleição: ${err.message}`);
      }
    }
    
    if (!electionSuccess) {
      // Nenhum servidor respondeu, este servidor é o coordenador
      coordinator = serverId;
      coordinatorContainer = serverId;
      coordinatorDisplayName = serverName;
      console.log(`Servidor '${serverName}' (${serverId}) eleito como coordenador`);
      
      incrementLogicalClock();
      const electionData = {
        service: "election",
        data: {
          coordinator: serverId,
          coordinatorContainer: serverId,
          coordinatorDisplayName: serverName,
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

// Inicialização (não bloqueante - executa em background imediatamente)
(async () => {
  try {
    await getRank();
    await getServerList();
    await startElection();
    console.log("Inicialização do servidor concluída");
  } catch (err) {
    console.error("Erro na inicialização:", err);
  }
})();

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
        coordinatorDisplayName =
          data.data.coordinatorDisplayName || data.data.coordinator || null;
        console.log(
          `Novo coordenador eleito: ${
            coordinatorDisplayName || coordinator
          } (${coordinatorContainer})`
        );
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
      serverId: serverId,
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
      if (data.data?.serverId === serverId) {
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
      } else if (request.service === "clockAdjust") {
        const adjustment = request.data?.adjustment || 0;
        physicalClockOffset += adjustment;
        incrementLogicalClock();
        const reply = {
          service: "clockAdjust",
          data: {
            status: "OK",
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

for await (const [msg] of socket) {
  console.log(`Mensagem recebida | tamanho=${msg.length} bytes`);
  let request;
  try {
    request = decode(msg);
  } catch (err) {
    console.error(`Erro ao decodificar mensagem:`, err.message);
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
      console.log(`Resposta enviada | tamanho=${JSON.stringify(reply).length} bytes`);
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
