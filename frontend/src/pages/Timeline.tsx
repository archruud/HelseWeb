import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Clock, Sparkles, FileText } from 'lucide-react';
import api from '../api/client';
import { useAuthStore } from '../stores/authStore';

export default function Timeline() {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const isAdmin = user?.role === 'admin';

  const { data: events, isLoading } = useQuery({
    queryKey: ['timeline'],
    queryFn: async () => (await api.get('/timeline/')).data,
  });

  const autoGenerate = useMutation({
    mutationFn: async () => (await api.post('/timeline/auto-generate')).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['timeline'] }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2"><Clock className="text-teal-600" /> Tidslinje</h2>
        {isAdmin && (
          <button onClick={() => autoGenerate.mutate()} disabled={autoGenerate.isPending} className="bg-teal-600 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-teal-700 disabled:opacity-50">
            <Sparkles size={16} /> {autoGenerate.isPending ? 'Genererer...' : 'Generer fra dokumenter'}
          </button>
        )}
      </div>

      <p className="text-sm text-gray-600 bg-teal-50 p-3 rounded-lg">
        Tidslinjen viser viktige hendelser i sykehistorien kronologisk. Klikk "Generer fra dokumenter" for å
        la systemet automatisk trekke ut nøkkelhendelser (operasjoner, innleggelser, intravenøs ernæring, diagnoser).
      </p>

      {isLoading && <p className="text-gray-500">Laster...</p>}

      <div className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200" />
        <div className="space-y-4">
          {events?.map((event: any) => (
            <div key={event.id} className="relative pl-10">
              <div className={`absolute left-2.5 w-3 h-3 rounded-full border-2 border-white ${
                event.severity === 'critical' ? 'bg-red-500' : event.severity === 'important' ? 'bg-amber-500' : 'bg-blue-500'
              }`} />
              <div className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow">
                <div className="flex justify-between items-start">
                  <h3 className="font-semibold">{event.title}</h3>
                  <span className="text-xs text-gray-500">{event.event_date}</span>
                </div>
                {event.description && <p className="text-sm text-gray-600 mt-1">{event.description}</p>}
                <div className="flex items-center gap-3 mt-2">
                  <span className="text-xs text-gray-400">{event.hospital_name} | {event.event_type}</span>
                  {event.document_id && (
                    <button onClick={() => navigate(`/document/${event.document_id}`)} className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                      <FileText size={11} /> Se dokument
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
          {(!events || events.length === 0) && !isLoading && (
            <p className="text-gray-500 pl-10">Ingen hendelser ennå. {isAdmin && 'Klikk "Generer fra dokumenter" for å fylle tidslinjen.'}</p>
          )}
        </div>
      </div>
    </div>
  );
}
