FROM python:3.12-slim

# Muestra la salida de print() en tiempo real (necesario para ver el chat en
# docker attach / docker logs sin esperar a que se llene un buffer)
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY servidor.py .

# Puerto TCP que usa el chat (informativo; se publica en docker-compose.yml)
EXPOSE 5000

CMD ["python", "servidor.py"]
