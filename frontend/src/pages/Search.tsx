import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search as SearchIcon, FileText } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';

export default function Search() {
  const [query, setQuery] = useState('');
  const [hospitalFilter, setHospitalFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [searchTrigger, setSearchTrigger] = useState('');
  const navigate = useNavigate();

  const { data: results, isLoading } = useQuery({
    queryKey: ['search', searchTrigger, hospitalFilter, dateFrom, dateTo],
    queryFn: async () => {
      if (!searchTrigger) return null;
      const params = new URLSearchParams();
      if (searchTrigger) params.set('q', searchTrigger);
      if (hospitalFilter) params.set('hospital_id', hospitalFilter);
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);
      const res = await api.get(`/documents/search?${params}`);
      return res.data;
    },
    enabled: !!searchTrigger,
  });

  const { data: hospitals } = useQuery({
    queryKey: ['hospitals'],
    queryFn: async () => { const res = await api.get('/hospitals/'); return res.data; },
  });

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Søk i journaler</h2>
      
      {/* Search form */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex gap-4 mb-4">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && setSearchTrigger(query)}
            placeholder="Søk i dokumenter (fritekst)..."
            className="flex-1 border rounded-lg px-4 py-2"
          />
          <button
            onClick={() => setSearchTrigger(query)}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg flex items-center gap-2 hover:bg-blue-700"
          >
            <SearchIcon size={18} /> Søk
          </button>
        </div>
        
        {/* Filters */}
        <div className="flex gap-4 flex-wrap">
          <select
            value={hospitalFilter}
            onChange={(e) => setHospitalFilter(e.target.value)}
            className="border rounded px-3 py-1.5 text-sm"
          >
            <option value="">Alle sykehus</option>
            {hospitals?.map((h: any) => (
              <option key={h.id} value={h.id}>{h.name}</option>
            ))}
          </select>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="border rounded px-3 py-1.5 text-sm" />
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="border rounded px-3 py-1.5 text-sm" />
        </div>
      </div>
      
      {/* Results */}
      {isLoading && <p className="text-gray-500">Søker...</p>}
      {results && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-4 border-b">
            <p className="text-sm text-gray-500">{results.total} dokumenter funnet</p>
          </div>
          <div className="divide-y">
            {results.documents.map((doc: any) => (
              <div
                key={doc.id}
                onClick={() => navigate(`/document/${doc.id}`)}
                className="p-4 hover:bg-blue-50 cursor-pointer flex items-start gap-3"
              >
                <FileText size={18} className="text-blue-500 mt-0.5" />
                <div>
                  <p className="font-medium">{doc.title}</p>
                  <p className="text-sm text-gray-500">
                    {doc.document_date} | {doc.hospital_name} | {doc.document_type}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
