#include <zmq.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <msgpack.h>
#include <math.h>
#include <pthread.h>
#include <errno.h>

#define CLIENT_TAG "[cliente-bot]"
#define MAX_ATTEMPTS 3
#define BUFFER_SIZE 4096

typedef struct {
    int clock;
} RelogioLogico;

void relogio_init(RelogioLogico *r) {
    r->clock = 0;
}

int relogio_tick(RelogioLogico *r) {
    r->clock++;
    return r->clock;
}

void relogio_update(RelogioLogico *r, int clock_recebido) {
    r->clock = (clock_recebido > r->clock) ? clock_recebido : r->clock;
    r->clock++;
}

// Função para criar e empacotar uma mensagem MessagePack
size_t pack_request(msgpack_sbuffer *sbuf, const char *service, const char *opcao, 
                    const char *user, const char *channel, const char *message,
                    const char *src, const char *dst, double timestamp, int clock) {
    msgpack_sbuffer_init(sbuf);
    msgpack_packer pk;
    msgpack_packer_init(&pk, sbuf, msgpack_sbuffer_write);
    
    msgpack_pack_map(&pk, 2);
    
    // service ou opcao
    if (service) {
        msgpack_pack_str(&pk, 7);
        msgpack_pack_str_body(&pk, "service", 7);
        msgpack_pack_str(&pk, strlen(service));
        msgpack_pack_str_body(&pk, service, strlen(service));
    } else if (opcao) {
        msgpack_pack_str(&pk, 5);
        msgpack_pack_str_body(&pk, "opcao", 5);
        msgpack_pack_str(&pk, strlen(opcao));
        msgpack_pack_str_body(&pk, opcao, strlen(opcao));
    }
    
    // data
    msgpack_pack_str(&pk, 4);
    msgpack_pack_str_body(&pk, "data", 4);
    
    int data_items = 0;
    if (user) data_items++;
    if (channel) data_items++;
    if (message) data_items++;
    if (src) data_items++;
    if (dst) data_items++;
    data_items += 2; // timestamp e clock sempre presentes
    
    msgpack_pack_map(&pk, data_items);
    
    if (user) {
        msgpack_pack_str(&pk, 4);
        msgpack_pack_str_body(&pk, "user", 4);
        msgpack_pack_str(&pk, strlen(user));
        msgpack_pack_str_body(&pk, user, strlen(user));
    }
    if (channel) {
        msgpack_pack_str(&pk, 7);
        msgpack_pack_str_body(&pk, "channel", 7);
        msgpack_pack_str(&pk, strlen(channel));
        msgpack_pack_str_body(&pk, channel, strlen(channel));
    }
    if (message) {
        msgpack_pack_str(&pk, 7);
        msgpack_pack_str_body(&pk, "message", 7);
        msgpack_pack_str(&pk, strlen(message));
        msgpack_pack_str_body(&pk, message, strlen(message));
    }
    if (src) {
        msgpack_pack_str(&pk, 3);
        msgpack_pack_str_body(&pk, "src", 3);
        msgpack_pack_str(&pk, strlen(src));
        msgpack_pack_str_body(&pk, src, strlen(src));
    }
    if (dst) {
        msgpack_pack_str(&pk, 3);
        msgpack_pack_str_body(&pk, "dst", 3);
        msgpack_pack_str(&pk, strlen(dst));
        msgpack_pack_str_body(&pk, dst, strlen(dst));
    }
    
    msgpack_pack_str(&pk, 9);
    msgpack_pack_str_body(&pk, "timestamp", 9);
    msgpack_pack_double(&pk, timestamp);
    
    msgpack_pack_str(&pk, 5);
    msgpack_pack_str_body(&pk, "clock", 5);
    msgpack_pack_int(&pk, clock);
    
    return sbuf->size;
}

