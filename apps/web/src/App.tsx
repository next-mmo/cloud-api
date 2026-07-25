import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Cloud, Database, Download, ExternalLink, Film, HardDrive, KeyRound, LoaderCircle, Mic2, RefreshCw, Save, Upload } from 'lucide-react'
import { API_URL, api } from './api'

type ComputeProvider = 'local' | 'salad' | 'runpod' | 'vast' | 'clore' | 'custom'
type StorageProvider = 'local' | 'r2' | 'google_drive'
type JobFilter = 'all' | 'active' | 'ready' | 'failed'
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

type Capabilities = {
  compute: Record<string, boolean>
  storage: Record<string, boolean>
  missing?: Record<string, string[]>
}

type ProviderCheck = {
  ok: boolean
  issues: string[]
  warnings: string[]
  compute_ready: boolean
  storage_ready: boolean
  worker_health: string | null
  capabilities?: Capabilities
}

const DEFAULT_PREFS: Preferences = { computeProvider: 'vast', storageProvider: 'local', customWorkerUrl: '' }
const HTTP_WORKER_PROVIDERS = new Set<ComputeProvider>(['custom', 'vast', 'clore'])
const ACTIVE_STATUSES = new Set(['submitting', 'pending', 'running'])

const COMPUTE_OPTIONS: { id: ComputeProvider; label: string; settingsGroup: string }[] = [
  { id: 'vast', label: 'Vast.ai GPU rental', settingsGroup: 'vast' },
  { id: 'clore', label: 'Clore.ai GPU rental', settingsGroup: 'clore' },
  { id: 'custom', label: 'Custom FastAPI URL', settingsGroup: 'workers' },
  { id: 'local', label: 'Local FastAPI workers', settingsGroup: 'workers' },
  { id: 'salad', label: 'SaladCloud Job Queue', settingsGroup: 'salad' },
  { id: 'runpod', label: 'RunPod Serverless', settingsGroup: 'runpod' },
]

const STORAGE_OPTIONS: { id: StorageProvider; label: string; settingsGroup: string | null }[] = [
  { id: 'local', label: 'Local disk', settingsGroup: null },
  { id: 'r2', label: 'Cloudflare R2 / S3', settingsGroup: 'r2' },
  { id: 'google_drive', label: 'Google Drive', settingsGroup: 'google_drive' },
]

function loadPreferences(): Preferences {
  try {
    const parsed = { ...DEFAULT_PREFS, ...JSON.parse(localStorage.getItem('gpu-studio.preferences') ?? '{}') }
    // Migrate removed mock provider from older browser sessions.
    if ((parsed.computeProvider as string) === 'mock') {
      parsed.computeProvider = 'vast'
    }
    return parsed
  } catch {
    return DEFAULT_PREFS
  }
}

function kindLabel(kind: string) {
  return kind === 'tts' ? 'Voice' : kind === 'video' ? 'Video' : kind
}

function statusLabel(status: string) {
  if (ACTIVE_STATUSES.has(status)) {
    if (status === 'running') return 'Working'
    if (status === 'submitting') return 'Starting'
    return 'Queued'
  }
  if (status === 'succeeded') return 'Ready'
  if (status === 'failed') return 'Failed'
  return status
}

function providerLabel(provider: string) {
  const labels: Record<string, string> = {
    local: 'Local GPU',
    custom: 'Custom worker',
    vast: 'Vast.ai',
    clore: 'Clore.ai',
    salad: 'SaladCloud',
    runpod: 'RunPod',
    mock: 'Demo',
    r2: 'Cloud storage',
    google_drive: 'Google Drive',
  }
  return labels[provider] ?? provider
}

