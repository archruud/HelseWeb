import { useState } from 'react';
import { useAuthStore } from '../stores/authStore';
import { LogOut, User, KeyRound, X } from 'lucide-react';
import api from '../api/client';

const roleLabels: Record<string, string> = {
  admin: 'Administrator',
  super_editor: 'Super Editor',
  editor: 'Editor',
  viewer: 'Viewer',
};

export default function TopBar() {
  const { user, logout } = useAuthStore();
  const [showPw, setShowPw] = useState(false);
  const [cur, setCur] = useState('');
  const [next, setNext] = useState('');
  const [msg, setMsg] = useState('');

  const canChangePw = user?.permissions?.includes('change_own_password');

  const submit = async () => {
    setMsg('');
    try {
      await api.post('/auth/change-password', { current_password: cur, new_password: next });
      setMsg('Passord endret!');
      setCur(''); setNext('');
      setTimeout(() => setShowPw(false), 1200);
    } catch (e: any) {
      setMsg(e.response?.data?.detail || 'Feil ved endring');
    }
  };

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm">
          <User size={16} className="text-gray-500" />
          <span className="font-medium">{user?.full_name}</span>
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">{roleLabels[user?.role || 'viewer']}</span>
        </div>
        {canChangePw && (
          <button onClick={() => setShowPw(true)} className="flex items-center gap-1 text-sm text-gray-500 hover:text-blue-600" title="Endre passord">
            <KeyRound size={16} /> Passord
          </button>
        )}
        <button onClick={logout} className="flex items-center gap-1 text-sm text-gray-500 hover:text-red-600">
          <LogOut size={16} /> Logg ut
        </button>
      </div>

      {showPw && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowPw(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-lg flex items-center gap-2"><KeyRound size={18} /> Endre passord</h3>
              <button onClick={() => setShowPw(false)}><X size={18} /></button>
            </div>
            {msg && <div className="bg-blue-50 text-blue-700 p-2 rounded text-sm mb-3">{msg}</div>}
            <input type="password" placeholder="Nåværende passord" value={cur} onChange={(e) => setCur(e.target.value)} className="w-full border rounded px-3 py-2 text-sm mb-2" />
            <input type="password" placeholder="Nytt passord" value={next} onChange={(e) => setNext(e.target.value)} className="w-full border rounded px-3 py-2 text-sm mb-3" />
            <button onClick={submit} disabled={!cur || !next} className="w-full bg-blue-600 text-white py-2 rounded font-medium hover:bg-blue-700 disabled:opacity-50">Endre passord</button>
          </div>
        </div>
      )}
    </header>
  );
}
