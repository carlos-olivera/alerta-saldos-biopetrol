#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor de Surtidores Biopetrol con Notificaciones Telegram

Este script monitorea cada 5 minutos uno o varios surtidores específicos de Biopetrol
y envía notificaciones a Telegram cuando se detecta una nueva carga de combustible.

Uso:
    python biopetrol-monitor.py --surtidor NOMBRE_SURTIDOR
    
    Para monitorear múltiples surtidores, separarlos con "-":
    python biopetrol-monitor.py --surtidor CHACO-FORMOSA-CORRIENTES
    
    Para mostrar la versión:
    python biopetrol-monitor.py --version
"""

__version__ = '1.0.0'
__author__ = 'Carlos Olivera'
__license__ = 'MIT'

import requests
from bs4 import BeautifulSoup
import json
import sys
import time
import argparse
import logging
import platform
import os
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env
load_dotenv()

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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# URL de la API de Telegram para enviar mensajes
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Configuración de CallMeBot para llamadas telefónicas
CALLMEBOT_USER = os.getenv("CALLMEBOT_USER")
CALLMEBOT_URL = "http://api.callmebot.com/start.php"
CALLMEBOT_DEFAULT_MESSAGE = "Llego la gasolina"
CALLMEBOT_LANG = os.getenv("CALLMEBOT_LANG", "es-ES-Standard-A")
CALLMEBOT_MAX_RETRIES = int(os.getenv("CALLMEBOT_MAX_RETRIES", "3"))
CALLMEBOT_RETRY_DELAY = int(os.getenv("CALLMEBOT_RETRY_DELAY", "60"))  # segundos

# URL de Biopetrol
BIOPETROL_URL = os.getenv("BIOPETROL_URL", 'http://ec2-3-22-240-207.us-east-2.compute.amazonaws.com/guiasaldos/main/donde/134')

# Intervalo de tiempo entre verificaciones (en segundos)
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # 5 minutos por defecto

# Estado global para almacenar el estado y saldo de los surtidores
ultimo_estado = {}
# Flag para indicar si es la primera ejecución
es_primera_ejecucion = True

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


def realizar_llamada_telefonica(mensaje=None):
    """
    Realiza una llamada telefónica a través de CallMeBot.
    
    Args:
        mensaje: El mensaje a convertir en voz (opcional)
        
    Returns:
        bool: True si la llamada se realizó correctamente, False en caso contrario
    """
    # Usar mensaje personalizado o el predeterminado
    texto = mensaje if mensaje else CALLMEBOT_DEFAULT_MESSAGE
    
    # Parámetros de la llamada
    params = {
        'source': 'web',
        'user': CALLMEBOT_USER,
        'text': texto,
        'lang': CALLMEBOT_LANG
    }
    
    # Intentar realizar la llamada con reintentos
    for intento in range(1, CALLMEBOT_MAX_RETRIES + 1):
        try:
            logger.info(f"Realizando llamada telefónica (intento {intento}/{CALLMEBOT_MAX_RETRIES})")
            response = requests.get(CALLMEBOT_URL, params=params, timeout=30)
            
            # Verificar respuesta
            if response.status_code == 200:
                # Verificar contenido de la respuesta
                if "queued" in response.text.lower() or "success" in response.text.lower():
                    logger.info(f"Llamada telefónica realizada con éxito")
                    return True
                elif "busy" in response.text.lower():
                    logger.warning(f"API de CallMeBot indica: Línea ocupada. Reintentando en {CALLMEBOT_RETRY_DELAY} segundos...")
                    logger.debug(f"Respuesta completa de CallMeBot: {response.text}")
                else:
                    logger.warning(f"API de CallMeBot devolvió respuesta inesperada: {response.text}. Reintentando en {CALLMEBOT_RETRY_DELAY} segundos...")
            else:
                logger.warning(f"Error en la llamada: {response.status_code}. Reintentando en {CALLMEBOT_RETRY_DELAY} segundos...")
            
            # Si no es el último intento, esperar antes de reintentar
            if intento < CALLMEBOT_MAX_RETRIES:
                time.sleep(CALLMEBOT_RETRY_DELAY)
                
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout en la llamada. Reintentando en {CALLMEBOT_RETRY_DELAY} segundos...")
            if intento < CALLMEBOT_MAX_RETRIES:
                time.sleep(CALLMEBOT_RETRY_DELAY)
        except Exception as e:
            logger.error(f"Error al realizar la llamada telefónica: {e}")
            if intento < CALLMEBOT_MAX_RETRIES:
                time.sleep(CALLMEBOT_RETRY_DELAY)
    
    logger.error(f"No se pudo realizar la llamada telefónica después de {CALLMEBOT_MAX_RETRIES} intentos")
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


def verificar_surtidor(nombre_surtidor, enviar_alertas=True):
    """
    Verifica si un surtidor específico está disponible y envía una notificación si corresponde.
    
    Args:
        nombre_surtidor: El nombre del surtidor a verificar
        enviar_alertas: Indica si se deben enviar alertas o solo actualizar el estado
        
    Returns:
        bool: True si el surtidor está disponible, False en caso contrario
    """
    global ultimo_estado, es_primera_ejecucion
    
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
        # Registrar que no existe la estación
        if nombre_surtidor in ultimo_estado:
            logger.info(f"El surtidor {nombre_surtidor} ya no aparece en la lista")
        return False
    
    # Verificar si hay combustible disponible
    try:
        existencia_str = estacion["existencia_litros"].replace(',', '').replace('.', '')
        existencia_str = ''.join(filter(str.isdigit, existencia_str))
        existencia = float(existencia_str) if existencia_str else 0
        
        # Si hay combustible disponible
        disponible = existencia > 0
        
        # Obtener el nombre exacto de la estación
        key = estacion["nombre"]
        
        # Verificar si tenemos registro previo y comparar saldos
        if key in ultimo_estado:
            saldo_anterior = ultimo_estado[key].get("saldo", 0)
            estado_anterior = ultimo_estado[key].get("disponible", False)
            
            # Determinar si hay nueva carga (saldo actual > saldo anterior)
            hay_nueva_carga = existencia > saldo_anterior
            
            # Actualizar el estado con el nuevo saldo
            ultimo_estado[key] = {
                "disponible": disponible,
                "saldo": existencia,
                "ultima_actualizacion": datetime.now()
            }
            
            # Enviar alerta solo si:
            # 1. No es la primera ejecución (ya pasaron 5 minutos)
            # 2. Hay combustible disponible
            # 3. Hay nueva carga (saldo aumentó) o la estación no estaba disponible antes
            # 4. Se ha habilitado el envío de alertas
            if not es_primera_ejecucion and disponible and (hay_nueva_carga or not estado_anterior) and enviar_alertas:
                mensaje = f"""
