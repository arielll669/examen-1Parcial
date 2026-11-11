"""
SERVIDOR DE CHAT EN TIEMPO REAL (TCP + hilos)

Este programa corre dentro de un contenedor Docker. Hace tres cosas a la vez,
cada una en su propio hilo (threading.Thread):

  1. Hilo principal  -> acepta conexiones nuevas de clientes (bucle accept).
  2. Un hilo POR CLIENTE -> lee los mensajes de ese cliente y los distribuye
                            a todos los participantes.
  3. Hilo de consola -> lee lo que escribe el SERVIDOR por teclado
                        (docker attach) y lo envia a todos los clientes.

Gracias a los hilos nadie espera su turno: cualquiera puede escribir en
cualquier momento y el mensaje llega a los demas al instante.

Participantes y etiquetas:
  [CLIENTE 1]  programa cliente/cliente1.py
  [CLIENTE 2]  programa cliente/cliente2.py
  [SERVIDOR]   este programa

Protocolo (muy simple): cada mensaje es una linea de texto UTF-8 terminada en
salto de linea ("\n"). TCP es un flujo continuo de bytes y no marca donde
termina un mensaje, por eso usamos "\n" como separador.

Al conectarse, cada cliente envia PRIMERO una linea de identificacion:

    IDENTIDAD 1      (lo envia cliente1.py)
    IDENTIDAD 2      (lo envia cliente2.py)

El servidor valida esa identidad y, a partir de ahi, etiqueta todos los
mensajes de esa conexion con [CLIENTE 1] o [CLIENTE 2].
"""

import os
import re
import socket
import threading
from datetime import datetime

# ----------------------------------------------------------------------------
# Configuracion (el puerto se puede cambiar con la variable de entorno CHAT_PORT)
# ----------------------------------------------------------------------------
HOST = "0.0.0.0"                                 # escuchar en todas las interfaces del contenedor
PORT = int(os.environ.get("CHAT_PORT", "5000"))  # puerto TCP del chat
PARTICIPANTES = (1, 2)                           # clientes permitidos: CLIENTE 1 y CLIENTE 2
MAX_LARGO_MENSAJE = 1000                         # evita mensajes gigantes
SEGUNDOS_PARA_IDENTIFICARSE = 10                 # tiempo maximo para enviar "IDENTIDAD n"

# ----------------------------------------------------------------------------
# Estado compartido entre hilos
# ----------------------------------------------------------------------------
# Diccionario {numero_de_cliente: socket}. Lo leen y modifican VARIOS hilos a la
# vez (uno por cliente + consola + accept), asi que TODO acceso se hace dentro
# de `with candado:`. Es el mismo concepto de Lock del ejercicio de condiciones
# de carrera: sin el candado dos hilos podrian modificar el diccionario al mismo
# tiempo y corromper la lista de conectados.
clientes: dict[int, socket.socket] = {}
candado = threading.Lock()

# Candado SOLO para imprimir: print() escribe el texto y el salto de linea por
# separado, y si dos hilos imprimen a la vez sus lineas se mezclan en pantalla.
candado_impresion = threading.Lock()


def hora() -> str:
    """Hora actual HH:MM:SS, solo para los registros de la consola del servidor."""
    return datetime.now().strftime("%H:%M:%S")


def mostrar(texto: str) -> None:
    """Imprime en la consola del servidor (lo que se ve con docker attach / logs)."""
    with candado_impresion:
        print(f"{hora()} {texto}", flush=True)


def registrar(numero: int, conexion: socket.socket) -> bool:
    """
    Apunta al cliente `numero` como conectado.
    Devuelve False si ese cliente ya estaba conectado (no se admiten dos
    "CLIENTE 1" a la vez: cada participante es unico).
    """
    with candado:
        if numero in clientes:
            return False
        clientes[numero] = conexion
        return True


def enviar(conexion: socket.socket, linea: str) -> bool:
    """Envia una linea a UN cliente. Devuelve False si la conexion fallo."""
    try:
        conexion.sendall((linea + "\n").encode("utf-8"))
        return True
    except OSError:
        return False


