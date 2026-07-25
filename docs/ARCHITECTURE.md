# Architecture

```text
React/Vite web
    |
    v
FastAPI controller (CPU)
    |-- provider=local/custom --> direct FastAPI worker
    |-- provider=salad -------> Salad Job Queue API
    |-- provider=runpod ------> RunPod Serverless API
    |
    +--> local / R2-S3 / Google Drive storage

GPU workers
    |-- VoxCPM2 worker --> WAV
    +-- WanGP worker ---> MP4
```

The browser stores only the selected provider names and custom public URL in
`localStorage`. Cloud API keys and storage credentials stay in controller or
worker environment variables.

WanGP and VoxCPM2 use separate images because their CUDA, PyTorch, and model
requirements can diverge. It also lets each queue scale to zero independently.