🚨 <b>ALERTA DE COMBUSTIBLE DISPONIBLE</b> 🚨

📍 <b>Estación:</b> {estacion["nombre"]}
⛽ <b>Disponible:</b> {estacion["existencia_litros"]}
🕒 <b>Actualizado:</b> {estacion["hora_medicion"]}
📌 <b>Dirección:</b> {estacion["direccion"]}

<i>Verificado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>
"""
                enviar_mensaje_telegram(mensaje)
                logger.info(f"Notificación enviada para {estacion['nombre']} - Nueva carga detectada")
                
                # Realizar llamada telefónica
                mensaje_llamada = f"Alerta de combustible disponible en {estacion['nombre']} con {estacion['existencia_litros']}"
                resultado_llamada = realizar_llamada_telefonica(mensaje_llamada)
                if resultado_llamada:
                    logger.info(f"Llamada telefónica realizada con éxito para {estacion['nombre']}")
                else:
                    logger.warning(f"No se pudo realizar la llamada telefónica para {estacion['nombre']}")
        else:
            # Primera vez que vemos esta estación
            ultimo_estado[key] = {
                "disponible": disponible,
                "saldo": existencia,
                "ultima_actualizacion": datetime.now()
            }
            
            # No enviamos alerta en la primera ejecución, solo registramos
            if not es_primera_ejecucion and disponible and enviar_alertas:
                mensaje = f"""
🚨 <b>ALERTA DE COMBUSTIBLE DISPONIBLE</b> 🚨

📍 <b>Estación:</b> {estacion["nombre"]}
⛽ <b>Disponible:</b> {estacion["existencia_litros"]}
🕒 <b>Actualizado:</b> {estacion["hora_medicion"]}
📌 <b>Dirección:</b> {estacion["direccion"]}

<i>Verificado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>
"""
                # Enviar mensaje a Telegram
                enviar_mensaje_telegram(mensaje)
                logger.info(f"Notificación enviada para {estacion['nombre']} - Nueva estación detectada")
                
                # Realizar llamada telefónica
                mensaje_llamada = f"Alerta de combustible disponible en {estacion['nombre']} con {estacion['existencia_litros']}"
                resultado_llamada = realizar_llamada_telefonica(mensaje_llamada)
                if resultado_llamada:
                    logger.info(f"Llamada telefónica realizada con éxito para {estacion['nombre']}")
                else:
                    logger.warning(f"No se pudo realizar la llamada telefónica para {estacion['nombre']}")
        
        # Registrar estado actual
        if disponible:
            logger.info(f"El surtidor {estacion['nombre']} está disponible con {estacion['existencia_litros']}")
        else:
            logger.info(f"El surtidor {estacion['nombre']} no está disponible")
        
        return disponible
        
    except Exception as e:
        logger.error(f"Error al verificar disponibilidad: {e}")
        return False


def monitor_continuo(nombres_surtidores):
    """
    Monitorea continuamente uno o varios surtidores específicos cada 5 minutos.
    
    Args:
        nombres_surtidores: Lista de nombres de surtidores a monitorear
    """
    global es_primera_ejecucion
    
    # Convertir a lista si es un solo nombre
    if isinstance(nombres_surtidores, str):
        nombres_surtidores = [nombres_surtidores]
    
    # Crear una cadena formateada para mostrar los nombres
    nombres_formateados = ", ".join([f"<b>{nombre}</b>" for nombre in nombres_surtidores])
    
    logger.info(f"Biopetrol Monitor v{__version__} iniciado")
    logger.info(f"Iniciando monitoreo de los surtidores: {', '.join(nombres_surtidores)} cada {CHECK_INTERVAL//60} minutos")
    
    # Enviar mensaje inicial
    mensaje_inicial = f"""