def difundir(linea: str) -> None:
    """
    Envia una linea a TODOS los clientes conectados (incluido quien la escribio,
    asi todos los terminales muestran la misma conversacion en el mismo orden)
    y la muestra tambien en la consola del servidor.
    """
    mostrar(linea)
    with candado:
        # list(...) porque si un envio falla se elimina al cliente mientras recorremos.
        for numero, conexion in list(clientes.items()):
            if not enviar(conexion, linea):
                clientes.pop(numero, None)


def leer_identidad(conexion: socket.socket, lector) -> int | None:
    """
    Lee la PRIMERA linea que manda el cliente ("IDENTIDAD 1" o "IDENTIDAD 2") y
    devuelve el numero, o None si no es valida o no llega a tiempo.
    """
    conexion.settimeout(SEGUNDOS_PARA_IDENTIFICARSE)  # no esperar eternamente
    try:
        primera_linea = lector.readline().strip()
    except OSError:
        return None
    conexion.settimeout(None)  # a partir de aqui, esperar mensajes sin limite de tiempo

    coincidencia = re.fullmatch(r"IDENTIDAD (\d+)", primera_linea)
    if coincidencia and int(coincidencia.group(1)) in PARTICIPANTES:
        return int(coincidencia.group(1))
    return None


def atender_cliente(conexion: socket.socket, direccion: tuple) -> None:
    """
    Funcion que ejecuta CADA HILO de cliente: lo identifica, recibe sus mensajes
    y los distribuye. Termina cuando el cliente se desconecta.
    """
    numero = None  # numero de cliente una vez identificado y registrado

    try:
        # makefile() nos permite leer el socket LINEA por LINEA (hasta cada "\n").
        with conexion.makefile("r", encoding="utf-8", errors="replace") as lector:

            # --- 1) Identificacion: quien es este cliente -----------------------
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

            # Mensaje privado de bienvenida: confirma al cliente quien es.
            enviar(conexion, f"[SERVIDOR]: Bienvenido, tu eres el {etiqueta}")
            # Aviso a todos (incluido el nuevo) de que se unio al chat.
            difundir(f"[SERVIDOR]: {etiqueta} se ha unido al chat")

            # --- 2) Bucle de mensajes ------------------------------------------
            for linea in lector:  # se bloquea esperando mensajes; no afecta a los otros hilos
                texto = linea.strip()
                if not texto:
                    continue  # ignorar lineas vacias
                difundir(f"[{etiqueta}]: {texto[:MAX_LARGO_MENSAJE]}")
    except (OSError, ConnectionError):
        pass  # el cliente cerro de golpe; lo tratamos igual que una desconexion normal
    finally:
        # --- 3) Limpieza -------------------------------------------------------
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
    """
    Hilo que permite que el SERVIDOR tambien escriba en el chat.
    Lee del teclado de la consola del contenedor (se usa con `docker attach`)
    y envia cada linea a todos los clientes con la etiqueta [SERVIDOR].
    """
    while True:
        try:
            texto = input()
        except EOFError:
            # Nadie esta conectado a la consola (el contenedor corre sin stdin).
            mostrar("[SERVIDOR]: consola sin entrada de teclado; el servidor sigue funcionando")
            return
        texto = texto.strip()
        if texto:
            difundir(f"[SERVIDOR]: {texto[:MAX_LARGO_MENSAJE]}")


def main() -> None:
    # Socket TCP (SOCK_STREAM) sobre IPv4 (AF_INET).
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Permite reiniciar el servidor enseguida sin esperar a que el SO libere el puerto.
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((HOST, PORT))
    servidor.listen()

    mostrar("=" * 60)
    mostrar(f"[SERVIDOR]: Chat TCP iniciado en el puerto {PORT}")
    mostrar("[SERVIDOR]: Esperando al CLIENTE 1 y al CLIENTE 2...")
    mostrar("[SERVIDOR]: Escribe aqui para hablar como SERVIDOR.")
    mostrar("=" * 60)

    # Hilo "daemon": se cierra solo cuando el programa termina.
    threading.Thread(target=consola_servidor, name="consola", daemon=True).start()

    try:
        while True:
            # accept() se bloquea hasta que un cliente se conecta.
            conexion, direccion = servidor.accept()
            conexion.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Un hilo nuevo por cliente: mientras uno espera mensajes, los demas siguen.
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
