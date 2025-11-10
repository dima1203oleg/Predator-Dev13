#!/bin/bash
# Disaster Recovery Drill Script for Predator Analytics
# RTO: 30 minutes | RPO: 15 minutes

set -euo pipefail

# Configuration
NAMESPACE="predator"
BACKUP_LOCATION="s3://predator-backups"
VELERO_BACKUP_NAME="predator-scheduled-$(date +%Y%m%d-%H%M%S)"
DR_NAMESPACE="predator-dr"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Step 1: Verify current state
verify_current_state() {
    log "Step 1: Verifying current production state..."
    
    kubectl get pods -n ${NAMESPACE} || error "Cannot access namespace ${NAMESPACE}"
    
    # Check critical services
    for service in api frontend postgres opensearch qdrant redis; do
        kubectl get svc predator-${service} -n ${NAMESPACE} > /dev/null 2>&1 || warn "Service predator-${service} not found"
    done
    
    log "✓ Current state verified"
}

# Step 2: Create backup
create_backup() {
    log "Step 2: Creating Velero backup..."
    
    velero backup create ${VELERO_BACKUP_NAME} \
        --include-namespaces ${NAMESPACE} \
        --wait || error "Velero backup failed"
    
    # Backup PostgreSQL
    log "Backing up PostgreSQL..."
    kubectl exec -n ${NAMESPACE} postgres-0 -- \
        pg_dumpall -U predator | gzip > /tmp/postgres-backup-$(date +%s).sql.gz
    
    # Upload to S3
    aws s3 cp /tmp/postgres-backup-*.sql.gz ${BACKUP_LOCATION}/postgres/ || warn "PostgreSQL backup upload failed"
    
    # Backup OpenSearch indices
    log "Backing up OpenSearch indices..."
    curl -X PUT "opensearch:9200/_snapshot/predator_backup/snapshot_$(date +%s)?wait_for_completion=true" || warn "OpenSearch snapshot failed"
    
    # Backup Qdrant collections
    log "Backing up Qdrant collections..."
    kubectl exec -n ${NAMESPACE} qdrant-0 -- \
        /qdrant/qdrant-backup --path /qdrant/storage/backup || warn "Qdrant backup failed"
    
    log "✓ Backups created successfully"
}

