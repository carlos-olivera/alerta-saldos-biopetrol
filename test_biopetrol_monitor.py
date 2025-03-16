#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test automatizado para biopetrol-monitor.py

Este script permite probar las funcionalidades de alerta y llamada telefónica
sin necesidad de esperar a que haya cambios reales en los surtidores.

Uso:
    python test_biopetrol_monitor.py         # Ejecutar tests automatizados
    python test_biopetrol_monitor.py --manual # Probar alertas reales
"""

import unittest
import sys
import os
import json
import logging
import time
import requests
from unittest.mock import patch, MagicMock
from io import StringIO
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env
load_dotenv()

# Configurar logging para tests
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BiopetrolTest")

# Importar el módulo a testear
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Importar el script como módulo (el nombre del archivo tiene guiones)
import importlib.util
spec = importlib.util.spec_from_file_location("bm", os.path.join(os.path.dirname(os.path.abspath(__file__)), "biopetrol-monitor.py"))
bm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bm)


class TestBiopetrolMonitor(unittest.TestCase):
    """Clase para testear las funcionalidades de Biopetrol Monitor"""
    
    def setUp(self):
        """Preparar el entorno para cada test"""
        # Resetear el estado global
        bm.ultimo_estado = {}
        bm.es_primera_ejecucion = True
        
        # Datos de prueba para simular estaciones
        self.estaciones_test = [
            {
                "nombre": "CHACO",
                "existencia_litros": "5000",
                "hora_medicion": "17:30",
                "direccion": "Av. Test 123",
                "coordenadas": "-27.451,-58.986"
            },
            {
                "nombre": "FORMOSA",
                "existencia_litros": "0",
                "hora_medicion": "17:25",
                "direccion": "Calle Prueba 456",
                "coordenadas": "-26.184,-58.173"
            }
        ]
    
    @patch.object(bm, 'extraer_datos')
    @patch.object(bm, 'enviar_mensaje_telegram')
    @patch.object(bm, 'realizar_llamada_telefonica')
    def test_verificar_surtidor_nueva_carga(self, mock_llamada, mock_telegram, mock_extraer):
        """Test para verificar detección de nueva carga y envío de alertas"""
        # Configurar el mock para simular datos de estaciones
        mock_extraer.return_value = self.estaciones_test
        mock_telegram.return_value = True
        mock_llamada.return_value = True
        
        # Primera ejecución - no debe enviar alertas
        resultado = bm.verificar_surtidor("CHACO", enviar_alertas=False)
        self.assertTrue(resultado)
        mock_telegram.assert_not_called()
        mock_llamada.assert_not_called()
        
        # Cambiar el flag de primera ejecución
        bm.es_primera_ejecucion = False
        
        # Simular aumento de saldo
        estaciones_actualizadas = self.estaciones_test.copy()
        estaciones_actualizadas[0] = dict(self.estaciones_test[0])
        estaciones_actualizadas[0]["existencia_litros"] = "8000"
        mock_extraer.return_value = estaciones_actualizadas
        
        resultado = bm.verificar_surtidor("CHACO", enviar_alertas=True)
        
        # Verificar que se enviaron las alertas
        self.assertTrue(resultado)
        mock_telegram.assert_called_once()
        mock_llamada.assert_called_once()
    
    @patch.object(bm, 'extraer_datos')
    @patch.object(bm, 'enviar_mensaje_telegram')
    @patch.object(bm, 'realizar_llamada_telefonica')
    def test_verificar_surtidor_sin_cambios(self, mock_llamada, mock_telegram, mock_extraer):
        """Test para verificar que no se envían alertas si no hay cambios"""
        # Configurar el mock para simular datos de estaciones
        mock_extraer.return_value = self.estaciones_test
        
        # Primera ejecución - actualizar estado
        bm.verificar_surtidor("CHACO", enviar_alertas=False)
        
        # Cambiar el flag de primera ejecución
        bm.es_primera_ejecucion = False
        
        # Segunda ejecución sin cambios en el saldo
        resultado = bm.verificar_surtidor("CHACO", enviar_alertas=True)
        
        # Verificar que no se enviaron alertas
        self.assertTrue(resultado)
        mock_telegram.assert_not_called()
        mock_llamada.assert_not_called()
    
    @patch.object(bm, 'extraer_datos')
    @patch.object(bm, 'enviar_mensaje_telegram')
    @patch.object(bm, 'realizar_llamada_telefonica')
    def test_verificar_multiples_surtidores(self, mock_llamada, mock_telegram, mock_extraer):
        """Test para verificar monitoreo de múltiples surtidores"""
        # Configurar el mock para simular datos de estaciones
        mock_extraer.return_value = self.estaciones_test
        mock_telegram.return_value = True
        mock_llamada.return_value = True
        
        # Verificar cada surtidor individualmente para establecer el estado inicial
        bm.verificar_surtidor("CHACO", enviar_alertas=False)
        bm.verificar_surtidor("FORMOSA", enviar_alertas=False)
        
        # Cambiar el flag de primera ejecución
        bm.es_primera_ejecucion = False
        
        # Simular que ambos surtidores tienen combustible
        estaciones_actualizadas = self.estaciones_test.copy()
        estaciones_actualizadas[0] = dict(self.estaciones_test[0])
        estaciones_actualizadas[1] = dict(self.estaciones_test[1])
        estaciones_actualizadas[0]["existencia_litros"] = "7000"
        estaciones_actualizadas[1]["existencia_litros"] = "3000"
        mock_extraer.return_value = estaciones_actualizadas
        
        # Verificar cada surtidor por separado
        resultado1 = bm.verificar_surtidor("CHACO", enviar_alertas=True)
        resultado2 = bm.verificar_surtidor("FORMOSA", enviar_alertas=True)
        
        # Verificar que se enviaron las alertas para ambos surtidores
        self.assertTrue(resultado1)
        self.assertTrue(resultado2)
        self.assertEqual(mock_telegram.call_count, 2)
        self.assertEqual(mock_llamada.call_count, 2)
    
    @patch('requests.get')
    def test_realizar_llamada_telefonica_exitosa(self, mock_get):
        """Test para verificar llamada telefónica exitosa"""
        # Configurar mock para simular respuesta exitosa
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Call queued successfully"
        mock_get.return_value = mock_response
        
        resultado = bm.realizar_llamada_telefonica("Test mensaje")
        
        # Verificar que la llamada fue exitosa
        self.assertTrue(resultado)
        mock_get.assert_called_once()
        
        # Verificar parámetros de la llamada
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], bm.CALLMEBOT_URL)
        self.assertEqual(kwargs['params']['text'], "Test mensaje")
        self.assertEqual(kwargs['params']['user'], bm.CALLMEBOT_USER)
    
    @patch('time.sleep')  # Mock sleep para no esperar en tests
    @patch('requests.get')
    def test_realizar_llamada_telefonica_con_reintentos(self, mock_get, mock_sleep):
        """Test para verificar reintentos en llamada telefónica"""
        # Este test simula una situación donde la primera llamada falla con 'línea ocupada'
        # y la segunda llamada tiene éxito. Esto es solo para probar la lógica de reintentos
        # y no significa que haya un problema real con la API.
        
        # Primera respuesta: línea ocupada (simulada)
        mock_busy = MagicMock()
        mock_busy.status_code = 200
        mock_busy.text = "Line busy, try again later"
        
        # Segunda respuesta: éxito
        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.text = "Call queued successfully"
        
        # Configurar el mock para devolver primero 'ocupado' y luego 'éxito'
        mock_get.side_effect = [mock_busy, mock_success]
        
        # Ejecutar la función que estamos probando
        resultado = bm.realizar_llamada_telefonica("Test mensaje")
        
        # Verificar que la llamada fue exitosa después del reintento
        self.assertTrue(resultado)
        self.assertEqual(mock_get.call_count, 2)  # Verificar que se hicieron dos intentos
        mock_sleep.assert_called_once()  # Verificar que se esperó entre intentos


def test_manual_alerta():
    """Función para probar manualmente el envío de alertas"""
    print("\n=== Prueba Manual de Alertas ===")
    
    # Crear una estación de prueba
    estacion_prueba = {
        "nombre": "ESTACION_TEST",
        "existencia_litros": "10000",
        "hora_medicion": "17:45",
        "direccion": "Dirección de Prueba",
        "coordenadas": None
    }
    
    # Enviar mensaje de Telegram
    mensaje = f"""
