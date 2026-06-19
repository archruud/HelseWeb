import { useQuery } from '@tanstack/react-query';
import { Shield, Upload, Mic, FileText } from 'lucide-react';
import api from '../api/client';

export default function PrivateFiles() {
  const { data: files } = useQuery({
    queryKey: ['private-files'],
    queryFn: async () => { const res = await api.get('/private/'); return res.data; },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Shield className="text-green-600" /> Mine private filer
        </h2>
        <button onClick={() => alert('Opplasting kommer i Steg 7 (lydtranskribering)')} className="bg-green-600 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-green-700">
          <Upload size={16} /> Last opp fil
        </button>
      </div>
      
      <p className="text-sm text-gray-600 bg-yellow-50 p-3 rounded-lg">
        Disse filene er dine egne og holdes adskilt fra den offisielle helsejournalen.
        Kun brukere med spesifikk tillatelse kan se disse.
      </p>
      
      <div className="bg-white rounded-lg shadow divide-y">
        {files?.map((file: any) => (
          <div key={file.id} className="p-4 flex items-center gap-3">
            {file.file_type === 'audio' ? <Mic size={18} className="text-purple-500" /> : <FileText size={18} className="text-blue-500" />}
            <div className="flex-1">
              <p className="font-medium">{file.title}</p>
              <p className="text-sm text-gray-500">
                {file.file_type} | {file.related_date || 'Ingen dato'} 
                {file.has_transcript && ' | Transkribert'}
              </p>
            </div>
          </div>
        ))}
        {(!files || files.length === 0) && (
          <p className="p-6 text-gray-400 text-center">Ingen private filer lastet opp ennå.</p>
        )}
      </div>
    </div>
  );
}