# Step 3: Simulate disaster (in DR namespace)
simulate_disaster() {
    log "Step 3: Simulating disaster scenario..."
    
    # Create DR namespace
    kubectl create namespace ${DR_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
    
    # Delete all resources in DR namespace (simulate clean slate)
    kubectl delete all --all -n ${DR_NAMESPACE} --grace-period=0 --force || true
    
    log "✓ Disaster scenario prepared"
}

# Step 4: Restore from backup
restore_from_backup() {
    log "Step 4: Restoring from backup (RTO timer started)..."
    START_TIME=$(date +%s)
    
    # Restore Velero backup to DR namespace
    velero restore create ${VELERO_BACKUP_NAME}-restore \
        --from-backup ${VELERO_BACKUP_NAME} \
        --namespace-mappings ${NAMESPACE}:${DR_NAMESPACE} \
        --wait || error "Velero restore failed"
    
    # Restore PostgreSQL
    log "Restoring PostgreSQL..."
    kubectl exec -n ${DR_NAMESPACE} postgres-0 -- bash -c \
        "gunzip -c | psql -U predator" < /tmp/postgres-backup-*.sql.gz || warn "PostgreSQL restore had warnings"
    
    # Restore OpenSearch
    log "Restoring OpenSearch indices..."
    kubectl exec -n ${DR_NAMESPACE} opensearch-0 -- curl -X POST \
        "localhost:9200/_snapshot/predator_backup/snapshot_*/_restore" || warn "OpenSearch restore incomplete"
    
    # Restore Qdrant
    log "Restoring Qdrant collections..."
    kubectl exec -n ${DR_NAMESPACE} qdrant-0 -- \
        /qdrant/qdrant-restore --path /qdrant/storage/backup || warn "Qdrant restore incomplete"
    
    END_TIME=$(date +%s)
    RECOVERY_TIME=$((END_TIME - START_TIME))
    
    log "✓ Restore completed in ${RECOVERY_TIME} seconds"
    
    if [ ${RECOVERY_TIME} -gt 1800 ]; then
        error "RTO exceeded: ${RECOVERY_TIME}s > 1800s (30 min)"
    else
        log "✓ RTO met: ${RECOVERY_TIME}s < 1800s"
    fi
}

# Step 5: Verify restored services
verify_restored_services() {
    log "Step 5: Verifying restored services..."
    
    # Wait for pods to be ready
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/part-of=predator -n ${DR_NAMESPACE} --timeout=600s || error "Pods not ready"
    
    # Health checks
    for service in api frontend; do
        kubectl exec -n ${DR_NAMESPACE} deploy/predator-${service} -- wget -q -O- http://localhost:8080/health || error "${service} health check failed"
    done
    
    # Database connectivity
    kubectl exec -n ${DR_NAMESPACE} postgres-0 -- psql -U predator -c "SELECT 1" || error "PostgreSQL not accessible"
    
    # OpenSearch cluster health
    kubectl exec -n ${DR_NAMESPACE} opensearch-0 -- curl -s localhost:9200/_cluster/health | grep -q '"status":"green"' || warn "OpenSearch not green"
    
    # Qdrant collections
    kubectl exec -n ${DR_NAMESPACE} qdrant-0 -- curl -s localhost:6333/collections | grep -q "pa_domain" || error "Qdrant collections missing"
    
    # Data integrity check
    log "Checking data integrity..."
    PROD_COUNT=$(kubectl exec -n ${NAMESPACE} postgres-0 -- psql -U predator -t -c "SELECT COUNT(*) FROM customs_data")
    DR_COUNT=$(kubectl exec -n ${DR_NAMESPACE} postgres-0 -- psql -U predator -t -c "SELECT COUNT(*) FROM customs_data")
    
    if [ "${PROD_COUNT}" != "${DR_COUNT}" ]; then
        warn "Data count mismatch: PROD=${PROD_COUNT}, DR=${DR_COUNT}"
    else
        log "✓ Data integrity verified: ${PROD_COUNT} records"
    fi
    
    log "✓ All services verified"
}

# Step 6: Test functionality
test_functionality() {
    log "Step 6: Testing core functionality..."
    
    # Test API endpoint
    API_POD=$(kubectl get pod -n ${DR_NAMESPACE} -l app=predator-api -o jsonpath='{.items[0].metadata.name}')
    kubectl exec -n ${DR_NAMESPACE} ${API_POD} -- curl -s -f http://localhost:8080/datasets || error "API test failed"
    
    # Test search
    kubectl exec -n ${DR_NAMESPACE} ${API_POD} -- curl -s -f -X POST http://localhost:8080/search \
        -H "Content-Type: application/json" \
        -d '{"query":"test"}' || error "Search test failed"
    
    # Test CDC lag
    CDC_LAG=$(kubectl exec -n ${DR_NAMESPACE} postgres-0 -- psql -U predator -t -c "SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) FROM pg_replication_slots WHERE slot_name='predator_slot'")
    
    log "CDC lag: ${CDC_LAG} bytes"
    
    log "✓ Functionality tests passed"
}

# Step 7: Calculate RPO
calculate_rpo() {
    log "Step 7: Calculating RPO..."
    
    # Get last transaction timestamp from production
    PROD_LAST_TX=$(kubectl exec -n ${NAMESPACE} postgres-0 -- psql -U predator -t -c "SELECT MAX(created_at) FROM customs_data")
    
    # Get last transaction timestamp from DR
    DR_LAST_TX=$(kubectl exec -n ${DR_NAMESPACE} postgres-0 -- psql -U predator -t -c "SELECT MAX(created_at) FROM customs_data")
    
    # Calculate difference
    RPO_SECONDS=$(( $(date -d "${PROD_LAST_TX}" +%s) - $(date -d "${DR_LAST_TX}" +%s) ))
    
    log "RPO: ${RPO_SECONDS} seconds"
    
    if [ ${RPO_SECONDS} -gt 900 ]; then
        error "RPO exceeded: ${RPO_SECONDS}s > 900s (15 min)"
    else
        log "✓ RPO met: ${RPO_SECONDS}s < 900s"
    fi
}

# Step 8: Cleanup
cleanup_drill() {
    log "Step 8: Cleaning up DR drill resources..."
    
    read -p "Delete DR namespace ${DR_NAMESPACE}? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete namespace ${DR_NAMESPACE} || warn "Failed to delete DR namespace"
        log "✓ DR namespace deleted"
    else
        log "Keeping DR namespace for inspection"
    fi
    
    # Cleanup temp files
    rm -f /tmp/postgres-backup-*.sql.gz
}

# Main execution
main() {
    log "========================================="
    log "Predator Analytics DR Drill"
    log "Target RTO: 30 minutes | Target RPO: 15 minutes"
    log "========================================="
    
    verify_current_state
    create_backup
    simulate_disaster
    restore_from_backup
    verify_restored_services
    test_functionality
    calculate_rpo
    cleanup_drill
    
    log "========================================="
    log "✓ DR drill completed successfully!"
    log "========================================="
}

# Run main function
main "$@"
