import { useState, useEffect, useRef } from 'react'
import { Modal, Input, Button, Toast } from './index.jsx'
import { fetchApi } from '../api/client.js'

// The backend callback URL.
// Hardcoded to http://localhost:8080 for both dev and production: the OAuth flow
// must be completed FROM the host server's browser (Windows production host),
// so the redirect URI is always localhost from that machine's perspective.
// Don't derive from window.location — accessing the console from another machine
// on the LAN would send Google a non-localhost redirect URI that the OAuth client
// is not configured for.
const CALLBACK_URI = "http://localhost:8080/api/credentials/youtube/callback"

const STEPS = [
  {
    id: 'gcp_project',
    label: 'Create Google Cloud Project',
    type: 'manual',
    description: 'Create a project in Google Cloud Console to house your YouTube API credentials. If you already have one, skip this step.',
    link: 'https://console.cloud.google.com/projectcreate',
    linkLabel: 'Open Google Cloud Console →',
  },
  {
    id: 'enable_api',
    label: 'Enable YouTube Data API v3',
    type: 'manual',
    description: 'In your Google Cloud project, enable the YouTube Data API v3.',
    link: 'https://console.cloud.google.com/apis/library/youtube.googleapis.com',
    linkLabel: 'Open YouTube Data API Library →',
  },
  {
    id: 'create_oauth',
    label: 'Create OAuth 2.0 Credentials',
    type: 'manual',
    description: 'Create a Web Application OAuth 2.0 client ID. In "Authorized redirect URIs", add the URI shown below exactly as written.',
    link: 'https://console.cloud.google.com/apis/credentials',
    linkLabel: 'Open Credentials Page →',
    callbackUri: true,
  },
  {
    id: 'enter_creds',
    label: 'Enter Credentials',
    type: 'form',
  },
  {
    id: 'authorize',
    label: 'Authorize with Google',
    type: 'oauth',
  },
  {
    id: 'verify',
    label: 'Verify Connection',
    type: 'verify',
  },
  {
    id: 'create_channel',
    label: 'Create Channel Entry',
    type: 'create',
  },
]

