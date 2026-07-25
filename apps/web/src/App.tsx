import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Cloud, Database, Film, HardDrive, LoaderCircle, Mic2, RefreshCw, Save, Upload } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

type ComputeProvider = 'mock' | 'local' | 'salad' | 'runpod' | 'custom'
type StorageProvider = 'local' | 'r2' | 'google_drive'
type Job = {
  id: string
  kind: string
  status: string
  compute_provider: string
  storage_provider: string
  result?: { public_url?: string; output_uri?: string; message?: string } | null
  error?: string | null
  created_at: string
}

type Preferences = {
  computeProvider: ComputeProvider
  storageProvider: StorageProvider
  customWorkerUrl: string
}

const DEFAULT_PREFS: Preferences = { computeProvider: 'mock', storageProvider: 'local', customWorkerUrl: '' }

function loadPreferences(): Preferences {
  try {
    return { ...DEFAULT_PREFS, ...JSON.parse(localStorage.getItem('gpu-studio.preferences') ?? '{}') }
  } catch {
    return DEFAULT_PREFS
  }
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

export default function App() {
  const [prefs, setPrefs] = useState<Preferences>(loadPreferences)
  const [saved, setSaved] = useState(false)
  const [jobs, setJobs] = useState<Job[]>([])
  const [busy, setBusy] = useState(false)
  const [ttsText, setTtsText] = useState('សួស្តី! នេះជាការសាកល្បងសំឡេងខ្មែរ។')
  const [voiceDescription, setVoiceDescription] = useState('Warm Khmer narrator, clear and confident')
  const [referenceAudioUri, setReferenceAudioUri] = useState('')
  const [videoPrompt, setVideoPrompt] = useState('Cinematic portrait shot, gentle camera movement, realistic lighting')
  const [startImageUri, setStartImageUri] = useState('')
  const [modelType, setModelType] = useState('ltx2_22B_distilled')

  const activeCount = useMemo(() => jobs.filter(j => ['submitting', 'pending', 'running'].includes(j.status)).length, [jobs])

  async function refreshJobs() {
    try {
      const listed = await api<Job[]>('/api/jobs')
      const hydrated = await Promise.all(listed.map(job =>
        ['pending', 'running'].includes(job.status) ? api<Job>(`/api/jobs/${job.id}`).catch(() => job) : job
      ))
      setJobs(hydrated)
    } catch (error) { console.error(error) }
  }

  useEffect(() => {
    refreshJobs()
    const timer = window.setInterval(refreshJobs, 4000)
    return () => window.clearInterval(timer)
  }, [])

  function savePreferences() {
    localStorage.setItem('gpu-studio.preferences', JSON.stringify(prefs))
    setSaved(true)
    window.setTimeout(() => setSaved(false), 1400)
  }

  async function uploadFile(file: File, setter: (uri: string) => void) {
    const form = new FormData()
    form.append('file', file)
    form.append('storage_provider', prefs.storageProvider)
    setBusy(true)
    try {
      const result = await api<{ uri: string }>('/api/uploads', { method: 'POST', body: form })
      setter(result.uri)
    } finally {
      setBusy(false)
    }
  }

  async function submitTts(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      await api('/api/jobs/tts', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: ttsText, voice_description: voiceDescription || null,
          reference_audio_uri: referenceAudioUri || null,
          compute_provider: prefs.computeProvider, storage_provider: prefs.storageProvider,
          custom_worker_url: prefs.customWorkerUrl || null,
        }),
      })
      await refreshJobs()
    } finally { setBusy(false) }
  }

  async function submitVideo(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      await api('/api/jobs/video', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: videoPrompt, model_type: modelType, start_image_uri: startImageUri || null,
          compute_provider: prefs.computeProvider, storage_provider: prefs.storageProvider,
          custom_worker_url: prefs.customWorkerUrl || null,
          resolution: '720x1280', video_length: 97, duration_seconds: 4,
          force_fps: 24, num_inference_steps: 8, seed: 42,
        }),
      })
      await refreshJobs()
    } finally { setBusy(false) }
  }

  return <main>
    <header className="hero">
      <div><span className="eyebrow">GPU CREATION STUDIO</span><h1>WanGP + VoxCPM2</h1><p>One web UI. Local workers, SaladCloud, RunPod, custom FastAPI, Google Drive, or R2.</p></div>
      <div className="status"><Cloud size={18}/><strong>{activeCount}</strong> active jobs</div>
    </header>

    <section className="panel settings-panel">
      <div className="section-title"><Database/><div><h2>Provider settings</h2><p>Selections are saved in this browser. Secrets stay on your API server.</p></div></div>
      <div className="settings-grid">
        <label>Compute provider<select value={prefs.computeProvider} onChange={e => setPrefs({...prefs, computeProvider: e.target.value as ComputeProvider})}>
          <option value="mock">Mock demo</option><option value="local">Local FastAPI workers</option><option value="salad">SaladCloud Job Queue</option><option value="runpod">RunPod Serverless</option><option value="custom">Custom FastAPI URL</option>
        </select></label>
        <label>Storage provider<select value={prefs.storageProvider} onChange={e => setPrefs({...prefs, storageProvider: e.target.value as StorageProvider})}>
          <option value="local">Local disk</option><option value="r2">Cloudflare R2 / S3</option><option value="google_drive">Google Drive</option>
        </select></label>
        {prefs.computeProvider === 'custom' && <label className="wide">Custom worker URL<input value={prefs.customWorkerUrl} onChange={e => setPrefs({...prefs, customWorkerUrl: e.target.value})} placeholder="https://worker.example.com" /></label>}
        <button className="primary save-button" onClick={savePreferences}><Save size={17}/>{saved ? 'Saved' : 'Save providers'}</button>
      </div>
    </section>

    <div className="two-column">
      <form className="panel" onSubmit={submitTts}>
        <div className="section-title"><Mic2/><div><h2>VoxCPM2 TTS</h2><p>Text, voice design, and optional reference voice.</p></div></div>
        <label>Text<textarea value={ttsText} onChange={e => setTtsText(e.target.value)} rows={6}/></label>
        <label>Voice description<input value={voiceDescription} onChange={e => setVoiceDescription(e.target.value)}/></label>
        <label className="upload-box"><Upload size={18}/><span>{referenceAudioUri || 'Upload reference voice'}</span><input type="file" accept="audio/*" onChange={e => e.target.files?.[0] && uploadFile(e.target.files[0], setReferenceAudioUri)}/></label>
        <button className="primary" disabled={busy}><Mic2 size={18}/>Generate voice</button>
      </form>

      <form className="panel" onSubmit={submitVideo}>
        <div className="section-title"><Film/><div><h2>WanGP Video</h2><p>Submit text-to-video or image-to-video jobs.</p></div></div>
        <label>Prompt<textarea value={videoPrompt} onChange={e => setVideoPrompt(e.target.value)} rows={5}/></label>
        <label>WanGP model type<input value={modelType} onChange={e => setModelType(e.target.value)}/></label>
        <label className="upload-box"><Upload size={18}/><span>{startImageUri || 'Upload start image'}</span><input type="file" accept="image/*" onChange={e => e.target.files?.[0] && uploadFile(e.target.files[0], setStartImageUri)}/></label>
        <button className="primary" disabled={busy}><Film size={18}/>Generate video</button>
      </form>
    </div>

    <section className="panel jobs-panel">
      <div className="section-title"><HardDrive/><div><h2>Recent jobs</h2><p>Queued jobs are polled every four seconds.</p></div><button className="icon-button" onClick={refreshJobs}><RefreshCw size={18}/></button></div>
      <div className="jobs-list">
        {jobs.length === 0 && <div className="empty">No jobs yet. Mock mode works immediately.</div>}
        {jobs.map(job => <article className="job" key={job.id}>
          <div className={`job-icon ${job.kind}`}>{job.kind === 'tts' ? <Mic2/> : <Film/>}</div>
          <div className="job-main"><strong>{job.kind.toUpperCase()} · {job.id.slice(0, 8)}</strong><span>{job.compute_provider} → {job.storage_provider}</span>{job.error && <small className="error">{job.error}</small>}</div>
          <div className={`badge ${job.status}`}>{['submitting','pending','running'].includes(job.status) && <LoaderCircle className="spin" size={14}/>} {job.status}</div>
          {(job.result?.public_url || job.result?.output_uri) && <a className="result-link" href={job.result.public_url || '#'} target="_blank" rel="noreferrer">Open result</a>}
        </article>)}
      </div>
    </section>
  </main>
}