🚨 <b>ALERTA DE PRUEBA</b> 🚨

📍 <b>Estación:</b> {estacion_prueba["nombre"]}
⛽ <b>Disponible:</b> {estacion_prueba["existencia_litros"]}
🕒 <b>Actualizado:</b> {estacion_prueba["hora_medicion"]}
📌 <b>Dirección:</b> {estacion_prueba["direccion"]}

<i>Esta es una alerta de prueba generada manualmente</i>
"""
    
    print("Enviando mensaje de prueba a Telegram...")
    if bm.enviar_mensaje_telegram(mensaje):
        print("✅ Mensaje enviado correctamente")
    else:
        print("❌ Error al enviar mensaje")
    
    # Realizar llamada telefónica
    print("Realizando llamada telefónica de prueba...")
    mensaje_llamada = f"Alerta de prueba. Esto es una prueba del sistema de monitoreo de combustible."
    if bm.realizar_llamada_telefonica(mensaje_llamada):
        print("✅ Llamada realizada correctamente")
    else:
        print("❌ Error al realizar llamada")


if __name__ == "__main__":
    print(f"Ejecutando tests para Biopetrol Monitor v{bm.__version__}")
    
    # Verificar argumentos
    if len(sys.argv) > 1 and sys.argv[1] == "--manual":
        test_manual_alerta()
    else:
        # Ejecutar suite de tests automáticos
        unittest.main(argv=['first-arg-is-ignored'], exit=False)
