import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search as SearchIcon, FileText, Building2, Calendar, Filter } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';

export default function Search() {
  const [query, setQuery] = useState('');
  const [hospitalFilter, setHospitalFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [searchKey, setSearchKey] = useState(0);
  const navigate = useNavigate();

  const { data: hospitals } = useQuery({
    queryKey: ['hospitals'],
    queryFn: async () => (await api.get('/hospitals/')).data,
  });

  const { data: results, isLoading } = useQuery({
    queryKey: ['search', searchKey, hospitalFilter, typeFilter, dateFrom, dateTo],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (query) params.set('q', query);
      if (hospitalFilter) { params.set('hospital_id', hospitalFilter); params.set('group_by_department', 'true'); }
      if (typeFilter) params.set('document_type', typeFilter);
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);
      params.set('page_size', '300');
      return (await api.get(`/documents/search?${params}`)).data;
    },
    enabled: searchKey > 0,
  });

  const doSearch = () => setSearchKey((k) => k + 1);
  const grouped = results?.grouped_by_department && Object.keys(results.grouped_by_department).length > 0;

  const docById = (id: string) => results?.documents.find((d: any) => d.id === id);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Søk i journaler</h2>

      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex gap-3 mb-4">
          <input
            type="text" value={query} onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && doSearch()}
            placeholder="Søk i fritekst (f.eks. magesmerter, parathyreoidea)..."
            className="flex-1 border rounded-lg px-4 py-2"
          />
          <button onClick={doSearch} className="bg-blue-600 text-white px-6 py-2 rounded-lg flex items-center gap-2 hover:bg-blue-700">
            <SearchIcon size={18} /> Søk
          </button>
        </div>

        <div className="flex gap-3 flex-wrap items-center">
          <Filter size={16} className="text-gray-400" />
          <select value={hospitalFilter} onChange={(e) => setHospitalFilter(e.target.value)} className="border rounded px-3 py-1.5 text-sm">
            <option value="">Alle sykehus</option>
            {hospitals?.map((h: any) => <option key={h.id} value={h.id}>{h.name} ({h.document_count})</option>)}
          </select>
          <input placeholder="Dokumenttype" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="border rounded px-3 py-1.5 text-sm w-40" />
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="border rounded px-3 py-1.5 text-sm" />
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="border rounded px-3 py-1.5 text-sm" />
        </div>
        <p className="text-xs text-gray-400 mt-2">Tips: Velg et sykehus for å se ALLE dokumenter derfra, gruppert per avdeling.</p>
      </div>

      {isLoading && <p className="text-gray-500">Søker...</p>}

      {results && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-4 border-b">
            <p className="text-sm text-gray-600 font-medium">{results.total} dokumenter funnet</p>
          </div>

          {grouped ? (
            <div className="divide-y">
              {Object.entries(results.grouped_by_department).map(([dept, ids]: [string, any]) => (
                <div key={dept}>
                  <div className="px-4 py-2 bg-gray-50 flex items-center gap-2 sticky top-0">
                    <Building2 size={14} className="text-amber-500" />
                    <span className="font-semibold text-sm">{dept}</span>
                    <span className="text-xs text-gray-400">({ids.length})</span>
                  </div>
                  {ids.map((id: string) => {
                    const doc = docById(id);
                    if (!doc) return null;
                    return (
                      <div key={id} onClick={() => navigate(`/document/${id}`)} className="px-4 py-2 pl-10 hover:bg-blue-50 cursor-pointer flex items-center gap-3">
                        <FileText size={15} className="text-blue-500" />
                        <span className="text-sm flex-1">{doc.title}</span>
                        <span className="text-xs text-gray-400">{doc.document_date}</span>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          ) : (
            <div className="divide-y">
              {results.documents.map((doc: any) => (
                <div key={doc.id} onClick={() => navigate(`/document/${doc.id}`)} className="p-4 hover:bg-blue-50 cursor-pointer flex items-start gap-3">
                  <FileText size={18} className="text-blue-500 mt-0.5" />
                  <div className="flex-1">
                    <p className="font-medium">{doc.title}</p>
                    <p className="text-sm text-gray-500">{doc.document_date} | {doc.hospital_name} | {doc.department || doc.document_type}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
