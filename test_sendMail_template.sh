#!/bin/bash

# =============================================================================
# Test Templates Script - Envío automático de TODOS los templates disponibles
# =============================================================================

# Configuración
API_BASE="http://localhost:8000"
API_KEY="notify_api_key_abc123def456"
CONTENT_TYPE="application/json"

# Correos fijos
TO_EMAILS=("vsoto@tecnocomp.cl")
CC_EMAILS=("blk.zeus@gmail.com" "vasotosoto@gmail.com")

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Variables globales
declare -a TEMPLATES_LIST

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

print_header() { echo -e "\n${BLUE}================================================${NC}\n${BLUE}  $1${NC}\n${BLUE}================================================${NC}\n"; }
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error()   { echo -e "${RED}✗ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_info()    { echo -e "${CYAN}ℹ $1${NC}"; }

# Verificar conectividad
check_api() {
    echo "Verificando conectividad con API..."
    HEALTH=$(curl -s "${API_BASE}/healthz" 2>/dev/null)
    if [ $? -eq 0 ]; then
        print_success "API disponible en ${API_BASE}"
        return 0
    else
        print_error "No se puede conectar a la API en ${API_BASE}"
        return 1
    fi
}

# Obtener lista de templates
load_templates() {
    print_info "Obteniendo templates del servidor..."
    TEMPLATES_RESPONSE=$(curl -s "${API_BASE}/api/templates" -H "X-API-Key: ${API_KEY}" 2>/dev/null)
    
    if echo "$TEMPLATES_RESPONSE" | jq -e '.templates' >/dev/null 2>&1; then
        TEMPLATES_LIST=($(echo "$TEMPLATES_RESPONSE" | jq -r '.templates[]?.template_id // empty' 2>/dev/null))
    else
        print_error "Respuesta del servidor no tiene el formato esperado"
        echo "Respuesta recibida: $TEMPLATES_RESPONSE"
        return 1
    fi

    if [ ${#TEMPLATES_LIST[@]} -eq 0 ]; then
        print_error "No se encontraron templates en el servidor"
        return 1
    fi

    print_success "Encontrados ${#TEMPLATES_LIST[@]} templates"
    return 0
}

# Info de un template
get_template_info() {
    local template_id=$1
    curl -s "${API_BASE}/api/templates/${template_id}/info" -H "X-API-Key: ${API_KEY}" 2>/dev/null
}

# Convertir emails a JSON
emails_to_json() {
    local emails=($@)
    local json="["
    for i in "${!emails[@]}"; do
        [ $i -gt 0 ] && json+=","
        json+="\"${emails[$i]}\""
    done
    echo "$json]"
}

# Generar variables de prueba
generate_template_vars() {
    local template_id=$1
    local template_info=$2
    local required_vars=$(echo "$template_info" | jq -r '.required_variables[]?' 2>/dev/null)
    local example_data=$(echo "$template_info" | jq -r '.example_usage' 2>/dev/null)
    if [ "$example_data" != "null" ] && [ -n "$example_data" ]; then
        echo "$example_data"
    else
        generate_default_vars "$template_id" "$required_vars"
    fi
}

generate_default_vars() {
    local template_id=$1
    local required_vars=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local user=$(whoami)
    local hostname=$(hostname)
    local vars_json="{"
    local first=true
    
    while IFS= read -r var; do
        [ -z "$var" ] && continue
        [ "$first" = false ] && vars_json+=","
        first=false
        case "$var" in
            *fecha*|*date*|*timestamp*|*hora*) vars_json+="\"$var\": \"$timestamp\"" ;;
            *usuario*|*user*|*nombre*)          vars_json+="\"$var\": \"$user\"" ;;
            *host*|*server*)                    vars_json+="\"$var\": \"$hostname\"" ;;
            *total*|*count*|*cantidad*)         vars_json+="\"$var\": $((RANDOM % 100 + 1))" ;;
            *email*|*correo*)                   vars_json+="\"$var\": \"vsoto@tecnocomp.cl\"" ;;
            *estado*|*status*)                  vars_json+="\"$var\": \"OK\"" ;;
            *mensaje*|*descripcion*)            vars_json+="\"$var\": \"Mensaje de prueba generado para $template_id\"" ;;
            *)                                  vars_json+="\"$var\": \"Valor de prueba para $var\"" ;;
        esac
    done <<< "$required_vars"
    echo "$vars_json}"
}

