#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor de Surtidores Biopetrol con Notificaciones Telegram

Este script monitorea cada 5 minutos un surtidor específico de Biopetrol
y envía notificaciones a Telegram cuando está disponible.

Uso:
    python biopetrol-monitor.py --surtidor NOMBRE_SURTIDOR
    
    Por ejemplo:
    python biopetrol-monitor.py --surtidor CHACO
"""

import requests
from bs4 import BeautifulSoup
import json
import sys
import time
import argparse
import logging
from datetime import datetime

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("biopetrol_monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("BiopetrolMonitor")

# Configuración de Telegram
TELEGRAM_BOT_TOKEN = "7540004750:AAF5BJxZb6XZRxRvh4hc2gF7kLvqMrHhTU8"
TELEGRAM_CHAT_ID = "-4765545244"

# URL de la API de Telegram para enviar mensajes
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# URL de Biopetrol
BIOPETROL_URL = 'http://ec2-3-22-240-207.us-east-2.compute.amazonaws.com/guiasaldos/main/donde/134'

# Intervalo de tiempo entre verificaciones (en segundos)
CHECK_INTERVAL = 300  # 5 minutos

# Estado global para evitar enviar notificaciones duplicadas
ultimo_estado = {}

def enviar_mensaje_telegram(mensaje):
    """
    Envía un mensaje a Telegram.
    
    Args:
        mensaje: El mensaje a enviar
        
    Returns:
        bool: True si el mensaje se envió correctamente, False en caso contrario
    """
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': mensaje,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(TELEGRAM_URL, data=payload)
        if response.status_code == 200:
            logger.info(f"Mensaje enviado a Telegram con éxito")
            return True
        else:
            logger.error(f"Error al enviar mensaje a Telegram: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Excepción al enviar mensaje a Telegram: {e}")
        return False


def extraer_datos():
    """
    Extrae datos de las estaciones de combustible desde la URL de Biopetrol.
    
    Returns:
        list: Lista de diccionarios con la información de las estaciones
    """
    logger.info(f"Extrayendo datos de: {BIOPETROL_URL}")
    
    try:
        # Realizar solicitud HTTP
        response = requests.get(BIOPETROL_URL)
        response.raise_for_status()
        html = response.text
        
        # Parsear el HTML con BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Encontrar todas las tarjetas de estaciones
        tarjetas = soup.find_all('div', class_='btn-bio-app')
        
        # Lista para almacenar la información extraída
        estaciones = []
        
        for tarjeta in tarjetas:
            try:
                # Extraer nombre
                nombre_div = tarjeta.find('div', class_='bg-oscuro-1')
                nombre = nombre_div.text.strip() if nombre_div else "N/A"
                
                # Extraer existencia y hora
                divs_derecha = tarjeta.find_all('div', class_='text-right')
                existencia = divs_derecha[0].text.strip() if len(divs_derecha) > 0 else "N/A"
                hora = divs_derecha[1].text.strip() if len(divs_derecha) > 1 else "N/A"
                
                # Extraer dirección
                div_direccion = tarjeta.find('div', class_='alert-secondary')
                direccion = "N/A"
                if div_direccion:
                    direccion_div = div_direccion.find('div')
                    if direccion_div:
                        direccion = direccion_div.text.strip()
                
                # Extraer coordenadas
                coordenadas = None
                icono_mapa = tarjeta.find('i', class_='fa-map-marker-alt')
                if icono_mapa and 'data-target' in icono_mapa.parent.attrs:
                    modal_id = icono_mapa.parent['data-target'].lstrip('.')
                    modal = soup.find('div', class_=modal_id)
                    if modal:
                        icono_ubicacion = modal.find('i', class_='fa-location-arrow')
                        if icono_ubicacion and 'onclick' in icono_ubicacion.attrs:
                            onclick = icono_ubicacion['onclick']
                            if "invokeCSCode('" in onclick and "'" in onclick:
                                coordenadas = onclick.split("'")[1]
                
                # Crear diccionario con los datos
                estacion = {
                    "nombre": nombre,
                    "existencia_litros": existencia,
                    "hora_medicion": hora,
                    "direccion": direccion,
                    "coordenadas": coordenadas
                }
                
                estaciones.append(estacion)
                
            except Exception as e:
                logger.error(f"Error al procesar una tarjeta: {e}")
        
        return estaciones
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al realizar la solicitud HTTP: {e}")
        return []
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        return []


def verificar_surtidor(nombre_surtidor):
    """
    Verifica si un surtidor específico está disponible y envía una notificación si lo está.
    
    Args:
        nombre_surtidor: El nombre del surtidor a verificar
        
    Returns:
        bool: True si el surtidor está disponible, False en caso contrario
    """
    global ultimo_estado
    
    # Obtener todas las estaciones
    estaciones = extraer_datos()
    
    if not estaciones:
        logger.warning("No se pudieron obtener datos de estaciones")
        return False
    
    # Filtrar la estación específica
    estacion = None
    for e in estaciones:
        if nombre_surtidor.upper() in e["nombre"].upper():
            estacion = e
            break
    
    # Si no se encontró la estación
    if not estacion:
        logger.warning(f"No se encontró el surtidor '{nombre_surtidor}'")
        return False
    
    # Verificar si hay combustible disponible
    try:
        existencia_str = estacion["existencia_litros"].replace(',', '').replace('.', '')
        existencia_str = ''.join(filter(str.isdigit, existencia_str))
        existencia = float(existencia_str) if existencia_str else 0
        
        # Si hay combustible disponible
        disponible = existencia > 0
        
        # Verificar si el estado ha cambiado
        key = estacion["nombre"]
        estado_anterior = ultimo_estado.get(key, None)
        
        # Si el estado ha cambiado o no hay registro previo
        if estado_anterior != disponible:
            ultimo_estado[key] = disponible
            
            # Si está disponible, enviar notificación
            if disponible:
                mensaje = f"""
