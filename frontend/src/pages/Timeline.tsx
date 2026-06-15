import { useQuery } from '@tanstack/react-query';
import api from '../api/client';

export default function Timeline() {
  const { data: events } = useQuery({
    queryKey: ['timeline'],
    queryFn: async () => { const res = await api.get('/timeline/'); return res.data; },
  });

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Tidslinje</h2>
      <div className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200" />
        <div className="space-y-6">
          {events?.map((event: any) => (
            <div key={event.id} className="relative pl-10">
              <div className={`absolute left-2.5 w-3 h-3 rounded-full border-2 border-white ${
                event.severity === 'critical' ? 'bg-red-500' :
                event.severity === 'important' ? 'bg-yellow-500' : 'bg-blue-500'
              }`} />
              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex justify-between items-start">
                  <h3 className="font-semibold">{event.title}</h3>
                  <span className="text-xs text-gray-500">{event.event_date}</span>
                </div>
                {event.description && <p className="text-sm text-gray-600 mt-1">{event.description}</p>}
                <p className="text-xs text-gray-400 mt-2">{event.hospital_name} | {event.event_type}</p>
              </div>
            </div>
          ))}
          {(!events || events.length === 0) && (
            <p className="text-gray-500 pl-10">Ingen tidslinjehendelser ennå.</p>
          )}
        </div>
      </div>
    </div>
  );
}
