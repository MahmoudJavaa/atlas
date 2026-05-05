#!/bin/bash
# Atlas Ollama entrypoint — starts the server, pulls the model if needed, then waits.
set -e

echo "[Atlas/Ollama] Starting Ollama server..."
/bin/ollama serve &
OLLAMA_PID=$!

# Wait for the server to accept connections
echo "[Atlas/Ollama] Waiting for server to be ready..."
until /bin/ollama list >/dev/null 2>&1; do
    sleep 1
done
echo "[Atlas/Ollama] Server is ready."

# Pull llama3.2:3b only if it isn't already on disk (skips on restart)
if /bin/ollama list 2>/dev/null | grep -q "llama3.2"; then
    echo "[Atlas/Ollama] Model llama3.2:3b already present — skipping download."
else
    echo "[Atlas/Ollama] Downloading llama3.2:3b (~2 GB, one-time download)..."
    /bin/ollama pull llama3.2:3b
    echo "[Atlas/Ollama] Model download complete."
fi

echo "[Atlas/Ollama] AI engine ready. Atlas is fully offline."

# Keep the container alive
wait $OLLAMA_PID
