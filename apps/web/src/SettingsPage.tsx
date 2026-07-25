import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ChevronDown, ExternalLink, HardDrive, KeyRound, LoaderCircle, Save, Trash2, Upload } from 'lucide-react'
import { api } from './api'

type FieldDef = {
  key: string
  label: string
  kind: 'secret' | 'text' | 'url' | 'number'
  help?: string
  placeholder?: string
  secret: boolean
}

type GroupDef = {
  id: string
  title: string
  description: string
  docs_url?: string | null
  console_url?: string | null
  keys_url?: string | null
  fields: FieldDef[]
}

type FieldStatus = {
  key: string
  configured: boolean
  secret: boolean
  hint: string | null
  value: string | null
}

type SettingsStatus = {
  configured_count: number
  fields: FieldStatus[]
}

/** Groups that match the studio's selected compute / storage providers. */
function preferredGroupIds(): string[] {
  try {
    const prefs = JSON.parse(localStorage.getItem('gpu-studio.preferences') ?? '{}') as {
      computeProvider?: string
      storageProvider?: string
    }
    const ids = new Set<string>()
    const compute = prefs.computeProvider
    if (compute === 'local' || compute === 'custom') ids.add('workers')
    if (compute === 'vast') ids.add('vast')
    if (compute === 'clore') ids.add('clore')
    if (compute === 'custom') {
      ids.add('vast')
      ids.add('clore')
    }
    if (compute === 'salad') ids.add('salad')
    if (compute === 'runpod') ids.add('runpod')
    if (prefs.storageProvider === 'r2') ids.add('r2')
    if (prefs.storageProvider === 'google_drive') ids.add('google_drive')
    return [...ids]
  } catch {
    return []
  }
}

function groupConfiguredCount(group: GroupDef, statusByKey: Record<string, FieldStatus>) {
  return group.fields.filter(field => statusByKey[field.key]?.configured).length
}

