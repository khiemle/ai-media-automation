import { useState } from 'react'
import { scriptsApi, fetchApi } from '../api/client.js'
import { Card, Button, Select, Toast, Spinner } from '../components/index.jsx'
import NicheCombobox from '../components/NicheCombobox.jsx'

const TEMPLATES = ['tiktok_viral', 'tiktok_30s', 'youtube_clean', 'shorts_hook']
const LANGUAGES = ['vietnamese', 'english']

export default function ComposerPage() {
  const [content,   setContent]   = useState('')
  const [expandFirst,setExpandFirst]=useState(false)
  const [niche,     setNiche]     = useState('')
  const [template,  setTemplate]  = useState('tiktok_viral')
  const [language,  setLanguage]  = useState('vietnamese')

  const [expanding,   setExpanding]   = useState(false)
  const [outline,     setOutline]     = useState('')   // after expand step
  const [outlineReady,setOutlineReady]= useState(false)

  const [generating, setGenerating] = useState(false)
  const [toast,      setToast]      = useState(null)

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3500) }

  const handleExpand = async () => {
    if (!content.trim()) return
    setExpanding(true)
    try {
      const res = await fetchApi('/api/scripts/expand', {
        method: 'POST',
        body: JSON.stringify({ content: content.trim() }),
      })
      if (res.expanded_outline?.trim()) {
        setOutline(res.expanded_outline)
        setOutlineReady(true)
      } else {
        showToast('Expansion returned empty — try rephrasing your idea', 'error')
      }
    } catch (e) { showToast(e.message, 'error') }
    finally { setExpanding(false) }
  }

  const handleGenerate = async () => {
    const finalContent = outlineReady ? outline : content
    if (!finalContent.trim() || !niche) return
    const topic = (
  finalContent.trim().split('\n')
    .map(l => l.replace(/^[#*\s]+/, '').trim())
    .find(l => l)
  ?? finalContent.trim().slice(0, 120)
).slice(0, 120)
    setGenerating(true)
    try {
      await scriptsApi.generate({
        topic,
        niche,
        template,
        language,
        raw_content: finalContent.trim(),
      })
      showToast('Script created — check the Scripts tab', 'success')
      // Reset
      setContent(''); setOutline(''); setOutlineReady(false); setNiche('')
    } catch (e) { showToast(e.message, 'error') }
    finally { setGenerating(false) }
  }

  const canGenerate = (outlineReady ? outline.trim() : content.trim()) && niche

  return (
    <div className="flex flex-col gap-5 max-w-3xl">
      <div>
        <h1 className="text-xl font-bold text-[#e8e8f0]">Composer</h1>
        <p className="text-sm text-[#9090a8] mt-0.5">Write or paste content, generate a script with Gemini</p>
      </div>

      <Card title="Content">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-[#9090a8]">Content / Idea</label>
            <textarea
              value={content}
              onChange={e => { setContent(e.target.value); if (outlineReady) setOutlineReady(false) }}
              rows={10}
              placeholder="Paste a full article, write a topic sentence, or describe a general idea…"
              className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-2 text-sm text-[#e8e8f0] placeholder-[#5a5a70] focus:outline-none focus:border-[#7c6af7] resize-y transition-colors"
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={expandFirst}
              onChange={e => { setExpandFirst(e.target.checked); setOutlineReady(false); setOutline('') }}
              className="accent-[#7c6af7] w-3.5 h-3.5"
            />
            <span className="text-sm text-[#9090a8]">Expand idea first — Gemini writes a detailed outline for you to review</span>
          </label>

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-1">
              <NicheCombobox label="Niche *" value={niche} onChange={setNiche} />
            </div>
            <Select label="Template" value={template} onChange={e => setTemplate(e.target.value)}
              options={TEMPLATES.map(t => ({ value: t, label: t }))} />
            <Select label="Language" value={language} onChange={e => setLanguage(e.target.value)}
              options={LANGUAGES.map(l => ({ value: l, label: l }))} />
          </div>

          {!expandFirst && (
            <Button variant="primary" disabled={!canGenerate} loading={generating} onClick={handleGenerate}>
              Generate Script
            </Button>
          )}

          {expandFirst && !outlineReady && (
            <Button variant="default" disabled={!content.trim()} loading={expanding} onClick={handleExpand}>
              Expand &amp; Preview
            </Button>
          )}
        </div>
      </Card>

      {outlineReady && (
        <Card title="Expanded Outline">
          <div className="flex flex-col gap-4">
            <p className="text-xs text-[#9090a8]">Review and edit the outline before generating the script.</p>
            <textarea
              value={outline}
              onChange={e => setOutline(e.target.value)}
              rows={12}
              className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-2 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] resize-y transition-colors font-mono"
            />
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setOutlineReady(false)}>← Back</Button>
              <Button variant="primary" disabled={!canGenerate} loading={generating} onClick={handleGenerate}>
                Generate Script from Outline
              </Button>
            </div>
          </div>
        </Card>
      )}

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}

