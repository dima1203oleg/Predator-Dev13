#!/bin/bash

# Script to add missing sections to all Helm values.yaml files

CHARTS_DIR="/Users/dima/Documents/Predator analitycs 13/helm/predator-umbrella/charts"

# Skip charts that already have these sections
SKIP_CHARTS=("redis" "postgres" "opensearch" "observability")

# Function to add sections to a values.yaml file
add_sections() {
    local file="$1"
    local chart_name=$(basename "$(dirname "$file")")

    # Check if chart should be skipped
    for skip in "${SKIP_CHARTS[@]}"; do
        if [[ "$chart_name" == "$skip" ]]; then
            echo "Skipping $chart_name (already processed)"
            return
        fi
    done

    echo "Processing $chart_name..."

    # Add image section if not present
    if ! grep -q "^image:" "$file"; then
        echo "Adding image section to $file"
        cat >> "$file" << 'EOF'

# Image configuration
image:
  repository: nginx
  tag: "latest"
  pullPolicy: IfNotPresent
EOF
    fi

    # Add service section if not present
    if ! grep -q "^service:" "$file"; then
        echo "Adding service section to $file"
        cat >> "$file" << 'EOF'

# Service configuration
service:
  type: ClusterIP
  port: 80
EOF
    fi

    # Add autoscaling section if not present
    if ! grep -q "^autoscaling:" "$file"; then
        echo "Adding autoscaling section to $file"
        cat >> "$file" << 'EOF'

# Autoscaling configuration
autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 3
  targetCPUUtilizationPercentage: 80
EOF
    fi

    # Add serviceAccount section if not present
    if ! grep -q "^serviceAccount:" "$file"; then
        echo "Adding serviceAccount section to $file"
        cat >> "$file" << 'EOF'

# ServiceAccount configuration
serviceAccount:
  create: true
  name: ""
EOF
    fi
}

# Find all values.yaml files
find "$CHARTS_DIR" -name "values.yaml" | while read -r file; do
    add_sections "$file"
done

echo "Done processing all charts"