# Chat en tiempo real con Python, Hilos, Sockets TCP y Docker

Aplicación de chat en tiempo real formada por **un servidor** (en un contenedor Docker) y **dos clientes** (cada uno es un programa distinto, ejecutado en su propia terminal de Visual Studio Code). Usa **sockets TCP** y **hilos** (`threading`) de Python, de modo que todos los participantes pueden escribir **al mismo tiempo, sin esperar turnos**.

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
        │   cliente1.py   │      │   cliente2.py   │
        └─────────────────┘      └─────────────────┘
```

## Participantes

| Participante | Etiqueta | Programa | Dónde se ejecuta |
|---|---|---|---|
| Servidor | `[SERVIDOR]` | `servidor/servidor.py` | Contenedor Docker |
| Cliente 1 | `[CLIENTE 1]` | `cliente/cliente1.py` | Terminal 2 de VS Code |
| Cliente 2 | `[CLIENTE 2]` | `cliente/cliente2.py` | Terminal 3 de VS Code |

Cada cliente es **su propio programa** y se identifica ante el servidor nada más conectarse (`IDENTIDAD 1` o `IDENTIDAD 2`). El servidor etiqueta cada mensaje con el autor correcto y no permite dos clientes con la misma identidad.

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
    ├── cliente1.py         # Programa del CLIENTE 1
    └── cliente2.py         # Programa del CLIENTE 2
```

## Cómo ejecutar toda la aplicación

Se usan **3 terminales** en VS Code (`Terminal → Nueva terminal`, o el botón `+` del panel de terminal).

### 0. Obtener el código

```bash
git clone https://github.com/arielll669/examen-1Parcial.git
cd examen-1Parcial
```

> Luego abre esa carpeta en VS Code (`code .`).

### 1. Terminal 1: SERVIDOR (Docker)

Construye la imagen e inicia el contenedor en segundo plano:

```bash
docker compose up -d --build
```

Luego conecta esta terminal a la consola del servidor:

```bash
docker attach chat-servidor
```

**La pantalla aparece en blanco: es normal.** `docker attach` no repite lo que el servidor imprimió antes de conectarte, solo muestra lo nuevo. Pulsa **Enter** y verás:

```
12:00:00 [SERVIDOR]: Consola conectada. En linea: ninguno
```

(El mensaje de arranque "Chat TCP iniciado en el puerto 5000" se consulta con `docker logs chat-servidor`.)

Esta terminal es la **consola del servidor**: a partir de ahora ahí se ve todo lo que circula en el chat, y lo que escribas sale con la etiqueta `[SERVIDOR]`. Un Enter en blanco no envía nada al chat; solo muestra quién está en línea.

> **Para salir de la consola sin apagar el servidor:** pulsa `Ctrl+P` y después `Ctrl+Q`.
> `Ctrl+C` no apaga el servidor (se ignora y se muestra un aviso). Para apagarlo usa `docker compose down`.

### 2. Terminal 2: CLIENTE 1

```bash
python cliente/cliente1.py
```

Debe mostrar `[SERVIDOR]: Bienvenido, tu eres el CLIENTE 1`.

### 3. Terminal 3: CLIENTE 2

```bash
python cliente/cliente2.py
```

Debe mostrar `[SERVIDOR]: Bienvenido, tu eres el CLIENTE 2`.

> En Windows, si `python` no se reconoce, usa `py cliente/cliente1.py` y `py cliente/cliente2.py`.

### 4. Detener todo

Para salir de un cliente escribe `/salir` (o `Ctrl+C`). Para apagar el servidor, desde cualquier terminal:

```bash
docker compose down
```

## Guía para la demostración (pruebas de funcionamiento)

| # | Prueba | Qué hacer | Qué se debe ver |
|---|---|---|---|
| 1 | Iniciar el servidor en Docker | Terminal 1: `docker compose up -d --build`, `docker attach chat-servidor` y pulsar Enter | "Consola conectada. En linea: ninguno" (y `docker logs chat-servidor` muestra que escucha en el puerto 5000) |
| 2 | Conectar el Cliente 1 | Terminal 2: `python cliente/cliente1.py` | "Bienvenido, tu eres el CLIENTE 1". El servidor registra la conexión |
| 3 | Conectar el Cliente 2 | Terminal 3: `python cliente/cliente2.py` | "Bienvenido, tu eres el CLIENTE 2". Ambos clientes ven que el Cliente 2 se unió |
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
  - **Un hilo por cliente** lo identifica, lee sus mensajes y los distribuye a todos.
  - Un **hilo de consola** lee el teclado del servidor, para que también pueda escribir.
- **Hilos en cada cliente** (`cliente/cliente1.py` y `cliente/cliente2.py`): el hilo principal envía lo que escribes y un **hilo receptor** muestra lo que llega. Por eso se puede escribir y recibir a la vez, sin turnos.
- **Lock:** la lista de clientes conectados se comparte entre varios hilos, así que se protege con un `threading.Lock` para evitar condiciones de carrera.
- **Protocolo:** cada mensaje es una línea de texto UTF-8 terminada en `\n` (soporta tildes y signos como `¿`).
- **Identificación:** lo primero que envía cada cliente es `IDENTIDAD 1` o `IDENTIDAD 2`. El servidor etiqueta todos los mensajes de esa conexión con `[CLIENTE 1]` o `[CLIENTE 2]`, y rechaza identidades inválidas o repetidas.
- **Desconexiones:** si un cliente se va, el servidor avisa a los demás y libera su identidad para que pueda volver a conectarse.

## Solución de problemas

| Problema | Solución |
|---|---|
| `No se pudo conectar a 127.0.0.1:5000` | El servidor no está en marcha. Ejecuta `docker compose up -d --build` y comprueba con `docker ps` |
| `El CLIENTE 1 ya esta conectado` | Ya hay otra terminal ejecutando `cliente1.py`. Ciérrala con `/salir` o usa `cliente2.py` |
| `port is already allocated` / puerto 5000 ocupado | Cierra lo que use el 5000, o cambia en `docker-compose.yml` `"5000:5000"` por `"5001:5000"` y ejecuta los clientes con `CHAT_PORT=5001` (PowerShell: `$env:CHAT_PORT=5001; python cliente/cliente1.py`) |
| `docker attach` se ve en blanco | Es normal: solo muestra lo nuevo. Pulsa Enter para ver quién está en línea, o revisa lo anterior con `docker logs chat-servidor` |
| `cannot attach to a stopped container` | El servidor está apagado. Ejecuta `docker compose up -d --build` y vuelve a hacer `docker attach chat-servidor` |
| Aparecen caracteres raros al escribir en el cliente | Ejecuta el cliente con `CHAT_SIN_ANSI=1` (PowerShell: `$env:CHAT_SIN_ANSI=1`) |
| Quiero ver los registros del servidor sin `attach` | `docker logs -f chat-servidor` |
