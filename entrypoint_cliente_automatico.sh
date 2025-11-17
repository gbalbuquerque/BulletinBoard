#!/bin/sh
set -e

# Recompila se o arquivo fonte mudou ou se o binário não existe
if [ ! -f /app/cliente_automatico ] || [ /app/cliente_automatico.c -nt /app/cliente_automatico ]; then
    echo "[cliente-bot] Compilando cliente_automatico.c..."
    gcc -o /app/cliente_automatico /app/cliente_automatico.c -lzmq -lmsgpackc -lm -lpthread
    echo "[cliente-bot] Compilação concluída."
fi

# Executa o programa
exec /app/cliente_automatico

