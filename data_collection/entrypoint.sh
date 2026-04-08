#!/bin/bash
set -e

echo "=== Starting Data Collection Scheduler ==="
echo ""
echo "Current directory: $(pwd)"
echo ""
echo "Files in /app:"
ls -la /app
echo ""
echo "Files in /app/collectors (if exists):"
ls -la /app/collectors 2>/dev/null || echo "ERROR: /app/collectors not found!"
echo ""
echo "Files in /app/schedulers (if exists):"
ls -la /app/schedulers 2>/dev/null || echo "ERROR: /app/schedulers not found!"
echo ""
echo "PYTHONPATH: $PYTHONPATH"
echo "Python version: $(python --version)"
echo ""
echo "Python sys.path:"
python -c "import sys; print('\n'.join(sys.path))"
echo ""
echo "=== Starting application ==="
echo ""

# Execute the scheduler
exec python -u -m schedulers.data_scheduler
