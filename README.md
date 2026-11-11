# Chat en tiempo real con Python, Hilos, Sockets TCP y Docker

Aplicación de chat en tiempo real formada por **un servidor** (en un contenedor Docker) y **dos clientes** (en dos terminales independientes de Visual Studio Code). Usa **sockets TCP** y **hilos** (`threading`) de Python, de modo que todos los participantes pueden escribir **al mismo tiempo, sin esperar turnos**.

```
              ┌──────────────────────────────┐
              │          SERVIDOR            │
              │   Python + TCP (puerto 5000) │
              │     Contenedor Docker        │
              └───────▲──────────────▲───────┘
                      │              │
        ┌─────────────┴───┐      ┌───┴─────────────┐
        │    CLIENTE 1    │      │    CLIENTE 2    │
        │ Terminal VS Code│      │ Terminal VS Code│
        │     Python      │      │     Python      │
        └─────────────────┘      └─────────────────┘
```

## Participantes

| Participante | Etiqueta | Dónde se ejecuta |
|---|---|---|
| Servidor | `[SERVIDOR]` | Contenedor Docker |
| Primer cliente que se conecta | `[CLIENTE 1]` | Terminal de VS Code |
| Segundo cliente que se conecta | `[CLIENTE 2]` | Otra terminal de VS Code |

El **servidor numera a los clientes por orden de conexión**: el primero que entra es el Cliente 1 y el segundo es el Cliente 2. Los dos clientes ejecutan exactamente el mismo comando.

## Requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y **abierto** (incluye Docker Compose).
- [Python 3.10 o superior](https://www.python.org/downloads/) (se probó con 3.12). Los clientes no necesitan instalar ninguna librería.
- Visual Studio Code.
- El puerto **5000** libre en tu computadora.

## Estructura del proyecto

```
.
├── docker-compose.yml      # Levanta el servidor y publica el puerto 5000
├── README.md
├── servidor/
│   ├── servidor.py         # Servidor de chat (hilos + sockets), comentado
│   └── Dockerfile          # Imagen de Python 3.12 para el servidor
└── cliente/
    └── cliente.py          # Cliente de chat (se usa para el Cliente 1 y el 2)
```

## Cómo ejecutar toda la aplicación

Se usan **3 terminales** en VS Code (`Terminal → Nueva terminal`, o el botón `+` del panel de terminal).

### 0. Obtener el código

```bash
git clone https://github.com/arielll669/-EXAMEN-PR-CTICO---Distribuidas.git
cd ./-EXAMEN-PR-CTICO---Distribuidas
```

> El `./` es necesario porque el nombre de la carpeta empieza con `-`. Luego abre esa carpeta en VS Code (`code .`).

### 1. Terminal 1: SERVIDOR (Docker)

Construye la imagen e inicia el contenedor en segundo plano:

```bash
docker compose up -d --build
```

Luego conecta esta terminal a la consola del servidor:

```bash
docker attach chat-servidor
```

Verás algo como:

```
12:00:00 [SERVIDOR]: Chat TCP iniciado en el puerto 5000 (max. 2 clientes)
12:00:00 [SERVIDOR]: Esperando clientes... Escribe aqui para hablar como SERVIDOR.
```

Esta terminal es la **consola del servidor**: ahí se ve todo lo que circula en el chat y lo que escribas sale con la etiqueta `[SERVIDOR]`.

> **Para salir de la consola sin apagar el servidor:** pulsa `Ctrl+P` y después `Ctrl+Q`.
> Si pulsas `Ctrl+C` dentro de `docker attach`, se detiene el servidor.

### 2. Terminal 2: CLIENTE 1

```bash
python cliente/cliente.py
```

Debe mostrar `[SERVIDOR]: Bienvenido, tu eres el CLIENTE 1`.

### 3. Terminal 3: CLIENTE 2

```bash
python cliente/cliente.py
```

Debe mostrar `[SERVIDOR]: Bienvenido, tu eres el CLIENTE 2`.

> En Windows, si `python` no se reconoce, usa `py cliente/cliente.py`.

### 4. Detener todo

Para salir de un cliente escribe `/salir` (o `Ctrl+C`). Para apagar el servidor, desde cualquier terminal:

```bash
docker compose down
```

## Guía para la demostración (pruebas de funcionamiento)

| # | Prueba | Qué hacer | Qué se debe ver |
|---|---|---|---|
| 1 | Iniciar el servidor en Docker | Terminal 1: `docker compose up -d --build` y `docker attach chat-servidor` | El servidor indica que escucha en el puerto 5000 |
| 2 | Conectar el Cliente 1 | Terminal 2: `python cliente/cliente.py` | "Bienvenido, tu eres el CLIENTE 1". El servidor registra la conexión |
| 3 | Conectar el Cliente 2 | Terminal 3: `python cliente/cliente.py` | "Bienvenido, tu eres el CLIENTE 2". Ambos clientes ven que el Cliente 2 se unió |
| 4 | Enviar mensajes y verificar que ambos lo reciben | Escribe en el Cliente 1, en el Cliente 2 y en la consola del servidor | Cada mensaje aparece en las **tres** terminales con su etiqueta correcta |
| 5 | Escribir sin esperar turnos | Escribe en el Cliente 1 y en el Cliente 2 **a la vez**, sin esperar respuesta | Los mensajes de ambos llegan al instante, en cualquier orden |

## Salida esperada

En las tres terminales se ve la misma conversación:

```
[SERVIDOR]: CLIENTE 1 se ha unido al chat
[SERVIDOR]: CLIENTE 2 se ha unido al chat
[CLIENTE 1]: Hola a todos
[SERVIDOR]: Hola cliente 1
[CLIENTE 2]: Buenos días
[CLIENTE 1]: ¿Cómo están?
[CLIENTE 2]: Todo bien
```

(En la consola del servidor cada línea lleva además la hora al inicio.)

## Cómo funciona

- **Sockets TCP:** el servidor abre el puerto 5000 con `socket` y espera conexiones; los clientes se conectan a `127.0.0.1:5000`. Docker publica ese puerto con `ports: "5000:5000"`, por eso los clientes de VS Code (fuera de Docker) llegan al servidor (dentro de Docker).
- **Hilos en el servidor** (`servidor/servidor.py`):
  - El **hilo principal** acepta conexiones nuevas.
  - **Un hilo por cliente** lee sus mensajes y los distribuye a todos.
  - Un **hilo de consola** lee el teclado del servidor, para que también pueda escribir.
- **Hilos en el cliente** (`cliente/cliente.py`): el hilo principal envía lo que escribes y un **hilo receptor** muestra lo que llega. Por eso se puede escribir y recibir a la vez, sin turnos.
- **Lock:** la lista de clientes conectados se comparte entre varios hilos, así que se protege con un `threading.Lock` para evitar condiciones de carrera.
- **Protocolo:** cada mensaje es una línea de texto UTF-8 terminada en `\n` (soporta tildes y signos como `¿`).
- **Identificación:** el servidor asigna `CLIENTE 1` y `CLIENTE 2` por orden de conexión y etiqueta cada mensaje con su autor. Solo admite 2 clientes a la vez; un tercero recibe un aviso de "Chat lleno".
- **Desconexiones:** si un cliente se va, el servidor avisa a los demás y libera su número.

## Solución de problemas

| Problema | Solución |
|---|---|
| `No se pudo conectar a 127.0.0.1:5000` | El servidor no está en marcha. Ejecuta `docker compose up -d --build` y comprueba con `docker ps` |
| `port is already allocated` / puerto 5000 ocupado | Cierra lo que use el 5000, o cambia en `docker-compose.yml` `"5000:5000"` por `"5001:5000"` y ejecuta los clientes con `CHAT_PORT=5001` (PowerShell: `$env:CHAT_PORT=5001; python cliente/cliente.py`) |
| `docker attach` no muestra nada | Pulsa Enter, o revisa el historial con `docker logs chat-servidor` |
| Aparecen caracteres raros al escribir en el cliente | Ejecuta el cliente con `CHAT_SIN_ANSI=1` (PowerShell: `$env:CHAT_SIN_ANSI=1`) |
| Quiero ver los registros del servidor sin `attach` | `docker logs -f chat-servidor` |
