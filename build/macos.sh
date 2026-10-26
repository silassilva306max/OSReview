#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec bash build/Gerar_Instalador_macOS.sh
