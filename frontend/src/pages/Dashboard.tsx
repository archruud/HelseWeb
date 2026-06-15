import { useQuery } from '@tanstack/react-query';
import api from '../api/client';
import { FileText, Building2, MessageSquare, Clock } from 'lucide-react';

export default function Dashboard() {
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: async () => {
      try {
        const res = await api.get('/admin/stats');
        return res.data;
      } catch { return null; }
    },
  });

  const { data: timeline } = useQuery({
    queryKey: ['recent-timeline'],
    queryFn: async () => {
      const res = await api.get('/timeline?limit=5');
      return res.data;
    },
  });

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Oversikt</h2>
      
      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard icon={FileText} label="Dokumenter" value={stats?.total_documents || 0} color="blue" />
        <StatCard icon={Building2} label="Sykehus" value="6" color="green" />
        <StatCard icon={MessageSquare} label="Notater" value={stats?.total_annotations || 0} color="yellow" />
        <StatCard icon={Clock} label="Tidsperiode" value="1983-2026" color="purple" />
      </div>
      
      {/* Recent activity */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Siste hendelser i tidslinjen</h3>
        {timeline && timeline.length > 0 ? (
          <div className="space-y-3">
            {timeline.map((event: any) => (
              <div key={event.id} className="flex items-start gap-3 p-3 bg-gray-50 rounded">
                <div className={`w-2 h-2 mt-2 rounded-full ${
                  event.severity === 'critical' ? 'bg-red-500' :
                  event.severity === 'important' ? 'bg-yellow-500' : 'bg-blue-500'
                }`} />
                <div>
                  <p className="font-medium text-sm">{event.title}</p>
                  <p className="text-xs text-gray-500">{event.event_date} - {event.hospital_name}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">Ingen hendelser ennå. Last opp dokumenter for å komme i gang.</p>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }: any) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-700',
    green: 'bg-green-50 text-green-700',
    yellow: 'bg-yellow-50 text-yellow-700',
    purple: 'bg-purple-50 text-purple-700',
  };
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${colors[color]}`}>
          <Icon size={20} />
        </div>
        <div>
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-sm text-gray-500">{label}</p>
        </div>
      </div>
    </div>
  );
}
