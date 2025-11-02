#!/bin/bash
# Manage data cache files for testing
# Usage: ./manage_cache.sh <action> <symbol> <timeframe>
#
# Actions:
#   backup   - Backup existing cache file
#   restore  - Restore backed up cache file
#   delete   - Delete cache file (keeps backup if exists)
#   clean    - Remove both cache and backup
#
# Examples:
#   ./manage_cache.sh backup EURUSD 1h
#   ./manage_cache.sh restore EURUSD 1h
#   ./manage_cache.sh delete AAPL 1d
#   ./manage_cache.sh clean EURUSD 1h

set -e

ACTION="$1"
SYMBOL="$2"
TIMEFRAME="$3"

if [ -z "$ACTION" ] || [ -z "$SYMBOL" ] || [ -z "$TIMEFRAME" ]; then
  echo "Usage: $0 <action> <symbol> <timeframe>"
  echo ""
  echo "Actions:"
  echo "  backup   - Backup existing cache file"
  echo "  restore  - Restore backed up cache file"
  echo "  delete   - Delete cache file (keeps backup if exists)"
  echo "  clean    - Remove both cache and backup"
  echo ""
  echo "Examples:"
  echo "  $0 backup EURUSD 1h"
  echo "  $0 restore EURUSD 1h"
  exit 1
fi

CACHE_FILE="data/${SYMBOL}_${TIMEFRAME}.csv"
BACKUP_FILE="data/${SYMBOL}_${TIMEFRAME}.csv.backup"

case "$ACTION" in
  backup)
    if [ -f "$CACHE_FILE" ]; then
      mv "$CACHE_FILE" "$BACKUP_FILE"
      echo "✅ Backed up: $CACHE_FILE → $BACKUP_FILE"
    else
      echo "⚠️  No cache file to backup: $CACHE_FILE"
    fi
    ;;

  restore)
    if [ -f "$BACKUP_FILE" ]; then
      mv "$BACKUP_FILE" "$CACHE_FILE"
      echo "✅ Restored: $BACKUP_FILE → $CACHE_FILE"
    else
      echo "❌ No backup file to restore: $BACKUP_FILE"
      exit 1
    fi
    ;;

  delete)
    if [ -f "$CACHE_FILE" ]; then
      rm "$CACHE_FILE"
      echo "✅ Deleted cache file: $CACHE_FILE"
      if [ -f "$BACKUP_FILE" ]; then
        echo "ℹ️  Backup still exists: $BACKUP_FILE"
      fi
    else
      echo "⚠️  No cache file to delete: $CACHE_FILE"
    fi
    ;;

  clean)
    REMOVED=0
    if [ -f "$CACHE_FILE" ]; then
      rm "$CACHE_FILE"
      echo "✅ Deleted cache file: $CACHE_FILE"
      REMOVED=1
    fi
    if [ -f "$BACKUP_FILE" ]; then
      rm "$BACKUP_FILE"
      echo "✅ Deleted backup file: $BACKUP_FILE"
      REMOVED=1
    fi
    if [ $REMOVED -eq 0 ]; then
      echo "⚠️  No files to clean for $SYMBOL $TIMEFRAME"
    fi
    ;;

  *)
    echo "❌ Unknown action: $ACTION"
    echo "Valid actions: backup, restore, delete, clean"
    exit 1
    ;;
esac
