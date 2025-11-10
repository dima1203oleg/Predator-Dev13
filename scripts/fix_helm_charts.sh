#!/bin/bash
# Автоматичне виправлення всіх помилок у Helm чартах Predator Analytics v13

set -e

CHARTS_DIR="/Users/dima/Documents/Predator analitycs 13/helm/predator-umbrella/charts"
REPO_ROOT="/Users/dima/Documents/Predator analitycs 13"

echo "🔧 Predator Analytics v13 - Helm Charts Fixer"
echo "=============================================="
echo ""

# Кольори для виводу
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функція для створення _helpers.tpl
create_helpers() {
    local chart=$1
    local helpers_file="$CHARTS_DIR/$chart/templates/_helpers.tpl"
    
    if [ -f "$helpers_file" ]; then
        echo -e "${YELLOW}⚠️  _helpers.tpl вже існує для $chart, пропускаємо${NC}"
        return
    fi
    
    echo -e "${GREEN}✅ Створення _helpers.tpl для $chart${NC}"
    
    mkdir -p "$CHARTS_DIR/$chart/templates"
    
    cat > "$helpers_file" <<EOF
{{/*
Expand the name of the chart.
*/}}
{{- define "$chart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "$chart.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- \$name := include "$chart.name" . -}}
{{- if contains \$name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name \$name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "$chart.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "$chart.labels" -}}
helm.sh/chart: {{ include "$chart.chart" . }}
{{ include "$chart.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels
*/}}
{{- define "$chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "$chart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Create the name of the service account to use
*/}}
{{- define "$chart.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
    {{- default (include "$chart.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
    {{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
EOF
}

# 1. Створити _helpers.tpl для всіх субчартів
echo -e "${YELLOW}📝 Крок 1/6: Створення _helpers.tpl для субчартів${NC}"
echo ""

SUBCHARTS=(
    "api"
    "agents"
    "frontend"
    "model-router"
    "celery"
    "postgres"
    "redis"
    "qdrant"
    "opensearch"
    "minio"
    "keycloak"
    "voice"
    "mlflow"
    "neo4j"
    "kafka"
    "observability"
)

for chart in "${SUBCHARTS[@]}"; do
    if [ -d "$CHARTS_DIR/$chart" ]; then
        create_helpers "$chart"
    else
        echo -e "${RED}❌ Директорія $chart не знайдена${NC}"
    fi
done

echo ""
echo -e "${GREEN}✅ Крок 1 завершено${NC}"
echo ""

# 2. Створити базові values.yaml якщо відсутні
echo -e "${YELLOW}📝 Крок 2/6: Перевірка values.yaml${NC}"
echo ""

for chart in "${SUBCHARTS[@]}"; do
    values_file="$CHARTS_DIR/$chart/values.yaml"
    if [ ! -f "$values_file" ] && [ -d "$CHARTS_DIR/$chart" ]; then
        echo -e "${GREEN}✅ Створення values.yaml для $chart${NC}"
        cat > "$values_file" <<EOF
# Default values for $chart
# This is a YAML-formatted file.

replicaCount: 1

image:
  repository: predator-$chart
  pullPolicy: IfNotPresent
  tag: "13.0.0"

serviceAccount:
  create: true
  annotations: {}
  name: ""

service:
  type: ClusterIP
  port: 80

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 100m
    memory: 128Mi

autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80

env: {}
EOF
    fi
done

echo ""
echo -e "${GREEN}✅ Крок 2 завершено${NC}"
echo ""

# 3. Створити Chart.yaml якщо відсутні
echo -e "${YELLOW}📝 Крок 3/6: Перевірка Chart.yaml${NC}"
echo ""

for chart in "${SUBCHARTS[@]}"; do
    chart_file="$CHARTS_DIR/$chart/Chart.yaml"
    if [ ! -f "$chart_file" ] && [ -d "$CHARTS_DIR/$chart" ]; then
        echo -e "${GREEN}✅ Створення Chart.yaml для $chart${NC}"
        cat > "$chart_file" <<EOF
apiVersion: v2
name: $chart
description: Predator Analytics v13 - $chart component
type: application
version: 13.0.0
appVersion: "13.0.0"
home: https://predator.analytics
maintainers:
  - name: Predator Team
    email: devops@predator.analytics
EOF
    fi
done

echo ""
echo -e "${GREEN}✅ Крок 3 завершено${NC}"
echo ""

# 4. Виправити .Values.global на .Values у deployment.yaml
echo -e "${YELLOW}📝 Крок 4/6: Виправлення .Values.global → .Values${NC}"
echo ""

find "$CHARTS_DIR" -type f -name "*.yaml" | while read file; do
    if grep -q "\.Values\.global\." "$file" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Виправлення global values у: $file${NC}"
        # Backup
        cp "$file" "$file.bak"
        # Replace .Values.global.env with .Values.env
        sed -i '' 's/\.Values\.global\.env/\.Values\.env/g' "$file"
        # Replace .Values.global.imageRegistry with .Values.image.repository
        sed -i '' 's/\.Values\.global\.imageRegistry/\.Values\.image\.repository/g' "$file"
        echo -e "${GREEN}✅ Виправлено: $file${NC}"
    fi
done

echo ""
echo -e "${GREEN}✅ Крок 4 завершено${NC}"
echo ""

# 5. Створити базові deployment.yaml для субчартів без них
echo -e "${YELLOW}📝 Крок 5/6: Створення базових deployment.yaml${NC}"
echo ""

for chart in "${SUBCHARTS[@]}"; do
    deployment_file="$CHARTS_DIR/$chart/templates/deployment.yaml"
    if [ ! -f "$deployment_file" ] && [ -d "$CHARTS_DIR/$chart/templates" ]; then
        echo -e "${GREEN}✅ Створення deployment.yaml для $chart${NC}"
        cat > "$deployment_file" <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "$chart.fullname" . }}
  labels:
    {{- include "$chart.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "$chart.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "$chart.selectorLabels" . | nindent 8 }}
    spec:
      serviceAccountName: {{ include "$chart.serviceAccountName" . }}
      containers:
      - name: {{ .Chart.Name }}
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        env:
        {{- range \$key, \$value := .Values.env }}
        - name: {{ \$key }}
          value: {{ \$value | quote }}
        {{- end }}
        resources:
          {{- toYaml .Values.resources | nindent 10 }}
EOF
    fi
done

echo ""
echo -e "${GREEN}✅ Крок 5 завершено${NC}"
echo ""

# 6. Створити service.yaml для субчартів
echo -e "${YELLOW}📝 Крок 6/6: Створення service.yaml${NC}"
echo ""

for chart in "${SUBCHARTS[@]}"; do
    service_file="$CHARTS_DIR/$chart/templates/service.yaml"
    if [ ! -f "$service_file" ] && [ -d "$CHARTS_DIR/$chart/templates" ]; then
        echo -e "${GREEN}✅ Створення service.yaml для $chart${NC}"
        cat > "$service_file" <<EOF
apiVersion: v1
kind: Service
metadata:
  name: {{ include "$chart.fullname" . }}
  labels:
    {{- include "$chart.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "$chart.selectorLabels" . | nindent 4 }}
EOF
    fi
done

echo ""
echo -e "${GREEN}✅ Крок 6 завершено${NC}"
echo ""

# Підсумок
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 Всі виправлення завершено!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Наступні кроки:"
echo -e "  1. ${YELLOW}helm lint helm/predator-umbrella${NC}"
echo -e "  2. ${YELLOW}helm dependency update helm/predator-umbrella${NC}"
echo -e "  3. ${YELLOW}helm template test helm/predator-umbrella --dry-run${NC}"
echo ""
