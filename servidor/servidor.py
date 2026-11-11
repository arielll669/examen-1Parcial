"""
Servidor del chat (TCP + hilos). Corre dentro de Docker.

Usa tres tipos de hilos para que nadie espere turno:
  - Principal: acepta conexiones nuevas.
  - Uno por cliente: lee sus mensajes y los reparte a todos.
  - Consola: lee lo que escribe el SERVIDOR (docker attach) y lo envía a todos.

Cada mensaje es una línea de texto UTF-8 terminada en "\n".
Lo primero que manda un cliente es "IDENTIDAD 1" o "IDENTIDAD 2".
"""

import os
import re
import signal
import socket
import threading
from datetime import datetime

HOST = "0.0.0.0"                                 # escucha en todo el contenedor
PORT = int(os.environ.get("CHAT_PORT", "5000"))
PARTICIPANTES = (1, 2)                           # solo existen CLIENTE 1 y CLIENTE 2
MAX_LARGO_MENSAJE = 1000
SEGUNDOS_PARA_IDENTIFICARSE = 10

# Clientes conectados {numero: socket}. Lo tocan varios hilos, así que
# siempre se usa con el candado para evitar condiciones de carrera.
clientes: dict[int, socket.socket] = {}
candado = threading.Lock()

# Evita que dos hilos mezclen sus líneas al imprimir.
candado_impresion = threading.Lock()


def mostrar(texto: str) -> None:
    """Imprime en la consola del servidor, con la hora."""
    with candado_impresion:
        print(f"{datetime.now():%H:%M:%S} {texto}", flush=True)


def registrar(numero: int, conexion: socket.socket) -> bool:
    """Marca al cliente como conectado. False si ya estaba conectado."""
    with candado:
        if numero in clientes:
            return False
        clientes[numero] = conexion
        return True


def enviar(conexion: socket.socket, linea: str) -> bool:
    """Envía una línea a un cliente. False si falla."""
    try:
        conexion.sendall((linea + "\n").encode("utf-8"))
        return True
    except OSError:
        return False


def difundir(linea: str) -> None:
    """Envía la línea a todos (incluido quien la escribió) y la muestra en el servidor."""
    mostrar(linea)
    with candado:
        for numero, conexion in list(clientes.items()):
            if not enviar(conexion, linea):
                clientes.pop(numero, None)  # estaba caído


def leer_identidad(conexion: socket.socket, lector) -> int | None:
    """Lee la primera línea ("IDENTIDAD n"). Devuelve n, o None si es inválida."""
    conexion.settimeout(SEGUNDOS_PARA_IDENTIFICARSE)
    try:
        primera_linea = lector.readline().strip()
    except OSError:
        return None
    conexion.settimeout(None)

    coincidencia = re.fullmatch(r"IDENTIDAD (\d+)", primera_linea)
    if coincidencia and int(coincidencia.group(1)) in PARTICIPANTES:
        return int(coincidencia.group(1))
    return None


def atender_cliente(conexion: socket.socket, direccion: tuple) -> None:
    """Hilo de un cliente: lo identifica y reparte sus mensajes hasta que se va."""
    numero = None

    try:
        with conexion.makefile("r", encoding="utf-8", errors="replace") as lector:
            # 1) ¿Quién es?
            identidad = leer_identidad(conexion, lector)
            if identidad is None:
                enviar(conexion, "[SERVIDOR]: Identificacion invalida. Usa cliente1.py o cliente2.py.")
                mostrar(f"[SERVIDOR]: Conexion de {direccion[0]}:{direccion[1]} rechazada (identificacion invalida)")
                return
            if not registrar(identidad, conexion):
                enviar(conexion, f"[SERVIDOR]: El CLIENTE {identidad} ya esta conectado.")
                mostrar(f"[SERVIDOR]: Conexion rechazada: el CLIENTE {identidad} ya esta conectado")
                return

            numero = identidad
            etiqueta = f"CLIENTE {numero}"
            mostrar(f"[SERVIDOR]: {etiqueta} conectado desde {direccion[0]}:{direccion[1]}")
            enviar(conexion, f"[SERVIDOR]: Bienvenido, tu eres el {etiqueta}")
            difundir(f"[SERVIDOR]: {etiqueta} se ha unido al chat")

            # 2) Repartir sus mensajes (esperar aquí no bloquea a los demás hilos)
            for linea in lector:
                texto = linea.strip()
                if texto:
                    difundir(f"[{etiqueta}]: {texto[:MAX_LARGO_MENSAJE]}")
    except (OSError, ConnectionError):
        pass  # se cayó la conexión: se trata como una desconexión normal
    finally:
        # 3) Limpieza y aviso a los demás
        if numero is not None:
            with candado:
                if clientes.get(numero) is conexion:
                    del clientes[numero]
        try:
            conexion.close()
        except OSError:
            pass
        if numero is not None:
            difundir(f"[SERVIDOR]: CLIENTE {numero} se ha desconectado")


def consola_servidor() -> None:
    """Hilo de consola: lo que escribe el SERVIDOR llega a todos los clientes."""
    while True:
        try:
            texto = input()
        except EOFError:
            mostrar("[SERVIDOR]: consola sin entrada de teclado; el servidor sigue funcionando")
            return
        texto = texto.strip()
        if texto:
            difundir(f"[SERVIDOR]: {texto[:MAX_LARGO_MENSAJE]}")
        else:
            # Enter en blanco: solo confirma la conexión (docker attach no repite lo anterior)
            with candado:
                en_linea = ", ".join(f"CLIENTE {n}" for n in sorted(clientes)) or "ninguno"
            mostrar(f"[SERVIDOR]: Consola conectada. En linea: {en_linea}")


def ignorar_ctrl_c(numero_senal, marco) -> None:
    """Evita apagar el servidor sin querer con Ctrl+C dentro de docker attach."""
    mostrar("[SERVIDOR]: Ctrl+C ignorado. Para salir de la consola sin apagar el servidor "
            "pulsa Ctrl+P y luego Ctrl+Q. Para apagarlo: docker compose down")


def apagar(numero_senal, marco) -> None:
    """docker compose down envía SIGTERM; sin este manejador Docker espera 10 s."""
    raise KeyboardInterrupt


def main() -> None:
    signal.signal(signal.SIGINT, ignorar_ctrl_c)
    signal.signal(signal.SIGTERM, apagar)

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # reiniciar sin esperar el puerto
    servidor.bind((HOST, PORT))
    servidor.listen()

    mostrar("=" * 60)
    mostrar(f"[SERVIDOR]: Chat TCP iniciado en el puerto {PORT}")
    mostrar("[SERVIDOR]: Esperando al CLIENTE 1 y al CLIENTE 2...")
    mostrar("[SERVIDOR]: Escribe aqui para hablar como SERVIDOR.")
    mostrar("=" * 60)

    threading.Thread(target=consola_servidor, name="consola", daemon=True).start()

    try:
        while True:
            conexion, direccion = servidor.accept()  # espera a un cliente
            conexion.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            threading.Thread(
                target=atender_cliente,
                args=(conexion, direccion),
                name=f"cliente-{direccion[1]}",
                daemon=True,
            ).start()
    except KeyboardInterrupt:
        mostrar("[SERVIDOR]: Apagando servidor...")
    finally:
        servidor.close()


if __name__ == "__main__":
    main()
