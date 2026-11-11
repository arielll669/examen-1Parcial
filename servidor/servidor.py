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
  [CLIENTE 1]  primer cliente en conectarse
  [CLIENTE 2]  segundo cliente en conectarse
  [SERVIDOR]   este programa

Protocolo (muy simple): cada mensaje es una linea de texto UTF-8 terminada en
salto de linea ("\n"). TCP es un flujo continuo de bytes y no marca donde
termina un mensaje, por eso usamos "\n" como separador.
"""

import os
import socket
import threading
from datetime import datetime

# ----------------------------------------------------------------------------
# Configuracion (se puede cambiar con variables de entorno)
# ----------------------------------------------------------------------------
HOST = "0.0.0.0"                                 # escuchar en todas las interfaces del contenedor
PORT = int(os.environ.get("CHAT_PORT", "5000"))  # puerto TCP del chat
MAX_CLIENTES = int(os.environ.get("MAX_CLIENTES", "2"))  # el ejercicio pide 2 clientes
MAX_LARGO_MENSAJE = 1000                         # evita mensajes gigantes

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


def hora() -> str:
    """Hora actual HH:MM:SS, solo para los registros de la consola del servidor."""
    return datetime.now().strftime("%H:%M:%S")


# Candado SOLO para imprimir: print() escribe el texto y el salto de linea por
# separado, y si dos hilos imprimen a la vez sus lineas se mezclan en pantalla.
candado_impresion = threading.Lock()


def mostrar(texto: str) -> None:
    """Imprime en la consola del servidor (lo que se ve con docker attach / logs)."""
    with candado_impresion:
        print(f"{hora()} {texto}", flush=True)


def reservar_numero(conexion: socket.socket) -> int | None:
    """
    Asigna al cliente el numero libre mas bajo (1, 2, ...) por orden de conexion.
    Devuelve None si el chat ya esta lleno.
    Si un cliente se va y otro entra, reutiliza el numero que quedo libre.
    """
    with candado:
        for numero in range(1, MAX_CLIENTES + 1):
            if numero not in clientes:
                clientes[numero] = conexion
                return numero
    return None


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


def atender_cliente(conexion: socket.socket, direccion: tuple) -> None:
    """
    Funcion que ejecuta CADA HILO de cliente: recibe sus mensajes y los distribuye.
    Termina cuando el cliente se desconecta.
    """
    numero = reservar_numero(conexion)

    if numero is None:
        enviar(conexion, f"[SERVIDOR]: Chat lleno (maximo {MAX_CLIENTES} clientes). Intenta mas tarde.")
        conexion.close()
        mostrar(f"[SERVIDOR]: Conexion de {direccion[0]}:{direccion[1]} rechazada (chat lleno)")
        return

    etiqueta = f"CLIENTE {numero}"
    mostrar(f"[SERVIDOR]: {etiqueta} conectado desde {direccion[0]}:{direccion[1]}")

    # Mensaje privado de bienvenida: le dice al cliente quien es.
    enviar(conexion, f"[SERVIDOR]: Bienvenido, tu eres el {etiqueta}")
    # Aviso a todos (incluido el nuevo) de que se unio al chat.
    difundir(f"[SERVIDOR]: {etiqueta} se ha unido al chat")

    try:
        # makefile() nos permite leer el socket LINEA por LINEA (hasta cada "\n").
        with conexion.makefile("r", encoding="utf-8", errors="replace") as lector:
            for linea in lector:  # se bloquea esperando mensajes; no afecta a los otros hilos
                texto = linea.strip()
                if not texto:
                    continue  # ignorar lineas vacias
                difundir(f"[{etiqueta}]: {texto[:MAX_LARGO_MENSAJE]}")
    except (OSError, ConnectionError):
        pass  # el cliente cerro de golpe; lo tratamos igual que una desconexion normal
    finally:
        # Limpieza: quitar al cliente de la lista y avisar a los demas.
        with candado:
            if clientes.get(numero) is conexion:
                del clientes[numero]
        try:
            conexion.close()
        except OSError:
            pass
        difundir(f"[SERVIDOR]: {etiqueta} se ha desconectado")


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
    mostrar(f"[SERVIDOR]: Chat TCP iniciado en el puerto {PORT} (max. {MAX_CLIENTES} clientes)")
    mostrar("[SERVIDOR]: Esperando clientes... Escribe aqui para hablar como SERVIDOR.")
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
