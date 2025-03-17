# Monitor Biopetrol - Sistema de Monitoreo de Combustible

[![Versión](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/yourusername/biopetrol-monitor)

Este sistema monitorea surtidores de combustible de la red Biopetrol y envía alertas por Telegram y llamadas telefónicas cuando hay nueva carga de combustible disponible.


## Características

- Monitoreo de múltiples surtidores simultáneamente
- Alertas por Telegram cuando hay nueva carga de combustible
- Llamadas telefónicas automáticas vía CallMeBot
- Sistema de reintentos para llamadas fallidas
- Tests automatizados para verificar el funcionamiento

## Guía para Instalar el Monitor Biopetrol en Fedora Linux


## 4. Configurar el Entorno e Instalar Dependencias

```bash
# Verificar que sudo funciona correctamente
sudo whoami  # Debería mostrar "root"

# Actualizar el sistema
sudo dnf update -y

# Instalar Python y dependencias
sudo dnf install python3 python3-pip screen -y

# Instalar las bibliotecas necesarias
pip3 install --user requests beautifulsoup4
```

## 5. Crear Directorio para el Proyecto

```bash
# Crear directorio para el proyecto
mkdir -p ~/biopetrol-monitor
cd ~/biopetrol-monitor
```

## 6. Configurar Variables de Entorno

El sistema utiliza un archivo `.env` para almacenar información sensible como tokens y credenciales. Esto sigue las mejores prácticas de seguridad para no exponer datos sensibles en el código fuente.

```bash
# Instalar python-dotenv para manejar variables de entorno
pip3 install --user python-dotenv

# Crear archivo .env
nano .env
```

Copia y pega el siguiente contenido en el archivo `.env`, reemplazando los valores con tus propias credenciales:

```
# Configuración de Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# Configuración de CallMeBot
CALLMEBOT_USER=your_callmebot_username_here
CALLMEBOT_LANG=es-ES-Standard-A

# Configuración de Biopetrol
BIOPETROL_URL=http://ec2-3-22-240-207.us-east-2.compute.amazonaws.com/guiasaldos/main/donde/134

# Configuración del monitor
CHECK_INTERVAL=300
CALLMEBOT_MAX_RETRIES=3
CALLMEBOT_RETRY_DELAY=60
```

Presiona `Ctrl+O` para guardar y `Ctrl+X` para salir.

> **IMPORTANTE**: Nunca compartas tu archivo `.env` en repositorios públicos. Asegúrate de incluirlo en tu archivo `.gitignore`.

## 7. Crear el Script del Monitor

```bash
# Crear el archivo del script
nano biopetrol-monitor.py
```

Copia y pega el código completo del script. Presiona `Ctrl+O` para guardar y `Ctrl+X` para salir.

## 8. Hacer el Script Ejecutable

```bash
chmod +x biopetrol-monitor.py
```

## 9. Probar el Script

```bash
# Ejecutar el script con un surtidor
python3 biopetrol-monitor.py --surtidor CHACO

# Ejecutar el script con múltiples surtidores
python3 biopetrol-monitor.py --surtidor CHACO-FORMOSA-CORRIENTES

# Ver la versión del script
python3 biopetrol-monitor.py --version
```

Presiona `Ctrl+C` para detener después de confirmar que funciona correctamente.

## 10. Ejecutar Tests Automatizados

El proyecto incluye tests automatizados para verificar el funcionamiento del sistema de alertas y llamadas telefónicas sin necesidad de realizar llamadas reales.

```bash
# Ejecutar todos los tests automatizados
python3 test_biopetrol_monitor.py

# Ejecutar prueba manual de alertas y llamadas
python3 test_biopetrol_monitor.py --manual
```

### Tests Automatizados

Los tests automatizados verifican:
- Detección de nuevas cargas de combustible
- Envío de alertas por Telegram
- Realización de llamadas telefónicas
- Sistema de reintentos para llamadas fallidas

#### Nota sobre los mensajes de "Línea ocupada"

Durante la ejecución de los tests, es posible que veas mensajes como:

```
API de CallMeBot indica: Línea ocupada. Reintentando en 60 segundos...
```

Esto es **normal y esperado** durante los tests, ya que uno de los tests (`test_realizar_llamada_telefonica_con_reintentos`) está diseñado específicamente para simular una situación donde la primera llamada falla con "línea ocupada" y la segunda llamada tiene éxito. Esto es solo para probar la lógica de reintentos y no significa que haya un problema real con la API.

### Prueba Manual

La opción `--manual` envía una alerta real por Telegram y realiza una llamada telefónica de prueba. Utiliza esta opción cuando quieras verificar que las notificaciones funcionan correctamente en el entorno real.

## 11. Configurar como Servicio Systemd

```bash
# Crear archivo de servicio
sudo nano /etc/systemd/system/biopetrol-monitor.service
```

Pega el siguiente contenido:

```ini
[Unit]
Description=Monitor de Surtidores Biopetrol
After=network.target

[Service]
Type=simple
User=carlos
WorkingDirectory=/home/carlos/biopetrol-monitor
ExecStart=/usr/bin/python3 /home/carlos/biopetrol-monitor/biopetrol-monitor.py --surtidor CHACO
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
```

## 12. Activar y Iniciar el Servicio

```bash
# Recargar la configuración de systemd
sudo systemctl daemon-reload

# Habilitar el servicio para iniciar con el sistema
sudo systemctl enable biopetrol-monitor.service

# Iniciar el servicio
sudo systemctl start biopetrol-monitor.service

# Verificar que está funcionando
sudo systemctl status biopetrol-monitor.service
```

## 13. Comandos Útiles para el Servicio

```bash
# Ver logs en tiempo real
sudo journalctl -u biopetrol-monitor.service -f

# Detener el servicio
sudo systemctl stop biopetrol-monitor.service

# Reiniciar el servicio
sudo systemctl restart biopetrol-monitor.service
```

