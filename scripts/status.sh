#!/usr/bin/env bash

echo "=== DCS Service Status — $(date) ==="
echo ""

for svc in dcs-api dcs-ui nginx; do
    status=$(systemctl is-active "$svc" 2>/dev/null || echo "not found")
    if [ "$status" = "active" ]; then
        printf "  %-12s ✓ running\n" "$svc"
    else
        printf "  %-12s ✗ %s\n" "$svc" "$status"
    fi
done

echo ""

for container in dcs-postgres dcs-redis; do
    status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || echo "not found")
    if [ "$status" = "running" ]; then
        printf "  %-12s ✓ running\n" "$container"
    else
        printf "  %-12s ✗ %s\n" "$container" "$status"
    fi
done

echo ""
echo "Endpoints:"
curl -sf http://127.0.0.1:8000/health && echo "  API:   OK" || echo "  API:   FAILED"
curl -sf http://127.0.0.1:3000 > /dev/null 2>&1 && echo "  UI:    OK" || echo "  UI:    FAILED"
curl -sf http://127.0.0.1:80 > /dev/null 2>&1 && echo "  nginx: OK" || echo "  nginx: FAILED"