export default function YouTubeSetupWizard({ onClose, onComplete }) {
  const [step, setStep] = useState(0)
  const [manualChecked, setManualChecked] = useState({})
  const [form, setForm] = useState({ name: '', client_id: '', client_secret: '' })
  const [credId, setCredId] = useState(null)
  const [oauthUrl, setOauthUrl] = useState(null)
  const [verifyResult, setVerifyResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const pollRef = useRef(null)

  const showToast = (msg, type = 'error') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 5000)
  }

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const current = STEPS[step]

  const handleNext = async () => {
    if (current.type === 'manual') {
      setStep(s => s + 1)
      return
    }

    if (current.type === 'form') {
      if (!form.name.trim() || !form.client_id.trim() || !form.client_secret.trim()) {
        showToast('All three fields are required')
        return
      }
      setLoading(true)
      try {
        const res = await fetchApi('/api/credentials/youtube/setup/start', {
          method: 'POST',
          body: JSON.stringify({
            name: form.name.trim(),
            client_id: form.client_id.trim(),
            client_secret: form.client_secret.trim(),
            redirect_uri: CALLBACK_URI,
          }),
        })
        setCredId(res.cred_id)
        setOauthUrl(res.oauth_url)
        setStep(s => s + 1)
      } catch (e) {
        showToast(e.message)
      } finally {
        setLoading(false)
      }
      return
    }

    if (current.type === 'verify') {
      setLoading(true)
      try {
        const res = await fetchApi(`/api/credentials/youtube/setup/verify/${credId}`, { method: 'POST' })
        setVerifyResult(res)
        setStep(s => s + 1)
      } catch (e) {
        showToast(e.message)
      } finally {
        setLoading(false)
      }
      return
    }

    if (current.type === 'create') {
      setLoading(true)
      try {
        await fetchApi(`/api/credentials/youtube/setup/create-channel/${credId}`, { method: 'POST' })
        onComplete?.()
        onClose()
      } catch (e) {
        showToast(e.message)
      } finally {
        setLoading(false)
      }
      return
    }
  }

  const startOAuth = () => {
    if (!oauthUrl) return
    window.open(oauthUrl, '_blank')
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetchApi(`/api/credentials/youtube/setup/status/${credId}`)
        if (res.status === 'connected') {
          clearInterval(pollRef.current)
          setStep(s => s + 1)
        }
      } catch {}
    }, 3000)
  }

  const canNext = () => {
    if (current.type === 'manual') return !!manualChecked[current.id]
    if (current.type === 'form') return true
    if (current.type === 'oauth') return false
    if (current.type === 'verify') return true
    if (current.type === 'create') return true
    return false
  }

  const isLastStep = step === STEPS.length - 1

  const cliCommand = `python3 scripts/setup_youtube_oauth.py \\
  --client-id  "${form.client_id || 'YOUR_CLIENT_ID'}" \\
  --client-secret "${form.client_secret || 'YOUR_CLIENT_SECRET'}" \\
  --channel-name "${form.name || 'ChannelName'}"`

  return (
    <Modal
      open
      onClose={onClose}
      title="Add YouTube Channel"
      width="max-w-xl"
      footer={
        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          {current.type !== 'oauth' && (
            <Button variant="primary" loading={loading} disabled={!canNext()} onClick={handleNext}>
              {isLastStep ? 'Finish' : 'Next →'}
            </Button>
          )}
        </div>
      }
    >
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}

      {/* Progress bar */}
      <div className="flex gap-1 mb-5">
        {STEPS.map((s, i) => (
          <div key={s.id} className={`flex-1 h-1 rounded-full transition-colors ${
            i < step ? 'bg-[#34d399]' : i === step ? 'bg-[#7c6af7]' : 'bg-[#2a2a32]'
          }`} />
        ))}
      </div>

      <div className="text-[10px] text-[#5a5a70] font-mono uppercase tracking-widest mb-1">
        Step {step + 1} of {STEPS.length}
      </div>
      <div className="text-base font-semibold text-[#e8e8f0] mb-4">{current.label}</div>

      {/* Manual step */}
      {current.type === 'manual' && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-[#9090a8] leading-relaxed">{current.description}</p>
          {current.callbackUri && (
            <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3">
              <div className="text-xs text-[#5a5a70] mb-1.5">Authorized Redirect URI to add:</div>
              <div className="flex items-center gap-2">
                <code className="text-xs font-mono text-[#7c6af7] flex-1 break-all">{CALLBACK_URI}</code>
                <button
                  onClick={() => navigator.clipboard.writeText(CALLBACK_URI)}
                  className="text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-0.5 bg-[#16161a] rounded border border-[#2a2a32] flex-shrink-0"
                >
                  Copy
                </button>
              </div>
            </div>
          )}
          <a
            href={current.link}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-sm text-[#7c6af7] hover:text-[#9d8df8] transition-colors"
          >
            {current.linkLabel}
          </a>
          <label className="flex items-center gap-2 text-sm text-[#9090a8] cursor-pointer select-none">
            <input
              type="checkbox"
              checked={!!manualChecked[current.id]}
              onChange={e => setManualChecked(p => ({ ...p, [current.id]: e.target.checked }))}
              className="accent-[#7c6af7]"
            />
            Done — ready to continue
          </label>
        </div>
      )}

      {/* Form step */}
      {current.type === 'form' && (
        <div className="flex flex-col gap-3">
          <Input
            label="Channel Nickname"
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            placeholder="e.g. Sleep Sounds Main"
          />
          <Input
            label="Client ID"
            value={form.client_id}
            onChange={e => setForm(f => ({ ...f, client_id: e.target.value }))}
            placeholder="1234567890-xxxx.apps.googleusercontent.com"
          />
          <Input
            label="Client Secret"
            type="password"
            value={form.client_secret}
            onChange={e => setForm(f => ({ ...f, client_secret: e.target.value }))}
            placeholder="GOCSPX-..."
          />
          <details className="mt-1 group">
            <summary className="text-xs text-[#5a5a70] cursor-pointer hover:text-[#9090a8]">
              Advanced: run via CLI instead
            </summary>
            <div className="mt-2 bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
              <pre className="text-xs font-mono text-[#9090a8] whitespace-pre-wrap break-all pr-12">{cliCommand}</pre>
              <button
                onClick={() => navigator.clipboard.writeText(cliCommand)}
                className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-0.5 bg-[#16161a] rounded border border-[#2a2a32]"
              >
                Copy
              </button>
            </div>
          </details>
        </div>
      )}

      {/* OAuth step */}
      {current.type === 'oauth' && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-[#9090a8] leading-relaxed">
            Click below to open Google's authorization screen in a new tab. Sign in with the Google account that owns the YouTube channel.
          </p>
          <div className="bg-[#fbbf24]/10 border border-[#fbbf24]/30 rounded-lg p-3 text-xs text-[#fbbf24] leading-relaxed">
            If your OAuth app is in <strong>Testing mode</strong>, only accounts listed as Test Users can authorize.{' '}
            <a
              href="https://console.cloud.google.com/apis/credentials/consent"
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              Add your account → OAuth consent screen → Test users
            </a>
          </div>
          <Button variant="primary" onClick={startOAuth}>
            Open Google Authorization →
          </Button>
          <div className="flex items-center gap-2 text-xs text-[#5a5a70]">
            <div className="flex gap-1">
              {[0, 1, 2].map(i => (
                <div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-[#7c6af7] animate-pulse"
                  style={{ animationDelay: `${i * 200}ms` }}
                />
              ))}
            </div>
            Waiting for authorization…
          </div>
        </div>
      )}

      {/* Verify step */}
      {current.type === 'verify' && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-[#9090a8]">
            Click "Next" to verify your YouTube connection and retrieve your channel name.
          </p>
        </div>
      )}

      {/* Create channel step */}
      {current.type === 'create' && (
        <div className="flex flex-col gap-4">
          {verifyResult && (
            <div className="bg-[#34d399]/10 border border-[#34d399]/30 rounded-lg p-4">
              <div className="text-xs text-[#5a5a70] mb-1">Connected channel</div>
              <div className="text-sm font-semibold text-[#e8e8f0]">{verifyResult.channel_title}</div>
              {verifyResult.subscriber_count > 0 && (
                <div className="text-xs text-[#9090a8] mt-0.5">{verifyResult.subscriber_count.toLocaleString()} subscribers</div>
              )}
            </div>
          )}
          <p className="text-sm text-[#9090a8] leading-relaxed">
            Click "Finish" to create the channel entry in your console. It will appear in the Channels tab and can be targeted for uploads.
          </p>
        </div>
      )}
    </Modal>
  )
}
