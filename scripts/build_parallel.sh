#!/bin/bash
# Quick rebuild script for all Predator Analytics containers
# This runs builds in the background and shows progress

set -e

VERSION="13.0.0"
LOG_DIR="/tmp/predator-build-logs"

mkdir -p "$LOG_DIR"

echo "🐳 Starting parallel Docker builds..."
echo "📁 Logs will be saved to: $LOG_DIR"
echo ""

# Function to build in background
build_async() {
    local service=$1
    local logfile="$LOG_DIR/${service}.log"
    
    echo "🔨 Building ${service}... (log: ${logfile})"
    
    (
        cd "/Users/dima/Documents/Predator analitycs 13"
        docker build \
            -f "${service}/Dockerfile" \
            -t "predator-${service}:${VERSION}" \
            -t "predator-${service}:latest" \
            . > "$logfile" 2>&1
        
        if [ $? -eq 0 ]; then
            echo "✅ ${service} build completed successfully" >> "$logfile"
            echo "✅ ${service} - SUCCESS"
        else
            echo "❌ ${service} build failed" >> "$logfile"
            echo "❌ ${service} - FAILED (check log: ${logfile})"
            exit 1
        fi
    ) &
}

# Start builds
build_async "api"
build_async "agents"
build_async "voice"
build_async "model-router"

# Frontend uses npm, not poetry
echo "🔨 Building frontend... (log: $LOG_DIR/frontend.log)"
(
    cd "/Users/dima/Documents/Predator analitycs 13"
    docker build \
        -f "frontend/Dockerfile" \
        -t "predator-frontend:${VERSION}" \
        -t "predator-frontend:latest" \
        . > "$LOG_DIR/frontend.log" 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✅ frontend build completed successfully" >> "$LOG_DIR/frontend.log"
        echo "✅ frontend - SUCCESS"
    else
        echo "❌ frontend build failed" >> "$LOG_DIR/frontend.log"
        echo "❌ frontend - FAILED (check log: $LOG_DIR/frontend.log)"
        exit 1
    fi
) &

echo ""
echo "⏳ Waiting for all builds to complete..."
echo "💡 Tip: Monitor progress with: tail -f $LOG_DIR/*.log"
echo ""

# Wait for all background jobs
wait

echo ""
echo "🎉 All builds completed!"
echo ""
echo "📊 Built images:"
docker images | grep "predator-" | grep -E "${VERSION}|latest"
echo ""
echo "🧪 Test a container:"
echo "   docker run --rm -p 8000:8000 predator-api:latest"