function formatRelativeTime(iso: string) {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const seconds = Math.round((Date.now() - then) / 1000)
  if (seconds < 45) return 'Just now'
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`
  if (seconds < 86400) return `${Math.round(seconds / 3600)} hr ago`
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

function resolveResultUrl(job: Job) {
  const publicUrl = job.result?.public_url
  if (publicUrl) {
    if (publicUrl.startsWith('http://') || publicUrl.startsWith('https://')) return publicUrl
    if (publicUrl.startsWith('/')) return `${API_URL}${publicUrl}`
    return publicUrl
  }
  const uri = job.result?.output_uri
  if (!uri) return null
  if (uri.startsWith('http://') || uri.startsWith('https://')) return uri
  if (uri.startsWith('file://') || uri.startsWith('/')) {
    const name = uri.replace(/^file:\/\//, '').split('/').pop()
    return name ? `${API_URL}/files/${name}` : null
  }
  return null
}

export default function App() {
  const [prefs, setPrefs] = useState<Preferences>(loadPreferences)
  const [saved, setSaved] = useState(false)
  const [checking, setChecking] = useState(false)
  const [setupError, setSetupError] = useState('')
  const [setupWarnings, setSetupWarnings] = useState<string[]>([])
  const [setupOk, setSetupOk] = useState<boolean | null>(null)
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [jobFilter, setJobFilter] = useState<JobFilter>('all')
  const [busy, setBusy] = useState(false)
  const [ttsText, setTtsText] = useState('សួស្តី! នេះជាការសាកល្បងសំឡេងខ្មែរ។')
  const [voiceDescription, setVoiceDescription] = useState('Warm Khmer narrator, clear and confident')
  const [referenceAudioUri, setReferenceAudioUri] = useState('')
  const [videoPrompt, setVideoPrompt] = useState('Cinematic portrait shot, gentle camera movement, realistic lighting')
  const [startImageUri, setStartImageUri] = useState('')
  const [modelType, setModelType] = useState('ltx2_22B_distilled')
  const [, setTick] = useState(0)

  const activeCount = useMemo(() => jobs.filter(j => ACTIVE_STATUSES.has(j.status)).length, [jobs])
  const readyCount = useMemo(() => jobs.filter(j => j.status === 'succeeded').length, [jobs])
  const failedCount = useMemo(() => jobs.filter(j => j.status === 'failed').length, [jobs])
  const filteredJobs = useMemo(() => {
    if (jobFilter === 'active') return jobs.filter(j => ACTIVE_STATUSES.has(j.status))
    if (jobFilter === 'ready') return jobs.filter(j => j.status === 'succeeded')
    if (jobFilter === 'failed') return jobs.filter(j => j.status === 'failed')
    return jobs
  }, [jobs, jobFilter])

  async function refreshJobs() {
    try {
      const listed = await api<Job[]>('/api/jobs')
      const hydrated = await Promise.all(listed.map(job =>
        ACTIVE_STATUSES.has(job.status) ? api<Job>(`/api/jobs/${job.id}`).catch(() => job) : job
      ))
      setJobs(hydrated)
    } catch (error) { console.error(error) }
  }

  async function refreshCapabilities() {
    try {
      setCapabilities(await api<Capabilities>('/api/capabilities'))
    } catch (error) {
      console.error(error)
    }
  }

  async function validateProviders(probeWorker = true): Promise<ProviderCheck | null> {
    setChecking(true)
    setSetupError('')
    try {
      const result = await api<ProviderCheck>('/api/providers/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          compute_provider: prefs.computeProvider,
          storage_provider: prefs.storageProvider,
          custom_worker_url: prefs.customWorkerUrl || null,
          probe_worker: probeWorker,
        }),
      })
      setSetupOk(result.ok)
      setSetupWarnings(result.warnings || [])
      if (!result.ok) {
        setSetupError(result.issues.join(' '))
      }
      if (result.capabilities) setCapabilities(result.capabilities)
      return result
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      setSetupOk(false)
      setSetupError(message)
      return null
    } finally {
      setChecking(false)
    }
  }

  useEffect(() => {
    refreshJobs()
    refreshCapabilities()
    const poll = window.setInterval(refreshJobs, 4000)
    const clock = window.setInterval(() => setTick(n => n + 1), 30000)
    return () => {
      window.clearInterval(poll)
      window.clearInterval(clock)
    }
  }, [])

  useEffect(() => {
    setSaved(false)
    setSetupOk(null)
    setSetupError('')
    setSetupWarnings([])
    const timer = window.setTimeout(() => {
      void validateProviders(false)
    }, 350)
    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefs.computeProvider, prefs.storageProvider, prefs.customWorkerUrl])

  async function savePreferences() {
    const result = await validateProviders(true)
    if (!result?.ok) return
    localStorage.setItem('gpu-studio.preferences', JSON.stringify(prefs))
    setSaved(true)
    setSetupWarnings(result.warnings || [])
    window.setTimeout(() => setSaved(false), 1600)
  }

  function optionReady(kind: 'compute' | 'storage', id: string) {
    if (kind === 'storage' && id === 'local') return true
    if (!capabilities) return false
    if (kind === 'compute' && HTTP_WORKER_PROVIDERS.has(id as ComputeProvider) && prefs.customWorkerUrl.trim()) {
      return true
    }
    return Boolean(capabilities[kind]?.[id])
  }

  function workerUrlLabel() {
    if (prefs.computeProvider === 'vast') return 'Vast.ai worker URL'
    if (prefs.computeProvider === 'clore') return 'Clore.ai worker URL'
    return 'Custom worker URL'
  }

  function workerUrlPlaceholder() {
    if (prefs.computeProvider === 'vast') return 'http://host:port (or VAST_WORKER_URL in Secrets)'
    if (prefs.computeProvider === 'clore') return 'http://host:port (or CLORE_WORKER_URL in Secrets)'
    return 'http://host:port (or CUSTOM_WORKER_URL in Secrets)'
  }

  const readyCompute = useMemo(
    () => COMPUTE_OPTIONS.filter(option => optionReady('compute', option.id)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [capabilities, prefs.customWorkerUrl],
  )
  const needsCompute = useMemo(
    () => COMPUTE_OPTIONS.filter(option => !optionReady('compute', option.id)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [capabilities, prefs.customWorkerUrl],
  )
  const readyStorage = useMemo(
    () => STORAGE_OPTIONS.filter(option => optionReady('storage', option.id)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [capabilities],
  )
  const needsStorage = useMemo(
    () => STORAGE_OPTIONS.filter(option => option.settingsGroup && !optionReady('storage', option.id)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [capabilities],
  )
  const selectedNeedsSetup = !optionReady('compute', prefs.computeProvider) || !optionReady('storage', prefs.storageProvider)
  const selectedSetupGroup =
    (!optionReady('compute', prefs.computeProvider)
      ? COMPUTE_OPTIONS.find(option => option.id === prefs.computeProvider)?.settingsGroup
      : null)
    || (!optionReady('storage', prefs.storageProvider)
      ? STORAGE_OPTIONS.find(option => option.id === prefs.storageProvider)?.settingsGroup
      : null)

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
    const check = await validateProviders(true)
    if (!check?.ok) return
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
    const check = await validateProviders(true)
    if (!check?.ok) return
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
      <div><span className="eyebrow">GPU CREATION STUDIO</span><h1>WanGP + VoxCPM2</h1><p>One web UI. Local GPU workers, SaladCloud, RunPod, Vast/Clore custom FastAPI, Google Drive, or R2.</p></div>
      <div className="hero-actions">
        <Link className="nav-link" to="/settings"><KeyRound size={16}/> Secrets</Link>
        <div className="status"><Cloud size={18}/><strong>{activeCount}</strong> in progress</div>
      </div>
    </header>

    <section className="panel settings-panel">
      <div className="section-title">
        <Database/>
        <div>
          <h2>Provider settings</h2>
          <p>Pick from providers that are already set up. Anything else gets a one-click link to Secrets.</p>
        </div>
      </div>

      <div className="provider-status-board">
        <div className="provider-status-col ready">
          <span className="provider-status-title"><CheckCircle2 size={14}/> Ready to use</span>
          <div className="provider-chip-row">
            {readyCompute.map(option => (
              <button
                key={`c-${option.id}`}
                type="button"
                className={`provider-chip${prefs.computeProvider === option.id ? ' active' : ''}`}
                onClick={() => setPrefs({ ...prefs, computeProvider: option.id })}
              >
                {option.label}
              </button>
            ))}
            {readyStorage.map(option => (
              <button
                key={`s-${option.id}`}
                type="button"
                className={`provider-chip storage${prefs.storageProvider === option.id ? ' active' : ''}`}
                onClick={() => setPrefs({ ...prefs, storageProvider: option.id })}
              >
                {option.label}
              </button>
            ))}
            {!capabilities && <span className="provider-status-empty">Checking Secrets…</span>}
          </div>
        </div>

        {(needsCompute.length > 0 || needsStorage.length > 0) && (
          <div className="provider-status-col needs">
            <span className="provider-status-title"><AlertTriangle size={14}/> Needs setup</span>
            <div className="provider-chip-row">
              {needsCompute.map(option => (
                <Link
                  key={`need-c-${option.id}`}
                  className="provider-chip cta"
                  to={`/settings?group=${option.settingsGroup}`}
                >
                  Set up {option.label} <ExternalLink size={13}/>
                </Link>
              ))}
              {needsStorage.map(option => (
                <Link
                  key={`need-s-${option.id}`}
                  className="provider-chip cta"
                  to={`/settings?group=${option.settingsGroup}`}
                >
                  Set up {option.label} <ExternalLink size={13}/>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="settings-grid">
        <label>
          Compute provider
          <select value={prefs.computeProvider} onChange={e => setPrefs({...prefs, computeProvider: e.target.value as ComputeProvider})}>
            {readyCompute.map(option => (
              <option key={option.id} value={option.id}>{option.label}</option>
            ))}
            {!optionReady('compute', prefs.computeProvider) && (
              <option value={prefs.computeProvider}>
                {COMPUTE_OPTIONS.find(option => option.id === prefs.computeProvider)?.label} (needs setup)
              </option>
            )}
          </select>
        </label>
        <label>
          Storage provider
          <select value={prefs.storageProvider} onChange={e => setPrefs({...prefs, storageProvider: e.target.value as StorageProvider})}>
            {readyStorage.map(option => (
              <option key={option.id} value={option.id}>{option.label}</option>
            ))}
            {!optionReady('storage', prefs.storageProvider) && (
              <option value={prefs.storageProvider}>
                {STORAGE_OPTIONS.find(option => option.id === prefs.storageProvider)?.label} (needs setup)
              </option>
            )}
          </select>
        </label>
        {HTTP_WORKER_PROVIDERS.has(prefs.computeProvider) && (
          <label className="wide">
            {workerUrlLabel()}
            <input
              value={prefs.customWorkerUrl}
              onChange={e => setPrefs({...prefs, customWorkerUrl: e.target.value})}
              placeholder={workerUrlPlaceholder()}
            />
          </label>
        )}
        <div className="settings-actions">
          <button className="secondary" type="button" disabled={checking} onClick={() => void validateProviders(true)}>
            {checking ? <LoaderCircle className="spin" size={17}/> : <RefreshCw size={17}/>}
            Check setup
          </button>
          <button className="primary save-button" type="button" disabled={checking || setupOk === false} onClick={() => void savePreferences()}>
            {checking ? <LoaderCircle className="spin" size={17}/> : <Save size={17}/>}
            {saved ? 'Saved' : 'Save providers'}
          </button>
        </div>
      </div>

      {selectedNeedsSetup && selectedSetupGroup && (
        <div className="setup-banner bad">
          <AlertTriangle size={16}/>
          <div>
            <strong>This selection is not set up yet</strong>
            <p>{setupError || 'Add the required keys, then come back and save.'}</p>
            <Link className="cta-button" to={`/settings?group=${selectedSetupGroup}`}>
              <KeyRound size={15}/> Set up in Secrets
            </Link>
          </div>
        </div>
      )}
      {setupOk === true && !selectedNeedsSetup && (
        <div className="setup-banner ok">
          <CheckCircle2 size={16}/>
          <span>Setup looks good{setupWarnings.length ? ` — ${setupWarnings.join(' ')}` : '. You can save and generate.'}</span>
        </div>
      )}
      {setupOk === false && setupError && !selectedNeedsSetup && (
        <div className="setup-banner bad">
          <AlertTriangle size={16}/>
          <div>
            <strong>Finish setup before saving</strong>
            <p>{setupError}</p>
            <Link className="cta-button" to={selectedSetupGroup ? `/settings?group=${selectedSetupGroup}` : '/settings'}>
              <KeyRound size={15}/> Open Secrets
            </Link>
          </div>
        </div>
      )}
    </section>

    <div className="two-column">
      <form className="panel" onSubmit={submitTts}>
        <div className="section-title"><Mic2/><div><h2>VoxCPM2 TTS</h2><p>Text, voice design, and optional reference voice.</p></div></div>
        <label>Text<textarea value={ttsText} onChange={e => setTtsText(e.target.value)} rows={6}/></label>
        <label>Voice description<input value={voiceDescription} onChange={e => setVoiceDescription(e.target.value)}/></label>
        <label className="upload-box"><Upload size={18}/><span>{referenceAudioUri || 'Upload reference voice'}</span><input type="file" accept="audio/*" onChange={e => e.target.files?.[0] && uploadFile(e.target.files[0], setReferenceAudioUri)}/></label>
        <button className="primary" disabled={busy || checking || setupOk === false}><Mic2 size={18}/>Generate voice</button>
      </form>

      <form className="panel" onSubmit={submitVideo}>
        <div className="section-title"><Film/><div><h2>WanGP Video</h2><p>Submit text-to-video or image-to-video jobs.</p></div></div>
        <label>Prompt<textarea value={videoPrompt} onChange={e => setVideoPrompt(e.target.value)} rows={5}/></label>
        <label>WanGP model type<input value={modelType} onChange={e => setModelType(e.target.value)}/></label>
        <label className="upload-box"><Upload size={18}/><span>{startImageUri || 'Upload start image'}</span><input type="file" accept="image/*" onChange={e => e.target.files?.[0] && uploadFile(e.target.files[0], setStartImageUri)}/></label>
        <button className="primary" disabled={busy || checking || setupOk === false}><Film size={18}/>Generate video</button>
      </form>
    </div>

    <section className="panel jobs-panel">
      <div className="section-title">
        <HardDrive/>
        <div>
          <h2>Your results</h2>
          <p>{activeCount > 0 ? `${activeCount} in progress — this list updates automatically.` : 'Listen, watch, or download finished generations here.'}</p>
        </div>
        <button className="icon-button" onClick={refreshJobs} aria-label="Refresh results" title="Refresh"><RefreshCw size={18}/></button>
      </div>

      {jobs.length > 0 && (
        <div className="job-filters" role="tablist" aria-label="Filter results">
          {([
            ['all', `All (${jobs.length})`],
            ['active', `In progress (${activeCount})`],
            ['ready', `Ready (${readyCount})`],
            ['failed', `Failed (${failedCount})`],
          ] as const).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={jobFilter === id}
              className={`job-filter${jobFilter === id ? ' active' : ''}`}
              onClick={() => setJobFilter(id)}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      <div className="jobs-list">
        {jobs.length === 0 && (
          <div className="empty">
            <strong>Nothing here yet</strong>
            <span>Generate a voice or video above — finished files will show up in this list.</span>
          </div>
        )}
        {jobs.length > 0 && filteredJobs.length === 0 && (
          <div className="empty">
            <strong>No matches</strong>
            <span>Try another filter, or submit a new generation.</span>
          </div>
        )}
        {filteredJobs.map(job => {
          const resultUrl = resolveResultUrl(job)
          const isActive = ACTIVE_STATUSES.has(job.status)
          const isReady = job.status === 'succeeded' && Boolean(resultUrl)
          return (
            <article className={`job${isActive ? ' is-active' : ''}${job.status === 'failed' ? ' is-failed' : ''}`} key={job.id}>
              <div className="job-top">
                <div className={`job-icon ${job.kind}`}>{job.kind === 'tts' ? <Mic2 size={20}/> : <Film size={20}/>}</div>
                <div className="job-main">
                  <strong>{kindLabel(job.kind)} generation</strong>
                  <span>
                    {formatRelativeTime(job.created_at)}
                    {' · '}
                    {providerLabel(job.compute_provider)}
                    {job.status === 'succeeded' ? ` · saved to ${providerLabel(job.storage_provider)}` : ''}
                  </span>
                  {job.error && <small className="error">{job.error}</small>}
                  {job.result?.message && !job.error && <small className="job-note">{job.result.message}</small>}
                </div>
                <div className={`badge ${job.status}`}>
                  {isActive && <LoaderCircle className="spin" size={14}/>}
                  {statusLabel(job.status)}
                </div>
              </div>

              {isActive && (
                <div className="job-progress" aria-hidden="true">
                  <span className="job-progress-bar"/>
                </div>
              )}

              {isReady && resultUrl && (
                <div className="job-result">
                  {job.kind === 'tts' ? (
                    <audio className="job-player" controls preload="metadata" src={resultUrl}>
                      Your browser does not support audio playback.
                    </audio>
                  ) : (
                    <video className="job-player job-video" controls preload="metadata" src={resultUrl}/>
                  )}
                  <div className="job-actions">
                    <a className="result-button" href={resultUrl} download>
                      <Download size={16}/> Download
                    </a>
                    <a className="result-button ghost" href={resultUrl} target="_blank" rel="noreferrer">
                      <ExternalLink size={16}/> Open
                    </a>
                  </div>
                </div>
              )}

              {job.status === 'succeeded' && !resultUrl && (
                <div className="job-result job-result-missing">
                  Finished, but no playable file URL was returned. Check storage settings or worker logs.
                </div>
              )}
            </article>
          )
        })}
      </div>
    </section>
  </main>
}