export default function SettingsPage() {
  const [searchParams] = useSearchParams()
  const focusGroup = searchParams.get('group')
  const [groups, setGroups] = useState<GroupDef[]>([])
  const [statusByKey, setStatusByKey] = useState<Record<string, FieldStatus>>({})
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set())
  const [uploadOpen, setUploadOpen] = useState(true)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [envText, setEnvText] = useState('')
  const [envFileName, setEnvFileName] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [driveConnecting, setDriveConnecting] = useState(false)
  const [replacingKeys, setReplacingKeys] = useState<Set<string>>(new Set())

  const preferred = useMemo(() => preferredGroupIds(), [])
  const driveConnected = Boolean(statusByKey.GOOGLE_DRIVE_REFRESH_TOKEN?.configured)
  const configuredCount = useMemo(
    () => Object.values(statusByKey).filter(item => item.configured).length,
    [statusByKey],
  )

  async function refresh() {
    const [schema, status] = await Promise.all([
      api<{ groups: GroupDef[] }>('/api/settings/schema'),
      api<SettingsStatus>('/api/settings'),
    ])
    setGroups(schema.groups)
    const map: Record<string, FieldStatus> = {}
    for (const field of status.fields) map[field.key] = field
    setStatusByKey(map)
    // Prefill non-secret configured values; secrets stay blank (never returned).
    const nextDraft: Record<string, string> = {}
    for (const field of status.fields) {
      if (!field.secret && field.value != null) nextDraft[field.key] = field.value
    }
    setDraft(nextDraft)
    setReplacingKeys(new Set())
    return { groups: schema.groups, map, configuredCount: status.configured_count }
  }

  useEffect(() => {
    let cancelled = false
    refresh()
      .then(({ groups: loaded, map, configuredCount: count }) => {
        if (cancelled) return
        const next = new Set(preferred)
        for (const group of loaded) {
          if (group.fields.some(field => map[field.key]?.configured)) next.add(group.id)
        }
        if (focusGroup && loaded.some(group => group.id === focusGroup)) {
          next.add(focusGroup)
        }
        // Always surface at least the active provider so the page isn't all closed.
        if (next.size === 0 && loaded[0]) next.add(loaded[0].id)
        setOpenGroups(next)
        if (count > 0) {
          setMessage(`Vault persisted — loaded ${count} encrypted key${count === 1 ? '' : 's'} after reload. Secret values stay masked.`)
        }
        if (focusGroup) {
          window.setTimeout(() => {
            document.getElementById(`settings-group-${focusGroup}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }, 80)
        }
      })
      .catch(err => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      })
    return () => { cancelled = true }
  }, [preferred, focusGroup])

  function setField(key: string, value: string) {
    setDraft(prev => ({ ...prev, [key]: value }))
  }

  function toggleGroup(id: string) {
    setOpenGroups(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function expandPreferred() {
    setOpenGroups(new Set(preferred.length ? preferred : groups.slice(0, 1).map(g => g.id)))
  }

  function expandAll() {
    setOpenGroups(new Set(groups.map(g => g.id)))
  }

  function collapseAll() {
    setOpenGroups(new Set())
  }

  async function saveFields(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const values: Record<string, string | null> = {}
      for (const [key, value] of Object.entries(draft)) {
        if (value.trim() !== '') values[key] = value
      }
      const status = await api<SettingsStatus>('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ values }),
      })
      const map: Record<string, FieldStatus> = {}
      for (const field of status.fields) map[field.key] = field
      setStatusByKey(map)
      // Clear secret drafts after save so plaintext never lingers in the form.
      setDraft(prev => {
        const next: Record<string, string> = {}
        for (const [key, value] of Object.entries(prev)) {
          if (map[key]?.secret) continue
          if (!map[key]?.secret && map[key]?.value != null) next[key] = map[key].value as string
          else if (value && !map[key]?.secret) next[key] = value
        }
        for (const field of status.fields) {
          if (!field.secret && field.value != null) next[field.key] = field.value
        }
        return next
      })
      setMessage(`Saved. ${status.configured_count} keys encrypted on the server.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function clearKey(key: string) {
    setBusy(true)
    setError('')
    try {
      const status = await api<SettingsStatus>('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ values: { [key]: '__CLEAR__' } }),
      })
      const map: Record<string, FieldStatus> = {}
      for (const field of status.fields) map[field.key] = field
      setStatusByKey(map)
      setDraft(prev => {
        const next = { ...prev }
        delete next[key]
        return next
      })
      setMessage(`Cleared ${key}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function clearAll() {
    if (!window.confirm('Remove all encrypted provider settings from the server vault?')) return
    setBusy(true)
    setError('')
    try {
      await api('/api/settings', { method: 'DELETE' })
      setDraft({})
      await refresh()
      setMessage('Vault cleared')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function uploadEnv(replace: boolean, contentOverride?: string) {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const content = (contentOverride ?? envText).trim()
      if (!content) throw new Error('Paste .env content or choose a file first')
      const status = await api<SettingsStatus>('/api/settings/env', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, replace }),
      })
      const map: Record<string, FieldStatus> = {}
      for (const field of status.fields) map[field.key] = field
      setStatusByKey(map)
      setEnvText('')
      setEnvFileName('')
      setDraft({})
      const refreshed = await refresh()
      const next = new Set(preferred)
      for (const group of refreshed.groups) {
        if (group.fields.some(field => refreshed.map[field.key]?.configured)) next.add(group.id)
      }
      setOpenGroups(next)
      setMessage(`Imported .env — ${status.configured_count} keys stored encrypted. Secrets are not shown again.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function onEnvFile(file: File, autoImport = true) {
    setUploadOpen(true)
    setEnvFileName(file.name)
    const text = await file.text()
    setEnvText(text)
    if (!text.trim()) {
      setError('That file is empty.')
      return
    }
    if (autoImport) {
      await uploadEnv(false, text)
    }
  }

  async function connectGoogleDrive() {
    setDriveConnecting(true)
    setError('')
    setMessage('')
    try {
      const started = await api<{ status: string; auth_url?: string; error?: string; hint?: string }>(
        '/api/settings/google-drive/connect',
        { method: 'POST' },
      )
      if (started.auth_url) {
        window.open(started.auth_url, '_blank', 'noopener,noreferrer')
      }
      setMessage(started.hint || 'Complete Google Allow in the browser window…')
      const deadline = Date.now() + 180_000
      while (Date.now() < deadline) {
        await new Promise(resolve => window.setTimeout(resolve, 1200))
        const status = await api<{ status: string; error?: string | null }>('/api/settings/google-drive/connect')
        if (status.status === 'succeeded') {
          await refresh()
          setOpenGroups(prev => new Set([...prev, 'google_drive']))
          setMessage('Google Drive connected. Refresh token encrypted on the server — no Cloud Console setup needed.')
          return
        }
        if (status.status === 'failed' || status.status === 'expired') {
          throw new Error(status.error || 'Google Drive connect failed')
        }
      }
      throw new Error('Timed out waiting for Google Allow. Try Connect again.')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setDriveConnecting(false)
    }
  }

  return (
    <main className="settings-page">
      <header className="hero settings-hero">
        <div>
          <Link className="back-link" to="/"><ArrowLeft size={16}/> Studio</Link>
          <span className="eyebrow">SECURE SETTINGS</span>
          <h1>Provider secrets</h1>
          <p>
            Upload a <code>.env</code> or open a provider below. Values are encrypted on the API server and
            persist across hard reloads. Secret fields never return plaintext — only a short hint.
          </p>
        </div>
        <div className="status"><KeyRound size={18}/><strong>{configuredCount}</strong> encrypted keys</div>
      </header>

      {(message || error) && (
        <div className={`banner ${error ? 'error' : 'ok'}`}>{error || message}</div>
      )}

      <section className={`panel collapsible-panel${uploadOpen ? ' open' : ''}`}>
        <button type="button" className="collapse-toggle" onClick={() => setUploadOpen(v => !v)} aria-expanded={uploadOpen}>
          <Upload/>
          <div className="collapse-copy">
            <h2>Upload .env</h2>
            <p>Click below to choose a file (or drag it in). The header only expands this section.</p>
          </div>
          <ChevronDown className={`chevron${uploadOpen ? ' open' : ''}`} size={20}/>
        </button>
        {uploadOpen && (
          <div className="collapse-body">
            <label
              className={`upload-box env-drop${dragOver ? ' drag-over' : ''}`}
              onDragEnter={e => { e.preventDefault(); setDragOver(true) }}
              onDragOver={e => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={e => { e.preventDefault(); setDragOver(false) }}
              onDrop={e => {
                e.preventDefault()
                setDragOver(false)
                const file = e.dataTransfer.files?.[0]
                if (file) void onEnvFile(file, true)
              }}
            >
              <Upload size={18}/>
              <span>{envFileName ? `Selected: ${envFileName}` : 'Choose .env / .txt file, or drop it here'}</span>
              {/* No accept filter — macOS often hides `.env` when accept=".env" is set */}
              <input
                type="file"
                onChange={e => {
                  const file = e.target.files?.[0]
                  if (file) void onEnvFile(file, true)
                  e.target.value = ''
                }}
              />
            </label>
            <label>
              Or paste .env contents
              <textarea
                rows={8}
                value={envText}
                onChange={e => setEnvText(e.target.value)}
                placeholder={'VAST_API_KEY=...\nCUSTOM_WORKER_URL=http://...'}
              />
            </label>
            <div className="button-row">
              <button type="button" className="primary" disabled={busy || !envText.trim()} onClick={() => void uploadEnv(false)}>
                {busy ? <LoaderCircle className="spin" size={18}/> : <Upload size={18}/>}
                Merge into vault
              </button>
              <button type="button" className="secondary" disabled={busy || !envText.trim()} onClick={() => void uploadEnv(true)}>
                Replace vault
              </button>
            </div>
          </div>
        )}
      </section>

      <div className="accordion-toolbar">
        <p>Providers collapse by default. Open ones match your studio selection{preferred.length ? ` (${preferred.join(', ')})` : ''} and any keys already saved.</p>
        <div className="button-row">
          <button type="button" className="ghost-button" onClick={expandPreferred}>My providers</button>
          <button type="button" className="ghost-button" onClick={expandAll}>Expand all</button>
          <button type="button" className="ghost-button" onClick={collapseAll}>Collapse all</button>
        </div>
      </div>

      <form className="settings-form" onSubmit={saveFields}>
        {groups.map(group => {
          const open = openGroups.has(group.id)
          const savedCount = groupConfiguredCount(group, statusByKey)
          const isPreferred = preferred.includes(group.id)
          return (
            <section
              id={`settings-group-${group.id}`}
              className={`panel collapsible-panel${open ? ' open' : ''}${isPreferred ? ' preferred' : ''}${focusGroup === group.id ? ' focus-target' : ''}`}
              key={group.id}
            >
              <button
                type="button"
                className="collapse-toggle"
                onClick={() => toggleGroup(group.id)}
                aria-expanded={open}
              >
                <KeyRound/>
                <div className="collapse-copy">
                  <h2>
                    {group.title}
                    {isPreferred && <em className="active-provider-pill">active</em>}
                    {savedCount > 0 && <em className="configured-pill">{savedCount}/{group.fields.length} saved</em>}
                  </h2>
                  <p>{group.description}</p>
                </div>
                <ChevronDown className={`chevron${open ? ' open' : ''}`} size={20}/>
              </button>

              {open && (
                <div className="collapse-body">
                  <div className="provider-links">
                    {group.console_url && (
                      <a href={group.console_url} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Console</a>
                    )}
                    {group.keys_url && (
                      <a href={group.keys_url} target="_blank" rel="noreferrer"><ExternalLink size={14}/> API keys</a>
                    )}
                    {group.docs_url && (
                      <a href={group.docs_url} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Docs</a>
                    )}
                  </div>
                  {group.id === 'google_drive' && (
                    <div className="easy-connect">
                      <div>
                        <strong>Easy connect (rclone style)</strong>
                        <p>
                          No Google Cloud Console app. Click Connect, Allow in the browser, done.
                          Leave client ID / secret blank — we use rclone&apos;s built-in Google OAuth app.
                        </p>
                        {driveConnected && <small className="ok-text">Drive refresh token is saved encrypted.</small>}
                      </div>
                      <button type="button" className="primary" disabled={busy || driveConnecting} onClick={connectGoogleDrive}>
                        {driveConnecting ? <LoaderCircle className="spin" size={18}/> : <HardDrive size={18}/>}
                        {driveConnected ? 'Reconnect Google Drive' : 'Connect with Google'}
                      </button>
                    </div>
                  )}
                  <div className="settings-fields">
                    {group.fields.map(field => {
                      const status = statusByKey[field.key]
                      const configured = Boolean(status?.configured)
                      const inputType = field.kind === 'secret' ? 'password' : field.kind === 'number' ? 'number' : 'text'
                      const replacing = replacingKeys.has(field.key)
                      const showSecretLock = configured && field.secret && !replacing
                      const placeholder = configured && field.secret
                        ? status?.hint || '•••• configured'
                        : field.placeholder || ''
                      return (
                        <label key={field.key} className={`settings-field${configured ? ' is-configured' : ''}`}>
                          <span className="field-label">
                            {field.label}
                            <code>{field.key}</code>
                            {configured && <em className="configured-pill">saved · persists</em>}
                          </span>
                          <div className="field-row">
                            {showSecretLock ? (
                              <div className="secret-persisted" title="Encrypted on server — plaintext is never returned">
                                <KeyRound size={15}/>
                                <span>{status?.hint || '•••• saved'}</span>
                                <em>encrypted on server</em>
                              </div>
                            ) : (
                              <input
                                type={inputType}
                                autoComplete="off"
                                spellCheck={false}
                                value={draft[field.key] ?? ''}
                                placeholder={placeholder}
                                onChange={e => setField(field.key, e.target.value)}
                              />
                            )}
                            {showSecretLock && (
                              <button
                                type="button"
                                className="ghost-button"
                                onClick={() => setReplacingKeys(prev => new Set([...prev, field.key]))}
                                title="Replace value"
                              >
                                Replace
                              </button>
                            )}
                            {configured && (
                              <button type="button" className="icon-button" title={`Clear ${field.key}`} onClick={() => clearKey(field.key)}>
                                <Trash2 size={16}/>
                              </button>
                            )}
                          </div>
                          {field.help && <small>{field.help}</small>}
                        </label>
                      )
                    })}
                  </div>
                </div>
              )}
            </section>
          )
        })}

        <div className="button-row sticky-actions">
          <button className="primary" disabled={busy} type="submit">
            {busy ? <LoaderCircle className="spin" size={18}/> : <Save size={18}/>}
            Save encrypted settings
          </button>
          <button type="button" className="secondary danger" disabled={busy} onClick={clearAll}>
            <Trash2 size={16}/> Clear vault
          </button>
        </div>
      </form>
    </main>
  )
}
