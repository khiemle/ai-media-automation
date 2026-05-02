import { useState } from 'react'
import { channelPlansApi } from '../api/client.js'
import { Button, Input } from './index.jsx'

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <button
      onClick={handleCopy}
      className="text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-0.5 bg-[#16161a] rounded border border-[#2a2a32] transition-colors flex-shrink-0"
    >
      {copied ? '✓' : 'Copy'}
    </button>
  )
}

function ResultBlock({ label, text }) {
  if (!text) return null
  return (
    <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] font-bold text-[#5a5a70] tracking-widest uppercase">{label}</span>
        <CopyButton text={text} />
      </div>
      <p className="text-xs text-[#9090a8] leading-relaxed whitespace-pre-wrap font-mono">{text}</p>
    </div>
  )
}

function AccordionSection({ title, open, onToggle, children }) {
  return (
    <div className="border border-[#2a2a32] rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 bg-[#1c1c22] hover:bg-[#222228] transition-colors text-left"
      >
        <span className="text-sm font-semibold text-[#e8e8f0]">{title}</span>
        <span className="text-[#9090a8] text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="p-4 flex flex-col gap-3 bg-[#16161a]">{children}</div>}
    </div>
  )
}

export default function AIAssistantPanel({ planId }) {
  const [openSection, setOpenSection] = useState('seo')

  // SEO state
  const [seoTheme, setSeoTheme]       = useState('')
  const [seoContext, setSeoContext]   = useState('')
  const [seoResult, setSeoResult]     = useState(null)
  const [seoLoading, setSeoLoading]   = useState(false)
  const [seoError, setSeoError]       = useState(null)

  // Prompts state
  const [pTheme, setPTheme]           = useState('')
  const [pContext, setPContext]       = useState('')
  const [pResult, setPResult]         = useState(null)
  const [pLoading, setPLoading]       = useState(false)
  const [pError, setPError]           = useState(null)

  // Q&A state
  const [question, setQuestion]       = useState('')
  const [answer, setAnswer]           = useState(null)
  const [qaLoading, setQaLoading]     = useState(false)
  const [qaError, setQaError]         = useState(null)

  const toggle = (section) => setOpenSection(s => s === section ? null : section)

  const handleSeo = async () => {
    if (!seoTheme.trim()) return
    setSeoLoading(true); setSeoError(null); setSeoResult(null)
    try {
      setSeoResult(await channelPlansApi.aiSeo(planId, seoTheme.trim(), seoContext.trim()))
    } catch (e) {
      setSeoError(e.message)
    } finally {
      setSeoLoading(false)
    }
  }

  const handlePrompts = async () => {
    if (!pTheme.trim()) return
    setPLoading(true); setPError(null); setPResult(null)
    try {
      setPResult(await channelPlansApi.aiPrompts(planId, pTheme.trim(), pContext.trim()))
    } catch (e) {
      setPError(e.message)
    } finally {
      setPLoading(false)
    }
  }

  const handleAsk = async () => {
    if (!question.trim()) return
    setQaLoading(true); setQaError(null); setAnswer(null)
    try {
      const res = await channelPlansApi.aiAsk(planId, question.trim())
      setAnswer(res.answer)
    } catch (e) {
      setQaError(e.message)
    } finally {
      setQaLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">

      {/* SEO */}
      <AccordionSection title="SEO" open={openSection === 'seo'} onToggle={() => toggle('seo')}>
        <Input
          label="Theme"
          value={seoTheme}
          onChange={e => setSeoTheme(e.target.value)}
          placeholder="e.g. Heavy Rain on Window"
          disabled={seoLoading}
        />
        <Input
          label="Context (optional)"
          value={seoContext}
          onChange={e => setSeoContext(e.target.value)}
          placeholder="Any extra context..."
          disabled={seoLoading}
        />
        <Button variant="primary" size="sm" loading={seoLoading} onClick={handleSeo} disabled={!seoTheme.trim()}>
          Generate SEO
        </Button>
        {seoError && <p className="text-xs text-[#f87171]">{seoError}</p>}
        {seoResult && (
          <div className="flex flex-col gap-2">
            <ResultBlock label="Title" text={seoResult.title} />
            <ResultBlock label="Description" text={seoResult.description} />
            <ResultBlock label="Tags" text={seoResult.tags} />
          </div>
        )}
      </AccordionSection>

      {/* Prompts */}
      <AccordionSection title="Prompts" open={openSection === 'prompts'} onToggle={() => toggle('prompts')}>
        <Input
          label="Theme"
          value={pTheme}
          onChange={e => setPTheme(e.target.value)}
          placeholder="e.g. Heavy Rain on Window"
          disabled={pLoading}
        />
        <Input
          label="Context (optional)"
          value={pContext}
          onChange={e => setPContext(e.target.value)}
          placeholder="Any extra context..."
          disabled={pLoading}
        />
        <Button variant="primary" size="sm" loading={pLoading} onClick={handlePrompts} disabled={!pTheme.trim()}>
          Generate All
        </Button>
        {pError && <p className="text-xs text-[#f87171]">{pError}</p>}
        {pResult && (
          <div className="flex flex-col gap-2">
            <ResultBlock label="Suno" text={pResult.suno} />
            <ResultBlock label="Midjourney" text={pResult.midjourney} />
            <ResultBlock label="Runway" text={pResult.runway} />
            <ResultBlock label="Thumbnail (based on Midjourney)" text={pResult.thumbnail} />
          </div>
        )}
      </AccordionSection>

      {/* Q&A */}
      <AccordionSection title="Q&A" open={openSection === 'qa'} onToggle={() => toggle('qa')}>
        <Input
          label="Question"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          placeholder="e.g. What is the recommended upload schedule?"
          disabled={qaLoading}
        />
        <Button variant="primary" size="sm" loading={qaLoading} onClick={handleAsk} disabled={!question.trim()}>
          Ask
        </Button>
        {qaError && <p className="text-xs text-[#f87171]">{qaError}</p>}
        {answer && (
          <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-bold text-[#5a5a70] tracking-widest uppercase">Answer</span>
              <CopyButton text={answer} />
            </div>
            <p className="text-xs text-[#9090a8] leading-relaxed whitespace-pre-wrap">{answer}</p>
          </div>
        )}
      </AccordionSection>

    </div>
  )
}
