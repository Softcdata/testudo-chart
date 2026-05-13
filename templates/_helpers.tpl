{{- define "disaster-system.imagePullSecretName" -}}
{{- default "default-secret" .Values.imagePullSecret.existingSecret -}}
{{- end -}}

{{- define "disaster-system.namespace" -}}
{{- default "disaster-system" .Values.global.namespace -}}
{{- end -}}

{{- define "disaster-system.licenseNamespace" -}}
{{- default (include "disaster-system.namespace" .) .Values.license.namespace -}}
{{- end -}}