# Enviar template
send_template() {
    local template_id=$1 
    local provider=$2 
    
    print_header "📨 Envío de template"
    print_info "Se usará el template: ${YELLOW}$template_id${NC}"
    
    local template_info=$(get_template_info "$template_id")
    [ -z "$template_info" ] && template_info="{}"
    
    local template_vars=$(generate_template_vars "$template_id" "$template_info")
    local template_name=$(echo "$template_info" | jq -r '.name // "Unknown"')
    
    echo -e "${CYAN}Nombre:${NC} $template_name"
    echo -e "${CYAN}Provider:${NC} $provider"
    echo -e "${CYAN}Variables:${NC}"
    echo "$template_vars" | jq . 2>/dev/null || echo "$template_vars"
    echo ""
    
    local to_json=$(emails_to_json "${TO_EMAILS[@]}")
    local cc_json=$(emails_to_json "${CC_EMAILS[@]}")
    
    local payload="{\"to\": $to_json, \"cc\": $cc_json, \"template_id\": \"$template_id\", \"vars\": $template_vars, \"provider\": \"$provider\"}"
    echo "DEBUG: Payload a enviar:"
    echo "$payload" | jq . 2>/dev/null || echo "$payload"
    
    local response=$(curl -s -X 'POST' "${API_BASE}/api/notify" \
        -H "X-API-Key: ${API_KEY}" -H "Content-Type: ${CONTENT_TYPE}" \
        -d "$payload")
    
    echo "DEBUG: Respuesta del servidor:"
    echo "$response" | jq . 2>/dev/null || echo "$response"
    
    local message_id=$(echo "$response" | jq -r '.message_id // empty')
    local status=$(echo "$response" | jq -r '.status // empty')
    local queue_id=$(echo "$response" | jq -r '.queue_id // empty')
    
    if [ -n "$message_id" ] && [ "$status" = "accepted" ]; then
        print_success "Envío exitoso"
        echo -e "${GREEN}→ ID Mensaje:${NC} $message_id"
        [ -n "$queue_id" ] && echo -e "${GREEN}→ ID Cola:${NC} $queue_id"
        echo "$message_id" > /tmp/last_message_id
        return 0
    else
        print_error "Fallo en el envío"
        echo "$response" | jq . 2>/dev/null || echo "$response"
        return 1
    fi
}

# Validar estado
validate_message_status() {
    local message_id=$1
    print_info "Validando estado de ID: $message_id"
    local response=$(curl -s "${API_BASE}/api/notify/status/$message_id" -H "X-API-Key: ${API_KEY}")
    echo "DEBUG: Respuesta del servidor:"
    echo "$response" | jq . 2>/dev/null || echo "$response"
}

