# WanGP + VoxCPM2 Cloud Starter

A runnable starter for connecting a local or hosted React web app to:

- **WanGP** video generation
- **VoxCPM2** multilingual TTS and voice cloning
- **Local FastAPI**, **SaladCloud Job Queues**, **RunPod Serverless**, **[Clore.ai](https://clore.ai/) / [Vast.ai](https://vast.ai/) GPU rentals**, or a custom FastAPI worker
- **Google Drive**, **Cloudflare R2 / S3-compatible storage**, or local disk

The included Docker Compose setup runs immediately in **mock mode**. Real GPU
inference is enabled with the separate `.gpu` Dockerfiles.

> This repository does not redistribute WanGP, VoxCPM2, or their model weights.
> Review and follow each upstream project's license and terms before production
> or commercial deployment.

## Project structure

```text
apps/web/                 React + Vite UI
services/controller/      Public CPU FastAPI API and job database
workers/voxcpm2/          VoxCPM2 FastAPI/Salad worker
workers/wangp/            WanGP FastAPI/Salad worker
packages/python_common/   Google Drive, R2/S3, and local storage adapters
deploy/salad/             SaladCloud queue and container templates
deploy/runpod/            RunPod Serverless template and endpoint scripts
deploy/clore/             Clore.ai marketplace rental scripts
deploy/vast/              Vast.ai GPU cloud instance scripts
docs/                     Architecture notes
```

## 1. Run the complete local demo

Requirements: Docker Desktop with Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Web UI: `http://localhost:5173`
- Controller docs: `http://localhost:8000/docs`
- Vox worker docs: `http://localhost:8011/docs`
- WanGP worker docs: `http://localhost:8012/docs`

Choose **Mock demo** and **Local disk** in Provider Settings. The UI saves the
selection in browser `localStorage`.

## 2. Provider selection and saved settings

The web UI lets each user choose and save:

### Compute provider

- `mock`: immediate integration demo
- `local`: direct calls to `VOX_WORKER_URL` and `WAN_WORKER_URL`
- `salad`: submits to two Salad Job Queues
- `runpod`: submits to configured RunPod Serverless endpoints
- `custom`: calls a user-selected FastAPI worker URL (also used for Clore.ai / Vast.ai rentals)

### Storage provider

- `local`
- `r2` (Cloudflare R2 or any S3-compatible service)
- `google_drive`

Only provider names and the optional custom URL are saved in the browser. Never
put Salad, RunPod, Clore, Vast, Google, or S3 credentials in Vite environment variables.

## 3. Use your Google Drive storage

Google Drive support uses an OAuth refresh token. Create a Google Cloud OAuth
client, enable Google Drive API, obtain a refresh token with the
`drive.file` scope, and set:

```env
GOOGLE_DRIVE_CLIENT_ID=...
GOOGLE_DRIVE_CLIENT_SECRET=...
GOOGLE_DRIVE_REFRESH_TOKEN=...
GOOGLE_DRIVE_FOLDER_ID=your_destination_folder_id
GOOGLE_DRIVE_MAKE_PUBLIC=false
```

Then select **Google Drive** in the UI. Uploaded input files and generated
outputs use `gdrive://FILE_ID` internally.

Notes:

- `drive.file` allows the application to manage files it creates or that the
  user explicitly opens with the app.
- Keep `GOOGLE_DRIVE_MAKE_PUBLIC=false` for private files.
- Workers need the same Google OAuth credentials to download input files and
  upload results.
- Google Drive is excellent for inexpensive persistence, but R2 can have lower
  operational friction for distributed GPU workers and direct media delivery.

## 4. Configure Cloudflare R2 / S3

```env
S3_ENDPOINT_URL=https://ACCOUNT_ID.r2.cloudflarestorage.com
S3_REGION=auto
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_BUCKET=ai-media
S3_PUBLIC_BASE_URL=https://media.example.com
```

The same adapter works with AWS S3, MinIO, Backblaze B2 S3, and similar
S3-compatible providers.

## 5. Build the real VoxCPM2 GPU image

The mock image is intentionally small. Build the real image:

```bash
docker build \
  -f workers/voxcpm2/Dockerfile.gpu \
  --build-arg BAKE_MODEL=1 \
  --build-arg MODEL_ID=openbmb/VoxCPM2 \
  -t YOUR_REGISTRY/voxcpm2-worker:latest .

docker push YOUR_REGISTRY/voxcpm2-worker:latest
```

When `BAKE_MODEL=1`, the model is downloaded during image build and loaded from
`/models/VoxCPM2`. This reduces repeated runtime downloads but increases image
size. Set `BAKE_MODEL=0` and `MODEL_PATH=openbmb/VoxCPM2` only when you accept a
model download on a fresh worker.

Local GPU test:

```bash
docker run --rm --gpus all -p 8011:8011 \
  --env-file .env \
  -e ENGINE_MODE=real \
  -e SALAD_QUEUE_WORKER_ENABLED=0 \
  YOUR_REGISTRY/voxcpm2-worker:latest
```

Test:

```bash
curl -X POST http://localhost:8011/process \
  -H 'Content-Type: application/json' \
  -d '{
    "job_id":"demo-tts",
    "kind":"tts",
    "text":"សួស្តី ពិភពលោក",
    "storage_provider":"local"
  }'
```

## 6. Build the real WanGP GPU image

WanGP changes frequently. This Dockerfile now follows the upstream CUDA 12.8 / PyTorch 2.10 baseline. Pin a tested tag or commit instead of using `main` in production:

```bash
docker build \
  -f workers/wangp/Dockerfile.gpu \
  --build-arg WANGP_REF=main \
  --build-arg CUDA_ARCHITECTURES="8.6;8.9" \
  -t YOUR_REGISTRY/wangp-worker:latest .

docker push YOUR_REGISTRY/wangp-worker:latest
```

The worker uses WanGP's in-process Python API:

```python
from shared.api import init
session = init(root=Path('/opt/Wan2GP'), output_dir=Path('/outputs'))
result = session.submit_task(settings).result()
```

WanGP model files are not automatically baked by this starter because the exact
files depend on `model_type`, quantization, profile, and GPU target. Recommended
production workflow:

1. Test your selected model locally in WanGP.
2. Export its settings from WanGP.
3. Confirm the exact model files and licenses.
4. Add only those files to a derived image or an image-build download stage.
5. Keep the compressed Salad image under its current limit.
6. Put user images, audio, videos, checkpoints, and outputs in Drive or R2.

The API accepts `advanced_settings` so you can pass fields exported from WanGP
without changing the controller schema. Generic start/end image fields in this
starter are mapped as common WanGP settings, but model families can differ; an
exported settings payload should be treated as the source of truth.

## 7. Deploy to SaladCloud

> **July 2026 deployment note:** current Salad API examples use GPU-class UUIDs, not labels such as `rtx4090`. Retrieve the UUIDs with `deploy/salad/list-gpu-classes.sh` or the Windows PowerShell equivalent. The templates in this ZIP already use the current `autostart_policy`, `restart_policy`, and queue autoscaling fields.

### 7.1 Prepare environment

```bash
export SALAD_API_KEY='...'
export SALAD_ORGANIZATION='your-org-slug'
export SALAD_PROJECT='your-project-slug'
export SALAD_VOX_QUEUE='voxcpm2-jobs'
export SALAD_WAN_QUEUE='wangp-jobs'
```

Windows PowerShell:

```powershell
$env:SALAD_API_KEY="..."
$env:SALAD_ORGANIZATION="your-org-slug"
$env:SALAD_PROJECT="your-project-slug"
$env:SALAD_VOX_QUEUE="voxcpm2-jobs"
$env:SALAD_WAN_QUEUE="wangp-jobs"
```

### 7.2 Get current GPU-class IDs

```bash
chmod +x deploy/salad/*.sh
./deploy/salad/list-gpu-classes.sh
```

Windows PowerShell:

```powershell
.\deploy\salad\windows\list-gpu-classes.ps1
```

Copy the UUID for the GPU you want, such as an RTX 3090 or RTX 4090, into each container JSON template.

### 7.3 Create queues

```bash
./deploy/salad/create-queues.sh
```

Windows PowerShell:

```powershell
.\deploy\salad\windows\create-queues.ps1
```

### 7.4 Prepare container JSON

Copy and edit:

```bash
cp deploy/salad/container-voxcpm2.json.template deploy/salad/container-voxcpm2.json
cp deploy/salad/container-wangp.json.template deploy/salad/container-wangp.json
```

Replace:

- image names
- GPU classes available in your Salad project
- Google Drive or R2 credentials
- queue names if you changed them
- CPU, RAM, disk, regions, and autoscaling limits

Do not commit the edited JSON files because they contain secrets.

### 7.5 Create container groups

```bash
./deploy/salad/deploy-container.sh deploy/salad/container-voxcpm2.json
./deploy/salad/deploy-container.sh deploy/salad/container-wangp.json
```

Windows PowerShell:

```powershell
.\deploy\salad\windows\deploy-container.ps1 -File .\deploy\salad\container-voxcpm2.json
.\deploy\salad\windows\deploy-container.ps1 -File .\deploy\salad\container-wangp.json
```

Both templates use:

```json
{
  "replicas": 0,
  "queue_autoscaler": {
    "min_replicas": 0,
    "max_replicas": 1,
    "desired_queue_length": 1,
    "polling_period": 30
  }
}
```

This scales to zero when no jobs are queued. The first job can have a long cold
start, especially for the larger WanGP image.

### 7.6 Configure the controller

On your CPU server, set:

```env
SALAD_API_KEY=...
SALAD_ORGANIZATION=...
SALAD_PROJECT=...
SALAD_VOX_QUEUE=voxcpm2-jobs
SALAD_WAN_QUEUE=wangp-jobs
```

Run only the controller and web app there. It submits jobs to Salad and polls
job status. Salad credentials never reach the browser.

### 7.7 Salad job contract

The controller submits:

```json
{
  "metadata": {"app_job_id": "...", "kind": "tts"},
  "input": {
    "job_id": "...",
    "kind": "tts",
    "storage_provider": "google_drive",
    "text": "Hello"
  }
}
```

The Salad job-queue worker forwards the input to `/process`. A successful worker
returns JSON like:

```json
{
  "job_id": "...",
  "status": "succeeded",
  "kind": "tts",
  "output_uri": "gdrive://FILE_ID",
  "public_url": "https://drive.google.com/..."
}
```

Do not return media bytes through the queue response. Upload the artifact to
Drive/R2 and return a small JSON result.

## 8. Deploy to RunPod Serverless

The controller already talks to RunPod via `https://api.runpod.ai/v2/{endpoint}/run`.
GPU images include a small RunPod handler that forwards queue jobs to the local
FastAPI `/process` endpoint when `RUNPOD_HANDLER_ENABLED=1`.

### 8.1 Prepare environment

```bash
export RUNPOD_API_KEY='...'
```

### 8.2 Create templates and endpoints

```bash
cp deploy/runpod/template-voxcpm2.json.template deploy/runpod/template-voxcpm2.json
cp deploy/runpod/endpoint-voxcpm2.json.template deploy/runpod/endpoint-voxcpm2.json
# edit imageName, env secrets, and gpuTypeIds
chmod +x deploy/runpod/*.sh
./deploy/runpod/deploy-voxcpm2.sh
```

Or create them separately:

```bash
./deploy/runpod/create-template.sh deploy/runpod/template-voxcpm2.json
# paste the returned template id into endpoint-voxcpm2.json
./deploy/runpod/create-endpoint.sh deploy/runpod/endpoint-voxcpm2.json
```

Repeat with the WanGP templates when needed. Put the endpoint ids in `.env`:

```env
RUNPOD_API_KEY=...
RUNPOD_VOX_ENDPOINT_ID=...
RUNPOD_WAN_ENDPOINT_ID=...
```

### 8.3 Smoke-test a job

```bash
./deploy/runpod/submit-voxcpm2-inline.sh
```

Select **RunPod Serverless** in the web UI. Private registry images need a
container-registry auth configured in the RunPod console and attached to the
template (`containerRegistryAuthId`).

## 9. Deploy to Clore.ai

[Clore.ai](https://clore.ai/) is a GPU marketplace. You rent a server, pull your
Docker image, and expose the FastAPI worker port. The starter uses
`compute_provider=custom` with the rented HTTP URL. See the
[Clore API docs](https://docs.clore.ai/dev/reference/api-reference).

Clore expects a Docker Hub (or Clore-accepted) image name in the order payload.

### 9.1 Prepare environment

```bash
export CLORE_API_KEY='...'
```

### 9.2 Find a server and create an order

```bash
cp deploy/clore/order-voxcpm2.json.template deploy/clore/order-voxcpm2.json
# set image, env secrets, currency, and ssh_password
chmod +x deploy/clore/*.sh
./deploy/clore/list-marketplace.sh 'RTX 4090'
export CLORE_SERVER_ID='12345'
./deploy/clore/deploy-voxcpm2.sh
```

`wait-order.sh` prints the mapped worker URL, for example:

```bash
export CLORE_WORKER_URL='http://node123.clore.ai:40088'
```

### 9.3 Point the controller at the rental

```env
CUSTOM_WORKER_URL=http://node123.clore.ai:40088
```

In the web UI choose **Custom FastAPI URL** and paste the same URL, or set
`CUSTOM_WORKER_URL` server-side. Direct smoke test:

```bash
./deploy/clore/submit-voxcpm2-inline.sh
```

Cancel when finished:

```bash
./deploy/clore/cancel-order.sh ORDER_ID
```

`create_order` is rate-limited (about one call every five seconds). Keep
`CLORE_API_KEY` server-side only.

## 10. Deploy to Vast.ai

[Vast.ai](https://vast.ai/) is a GPU cloud marketplace with per-second billing.
You search offers, create an instance from your worker image, then point the
controller at the mapped HTTP URL with `compute_provider=custom`. See the
[Vast API hello world](https://docs.vast.ai/api-reference/hello-world).

### 10.1 Prepare environment

Put keys in `.env` (scripts load it automatically). Get an API key from
https://cloud.vast.ai/manage-keys/

```env
VAST_API_KEY=...
# optional private pull, e.g. -u USER -p TOKEN ghcr.io
VAST_IMAGE_LOGIN=
```

### 10.2 Find an offer and create an instance

```bash
cp deploy/vast/instance-voxcpm2.json.template deploy/vast/instance-voxcpm2.json
# set image to your public or private worker tag
chmod +x deploy/vast/*.sh
./deploy/vast/list-offers.sh 'RTX 4090'
```

Add the chosen offer id to `.env`, then deploy:

```env
VAST_OFFER_ID=12345678
```

```bash
./deploy/vast/deploy-voxcpm2.sh
```

`wait-instance.sh` prints values to add to `.env`, for example:

```env
VAST_WORKER_URL=http://65.x.x.x:33526
VAST_INSTANCE_ID=12345678
CUSTOM_WORKER_URL=http://65.x.x.x:33526
```

### 10.3 Point the controller at the instance

In the web UI choose **Custom FastAPI URL** (same URL as `VAST_WORKER_URL`), or
rely on `CUSTOM_WORKER_URL` in `.env`. Direct smoke test:

```bash
./deploy/vast/submit-voxcpm2-inline.sh
```

Destroy when finished (uses `VAST_INSTANCE_ID` from `.env`):

```bash
./deploy/vast/destroy-instance.sh
```

Templates use `runtype: "args"` so the image keeps `/app/start.sh`, and map
container port `8011` for VoxCPM2 (`8012` for WanGP). Keep `VAST_API_KEY`
server-side only.

## 11. Host the web and controller

The web app is static and can be deployed to Cloudflare Pages, Vercel, Netlify,
Nginx, or your existing host.

```bash
cd apps/web
corepack enable
pnpm install
VITE_API_URL=https://api.example.com pnpm build
```

Deploy `apps/web/dist`.

For the controller, deploy `services/controller/Dockerfile` to a CPU host and
set:

```env
CORS_ORIGINS=https://app.example.com,http://localhost:5173
PUBLIC_BASE_URL=https://api.example.com
```

Use HTTPS and authentication before exposing it publicly. The starter focuses
on provider orchestration; add your existing login, quotas, billing, and abuse
controls before production.

## 12. API examples

TTS:

```bash
curl -X POST http://localhost:8000/api/jobs/tts \
  -H 'Content-Type: application/json' \
  -d '{
    "text":"Hello from VoxCPM2",
    "compute_provider":"salad",
    "storage_provider":"google_drive"
  }'
```

Video:

```bash
curl -X POST http://localhost:8000/api/jobs/video \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt":"Cinematic rainy street at night",
    "model_type":"ltx2_22B_distilled",
    "resolution":"720x1280",
    "video_length":97,
    "duration_seconds":4,
    "force_fps":24,
    "num_inference_steps":8,
    "seed":42,
    "compute_provider":"salad",
    "storage_provider":"google_drive"
  }'
```

Poll:

```bash
curl http://localhost:8000/api/jobs/JOB_ID
```

## 13. Production checklist

- Add JWT/session authentication.
- Add per-user ownership to jobs and storage keys.
- Validate file types and upload sizes.
- Add content-safety and voice-consent rules.
- Validate Salad webhook signatures before trusting webhook payloads.
- Use a managed PostgreSQL database instead of SQLite for multiple replicas.
- Add cancellation, timeouts, idempotency keys, and cost limits.
- Save intermediate WanGP checkpoints for long or interruption-sensitive jobs.
- Pin Docker base images, Python packages, WanGP commit, and model revisions.
- Scan images and keep secrets in a secret manager.

## 14. Known limitations

- The included local demo uses mock inference.
- WanGP's setting names differ across model families. Start with exported WanGP
  settings and pass additional keys through `advanced_settings`.
- Google Drive links may require the signed-in Drive account unless files are
  made public.
- Salad and RunPod workers are ephemeral; generated files must be uploaded before
  the worker returns.
- Clore rentals stay billed until you cancel the order.
- Vast.ai instances stay billed until you destroy them (`destroy-instance.sh`).
- Very long video jobs need checkpointing because distributed GPU nodes can be
  interrupted.
