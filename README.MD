# Guía para Crear Usuario "carlos" e Instalar el Monitor Biopetrol en Fedora Linux


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

## 6. Crear el Script del Monitor

```bash
# Crear el archivo del script
nano biopetrol-monitor.py
```

Copia y pega el código completo del script. Presiona `Ctrl+O` para guardar y `Ctrl+X` para salir.

## 7. Hacer el Script Ejecutable

```bash
chmod +x biopetrol-monitor.py
```

## 8. Probar el Script

```bash
python3 biopetrol-monitor.py --surtidor CHACO
```

Presiona `Ctrl+C` para detener después de confirmar que funciona correctamente.

## 9. Configurar como Servicio Systemd

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

## 10. Activar y Iniciar el Servicio

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

## 11. Comandos Útiles para el Servicio

```bash
# Ver logs en tiempo real
sudo journalctl -u biopetrol-monitor.service -f

# Detener el servicio
sudo systemctl stop biopetrol-monitor.service

# Reiniciar el servicio
sudo systemctl restart biopetrol-monitor.service
```

