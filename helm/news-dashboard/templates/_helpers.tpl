{{- define "news-dashboard.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "news-dashboard.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "news-dashboard.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
