"""
CLIENTE DE CHAT EN TIEMPO REAL (TCP + hilos)

El MISMO programa sirve para el Cliente 1 y el Cliente 2: es el servidor quien
asigna el numero segun el orden de conexion (el primero en entrar es CLIENTE 1,
el segundo es CLIENTE 2). Se ejecuta en una terminal de Visual Studio Code:

    python cliente/cliente.py

Para escribir y recibir SIN TURNOS usa dos hilos:

  * Hilo principal  -> espera lo que escribes con input() y lo envia al servidor.
  * Hilo receptor   -> escucha al servidor y muestra los mensajes en cuanto llegan.

Si ambas tareas estuvieran en un solo hilo, mientras input() espera tu teclado no
podrias ver los mensajes de los demas (tendrias que esperar tu turno). Con dos
hilos cada tarea avanza por su cuenta.

Protocolo: cada mensaje es una linea UTF-8 terminada en "\n".
"""

import os
import socket
import sys
import threading

# ----------------------------------------------------------------------------
# Configuracion (se puede cambiar con variables de entorno)
# ----------------------------------------------------------------------------
# Se usa 127.0.0.1 (y no "localhost") para evitar problemas de IPv6 en Windows.
HOST = os.environ.get("CHAT_HOST", "127.0.0.1")
PORT = int(os.environ.get("CHAT_PORT", "5000"))

# Secuencias ANSI para borrar la linea que acabas de escribir (la reemplazamos
# por el mensaje que devuelve el servidor, ya con tu etiqueta [CLIENTE N]).
SUBIR_Y_BORRAR_LINEA = "\033[A\033[2K\r"
# Si tu terminal muestra caracteres raros, desactiva esto con CHAT_SIN_ANSI=1
USAR_ANSI = sys.stdout.isatty() and not os.environ.get("CHAT_SIN_ANSI")
if USAR_ANSI and os.name == "nt":
    os.system("")  # truco: activa el soporte de secuencias ANSI en la consola de Windows


def recibir(conexion: socket.socket) -> None:
    """
    HILO RECEPTOR: imprime todo lo que llega del servidor, en cuanto llega.
    Si el servidor se cierra o se pierde la conexion, termina el programa.
    """
    try:
        with conexion.makefile("r", encoding="utf-8", errors="replace") as lector:
            for linea in lector:  # se bloquea esperando mensajes del servidor
                print(linea.rstrip("\n"), flush=True)
    except (OSError, ConnectionError):
        pass
    print("\n[CLIENTE]: Conexion con el servidor cerrada. Hasta luego.", flush=True)
    # El hilo principal esta bloqueado en input(), asi que salimos de golpe.
    os._exit(0)


def main() -> None:
    conexion = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        conexion.connect((HOST, PORT))
    except OSError as error:
        print(f"[CLIENTE]: No se pudo conectar a {HOST}:{PORT} ({error}).")
        print("          Verifica que el servidor este en ejecucion: docker compose up -d --build")
        sys.exit(1)

    print(f"[CLIENTE]: Conectado a {HOST}:{PORT}. Escribe y pulsa Enter. Para salir: /salir o Ctrl+C\n")

    # Arrancamos el hilo receptor. daemon=True: no impide que el programa termine.
    threading.Thread(target=recibir, args=(conexion,), name="receptor", daemon=True).start()

    # Bucle de ENVIO en el hilo principal.
    try:
        while True:
            texto = input().strip()
            if USAR_ANSI:
                # Borra tu linea escrita: el servidor te la devuelve con la etiqueta
                # [CLIENTE N], asi todos los terminales muestran lo mismo y en orden.
                print(SUBIR_Y_BORRAR_LINEA, end="", flush=True)
            if texto == "/salir":
                break
            if texto:
                conexion.sendall((texto + "\n").encode("utf-8"))
    except (EOFError, KeyboardInterrupt):
        pass  # Ctrl+C / Ctrl+D: salida normal
    except OSError:
        print("[CLIENTE]: Se perdio la conexion con el servidor.")
    finally:
        # shutdown() avisa de inmediato al servidor de que nos fuimos, aunque el
        # hilo receptor siga teniendo el socket abierto.
        try:
            conexion.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conexion.close()
        print("[CLIENTE]: Desconectado.")


if __name__ == "__main__":
    main()
