## 📄 

# 💬 **Sistema de Troca de Mensagens Bulletin Board**

## Visão Geral do Projeto

Este projeto consiste no desenvolvimento de uma versão simplificada de um sistema de troca de mensagens instantâneas.

O objetivo principal é aplicar conceitos de **Sistemas Distribuídos** para construir um serviço que permita a comunicação em tempo real e a persistência de dados.

## 🎯 Funcionalidades Principais

O sistema implementa as seguintes interações básicas entre usuários e o serviço:

* **Mensagens Privadas (P2P):** Troca de mensagens diretas entre dois usuários.
* **Canais Públicos:** Postagem e visualização de mensagens em canais de discussão abertos.
* **Persistência de Dados:** Todas as interações (mensagens privadas e postagens em canais) são armazenadas em disco, permitindo que os usuários recuperem o histórico de mensagens anteriores.

---

## 🛠️ Tecnologias e Arquitetura

Este projeto seguiu um conjunto de padronizações para garantir a interoperabilidade e a testabilidade, e integrou escolhas livres de tecnologia para demonstrar proficiência em múltiplas linguagens e armazenamento de dados.

### 🌐 Padronizações (Requisitos do Enunciado)

| Componente | Detalhe |
| :--- | :--- |
| **Comunicação** | Uso da biblioteca **ZeroMQ (ØMQ)** para a troca de mensagens entre os atores do sistema (clientes e servidor). |
| **Formato de Mensagem** | As mensagens seguem um **padrão definido** (descrito na documentação técnica) para garantir a interconexão. |
| **Ambiente de Teste** | Utilização de **Containers** (`Docker`) para encapsular e executar as instâncias de cada ator (cliente e servidor), facilitando os testes de ambiente distribuído. |

### Como Executar

**(Aqui você descreveria, de forma resumida, os passos para clonar, construir as imagens Docker e iniciar o servidor e clientes.)**

1.  Clone o repositório: `git clone https://github.com/gbalbuquerque/BulletinBoard.git`
2.  Navegue até o diretório do projeto
3.  Construa as imagens dos containers (se aplicável): `docker compose build`
4.  Inicie o sistema: `docker compose up`

