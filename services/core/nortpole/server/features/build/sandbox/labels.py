LABEL_SANDBOX_ID = "nortpole.local/sandbox-id"
LABEL_TENANT_ID = "nortpole.local/tenant-id"
# Creation attempt. Cleanup compares it with the database owner before deletion.
LABEL_PROVISIONING_ATTEMPT = "nortpole.local/provisioning-attempt"
LABEL_K8S_COMPONENT = "app.kubernetes.io/component"
LABEL_K8S_COMPONENT_SANDBOX = "sandbox"
LABEL_K8S_MANAGED_BY = "app.kubernetes.io/managed-by"
LABEL_K8S_MANAGED_BY_NORTPOLE = "nortpole"

# Docker-backend equivalents of the K8s component label. The proxy's
# DockerEventsLookup filters on these; ``docker_sandbox_manager`` stamps them
# onto every sandbox container it creates.
LABEL_DOCKER_COMPONENT = "nortpole.local/component"
LABEL_DOCKER_COMPONENT_SANDBOX = "craft-sandbox"
LABEL_DOCKER_NETWORK = "nortpole.local/sandbox-network"
LABEL_K8S_COMPONENT_AUTH = "sandbox-opencode-auth"
