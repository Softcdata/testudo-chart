import os
import yaml
import re

operator_in = "/home/chenxi/YS/disaster-operator/dist/install.yaml"
server_in = "/home/chenxi/YS/disaster-server/dist/disaster-server-install.yaml"

operator_out = "/home/chenxi/YS/disaster-system-chart/templates/operator-install.yaml"
server_out = "/home/chenxi/YS/disaster-system-chart/templates/server-install.yaml"

namespace_tmpl = '{{ .Values.global.namespace | default "disaster-system" }}'
operator_image_tmpl = '{{ .Values.images.operator.repository }}:{{ .Values.images.operator.tag }}'
server_image_tmpl = '{{ .Values.images.server.repository }}:{{ .Values.images.server.tag }}'

def process_operator():
    with open(operator_in, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    
    filtered_docs = []
    for doc in docs:
        if not doc:
            continue
        kind = doc.get("kind")
        if kind == "CustomResourceDefinition" or kind == "Namespace":
            continue
            
        # Update namespace
        if "metadata" in doc and "namespace" in doc["metadata"]:
            if doc["metadata"]["namespace"] == "disaster-system":
                doc["metadata"]["namespace"] = namespace_tmpl
                
        # Sub-namespace handling for ClusterRoleBinding/RoleBinding/ValidatingWebhookConfiguration etc.
        if "subjects" in doc:
            for subject in doc["subjects"]:
                if "namespace" in subject and subject["namespace"] == "disaster-system":
                    subject["namespace"] = namespace_tmpl
                    
        # Update Service webhook target namespace (if any)
        if "webhooks" in doc:
            for wh in doc["webhooks"]:
                if "clientConfig" in wh and "service" in wh["clientConfig"]:
                    if wh["clientConfig"]["service"].get("namespace") == "disaster-system":
                        wh["clientConfig"]["service"]["namespace"] = namespace_tmpl

        # Update image
        if kind == "Deployment" and "spec" in doc and "template" in doc["spec"]:
            for container in doc["spec"]["template"]["spec"]["containers"]:
                if "disaster-operator" in container.get("image", ""):
                    container["image"] = operator_image_tmpl
                    container["imagePullPolicy"] = '{{ .Values.images.operator.pullPolicy }}'

        filtered_docs.append(doc)

    with open(operator_out, "w", encoding="utf-8") as f:
        yaml.dump_all(filtered_docs, f, default_flow_style=False)
        
    # Replace single quotes around templating inserted by PyYAML
    with open(operator_out, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("'{{", "{{").replace("}}'", "}}")
    with open(operator_out, "w", encoding="utf-8") as f:
        f.write(text)

def process_server():
    with open(server_in, "r", encoding="utf-8") as f:
        text = f.read()
        
    text = text.replace("namespace: disaster-system", f"namespace: {namespace_tmpl}")
    # Fix the ServiceAccount reference in RoleBinding/ClusterRoleBinding manually just in case
    text = text.replace(
        "namespace: " + namespace_tmpl + "\nroleRef:",
        "namespace: " + namespace_tmpl + "\nroleRef:"
    )
    # Replaces the image
    text = re.sub(r'image:\s*".*?disaster-server.*?"', f'image: "{server_image_tmpl}"', text)
    text = re.sub(r'imagePullPolicy:\s*Always', 'imagePullPolicy: {{ .Values.images.server.pullPolicy }}', text)
    
    # Service port logic
    text = re.sub(r'type:\s*NodePort', 'type: {{ .Values.server.service.type }}', text)
    text = re.sub(r'port:\s*8081', 'port: {{ .Values.server.service.port }}', text)
    
    with open(server_out, "w", encoding="utf-8") as f:
        f.write(text)

process_operator()
process_server()
