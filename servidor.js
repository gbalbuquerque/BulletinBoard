import zmq from "zeromq";
import fs from "fs";

const socket = new zmq.Reply();
await socket.connect("tcp://broker:5556");
let erro = "";

let tarefas = {};
let cont = 0;

// ===============================
// Persistência em disco
// ===============================
const DATA_FILE = "data.json";

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

let db = loadData();

console.log("Servidor JS conectado ao broker: tcp://broker:5556");

for await (const [msg] of socket) { 
  let request;
  try {
    request = JSON.parse(msg.toString());
  } catch (err) {
    console.error("Erro ao parsear JSON:", err);
    await socket.send("ERRO: JSON inválido");
    erro = "ERRO: JSON inválido";
    continue;
  }

  const opcao = request.opcao;
  console.log('request', request)
  const data = request.data;
  let reply = "ERRO: função não escolhida";

  console.log("Tarefas atuais:", tarefas);

  switch (opcao) {
    // =================================
    // LOGIN
    // =================================
    case "login":
      console.log(`Mensagem recebida ${JSON.stringify(request)}`)
      if (!erro) {
        tarefas[cont] = data;
        cont++;

        // Salva em disco
        const { user, timestamp } = data;
        if (user) {
          const exists = db.users.find(u => u.user === user);
          if (!exists) {
            db.users.push({ user, timestamp });
            saveData(db);
          }
        }

        reply = {
          service: "login",
          data: {
            status: "sucesso",
            timestamp: Date.now(),
          },
        };
        console.log("Tarefas pós login:", tarefas); 
        break;
      } else {
        reply = {
          service: "login",
          data: {
            status: "erro",
            timestamp: Date.now(),
            description: erro,
          },
        };
        break;
      }

    // =================================
    // LISTAR USUÁRIOS
    // =================================
    case "users":
      reply = {
        service: "users",
        data: {
          timestamp: Date.now(),
          users: db.users.map(u => u.user)
        }
      };
      break;

    // =================================
    // CRIAR CANAL
    // =================================
    case "channel": {
      const { channel, timestamp } = data;
      if (!channel) {
        reply = {
          service: "channel",
          data: {
            status: "erro",
            description: "Nome do canal não informado",
            timestamp: Date.now()
          }
        };
        break;
      }

      const exists = db.channels.find(c => c.channel === channel);
      if (!exists) {
        db.channels.push({ channel, timestamp });
        saveData(db);
      }

      reply = {
        service: "channel",
        data: {
          status: "sucesso",
          timestamp: Date.now()
        }
      };
      break;
    }

    // =================================
    // LISTAR CANAIS
    // =================================
    case "channels":
      reply = {
        service: "channels",
        data: {
          timestamp: Date.now(),
          channels: db.channels.map(c => c.channel)
        }
      };
      break;

    // =================================
    // DEFAULT
    // =================================
    default:
      reply = "ERRO: função não encontrada";
  }

  if (typeof reply === "object") {
    console.log(`Mensagem enviada ${JSON.stringify(reply)}`)
    await socket.send(JSON.stringify(reply));
  } else {
    console.log(`Mensagem enviada ${JSON.stringify(reply)}`)
    await socket.send(reply);
  }
}
