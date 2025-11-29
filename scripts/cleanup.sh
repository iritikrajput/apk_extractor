#!/bin/bash

# ==============================================
# APK Extractor - Cleanup Script
# ==============================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
RETENTION_DAYS=${APK_RETENTION_DAYS:-7}
DRY_RUN=false

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true ;;
        --days) RETENTION_DAYS="$2"; shift ;;
        --help)
            echo "Usage: $0 [--dry-run] [--days N]"
            echo ""
            echo "Options:"
            echo "  --dry-run    Show what would be deleted without deleting"
            echo "  --days N     Delete files older than N days (default: 7)"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

echo -e "${CYAN}=============================================="
echo "APK Extractor - Cleanup"
echo -e "==============================================${NC}"
echo ""
echo "Configuration:"
echo "  Retention: $RETENTION_DAYS days"
echo "  Dry Run: $DRY_RUN"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Directories to clean
PULLS_DIRS=(
    "$PROJECT_DIR/device-agent/pulls"
    "$PROJECT_DIR/docker-android/pulls"
)

# Clean APK files
echo -e "${YELLOW}Cleaning APK files older than $RETENTION_DAYS days...${NC}"

total_deleted=0
total_size=0

for pulls_dir in "${PULLS_DIRS[@]}"; do
    if [ -d "$pulls_dir" ]; then
        echo -e "\nChecking: $pulls_dir"
        
        # Find old package directories
        old_dirs=$(find "$pulls_dir" -maxdepth 1 -type d -mtime +$RETENTION_DAYS 2>/dev/null | grep -v "^$pulls_dir$" || true)
        
        if [ -n "$old_dirs" ]; then
            while IFS= read -r dir; do
                dir_size=$(du -sh "$dir" 2>/dev/null | cut -f1)
                pkg_name=$(basename "$dir")
                
                if [ "$DRY_RUN" = true ]; then
                    echo -e "  ${YELLOW}Would delete: $pkg_name ($dir_size)${NC}"
                else
                    echo -e "  ${RED}Deleting: $pkg_name ($dir_size)${NC}"
                    rm -rf "$dir"
                fi
                
                ((total_deleted++)) || true
            done <<< "$old_dirs"
        else
            echo -e "  ${GREEN}No old packages to clean${NC}"
        fi
    fi
done

# Clean log files older than retention period
echo -e "\n${YELLOW}Cleaning old log files...${NC}"

LOG_DIRS=(
    "$PROJECT_DIR/device-agent/logs"
    "$PROJECT_DIR/web-backend/logs"
    "$PROJECT_DIR/orchestrator/logs"
)

logs_deleted=0

for log_dir in "${LOG_DIRS[@]}"; do
    if [ -d "$log_dir" ]; then
        old_logs=$(find "$log_dir" -name "*.log" -mtime +$RETENTION_DAYS 2>/dev/null || true)
        
        if [ -n "$old_logs" ]; then
            while IFS= read -r log_file; do
                if [ "$DRY_RUN" = true ]; then
                    echo -e "  ${YELLOW}Would delete: $log_file${NC}"
                else
                    echo -e "  ${RED}Deleting: $log_file${NC}"
                    rm -f "$log_file"
                fi
                ((logs_deleted++)) || true
            done <<< "$old_logs"
        fi
    fi
done

# Clean Docker resources (optional)
if command -v docker &> /dev/null; then
    echo -e "\n${YELLOW}Cleaning Docker resources...${NC}"
    
    if [ "$DRY_RUN" = true ]; then
        echo -e "  ${YELLOW}Would prune unused Docker resources${NC}"
    else
        # Remove dangling images
        dangling=$(docker images -f "dangling=true" -q 2>/dev/null || true)
        if [ -n "$dangling" ]; then
            echo "  Removing dangling images..."
            docker rmi $dangling 2>/dev/null || true
        fi
        
        # Remove unused volumes
        echo "  Pruning unused volumes..."
        docker volume prune -f 2>/dev/null || true
    fi
fi

# Summary
echo -e "\n${CYAN}=============================================="
echo "Cleanup Summary"
echo -e "==============================================${NC}"
echo "  Packages processed: $total_deleted"
echo "  Log files processed: $logs_deleted"

if [ "$DRY_RUN" = true ]; then
    echo -e "\n${YELLOW}This was a dry run. No files were actually deleted.${NC}"
    echo "Run without --dry-run to perform actual cleanup."
fi

echo -e "\n${GREEN}Cleanup complete!${NC}"
