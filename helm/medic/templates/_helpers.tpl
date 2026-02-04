{{/*
Expand the name of the chart.
*/}}
{{- define "medic.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "medic.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "medic.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "medic.labels" -}}
helm.sh/chart: {{ include "medic.chart" . }}
{{ include "medic.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "medic.selectorLabels" -}}
app.kubernetes.io/name: {{ include "medic.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
API selector labels
*/}}
{{- define "medic.api.selectorLabels" -}}
{{ include "medic.selectorLabels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Worker selector labels
*/}}
{{- define "medic.worker.selectorLabels" -}}
{{ include "medic.selectorLabels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "medic.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "medic.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the namespace name
*/}}
{{- define "medic.namespace" -}}
{{- if .Values.namespace.create }}
{{- .Values.namespace.name }}
{{- else }}
{{- .Release.Namespace }}
{{- end }}
{{- end }}

{{/*
Create the configmap name
*/}}
{{- define "medic.configmapName" -}}
{{- printf "%s-config" (include "medic.fullname" .) }}
{{- end }}

{{/*
Create the secret name
*/}}
{{- define "medic.secretName" -}}
{{- printf "%s-secret" (include "medic.fullname" .) }}
{{- end }}

{{/*
Container image
*/}}
{{- define "medic.image" -}}
{{- printf "%s:%s" .Values.image.repository .Values.image.tag }}
{{- end }}

{{/*
Environment variable configuration (from ConfigMap and Secret)
*/}}
{{- define "medic.envFrom" -}}
- configMapRef:
    name: {{ include "medic.configmapName" . }}
{{- if or .Values.secret.create .Values.externalSecret.enabled }}
- secretRef:
    name: {{ include "medic.secretName" . }}
{{- end }}
{{- end }}

{{/*
Pod security context
*/}}
{{- define "medic.podSecurityContext" -}}
{{- toYaml .Values.podSecurityContext }}
{{- end }}

{{/*
Container security context
*/}}
{{- define "medic.securityContext" -}}
{{- toYaml .Values.securityContext }}
{{- end }}
