{{- define "predator-app.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- define "predator-app.fullname" -}}
{{- include "predator-app.name" . -}}
{{- end -}}
{{- define "predator-app.chart" -}}
{{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}