# Enviar todos
send_all_templates() {
    local provider=$1 
    
    if [ ${#TEMPLATES_LIST[@]} -eq 0 ]; then
        print_error "No hay templates cargados"
        return 1
    fi
    
    local total=${#TEMPLATES_LIST[@]}
    local ok=0 
    local fail=0 
    local counter=1
    
    print_header "Enviando $total templates"
    
    for tid in "${TEMPLATES_LIST[@]}"; do
        echo -e "${CYAN}[$counter/$total] Template: $tid${NC}"
        if send_template "$tid" "$provider"; then 
            ok=$((ok+1))
        else 
            fail=$((fail+1))
        fi
        [ $counter -lt $total ] && sleep 2
        counter=$((counter+1))
    done
    
    print_header "Resumen"
    print_success "Exitosos: $ok"
    [ $fail -gt 0 ] && print_error "Fallidos: $fail" || print_info "Fallidos: $fail"
}

# Listar templates
show_templates_list() {
    if [ ${#TEMPLATES_LIST[@]} -eq 0 ]; then
        load_templates || return 1
    fi
    print_header "Templates disponibles"
    local counter=1
    for tid in "${TEMPLATES_LIST[@]}"; do
        local info=$(get_template_info "$tid")
        local name=$(echo "$info" | jq -r '.name // "Unknown"')
        echo -e "${CYAN}$counter)${NC} ${YELLOW}$tid${NC} - $name"
        counter=$((counter+1))
    done
}

# Seleccionar template
select_specific_template() {
    if [ ${#TEMPLATES_LIST[@]} -eq 0 ]; then
        load_templates || return 1
    fi
    show_templates_list >&2
    local total=${#TEMPLATES_LIST[@]}
    echo -en "\n${YELLOW}Selecciona template [1-$total]: ${NC}" >&2
    read choice
    echo -e "${CYAN}ℹ Ingresaste:${NC} $choice" >&2
    if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "$total" ]; then
        local idx=$((choice-1))
        echo "${TEMPLATES_LIST[$idx]}"
    else
        print_error "Selección inválida" >&2
        return 1
    fi
}

# Seleccionar provider
select_provider() {
    echo -e "\n${YELLOW}Selecciona proveedor:${NC}" >&2
    echo "  1) mailpit" >&2
    echo "  2) smtp_primary" >&2
    echo "  3) smtp_secondary" >&2
    echo -en "${YELLOW}Opción [1-3]: ${NC}" >&2
    read opt
    case "$opt" in
        1) echo "mailpit" ;;
        2) echo "smtp_primary" ;;
        3) echo "smtp_secondary" ;;
        *) echo "mailpit" ;;
    esac
}

# =============================================================================
# MENÚ PRINCIPAL
# =============================================================================
show_menu() {
    clear
    print_header "🚀 Test Templates - Notify API (Dinámico)"
    local count="No cargado"
    [ ${#TEMPLATES_LIST[@]} -gt 0 ] && count="${#TEMPLATES_LIST[@]}"
    echo -e "${BLUE}Estado:${NC} Templates cargados: ${YELLOW}$count${NC}"
    echo -e "${BLUE}API:${NC} ${CYAN}$API_BASE${NC}\n"
    echo -e "${BLUE}Opciones:${NC}"
    echo -e "  ${GREEN}A${NC}) Enviar TODOS"
    echo -e "  ${GREEN}S${NC}) Enviar uno"
    echo -e "  ${GREEN}L${NC}) Listar"
    echo -e "  ${GREEN}R${NC}) Recargar"
    echo -e "  ${GREEN}T${NC}) Test API"
    echo -e "  ${GREEN}Q${NC}) Salir\n"
}

main() {
    command -v jq >/dev/null || { print_error "jq no instalado"; exit 1; }
    command -v curl >/dev/null || { print_error "curl no instalado"; exit 1; }
    check_api || exit 1
    load_templates
    while true; do
        show_menu
        echo -en "${YELLOW}Selecciona opción: ${NC}"
        read choice
        case "$choice" in
            [Aa]) 
                provider=$(select_provider)
                send_all_templates "$provider"
                read -p "Enter para continuar..."
                ;;
            [Ss]) 
                tid=$(select_specific_template)
                [ -z "$tid" ] && { read -p "Enter para continuar..."; continue; }
                provider=$(select_provider)
                clear
                print_header "🚀 Enviando template seleccionado"
                print_info "Template elegido: $tid"
                sleep 1
                send_template "$tid" "$provider"
                last_message_id=$(cat /tmp/last_message_id 2>/dev/null)
                if [ -n "$last_message_id" ]; then
                    echo -en "\n${YELLOW}¿Quieres validar el estado del envío? (s/n): ${NC}"
                    read validate_choice
                    if [[ "$validate_choice" =~ ^[Ss]$ ]]; then
                        validate_message_status "$last_message_id"
                    fi
                fi
                read -p "Enter para volver al menú principal..."
                ;;
            [Ll]) show_templates_list; read -p "Enter para continuar...";;
            [Rr]) load_templates; read -p "Enter para continuar...";;
            [Tt]) check_api; read -p "Enter para continuar...";;
            [Qq]) print_success "¡Hasta luego!"; exit 0;;
            *) print_error "Opción inválida"; sleep 1;;
        esac
    done
}

if [ "${BASH_SOURCE[0]}" == "${0}" ]; then main "$@"; fi
