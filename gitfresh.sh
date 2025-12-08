#!/bin/bash

# Script para resetear Git y crear nueva rama de trabajo o solo sincronizar
# Uso: ./gitfresh.sh <nombre-de-la-rama>
# Uso: ./gitfresh.sh --sync (solo sincronizar sin crear rama)

set -e  # Salir si algún comando falla

# Función para mostrar mensajes con colores
print_step() {
    echo "🔄 $1"
}

print_success() {
    echo "✅ $1"
}

print_warning() {
    echo "⚠️  $1"
}

print_info() {
    echo "ℹ️  $1"
}

# Función para mostrar ayuda
show_help() {
    echo "🛠️  Uso del script gitfresh.sh:"
    echo ""
    echo "   Para crear nueva rama:"
    echo "   ./gitfresh.sh <nombre-de-la-rama>"
    echo "   Ejemplo: ./gitfresh.sh feat/admin-users"
    echo ""
    echo "   Para solo sincronizar:"
    echo "   ./gitfresh.sh --sync"
    echo ""
    echo "   Para mostrar ayuda:"
    echo "   ./gitfresh.sh --help"
}

# Verificar parámetros
if [ $# -eq 0 ]; then
    echo "❌ Error: Debes proporcionar un parámetro"
    show_help
    exit 1
fi

# Verificar si es modo ayuda
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    show_help
    exit 0
fi

# Verificar si es modo sync
SOLO_SYNC=false
if [ "$1" = "--sync" ]; then
    SOLO_SYNC=true
    echo "🔄 Iniciando solo sincronización..."
    echo "================================"
else
    NUEVA_RAMA="$1"
    echo "🚀 Iniciando reset de Git y creación de nueva rama: $NUEVA_RAMA"
    echo "=================================================="
fi

# Función común para sincronización
sync_repository() {
    # 1) Actualizar referencias
    print_step "Paso 1: Actualizando referencias..."
    git fetch origin --prune
    print_success "Referencias actualizadas"

    # 2) Ir a main y traer lo último
    print_step "Paso 2: Cambiando a main y actualizando..."
    git checkout main
    git pull --ff-only origin main
    print_success "Branch main actualizada"

    # 3) Sincronizar ramas remotas localmente
    print_step "Paso 3: Sincronizando ramas remotas..."
    
    # Obtener todas las ramas remotas
    RAMAS_REMOTAS=$(git branch -r | grep -v 'HEAD' | grep -v 'main' | sed 's/origin\///' | sed 's/^[ \t]*//' || true)
    
    if [ -n "$RAMAS_REMOTAS" ]; then
        echo "$RAMAS_REMOTAS" | while read -r rama; do
            if [ -n "$rama" ]; then
                # Verificar si la rama local ya existe
                if git branch --list "$rama" | grep -q "$rama"; then
                    print_info "Actualizando rama existente: $rama"
                    git checkout "$rama" 2>/dev/null || print_warning "No se pudo cambiar a $rama"
                    git pull origin "$rama" 2>/dev/null || print_warning "No se pudo actualizar $rama"
                else
                    print_info "Creando nueva rama local: $rama"
                    git checkout -b "$rama" "origin/$rama" 2>/dev/null || print_warning "No se pudo crear rama local $rama"
                fi
            fi
        done
        git checkout main
        print_success "Ramas remotas sincronizadas"
    else
        print_success "No hay ramas remotas adicionales para sincronizar"
    fi

    # 4) Limpiar ramas remotas obsoletas
    print_step "Paso 4: Limpiando ramas remotas obsoletas..."
    git remote prune origin
    print_success "Ramas remotas obsoletas limpiadas"

    # 5) Mostrar estado actual
    print_step "Estado actual del repositorio:"
    echo ""
    echo "📋 Ramas locales:"
    git branch --format='  %(refname:short)'
    echo ""
    echo "🌐 Ramas remotas:"
    git branch -r --format='  %(refname:short)'
}

# Ejecutar sincronización
sync_repository

# Si es solo sync, terminar aquí
if [ "$SOLO_SYNC" = true ]; then
    echo ""
    echo "🎉 ¡Sincronización completada!"
    echo "📍 Ahora estás en la rama: main"
    echo ""
    echo "Resumen de lo realizado:"
    echo "- ✅ Referencias actualizadas"
    echo "- ✅ Main actualizado"
    echo "- ✅ Ramas remotas sincronizadas localmente"
    echo "- ✅ Ramas remotas obsoletas limpiadas"
    exit 0
fi

# Continuar con creación de nueva rama
echo ""
print_step "Continuando con creación de nueva rama..."

# 6) Eliminar TODAS las demás ramas locales (excepto main)
print_step "Paso 5: Eliminando todas las ramas locales (excepto main)..."
RAMAS_A_ELIMINAR=$(git for-each-ref --format='%(refname:short)' refs/heads/ | grep -v '^main$' || true)

if [ -n "$RAMAS_A_ELIMINAR" ]; then
    echo "$RAMAS_A_ELIMINAR" | while read -r rama; do
        if [ -n "$rama" ]; then
            echo "  🗑️  Eliminando rama: $rama"
            git branch -D "$rama" 2>/dev/null || print_warning "No se pudo eliminar la rama: $rama"
        fi
    done
    print_success "Ramas locales eliminadas"
else
    print_success "No hay ramas adicionales para eliminar"
fi

# 7) Crear la nueva rama de trabajo
print_step "Paso 6: Creando nueva rama '$NUEVA_RAMA'..."
git checkout -b "$NUEVA_RAMA"
print_success "Nueva rama '$NUEVA_RAMA' creada"

# 8) Subir y establecer tracking
print_step "Paso 7: Subiendo rama y estableciendo tracking..."
git push -u origin "$NUEVA_RAMA"
print_success "Rama subida y tracking establecido"

echo ""
echo "🎉 ¡Proceso completado exitosamente!"
echo "📍 Ahora estás en la rama: $NUEVA_RAMA"
echo "🔗 Tracking configurado con: origin/$NUEVA_RAMA"
echo ""
echo "Resumen de lo realizado:"
echo "- ✅ Referencias actualizadas"
echo "- ✅ Main actualizado"
echo "- ✅ Ramas remotas sincronizadas"
echo "- ✅ Ramas locales limpiadas"
echo "- ✅ Ramas remotas obsoletas limpiadas"
echo "- ✅ Nueva rama '$NUEVA_RAMA' creada y sincronizada"