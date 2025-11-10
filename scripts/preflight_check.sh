#!/bin/bash
# Pre-flight checks for Predator Analytics v13 Production Deployment

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0
WARNINGS=0

check() {
    echo -n "  Checking $1... "
}

pass() {
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASSED++))
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    ((FAILED++))
}

warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
    ((WARNINGS++))
}

echo "========================================="
echo "Predator Analytics v13 Pre-flight Checks"
echo "========================================="
echo

# 1. Kubernetes cluster
echo "1. Kubernetes Cluster"
check "kubectl access"
if kubectl cluster-info &>/dev/null; then
    pass
else
    fail "Cannot access Kubernetes cluster"
fi

check "Kubernetes version (>= 1.27)"
K8S_VERSION=$(kubectl version --short 2>/dev/null | grep Server | awk '{print $3}' | sed 's/v//')
MAJOR=$(echo $K8S_VERSION | cut -d. -f1)
MINOR=$(echo $K8S_VERSION | cut -d. -f2)
if [ "$MAJOR" -ge 1 ] && [ "$MINOR" -ge 27 ]; then
    pass
else
    fail "Kubernetes version $K8S_VERSION < 1.27"
fi

check "Worker nodes (>= 6)"
NODE_COUNT=$(kubectl get nodes --no-headers | wc -l)
if [ "$NODE_COUNT" -ge 6 ]; then
    pass
else
    warn "Only $NODE_COUNT nodes (recommended: >= 6)"
fi

check "Total CPU cores (>= 64)"
TOTAL_CPU=$(kubectl get nodes -o json | jq '[.items[].status.capacity.cpu | tonumber] | add')
if [ "$TOTAL_CPU" -ge 64 ]; then
    pass
else
    warn "Only ${TOTAL_CPU} cores (recommended: >= 64)"
fi

check "Total memory (>= 256Gi)"
TOTAL_MEM_KB=$(kubectl get nodes -o json | jq '[.items[].status.capacity.memory | sub("Ki";"") | tonumber] | add')
TOTAL_MEM_GB=$((TOTAL_MEM_KB / 1024 / 1024))
if [ "$TOTAL_MEM_GB" -ge 256 ]; then
    pass
else
    warn "Only ${TOTAL_MEM_GB}Gi memory (recommended: >= 256Gi)"
fi

# 2. Storage
echo
echo "2. Storage"
check "StorageClass available"
if kubectl get storageclass &>/dev/null; then
    SC_COUNT=$(kubectl get storageclass --no-headers | wc -l)
    if [ "$SC_COUNT" -gt 0 ]; then
        pass
    else
        fail "No StorageClass found"
    fi
else
    fail "Cannot list StorageClasses"
fi

check "Default StorageClass"
if kubectl get storageclass -o json | jq -e '.items[] | select(.metadata.annotations["storageclass.kubernetes.io/is-default-class"]=="true")' &>/dev/null; then
    pass
else
    warn "No default StorageClass set"
fi

# 3. Networking
echo
echo "3. Networking"
check "Ingress Controller"
if kubectl get ingressclass &>/dev/null; then
    IC_COUNT=$(kubectl get ingressclass --no-headers | wc -l)
    if [ "$IC_COUNT" -gt 0 ]; then
        pass
    else
        fail "No IngressClass found"
    fi
else
    warn "IngressClass CRD not installed"
fi

check "LoadBalancer service type"
if kubectl get svc -A -o json | jq -e '.items[] | select(.spec.type=="LoadBalancer")' &>/dev/null; then
    pass
else
    warn "No LoadBalancer services found (metallb/cloud provider required)"
fi

check "DNS resolution"
if kubectl run dnstest --image=busybox:latest --rm -it --restart=Never -- nslookup kubernetes.default &>/dev/null; then
    pass
else
    warn "DNS resolution issues"
fi

# 4. Required Tools
echo
echo "4. Required CLI Tools"
for tool in helm argocd velero istioctl; do
    check "$tool"
    if command -v $tool &>/dev/null; then
        pass
    else
        warn "$tool not found in PATH"
    fi
done

# 5. Helm Chart
echo
echo "5. Helm Chart Validation"
check "Helm chart syntax"
if helm lint helm/predator-umbrella &>/dev/null; then
    pass
else
    fail "Helm chart has lint errors"
fi

check "Helm dependencies"
if [ -f "helm/predator-umbrella/Chart.lock" ]; then
    pass
else
    warn "Run 'helm dependency update' first"
fi

# 6. Secrets
echo
echo "6. Secrets (Environment Variables)"
REQUIRED_SECRETS=(
    "POSTGRES_PASSWORD"
    "REDIS_PASSWORD"
    "MINIO_ACCESS_KEY"
    "MINIO_SECRET_KEY"
    "KEYCLOAK_ADMIN_PASSWORD"
)

for secret in "${REQUIRED_SECRETS[@]}"; do
    check "$secret"
    if [ -n "${!secret:-}" ]; then
        pass
    else
        fail "$secret not set"
    fi
done

# Optional API keys
API_KEYS=("OPENAI_API_KEY" "ANTHROPIC_API_KEY" "GROQ_API_KEY" "GOOGLE_API_KEY")
for key in "${API_KEYS[@]}"; do
    check "$key (optional)"
    if [ -n "${!key:-}" ]; then
        pass
    else
        warn "$key not set (some LLM features disabled)"
    fi
done

# 7. Dependencies
echo
echo "7. Optional Dependencies"
check "Cert-Manager"
if kubectl get namespace cert-manager &>/dev/null; then
    pass
else
    warn "Cert-Manager not installed (mTLS disabled)"
fi

check "Istio"
if kubectl get namespace istio-system &>/dev/null; then
    pass
else
    warn "Istio not installed (service mesh disabled)"
fi

check "Kyverno"
if kubectl get namespace kyverno &>/dev/null; then
    pass
else
    warn "Kyverno not installed (policy enforcement disabled)"
fi

check "ArgoCD"
if kubectl get namespace argocd &>/dev/null; then
    pass
else
    warn "ArgoCD not installed (GitOps disabled)"
fi

# 8. Namespace
echo
echo "8. Target Namespace"
check "Namespace 'predator' exists"
if kubectl get namespace predator &>/dev/null; then
    warn "Namespace already exists (may conflict)"
else
    pass
fi

# Summary
echo
echo "========================================="
echo "Summary:"
echo "  ${GREEN}Passed: $PASSED${NC}"
echo "  ${YELLOW}Warnings: $WARNINGS${NC}"
echo "  ${RED}Failed: $FAILED${NC}"
echo "========================================="

if [ "$FAILED" -gt 0 ]; then
    echo -e "${RED}❌ Pre-flight checks FAILED${NC}"
    echo "Fix the issues above before proceeding with deployment."
    exit 1
elif [ "$WARNINGS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Pre-flight checks PASSED with warnings${NC}"
    echo "Review warnings before proceeding."
    exit 0
else
    echo -e "${GREEN}✅ Pre-flight checks PASSED${NC}"
    echo "Ready for production deployment!"
    exit 0
fi
