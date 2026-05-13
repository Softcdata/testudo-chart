import re
import sys
import argparse
from pathlib import Path

operator_in = "/home/chenxi/YS/disaster-operator/dist/install.yaml"
operator_crd_bases_dir = "/home/chenxi/YS/disaster-operator/config/crd/bases"
server_in = "/home/chenxi/YS/disaster-server/dist/disaster-server-install.yaml"

operator_out = "/home/chenxi/YS/disaster-system-chart/templates/operator-install.yaml"
operator_crds_out = "/home/chenxi/YS/disaster-system-chart/crds/operator-crds.yaml"
server_out = "/home/chenxi/YS/disaster-system-chart/templates/server-install.yaml"

namespace_tmpl = '{{ .Values.global.namespace | default "disaster-system" }}'
timezone_tmpl = '{{ .Values.global.timezone | default "Asia/Shanghai" | quote }}'
operator_image_tmpl = '{{ .Values.images.operator.repository }}:{{ .Values.images.operator.tag }}'
server_image_tmpl = '{{ .Values.images.server.repository }}:{{ .Values.images.server.tag }}'
image_pull_secrets_block = """      imagePullSecrets:
        - name: {{ include "disaster-system.imagePullSecretName" . }}
"""
operator_strategy_block = """  {{- with .Values.operator.strategy }}
  strategy:
{{- toYaml . | nindent 4 }}
  {{- end }}
"""
server_strategy_block = """  {{- with .Values.server.strategy }}
  strategy:
{{- toYaml . | nindent 4 }}
  {{- end }}
"""

required_cluster_status_fields = (
    "workloadNamespaceCount",
    "workloadNamespaceStats",
    "workloadTotalCount",
)


