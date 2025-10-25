#!/bin/bash

# test_happy_path.sh
# Este script prueba el ciclo de vida completo de un workflow:
# 1. Se autentica para obtener un token.
# 2. Crea un nuevo workflow, que debe iniciar en estado 'en_espera'.
# 3. Verifica el estado inicial.
# 4. Espera a que el worker procese el workflow.
# 5. Verifica que el estado final sea 'completado'.

# --- Configuración ---
API_BASE_URL="http://127.0.0.1:8000"

# Colores para una salida más legible
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}--- Iniciando prueba del Happy Path para Workflows ---${NC}"

# 1. Obtener token de autenticación
echo "1. Obteniendo token de autenticación..."
TOKEN=$(curl -s -X POST "${API_BASE_URL}/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "demo123"}' | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
    echo -e "${RED}Error: No se pudo obtener el token. Asegúrate de que la API esté corriendo en ${API_BASE_URL}.${NC}"
    exit 1
fi
echo -e "${GREEN}Token obtenido exitosamente.${NC}\n"


# 2. Crear un nuevo workflow
echo "2. Creando un nuevo workflow..."
CREATE_RESPONSE=$(curl -s -X POST "${API_BASE_URL}/workflow" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Workflow Happy Path Test", "definition": {"steps": []}}')

WORKFLOW_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id')
echo "Respuesta de creación: $CREATE_RESPONSE"
echo -e "${GREEN}Workflow creado con ID: $WORKFLOW_ID${NC}\n"


# 3. Verificar el estado inicial
echo "3. Verificando estado inicial del workflow (debe ser 'en_espera')..."
sleep 1 # Pequeña pausa para asegurar que la transacción se completó
INITIAL_STATUS_RESPONSE=$(curl -s -X GET "${API_BASE_URL}/workflows/$WORKFLOW_ID/status" -H "Authorization: Bearer $TOKEN")
INITIAL_STATUS=$(echo "$INITIAL_STATUS_RESPONSE" | jq -r '.status')

if [ "$INITIAL_STATUS" == "en_espera" ]; then
    echo -e "${GREEN}OK: El estado inicial es 'en_espera', como se esperaba.${NC}\n"
else
    echo -e "${RED}FALLO: El estado inicial es '$INITIAL_STATUS', pero se esperaba 'en_espera'.${NC}"
    exit 1
fi

# 4. Esperar a que el worker procese la tarea
echo -e "4. Esperando 10 segundos para que el worker procese el workflow..."
echo -e "(El worker debería cambiar el estado a 'en_progreso' y luego a 'completado')${NC}"
sleep 10

# 5. Verificar el estado final
echo -e "\n5. Verificando estado final del workflow (debe ser 'completado')..."
FINAL_STATUS_RESPONSE=$(curl -s -X GET "${API_BASE_URL}/workflows/$WORKFLOW_ID/status" -H "Authorization: Bearer $TOKEN")
FINAL_STATUS=$(echo "$FINAL_STATUS_RESPONSE" | jq -r '.status')

if [ "$FINAL_STATUS" == "completado" ]; then
    echo -e "${GREEN}✅ ¡ÉXITO! El estado final es 'completado'. El ciclo de vida del workflow funciona correctamente.${NC}"
else
    echo -e "${RED}FALLO: El estado final es '$FINAL_STATUS', pero se esperaba 'completado'. Revisa el log del worker.${NC}"
    exit 1
fi