{{- define "disaster-system.imagePullSecretName" -}}
{{- if .Values.imagePullSecret.existingSecret -}}
{{- .Values.imagePullSecret.existingSecret -}}
{{- else -}}
{{- default "default-secret" .Values.imagePullSecret.name -}}
{{- end -}}
{{- end -}}

{{- define "disaster-system.useImagePullSecret" -}}
{{- if or .Values.imagePullSecret.existingSecret .Values.imagePullSecret.create -}}
true
{{- end -}}
{{- end -}}

{{- define "disaster-system.namespace" -}}
{{- default "disaster-system" .Values.global.namespace -}}
{{- end -}}

{{- define "disaster-system.licenseNamespace" -}}
{{- default (include "disaster-system.namespace" .) .Values.license.namespace -}}
{{- end -}}