🔄 <b>MONITOREO INICIADO</b>

Estoy monitoreando los siguientes surtidores cada 5 minutos:
{nombres_formateados}

Recibirás una notificación cuando se detecte una nueva carga de combustible.

<i>Iniciado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>
"""
    enviar_mensaje_telegram(mensaje_inicial)
    
    # Verificación inicial - solo actualiza el estado, no envía alertas
    logger.info("Realizando verificación inicial (sin enviar alertas)...")
    for nombre in nombres_surtidores:
        verificar_surtidor(nombre, enviar_alertas=False)
    
    # Cambiar el flag después de la primera ejecución
    es_primera_ejecucion = False
    
    # Bucle de monitoreo continuo
    try:
        while True:
            # Esperar el intervalo de tiempo
            logger.info(f"Esperando {CHECK_INTERVAL//60} minutos para la próxima verificación...")
            time.sleep(CHECK_INTERVAL)
            
            # Verificar nuevamente - ahora sí envía alertas si corresponde
            logger.info("Realizando verificación periódica...")
            for nombre in nombres_surtidores:
                verificar_surtidor(nombre, enviar_alertas=True)
    except KeyboardInterrupt:
        logger.info("Monitoreo detenido por el usuario")
        enviar_mensaje_telegram(f"⛔ <b>MONITOREO DETENIDO</b>\n\nEl monitoreo de los surtidores {nombres_formateados} ha sido detenido manualmente.")
    except Exception as e:
        logger.error(f"Error en el bucle de monitoreo: {e}")
        enviar_mensaje_telegram(f"❌ <b>ERROR DE MONITOREO</b>\n\nEl monitoreo de los surtidores {nombres_formateados} se ha detenido debido a un error:\n<code>{str(e)}</code>")


def imprimir_info_version():
    """
    Imprime la información de versión del script.
    """
    print(f"\nBiopetrol Monitor v{__version__}")
    print(f"Autor: {__author__}")
    print(f"Licencia: {__license__}")
    print(f"Python: {platform.python_version()}")
    print(f"Sistema: {platform.system()} {platform.release()}\n")


def main():
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Monitor de surtidores Biopetrol con notificaciones Telegram')
    parser.add_argument('--surtidor', type=str, help='Nombre del surtidor a monitorear. Para múltiples surtidores, separarlos con "-" (ej: CHACO-FORMOSA-CORRIENTES)')
    parser.add_argument('--version', '-v', action='store_true', help='Muestra la versión del programa y sale')
    
    args = parser.parse_args()
    
    # Mostrar versión si se solicita
    if args.version:
        imprimir_info_version()
        sys.exit(0)
    
    # Verificar que se proporcionó el argumento surtidor
    if not args.surtidor:
        parser.error("Se requiere el argumento --surtidor")
        sys.exit(1)
    
    # Imprimir información de versión al inicio
    imprimir_info_version()
    
    # Verificar que las variables de entorno necesarias estén configuradas
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Error: Token de bot o ID de chat de Telegram no configurados")
        logger.error("Por favor, configure las variables en el archivo .env")
        logger.error("Consulte el archivo .env.example para ver las variables requeridas")
        sys.exit(1)
        
    if not CALLMEBOT_USER:
        logger.error("Error: Usuario de CallMeBot no configurado")
        logger.error("Por favor, configure las variables en el archivo .env")
        logger.error("Consulte el archivo .env.example para ver las variables requeridas")
        sys.exit(1)
    
    # Procesar nombres de surtidores (pueden ser múltiples separados por "-")
    nombres_surtidores = [nombre.strip() for nombre in args.surtidor.split('-')]
    logger.info(f"Surtidores a monitorear: {nombres_surtidores}")
    
    # Iniciar monitoreo continuo
    monitor_continuo(nombres_surtidores)


if __name__ == "__main__":
    main()