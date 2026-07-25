# Docker-free end-user deployment

End users do not need Docker. The project owner publishes ready-made OCI images to GHCR using GitHub Actions, then the web application deploys those images through SaladCloud's API.

## User-facing deployment modes

- **Managed cloud**: the operator owns Salad and bills users in the application.
- **Bring your own SaladCloud**: users connect an API key, organisation, and project; the controller deploys the prebuilt image for them.
- **Existing FastAPI**: users connect an already deployed compatible endpoint.
- **Local GPU**: advanced users connect local WanGP or VoxCPM2 workers.

Never expose Salad, Google Drive, R2, or RunPod secrets in browser environment variables. Store them server-side or in the operating-system keychain for a trusted desktop client.