// Função para desempacotar resposta MessagePack
int unpack_reply(const char *data, size_t size, int *clock, char *status, size_t status_len) {
    msgpack_unpacked msg;
    msgpack_unpacked_init(&msg);
    
    size_t off = 0;
    if (msgpack_unpack_next(&msg, data, size, &off) != MSGPACK_UNPACK_SUCCESS) {
        msgpack_unpacked_destroy(&msg);
        return -1;
    }
    
    msgpack_object root = msg.data;
    if (root.type != MSGPACK_OBJECT_MAP) {
        msgpack_unpacked_destroy(&msg);
        return -1;
    }
    
    // Procura por data.clock e data.status
    for (uint32_t i = 0; i < root.via.map.size; i++) {
        msgpack_object_kv *kv = &root.via.map.ptr[i];
        if (kv->key.type == MSGPACK_OBJECT_STR && 
            strncmp(kv->key.via.str.ptr, "data", kv->key.via.str.size) == 0 &&
            kv->val.type == MSGPACK_OBJECT_MAP) {
            
            for (uint32_t j = 0; j < kv->val.via.map.size; j++) {
                msgpack_object_kv *data_kv = &kv->val.via.map.ptr[j];
                
                if (data_kv->key.type == MSGPACK_OBJECT_STR) {
                    if (strncmp(data_kv->key.via.str.ptr, "clock", data_kv->key.via.str.size) == 0 &&
                        data_kv->val.type == MSGPACK_OBJECT_POSITIVE_INTEGER) {
                        *clock = (int)data_kv->val.via.u64;
                    } else if (strncmp(data_kv->key.via.str.ptr, "status", data_kv->key.via.str.size) == 0 &&
                               data_kv->val.type == MSGPACK_OBJECT_STR) {
                        size_t len = (data_kv->val.via.str.size < status_len - 1) ? 
                                     data_kv->val.via.str.size : status_len - 1;
                        strncpy(status, data_kv->val.via.str.ptr, len);
                        status[len] = '\0';
                    }
                }
            }
        }
    }
    
    msgpack_unpacked_destroy(&msg);
    return 0;
}

// Função para enviar requisição e receber resposta
int send_request(void *socket, msgpack_sbuffer *sbuf, RelogioLogico *relogio, 
                 const char *descricao) {
    for (int attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
        int sent = zmq_send(socket, sbuf->data, sbuf->size, 0);
        if (sent < 0) {
            if (errno == EAGAIN) {
        printf("%s Timeout ao enviar requisição de %s (tentativa %d/%d)\n", 
               CLIENT_TAG, descricao, attempt, MAX_ATTEMPTS);
        fflush(stdout);
                continue;
            } else {
                printf("%s Erro ao enviar requisição de %s: %s\n", 
                       CLIENT_TAG, descricao, zmq_strerror(errno));
                fflush(stdout);
                continue;
            }
        }
        
        char recv_buf[BUFFER_SIZE];
        int recv_size = zmq_recv(socket, recv_buf, sizeof(recv_buf), 0);
        if (recv_size < 0) {
            if (errno == EAGAIN) {
                printf("%s Timeout ao receber resposta de %s (tentativa %d/%d)\n", 
                       CLIENT_TAG, descricao, attempt, MAX_ATTEMPTS);
                fflush(stdout);
                continue;
            } else {
                printf("%s Erro ao receber resposta de %s: %s\n", 
                       CLIENT_TAG, descricao, zmq_strerror(errno));
                fflush(stdout);
                break;
            }
        }
        
        int reply_clock = 0;
        char status[64] = {0};
        if (unpack_reply(recv_buf, recv_size, &reply_clock, status, sizeof(status)) == 0) {
            if (reply_clock > 0) {
                relogio_update(relogio, reply_clock);
            }
            return 0; // Sucesso
        }
        
        // Mesmo que não consiga parsear completamente, se recebeu algo, considera sucesso
        if (recv_size > 0) {
            return 0;
        }
        
        printf("%s Nenhuma resposta válida para %s. Tentando novamente...\n", 
               CLIENT_TAG, descricao);
        fflush(stdout);
    }
    
    printf("%s Falha ao concluir %s após %d tentativas.\n", 
           CLIENT_TAG, descricao, MAX_ATTEMPTS);
    fflush(stdout);
    return -1;
}