def load_yaml_module():
    try:
        import yaml
    except ModuleNotFoundError:
        print(
            "PyYAML is required to run process_yamls.py. Install it with `python3 -m pip install PyYAML` "
            "or run the script in an environment that already provides the `yaml` module.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return yaml


def ensure_operator_install_is_fresh():
    operator_path = Path(operator_in)
    if not operator_path.exists():
        raise FileNotFoundError(f"{operator_in} does not exist; run `make build-installer` in disaster-operator first")

    crd_base_paths = list(Path(operator_crd_bases_dir).glob("*.yaml"))
    if not crd_base_paths:
        raise FileNotFoundError(f"No operator CRD bases found under {operator_crd_bases_dir}")

    latest_crd_base = max(crd_base_paths, key=lambda path: path.stat().st_mtime)
    if latest_crd_base.stat().st_mtime > operator_path.stat().st_mtime + 1:
        raise RuntimeError(
            f"{operator_in} is older than {latest_crd_base}. "
            "Regenerate it first with `cd /home/chenxi/YS/disaster-operator && make build-installer`, "
            "then rerun this script."
        )


def validate_cluster_crd_schema(crd_doc_texts):
    yaml = load_yaml_module()
    for raw_doc_text in crd_doc_texts:
        doc = yaml.safe_load(raw_doc_text)
        if not doc or doc.get("kind") != "CustomResourceDefinition":
            continue
        if doc.get("metadata", {}).get("name") != "clusters.disaster.wuxs.vip":
            continue

        versions = doc.get("spec", {}).get("versions", [])
        v1 = next((version for version in versions if version.get("name") == "v1"), None)
        status_properties = (
            (v1 or {})
            .get("schema", {})
            .get("openAPIV3Schema", {})
            .get("properties", {})
            .get("status", {})
            .get("properties", {})
        )
        missing = [field for field in required_cluster_status_fields if field not in status_properties]
        if missing:
            raise RuntimeError(
                "clusters.disaster.wuxs.vip CRD in operator installer is missing status fields: "
                + ", ".join(missing)
            )
        return

    raise RuntimeError("clusters.disaster.wuxs.vip CRD was not found in operator installer")


def split_yaml_document_texts(text):
    doc_start_pattern = re.compile(r"(?m)^---[ \t]*\n")
    matches = list(doc_start_pattern.finditer(text))
    if not matches:
        return [text] if text.strip() else []

    docs = []
    if matches[0].start() > 0:
        docs.append(text[:matches[0].start()])

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        docs.append(text[match.start():end])

    return [doc for doc in docs if doc.strip()]


def normalize_yaml_document_text(doc_text):
    doc_text = re.sub(r"\A---[ \t]*\n", "", doc_text)
    return doc_text.rstrip() + "\n"


def write_raw_yaml_documents(path, doc_texts):
    normalized_docs = [normalize_yaml_document_text(doc_text) for doc_text in doc_texts if doc_text.strip()]
    with open(path, "w", encoding="utf-8") as f:
        if not normalized_docs:
            f.write("")
            return
        f.write("\n---\n".join(doc.rstrip("\n") for doc in normalized_docs) + "\n")


def template_timezone_env(text, component):
    updated, count = re.subn(
        r"(?m)^(\s*-\s*name:\s*TZ\s*\n\s*value:\s*).+$",
        r"\1" + timezone_tmpl,
        text,
    )
    if count == 0:
        raise RuntimeError(f"{component} installer is missing TZ environment variable")
    return updated

def process_operator():
    ensure_operator_install_is_fresh()
    yaml = load_yaml_module()

    with open(operator_in, "r", encoding="utf-8") as f:
        operator_text = f.read()

    docs = list(yaml.safe_load_all(operator_text))
    doc_texts = split_yaml_document_texts(operator_text)
    if len(docs) != len(doc_texts):
        raise ValueError(f"Unexpected YAML document count mismatch in {operator_in}: {len(docs)} parsed vs {len(doc_texts)} raw")
    
    filtered_docs = []
    crd_doc_texts = []
    for doc, raw_doc_text in zip(docs, doc_texts):
        if not doc:
            continue
        kind = doc.get("kind")
        if kind == "CustomResourceDefinition":
            crd_doc_texts.append(raw_doc_text)
            continue
        if kind == "Namespace":
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
    validate_cluster_crd_schema(crd_doc_texts)
    write_raw_yaml_documents(operator_crds_out, crd_doc_texts)
        
    # Replace single quotes around templating inserted by PyYAML
    with open(operator_out, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("'{{", "{{").replace("}}'", "}}")
    text = template_timezone_env(text, "operator")
    text = text.replace(
        "spec:\n  replicas: 1\n  selector:\n",
        "spec:\n  replicas: 1\n" + operator_strategy_block + "  selector:\n",
        1,
    )
    text = text.replace(
        "    spec:\n      containers:\n",
        "    spec:\n" + image_pull_secrets_block + "      containers:\n",
        1,
    )
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
    text = re.sub(r'containerPort:\s*8081', 'containerPort: {{ .Values.server.service.port }}', text)
    text = text.replace(
        "spec:\n  replicas: 1\n  selector:\n",
        "spec:\n  replicas: 1\n" + server_strategy_block + "  selector:\n",
        1,
    )
    text = text.replace(
        "      imagePullSecrets:\n        - name: default-secret\n",
        image_pull_secrets_block,
        1,
    )
    text = template_timezone_env(text, "server")
    
    with open(server_out, "w", encoding="utf-8") as f:
        f.write(text)

def main():
    parser = argparse.ArgumentParser(description="Regenerate Helm chart YAMLs from component installers.")
    parser.add_argument("--operator-only", action="store_true", help="only regenerate operator templates and CRDs")
    parser.add_argument("--server-only", action="store_true", help="only regenerate server templates")
    args = parser.parse_args()

    if args.operator_only and args.server_only:
        parser.error("--operator-only and --server-only are mutually exclusive")

    if args.operator_only:
        process_operator()
        return
    if args.server_only:
        process_server()
        return

    process_operator()
    process_server()


if __name__ == "__main__":
    main()