🚨 <b>ALERTA DE COMBUSTIBLE DISPONIBLE</b> 🚨

📍 <b>Estación:</b> {estacion["nombre"]}
⛽ <b>Disponible:</b> {estacion["existencia_litros"]}
🕒 <b>Actualizado:</b> {estacion["hora_medicion"]}
📌 <b>Dirección:</b> {estacion["direccion"]}

<i>Verificado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>
"""
                enviar_mensaje_telegram(mensaje)
                logger.info(f"Notificación enviada para {estacion['nombre']}")
            else:
                logger.info(f"El surtidor {estacion['nombre']} ya no está disponible")
        
        # Registrar estado actual
        if disponible:
            logger.info(f"El surtidor {estacion['nombre']} está disponible con {estacion['existencia_litros']}")
        else:
            logger.info(f"El surtidor {estacion['nombre']} no está disponible")
        
        return disponible
        
    except Exception as e:
        logger.error(f"Error al verificar disponibilidad: {e}")
        return False


def monitor_continuo(nombre_surtidor):
    """
    Monitorea continuamente un surtidor específico cada 5 minutos.
    
    Args:
        nombre_surtidor: El nombre del surtidor a monitorear
    """
    logger.info(f"Iniciando monitoreo del surtidor '{nombre_surtidor}' cada {CHECK_INTERVAL//60} minutos")
    
    # Enviar mensaje inicial
    mensaje_inicial = f"""
🔄 <b>MONITOREO INICIADO</b>

Estoy monitoreando el surtidor <b>{nombre_surtidor}</b> cada 5 minutos.
Recibirás una notificación cuando el combustible esté disponible.

<i>Iniciado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>
"""
    enviar_mensaje_telegram(mensaje_inicial)
    
    # Verificación inicial
    verificar_surtidor(nombre_surtidor)
    
    # Bucle de monitoreo continuo
    try:
        while True:
            # Esperar el intervalo de tiempo
            logger.info(f"Esperando {CHECK_INTERVAL//60} minutos para la próxima verificación...")
            time.sleep(CHECK_INTERVAL)
            
            # Verificar nuevamente
            verificar_surtidor(nombre_surtidor)
    except KeyboardInterrupt:
        logger.info("Monitoreo detenido por el usuario")
        enviar_mensaje_telegram(f"⛔ <b>MONITOREO DETENIDO</b>\n\nEl monitoreo del surtidor <b>{nombre_surtidor}</b> ha sido detenido manualmente.")
    except Exception as e:
        logger.error(f"Error en el bucle de monitoreo: {e}")
        enviar_mensaje_telegram(f"❌ <b>ERROR DE MONITOREO</b>\n\nEl monitoreo del surtidor <b>{nombre_surtidor}</b> se ha detenido debido a un error:\n<code>{str(e)}</code>")


def main():
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Monitor de surtidores Biopetrol con notificaciones Telegram')
    parser.add_argument('--surtidor', type=str, required=True, help='Nombre del surtidor a monitorear')
    
    args = parser.parse_args()
    
    # Verificar configuración de Telegram
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Error: Token de bot o ID de chat de Telegram no configurados")
        sys.exit(1)
    
    # Iniciar monitoreo continuo
    monitor_continuo(args.surtidor)


if __name__ == "__main__":
    main()