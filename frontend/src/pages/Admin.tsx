import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Users, Activity, Plus, Trash2, Key, UserCog, X } from 'lucide-react';
import api from '../api/client';
import { useAuthStore } from '../stores/authStore';

const ROLE_LABELS: Record<string, string> = {
  admin: 'Administrator',
  super_editor: 'Super Editor',
  editor: 'Editor',
  viewer: 'Viewer',
};

export default function Admin() {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [resetUserId, setResetUserId] = useState<string | null>(null);
  const [newPass, setNewPass] = useState('');
  const [form, setForm] = useState({ username: '', password: '', full_name: '', email: '', role: 'viewer' });
  const [msg, setMsg] = useState('');

  const isAdmin = user?.role === 'admin';

  const { data: users } = useQuery({
    queryKey: ['admin-users'],
    queryFn: async () => (await api.get('/admin/users')).data,
    enabled: isAdmin,
  });

  const { data: audit } = useQuery({
    queryKey: ['admin-audit'],
    queryFn: async () => (await api.get('/admin/audit')).data,
    enabled: isAdmin,
  });

  const createUser = useMutation({
    mutationFn: async () => (await api.post('/admin/users', form)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setShowCreate(false);
      setForm({ username: '', password: '', full_name: '', email: '', role: 'viewer' });
      setMsg('Bruker opprettet');
    },
    onError: (e: any) => setMsg(e.response?.data?.detail || 'Feil ved oppretting'),
  });

  const deleteUser = useMutation({
    mutationFn: async (id: string) => (await api.delete(`/admin/users/${id}`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }),
    onError: (e: any) => setMsg(e.response?.data?.detail || 'Feil ved sletting'),
  });

  const resetPassword = useMutation({
    mutationFn: async () => (await api.post(`/admin/users/${resetUserId}/reset-password`, { new_password: newPass })).data,
    onSuccess: () => { setResetUserId(null); setNewPass(''); setMsg('Passord tilbakestilt'); },
    onError: (e: any) => setMsg(e.response?.data?.detail || 'Feil'),
  });

  const updateRole = useMutation({
    mutationFn: async ({ id, role }: { id: string; role: string }) => (await api.patch(`/admin/users/${id}`, { role })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  if (!isAdmin) {
    return <div className="text-center py-12 text-gray-500">Kun administrator har tilgang til denne siden.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Administrasjon</h2>
        <button onClick={() => setShowCreate(true)} className="bg-blue-600 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-blue-700">
          <Plus size={16} /> Ny bruker
        </button>
      </div>

      {msg && (
        <div className="bg-blue-50 text-blue-700 p-3 rounded flex justify-between items-center">
          {msg} <button onClick={() => setMsg('')}><X size={16} /></button>
        </div>
      )}

      {/* Users table */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b flex items-center gap-2"><Users size={18} /> <h3 className="font-semibold">Brukere</h3></div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-3">Navn</th>
              <th className="text-left p-3">Brukernavn</th>
              <th className="text-left p-3">Rolle</th>
              <th className="text-left p-3">Status</th>
              <th className="text-left p-3">Handlinger</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {users?.map((u: any) => (
              <tr key={u.id} className="hover:bg-gray-50">
                <td className="p-3 font-medium">{u.full_name}</td>
                <td className="p-3">{u.username}</td>
                <td className="p-3">
                  {u.is_system_admin ? (
                    <span className="bg-purple-100 text-purple-700 px-2 py-0.5 rounded text-xs">System-admin</span>
                  ) : (
                    <select
                      value={u.role}
                      onChange={(e) => updateRole.mutate({ id: u.id, role: e.target.value })}
                      className="text-xs border rounded px-2 py-1"
                    >
                      <option value="super_editor">Super Editor</option>
                      <option value="editor">Editor</option>
                      <option value="viewer">Viewer</option>
                    </select>
                  )}
                </td>
                <td className="p-3">{u.is_active ? 'Aktiv' : 'Deaktivert'}</td>
                <td className="p-3">
                  {u.is_system_admin ? (
                    <span className="text-xs text-gray-400">Endres via terminal</span>
                  ) : (
                    <div className="flex gap-2">
                      <button onClick={() => setResetUserId(u.id)} className="text-blue-600 hover:bg-blue-50 p-1 rounded" title="Tilbakestill passord">
                        <Key size={15} />
                      </button>
                      <button onClick={() => { if (confirm(`Slette ${u.username}?`)) deleteUser.mutate(u.id); }} className="text-red-600 hover:bg-red-50 p-1 rounded" title="Slett">
                        <Trash2 size={15} />
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Audit log */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b flex items-center gap-2"><Activity size={18} /> <h3 className="font-semibold">Aktivitetslogg</h3></div>
        <div className="divide-y max-h-96 overflow-auto">
          {audit?.map((log: any) => (
            <div key={log.id} className="p-3 flex items-center gap-3 text-sm">
              <span className="text-xs text-gray-400 w-40">{new Date(log.created_at).toLocaleString('nb-NO')}</span>
              <span className="font-medium">{log.user_name}</span>
              <span className="text-gray-500">{log.action}</span>
            </div>
          ))}
          {(!audit || audit.length === 0) && <p className="p-4 text-gray-400 text-sm">Ingen aktivitet logget ennå.</p>}
        </div>
      </div>

      {/* Create user modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowCreate(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-bold text-lg mb-4 flex items-center gap-2"><UserCog size={18} /> Ny bruker</h3>
            <div className="space-y-3">
              <input placeholder="Fullt navn" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" />
              <input placeholder="Brukernavn" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" />
              <input placeholder="E-post (valgfritt)" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" />
              <input type="text" placeholder="Midlertidig passord" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" />
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className="w-full border rounded px-3 py-2 text-sm">
                <option value="viewer">Viewer (kun lese)</option>
                <option value="editor">Editor (lese + laste opp + notere)</option>
                <option value="super_editor">Super Editor (alt + private filer)</option>
              </select>
              <button onClick={() => createUser.mutate()} disabled={!form.username || !form.password || !form.full_name} className="w-full bg-blue-600 text-white py-2 rounded font-medium hover:bg-blue-700 disabled:opacity-50">
                Opprett bruker
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reset password modal */}
      {resetUserId && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setResetUserId(null)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-bold text-lg mb-4 flex items-center gap-2"><Key size={18} /> Tilbakestill passord</h3>
            <input type="text" placeholder="Nytt passord" value={newPass} onChange={(e) => setNewPass(e.target.value)} className="w-full border rounded px-3 py-2 text-sm mb-3" />
            <button onClick={() => resetPassword.mutate()} disabled={!newPass} className="w-full bg-blue-600 text-white py-2 rounded font-medium hover:bg-blue-700 disabled:opacity-50">
              Tilbakestill
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
