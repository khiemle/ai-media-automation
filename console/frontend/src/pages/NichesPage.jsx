import { useState } from 'react'
import { nichesApi } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'
import { Card, Button, StatBox, Modal, Input, Toast, Spinner, EmptyState } from '../components/index.jsx'

export default function NichesPage() {
  const { data, loading, error, refetch } = useApi(() => nichesApi.list(), [])
  const niches = data || []

  const [addOpen,   setAddOpen]   = useState(false)
  const [newName,   setNewName]   = useState('')
  const [saving,    setSaving]    = useState(false)
  const [deletingId,setDeletingId]= useState(null)
  const [toast,     setToast]     = useState(null)

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const handleAdd = async () => {
    const name = newName.trim()
    if (!name) return
    if (niches.some(n => n.name.toLowerCase() === name.toLowerCase())) {
      showToast('Niche already exists', 'error'); return
    }
    setSaving(true)
    try {
      await nichesApi.create(name)
      refetch()
      setAddOpen(false); setNewName('')
      showToast(`Niche "${name}" added`)
    } catch (e) { showToast(e.message, 'error') }
    finally { setSaving(false) }
  }

  const handleDelete = async (niche) => {
    if (niche.script_count > 0) return
    setDeletingId(niche.id)
    try {
      await nichesApi.remove(niche.id)
      refetch()
      showToast(`Niche "${niche.name}" deleted`)
    } catch (e) { showToast(e.message, 'error') }
    finally { setDeletingId(null) }
  }

  const mostUsed = niches.length ? niches.reduce((a, b) => a.script_count > b.script_count ? a : b) : null

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#e8e8f0]">Niches</h1>
          <p className="text-sm text-[#9090a8] mt-0.5">Manage content niches used across scripts</p>
        </div>
        <Button variant="primary" onClick={() => setAddOpen(true)}>+ Add Niche</Button>
      </div>

      <div className="flex gap-3 flex-wrap">
        <StatBox label="Total Niches" value={niches.length} />
        <StatBox label="Most Used" value={mostUsed?.name || '—'} sub={mostUsed ? `${mostUsed.script_count} scripts` : ''} />
      </div>

      <Card title="All Niches">
        {loading ? (
          <div className="flex justify-center py-12"><Spinner size={28} /></div>
        ) : error ? (
          <div className="py-10 text-center">
            <p className="text-sm text-[#f87171] mb-3">{error}</p>
            <Button variant="ghost" size="sm" onClick={refetch}>Retry</Button>
          </div>
        ) : niches.length === 0 ? (
          <EmptyState icon="🏷️" title="No niches yet" description="Add your first niche above." />
        ) : (
          <div className="rounded-lg border border-[#2a2a32] overflow-hidden">
            <table className="w-full text-sm border-collapse">
              <thead className="bg-[#16161a]">
                <tr className="text-left">
                  <th className="px-4 py-2 text-xs text-[#9090a8] font-medium">Name</th>
                  <th className="w-32 px-4 py-2 text-xs text-[#9090a8] font-medium text-right">Scripts</th>
                  <th className="w-24 px-4 py-2 text-xs text-[#9090a8] font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {niches.map(n => (
                  <tr key={n.id} className="border-t border-[#2a2a32] hover:bg-[#1c1c22] transition-colors">
                    <td className="px-4 py-3">
                      <span className="text-[#e8e8f0] font-medium">{n.name}</span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-xs text-[#9090a8]">{n.script_count}</td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="danger" size="sm"
                        disabled={n.script_count > 0 || deletingId === n.id}
                        loading={deletingId === n.id}
                        onClick={() => handleDelete(n)}
                        title={n.script_count > 0 ? `Used by ${n.script_count} script(s)` : 'Delete'}
                      >
                        Delete
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal open={addOpen} onClose={() => { setAddOpen(false); setNewName('') }} title="Add Niche"
        footer={
          <>
            <Button variant="ghost" onClick={() => { setAddOpen(false); setNewName('') }}>Cancel</Button>
            <Button variant="primary" loading={saving} disabled={!newName.trim()} onClick={handleAdd}>Save</Button>
          </>
        }>
        <Input label="Niche Name" value={newName} onChange={e => setNewName(e.target.value)}
          placeholder="e.g. gaming" autoFocus
          onKeyDown={e => e.key === 'Enter' && !saving && handleAdd()} />
      </Modal>

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