// Função para obter canais
int obter_canais(void *socket, RelogioLogico *relogio, char **canais, int *num_canais) {
    msgpack_sbuffer sbuf;
    double timestamp = (double)time(NULL);
    int clock = relogio_tick(relogio);
    
    pack_request(&sbuf, NULL, "channels", NULL, NULL, NULL, NULL, NULL, timestamp, clock);
    
    if (send_request(socket, &sbuf, relogio, "channels") != 0) {
        msgpack_sbuffer_destroy(&sbuf);
        return -1;
    }
    
    // Por simplicidade, retornamos sucesso (parsing completo de canais seria mais complexo)
    msgpack_sbuffer_destroy(&sbuf);
    return 0;
}

// Função para criar canal
int criar_canal(void *socket, RelogioLogico *relogio, const char *canal) {
    msgpack_sbuffer sbuf;
    double timestamp = (double)time(NULL);
    int clock = relogio_tick(relogio);
    
    pack_request(&sbuf, NULL, "channel", NULL, canal, NULL, NULL, NULL, timestamp, clock);
    
    int result = send_request(socket, &sbuf, relogio, "criação de canal");
    msgpack_sbuffer_destroy(&sbuf);
    return result;
}

int main() {
    // Desabilita buffering de stdout para logs aparecerem imediatamente
    setvbuf(stdout, NULL, _IONBF, 0);
    
    void *context = zmq_ctx_new();
    void *req_socket = zmq_socket(context, ZMQ_REQ);
    
    if (zmq_connect(req_socket, "tcp://broker:5555") != 0) {
        printf("%s Erro ao conectar ao broker\n", CLIENT_TAG);
        fflush(stdout);
        return 1;
    }
    
    printf("%s Socket conectado ao broker: tcp://broker:5555\n", CLIENT_TAG);
    fflush(stdout);
    
    // Socket para Pub/Sub
    void *sub_socket = zmq_socket(context, ZMQ_SUB);
    if (zmq_connect(sub_socket, "tcp://proxy:5558") != 0) {
        printf("%s Erro ao conectar ao proxy Pub/Sub\n", CLIENT_TAG);
        fflush(stdout);
        zmq_close(req_socket);
        zmq_ctx_destroy(context);
        return 1;
    }
    
    // Gera nome de usuário aleatório
    srand(time(NULL));
    char username[64];
    snprintf(username, sizeof(username), "user_%d", 1000 + rand() % 9000);
    printf("%s Cliente automático iniciado com usuário: %s\n", CLIENT_TAG, username);
    fflush(stdout);
    
    // Inscreve-se no próprio tópico
    zmq_setsockopt(sub_socket, ZMQ_SUBSCRIBE, username, strlen(username));
    printf("%s Inscrito no tópico: %s\n", CLIENT_TAG, username);
    fflush(stdout);
    
    // Relógio lógico
    RelogioLogico relogio;
    relogio_init(&relogio);
    
    // Atraso inicial para desfasar bots
    const char *spread_env = getenv("BOT_SPREAD_SECONDS");
    double spread_seconds = spread_env ? atof(spread_env) : 2.0;
    if (spread_seconds > 0) {
        double initial_delay = ((double)rand() / RAND_MAX) * spread_seconds;
        printf("%s Atraso inicial para desfasar bots: %.2fs\n", CLIENT_TAG, initial_delay);
        fflush(stdout);
        usleep((unsigned int)(initial_delay * 1000000));
    }
    
    // Faz login
    while (1) {
        msgpack_sbuffer sbuf;
        double timestamp = (double)time(NULL);
        int clock = relogio_tick(&relogio);
        
        pack_request(&sbuf, NULL, "login", username, NULL, NULL, NULL, NULL, timestamp, clock);
        
        if (send_request(req_socket, &sbuf, &relogio, "login") == 0) {
            printf("%s Login realizado\n", CLIENT_TAG);
            fflush(stdout);
            msgpack_sbuffer_destroy(&sbuf);
            break;
        }
        
        printf("%s ERRO: Falha ao fazer login, tentando novamente rapidamente...\n", CLIENT_TAG);
        fflush(stdout);
        msgpack_sbuffer_destroy(&sbuf);
        usleep(100000); // 0.1s
    }
    
    // Lista de mensagens
    const char *mensagens[] = {
        "Olá, esta é uma mensagem de teste!",
        "Sistema funcionando corretamente.",
        "Teste de publicação em canal.",
        "Mensagem automática gerada pelo cliente.",
        "Verificando funcionalidade de Pub/Sub.",
        "Esta é a mensagem número 6.",
        "Teste de persistência de mensagens.",
        "Mensagem enviada automaticamente.",
        "Verificando comunicação entre clientes.",
        "Última mensagem do conjunto de testes.",
    };
    int num_mensagens = sizeof(mensagens) / sizeof(mensagens[0]);
    
    printf("%s Iniciando loop principal...\n", CLIENT_TAG);
    fflush(stdout);
    
    // Loop principal
    while (1) {
        // Obtém ou cria canais (simplificado - sempre tenta criar "geral" se necessário)
        char *canais[] = {"geral"};
        int num_canais = 1;
        
        // Tenta obter canais (se falhar, usa "geral" como padrão)
        obter_canais(req_socket, &relogio, canais, &num_canais);
        
        const char *canal_escolhido = canais[0];
        printf("%s Enviando mensagens para o canal '%s'\n", CLIENT_TAG, canal_escolhido);
        fflush(stdout);
        
        // Envia mensagens
        for (int i = 0; i < num_mensagens; i++) {
            const char *mensagem = mensagens[i];
            double timestamp = (double)time(NULL);
            int clock = relogio_tick(&relogio);
            
            msgpack_sbuffer sbuf;
            pack_request(&sbuf, "publish", NULL, username, canal_escolhido, mensagem, 
                        NULL, NULL, timestamp, clock);
            
            printf("%s Enviando mensagem: %.30s...\n", CLIENT_TAG, mensagem);
            printf("%s Mensagem enviada: service=publish, user=%s, channel=%s, message=%s, timestamp=%.3f, clock=%d\n", 
                   CLIENT_TAG, username, canal_escolhido, mensagem, timestamp, clock);
            fflush(stdout);
            
            if (send_request(req_socket, &sbuf, &relogio, "publicação") == 0) {
                printf("%s ✓ Mensagem publicada com sucesso: %.50s...\n", CLIENT_TAG, mensagem);
                fflush(stdout);
            } else {
                printf("%s ✗ Erro ao publicar\n", CLIENT_TAG);
                fflush(stdout);
            }
            
            msgpack_sbuffer_destroy(&sbuf);
        }
        
        printf("%s Fim do lote atual.\n", CLIENT_TAG);
        fflush(stdout);
        
        // Atraso entre lotes
        if (spread_seconds > 0) {
            double drift_delay = ((double)rand() / RAND_MAX) * spread_seconds;
            printf("%s Aguardando %.2fs antes do próximo lote\n", CLIENT_TAG, drift_delay);
            fflush(stdout);
            usleep((unsigned int)(drift_delay * 1000000));
        }
        
        // Verifica mensagens Pub/Sub (não bloqueante)
        char topic_buf[256];
        char msg_buf[BUFFER_SIZE];
        zmq_setsockopt(sub_socket, ZMQ_RCVTIMEO, &(int){100}, sizeof(int));
        
        int topic_size = zmq_recv(sub_socket, topic_buf, sizeof(topic_buf) - 1, ZMQ_DONTWAIT);
        if (topic_size > 0) {
            topic_buf[topic_size] = '\0';
            int msg_size = zmq_recv(sub_socket, msg_buf, sizeof(msg_buf), ZMQ_DONTWAIT);
            if (msg_size > 0) {
                int reply_clock = 0;
                char status[64] = {0};
                if (unpack_reply(msg_buf, msg_size, &reply_clock, status, sizeof(status)) == 0) {
                    if (reply_clock > 0) {
                        relogio_update(&relogio, reply_clock);
                    }
                }
                printf("%s Mensagem recebida no tópico '%s' (tamanho: %d bytes, clock: %d)\n", 
                       CLIENT_TAG, topic_buf, msg_size, reply_clock);
                fflush(stdout);
            }
        }
    }
    
    zmq_close(req_socket);
    zmq_close(sub_socket);
    zmq_ctx_destroy(context);
    
    return 0;
}

