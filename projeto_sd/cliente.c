#include <zmq.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

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
    if (clock_recebido > r->clock) {
        r->clock = clock_recebido;
    }
}

void enviar_simples(void *socket, const char *msg) {
    zmq_send(socket, msg, strlen(msg), 0);
    char buffer[4096];
    zmq_recv(socket, buffer, sizeof(buffer), 0);
}

int main() {
    void *context = zmq_ctx_new();
    void *socket = zmq_socket(context, ZMQ_REQ);
    
    int timeout = 10000;
    zmq_setsockopt(socket, ZMQ_RCVTIMEO, &timeout, sizeof(timeout));
    zmq_setsockopt(socket, ZMQ_SNDTIMEO, &timeout, sizeof(timeout));
    
    if (zmq_connect(socket, "tcp://broker:5555") != 0) {
        printf("Erro ao conectar\n");
        return 1;
    }
    
    RelogioLogico relogio;
    relogio_init(&relogio);
    
    printf("BulletInBoard\n");
    printf("[1] Login\n");
    printf("[2] Listar usuarios\n");
    printf("[3] Cadastrar canal\n");
    printf("[4] Listar canais\n");
    printf("[5] Publicar em canal\n");
    printf("[6] Mensagem privada\n");
    printf("[0] Sair\n");
    fflush(stdout);
    
    char opcao[10];
    char buffer_input[256];
    char message[1024];
    
    while (1) {
        printf("\nOpcao: ");
        fflush(stdout);
        
        if (fgets(opcao, sizeof(opcao), stdin) == NULL) break;
        opcao[strcspn(opcao, "\n")] = 0;
        
        if (strcmp(opcao, "0") == 0) {
            break;
            
        } else if (strcmp(opcao, "1") == 0) {
            printf("Entre com seu usuario: ");
            fflush(stdout);
            fgets(buffer_input, sizeof(buffer_input), stdin);
            buffer_input[strcspn(buffer_input, "\n")] = 0;
            
            snprintf(message, sizeof(message),
                "{\"service\":\"login\",\"data\":{\"user\":\"%s\",\"timestamp\":%ld,\"clock\":%d}}",
                buffer_input, (long)time(NULL), relogio_tick(&relogio));
            
            printf("[DEBUG] Enviando: %s\n", message);
            int sent = zmq_send(socket, message, strlen(message), 0);
            printf("[DEBUG] Bytes enviados: %d\n", sent);
            
            char recv_buf[4096];
            int size = zmq_recv(socket, recv_buf, sizeof(recv_buf), 0);
            printf("[DEBUG] Bytes recebidos: %d\n", size);
            
            if (size > 0) {
                recv_buf[size] = '\0';
                printf("[DEBUG] Recebido: %s\n", recv_buf);
                
                if (strstr(recv_buf, "erro") != NULL) {
                    printf("Erro\n");
                } else {
                    printf("Login OK\n");
                }
            } else {
                printf("[DEBUG] Erro ao receber (size=%d, errno=%d)\n", size, zmq_errno());
            }
            fflush(stdout);
            
        } else if (strcmp(opcao, "2") == 0) {
            snprintf(message, sizeof(message),
                "{\"service\":\"users\",\"data\":{\"timestamp\":%ld,\"clock\":%d}}",
                (long)time(NULL), relogio_tick(&relogio));
            
            printf("[DEBUG] Enviando: %s\n", message);
            zmq_send(socket, message, strlen(message), 0);
            
            char recv_buf[4096];
            int size = zmq_recv(socket, recv_buf, sizeof(recv_buf), 0);
            
            if (size > 0) {
                recv_buf[size] = '\0';
                printf("[DEBUG] Recebido: %s\n", recv_buf);
                
                // Parse simples da resposta JSON
                char *users_start = strstr(recv_buf, "\"users\":[");
                if (users_start) {
                    printf("Usuarios encontrados na resposta\n");
                } else {
                    printf("Lista de usuarios vazia ou erro\n");
                }
            } else {
                printf("[DEBUG] Nenhuma resposta recebida (size=%d)\n", size);
            }
            fflush(stdout);
            
        } else if (strcmp(opcao, "3") == 0) {
            printf("Entre com o canal: ");
            fflush(stdout);
            fgets(buffer_input, sizeof(buffer_input), stdin);
            buffer_input[strcspn(buffer_input, "\n")] = 0;
            
            snprintf(message, sizeof(message),
                "{\"service\":\"channel\",\"data\":{\"channel\":\"%s\",\"timestamp\":%ld,\"clock\":%d}}",
                buffer_input, (long)time(NULL), relogio_tick(&relogio));
            
            zmq_send(socket, message, strlen(message), 0);
            char recv_buf[4096];
            int size = zmq_recv(socket, recv_buf, sizeof(recv_buf), 0);
            
            if (size > 0) {
                recv_buf[size] = '\0';
                if (strstr(recv_buf, "erro") != NULL) {
                    printf("Erro\n");
                } else {
                    printf("Canal cadastrado\n");
                }
            }
            fflush(stdout);
            
        } else if (strcmp(opcao, "4") == 0) {
            snprintf(message, sizeof(message),
                "{\"service\":\"channels\",\"data\":{\"timestamp\":%ld,\"clock\":%d}}",
                (long)time(NULL), relogio_tick(&relogio));
            
            zmq_send(socket, message, strlen(message), 0);
            char recv_buf[4096];
            int size = zmq_recv(socket, recv_buf, sizeof(recv_buf), 0);
            
            if (size > 0) {
                recv_buf[size] = '\0';
                printf("Resposta recebida\n");
            }
            fflush(stdout);
            
        } else if (strcmp(opcao, "5") == 0) {
            char usuario[256], canal[256], msg_texto[256];
            
            printf("Entre com seu usuario: ");
            fflush(stdout);
            fgets(usuario, sizeof(usuario), stdin);
            usuario[strcspn(usuario, "\n")] = 0;
            
            printf("Entre com o canal: ");
            fflush(stdout);
            fgets(canal, sizeof(canal), stdin);
            canal[strcspn(canal, "\n")] = 0;
            
            printf("Entre com a mensagem: ");
            fflush(stdout);
            fgets(msg_texto, sizeof(msg_texto), stdin);
            msg_texto[strcspn(msg_texto, "\n")] = 0;
            
            snprintf(message, sizeof(message),
                "{\"service\":\"publish\",\"data\":{\"user\":\"%s\",\"channel\":\"%s\",\"message\":\"%s\",\"timestamp\":%ld,\"clock\":%d}}",
                usuario, canal, msg_texto, (long)time(NULL), relogio_tick(&relogio));
            
            zmq_send(socket, message, strlen(message), 0);
            char recv_buf[4096];
            int size = zmq_recv(socket, recv_buf, sizeof(recv_buf), 0);
            
            if (size > 0) {
                recv_buf[size] = '\0';
                if (strstr(recv_buf, "erro") != NULL) {
                    printf("Erro\n");
                } else {
                    printf("Publicado\n");
                }
            }
            fflush(stdout);
            
        } else if (strcmp(opcao, "6") == 0) {
            char src[256], dst[256], msg_texto[256];
            
            printf("Entre com seu usuario (de): ");
            fflush(stdout);
            fgets(src, sizeof(src), stdin);
            src[strcspn(src, "\n")] = 0;
            
            printf("Entre com o destinatario (para): ");
            fflush(stdout);
            fgets(dst, sizeof(dst), stdin);
            dst[strcspn(dst, "\n")] = 0;
            
            printf("Entre com a mensagem: ");
            fflush(stdout);
            fgets(msg_texto, sizeof(msg_texto), stdin);
            msg_texto[strcspn(msg_texto, "\n")] = 0;
            
            snprintf(message, sizeof(message),
                "{\"service\":\"message\",\"data\":{\"src\":\"%s\",\"dst\":\"%s\",\"message\":\"%s\",\"timestamp\":%ld,\"clock\":%d}}",
                src, dst, msg_texto, (long)time(NULL), relogio_tick(&relogio));
            
            zmq_send(socket, message, strlen(message), 0);
            char recv_buf[4096];
            int size = zmq_recv(socket, recv_buf, sizeof(recv_buf), 0);
            
            if (size > 0) {
                recv_buf[size] = '\0';
                if (strstr(recv_buf, "erro") != NULL) {
                    printf("Erro\n");
                } else {
                    printf("Enviado\n");
                }
            }
            fflush(stdout);
            
        } else {
            printf("Opcao invalida\n");
            fflush(stdout);
        }
    }
    
    zmq_close(socket);
    zmq_ctx_destroy(context);
    
    return 0;
}
