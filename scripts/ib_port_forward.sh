#!/bin/bash
#
# IB Gateway Port Forwarding Script
#
# This script creates a port forward from 4003 to localhost:4002
# allowing Docker containers to access IB Gateway via host.docker.internal:4003
#

PORT_FROM=4003
PORT_TO=4002
HOST_TO="127.0.0.1"

echo "🔌 Starting IB Gateway port forwarding..."
echo "   From: 0.0.0.0:${PORT_FROM} -> To: ${HOST_TO}:${PORT_TO}"
echo "   Container can connect via: host.docker.internal:${PORT_FROM}"
echo ""
echo "   Press Ctrl+C to stop"
echo ""

# Check if socat is available
if ! command -v socat &> /dev/null; then
    echo "❌ Error: socat is not installed"
    echo "   Install it with: brew install socat"
    exit 1
fi

# Check if port is already in use
if lsof -i :${PORT_FROM} &> /dev/null; then
    echo "⚠️  Warning: Port ${PORT_FROM} is already in use"
    echo "   Existing connections:"
    lsof -i :${PORT_FROM}
    echo ""
    read -p "   Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Start port forwarding
echo "✅ Port forwarding active..."
socat TCP-LISTEN:${PORT_FROM},bind=0.0.0.0,reuseaddr,fork TCP:${HOST_TO}:${PORT_TO}