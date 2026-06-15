import { useQuery } from '@tanstack/react-query';
import { Users, Activity } from 'lucide-react';
import api from '../api/client';

export default function Admin() {
  const { data: users } = useQuery({
    queryKey: ['admin-users'],
    queryFn: async () => { const res = await api.get('/admin/users'); return res.data; },
  });

  const { data: audit } = useQuery({
    queryKey: ['admin-audit'],
    queryFn: async () => { const res = await api.get('/admin/audit'); return res.data; },
  });

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Administrasjon</h2>
      
      {/* Users */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b flex items-center gap-2">
          <Users size={18} /> <h3 className="font-semibold">Brukere</h3>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-3">Navn</th>
              <th className="text-left p-3">Brukernavn</th>
              <th className="text-left p-3">Rolle</th>
              <th className="text-left p-3">Siste innlogging</th>
              <th className="text-left p-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {users?.map((u: any) => (
              <tr key={u.id} className="hover:bg-gray-50">
                <td className="p-3 font-medium">{u.full_name}</td>
                <td className="p-3">{u.username}</td>
                <td className="p-3"><span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs">{u.role}</span></td>
                <td className="p-3 text-gray-500">{u.last_login || 'Aldri'}</td>
                <td className="p-3">{u.is_active ? '✓ Aktiv' : '✗ Deaktivert'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {/* Audit log */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b flex items-center gap-2">
          <Activity size={18} /> <h3 className="font-semibold">Aktivitetslogg</h3>
        </div>
        <div className="divide-y max-h-96 overflow-auto">
          {audit?.map((log: any) => (
            <div key={log.id} className="p-3 flex items-center gap-3 text-sm">
              <span className="text-xs text-gray-400 w-32">{new Date(log.created_at).toLocaleString('nb-NO')}</span>
              <span className="font-medium">{log.user_name}</span>
              <span className="text-gray-500">{log.action}</span>
              <span className="text-gray-400">{log.resource_type}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
