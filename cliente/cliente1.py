"""
CLIENTE 1 del chat. Se ejecuta en una terminal de VS Code:

    python cliente/cliente1.py

Usa dos hilos para escribir y recibir sin turnos:
  - Principal: lee lo que escribes y lo envía al servidor.
  - Receptor: muestra los mensajes en cuanto llegan.
"""

import os
import socket
import sys
import threading

NUMERO_CLIENTE = 1  # único cambio respecto a cliente2.py

# 127.0.0.1 en vez de "localhost" para evitar problemas de IPv6 en Windows
HOST = os.environ.get("CHAT_HOST", "127.0.0.1")
PORT = int(os.environ.get("CHAT_PORT", "5000"))

# Borra la línea que acabas de escribir: el servidor te la devuelve con tu etiqueta.
# Si se ven caracteres raros, desactívalo con CHAT_SIN_ANSI=1
SUBIR_Y_BORRAR_LINEA = "\033[A\033[2K\r"
USAR_ANSI = sys.stdout.isatty() and not os.environ.get("CHAT_SIN_ANSI")
if USAR_ANSI and os.name == "nt":
    os.system("")  # activa los códigos ANSI en la consola de Windows


def recibir(conexion: socket.socket) -> None:
    """Hilo receptor: imprime lo que llega del servidor. Si se cierra, salimos."""
    try:
        with conexion.makefile("r", encoding="utf-8", errors="replace") as lector:
            for linea in lector:
                print(linea.rstrip("\n"), flush=True)
    except (OSError, ConnectionError):
        pass
    print(f"\n[CLIENTE {NUMERO_CLIENTE}]: Conexion con el servidor cerrada. Hasta luego.", flush=True)
    os._exit(0)  # el hilo principal está esperando input(), así que salimos directo


def main() -> None:
    conexion = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        conexion.connect((HOST, PORT))
    except OSError as error:
        print(f"[CLIENTE {NUMERO_CLIENTE}]: No se pudo conectar a {HOST}:{PORT} ({error}).")
        print("          Verifica que el servidor este en ejecucion: docker compose up -d --build")
        sys.exit(1)

    # Lo primero: decirle al servidor quién somos
    conexion.sendall(f"IDENTIDAD {NUMERO_CLIENTE}\n".encode("utf-8"))

    print(f"[CLIENTE {NUMERO_CLIENTE}]: Conectado a {HOST}:{PORT}. "
          "Escribe y pulsa Enter. Para salir: /salir o Ctrl+C\n")

    threading.Thread(target=recibir, args=(conexion,), name="receptor", daemon=True).start()

    # Bucle de envío (hilo principal)
    try:
        while True:
            texto = input().strip()
            if USAR_ANSI:
                print(SUBIR_Y_BORRAR_LINEA, end="", flush=True)
            if texto == "/salir":
                break
            if texto:
                conexion.sendall((texto + "\n").encode("utf-8"))
    except (EOFError, KeyboardInterrupt):
        pass  # Ctrl+C o Ctrl+D: salida normal
    except OSError:
        print(f"[CLIENTE {NUMERO_CLIENTE}]: Se perdio la conexion con el servidor.")
    finally:
        try:
            conexion.shutdown(socket.SHUT_RDWR)  # avisa al servidor de inmediato
        except OSError:
            pass
        conexion.close()
        print(f"[CLIENTE {NUMERO_CLIENTE}]: Desconectado.")


if __name__ == "__main__":
    main()
