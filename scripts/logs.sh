#!/usr/bin/env bash

SERVICE="${1:-all}"

case "$SERVICE" in
    api)
        sudo journalctl -u dcs-api -f
        ;;
    ui)
        sudo journalctl -u dcs-ui -f
        ;;
    nginx)
        sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
        ;;
    all)
        sudo journalctl -u dcs-api -u dcs-ui -f
        ;;
    *)
        echo "Usage: $0 {api|ui|nginx|all}"
        exit 1
        ;;
esac
