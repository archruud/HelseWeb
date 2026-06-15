import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import { FileText, MessageSquare, Plus, Printer, Download } from 'lucide-react';
import api from '../api/client';
import { useAuthStore } from '../stores/authStore';

// PDF viewer that fetches the file with auth token and shows it inline (no new tab)
function PdfViewer({ documentId, ocrText }: { documentId: string; ocrText?: string }) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let revoked: string | null = null;
    setError(false);
    setPdfUrl(null);
    api
      .get(`/documents/${documentId}/pdf`, { responseType: 'blob' })
      .then((res) => {
        const url = URL.createObjectURL(res.data);
        revoked = url;
        setPdfUrl(url);
      })
      .catch(() => setError(true));
    return () => {
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [documentId]);

  if (error) {
    return (
      <div className="prose max-w-none whitespace-pre-wrap text-sm">
        <p className="text-amber-600 mb-2">Kunne ikke laste PDF. Viser tekstinnhold:</p>
        {ocrText || 'Ingen tekstinnhold tilgjengelig.'}
      </div>
    );
  }

  if (!pdfUrl) {
    return <div className="text-center text-gray-400 py-12">Laster PDF...</div>;
  }

  return (
    <object data={pdfUrl} type="application/pdf" className="w-full h-full min-h-[600px] border rounded">
      <iframe src={pdfUrl} className="w-full h-full min-h-[600px] border rounded" title="PDF Viewer" />
    </object>
  );
}

export default function DocumentView() {
  const { id } = useParams();
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [newNote, setNewNote] = useState('');
  const [noteType, setNoteType] = useState('note');

  const { data: doc, isLoading } = useQuery({
    queryKey: ['document', id],
    queryFn: async () => {
      const res = await api.get(`/documents/${id}`);
      return res.data;
    },
  });

  const { data: annotations } = useQuery({
    queryKey: ['annotations', id],
    queryFn: async () => {
      const res = await api.get(`/annotations/document/${id}`);
      return res.data;
    },
  });

  const addAnnotation = useMutation({
    mutationFn: async () => {
      await api.post('/annotations/', {
        document_id: id,
        content: newNote,
        annotation_type: noteType,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['annotations', id] });
      setNewNote('');
    },
  });

  const handleDownload = async () => {
    const res = await api.get(`/documents/${id}/pdf`, { responseType: 'blob' });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${doc?.title || 'dokument'}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) return <div className="text-center py-8">Laster dokument...</div>;
  if (!doc) return <div className="text-center py-8">Dokument ikke funnet</div>;

  return (
    <div className="flex gap-6 h-full">
      {/* Document viewer (left side) */}
      <div className="flex-1 bg-white rounded-lg shadow overflow-hidden flex flex-col">
        <div className="p-4 border-b flex items-center justify-between">
          <div>
            <h2 className="font-bold text-lg">{doc.title}</h2>
            <p className="text-sm text-gray-500">
              {doc.document_date} | {doc.hospital_name} | {doc.doctor_name}
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => window.print()} className="p-2 hover:bg-gray-100 rounded" title="Skriv ut">
              <Printer size={18} />
            </button>
            <button onClick={handleDownload} className="p-2 hover:bg-gray-100 rounded" title="Last ned">
              <Download size={18} />
            </button>
          </div>
        </div>

        {/* PDF view (inline) */}
        <div className="flex-1 overflow-auto p-4">
          <PdfViewer documentId={id!} ocrText={doc.ocr_text} />
        </div>
      </div>

      {/* Annotations panel (right side) */}
      <div className="w-96 bg-white rounded-lg shadow flex flex-col">
        <div className="p-4 border-b">
          <h3 className="font-semibold flex items-center gap-2">
            <MessageSquare size={16} />
            Notater og kommentarer
          </h3>
        </div>

        {/* Document metadata */}
        <div className="p-4 border-b bg-gray-50 text-sm space-y-1">
          <p><span className="font-medium">Type:</span> {doc.document_type}</p>
          <p><span className="font-medium">Kategori:</span> {doc.category}</p>
          {doc.diagnoses?.length > 0 && (
            <p><span className="font-medium">Diagnoser:</span> {doc.diagnoses.join(', ')}</p>
          )}
          {doc.summary && (
            <div className="mt-2 p-2 bg-blue-50 rounded">
              <p className="font-medium text-blue-700 text-xs">AI-sammendrag:</p>
              <p className="text-xs mt-1">{doc.summary}</p>
            </div>
          )}
        </div>

        {/* Existing annotations */}
        <div className="flex-1 overflow-auto p-4 space-y-3">
          {annotations?.map((ann: any) => (
            <div key={ann.id} className={`p-3 rounded border-l-4 ${
              ann.annotation_type === 'correction' ? 'bg-red-50 border-red-400' :
              ann.annotation_type === 'important' ? 'bg-yellow-50 border-yellow-400' :
              ann.annotation_type === 'question' ? 'bg-purple-50 border-purple-400' :
              'bg-blue-50 border-blue-400'
            }`}>
              <p className="text-sm">{ann.content}</p>
              <p className="text-xs text-gray-500 mt-1">
                {ann.user_name} - {new Date(ann.created_at).toLocaleDateString('nb-NO')}
              </p>
            </div>
          ))}
          {(!annotations || annotations.length === 0) && (
            <p className="text-gray-400 text-sm text-center py-4">
              Ingen notater ennå
            </p>
          )}
        </div>

        {/* Add annotation form */}
        {(user?.role === 'admin' || user?.role === 'doctor' || user?.role === 'super_editor' || user?.role === 'editor') && (
          <div className="p-4 border-t">
            <select
              value={noteType}
              onChange={(e) => setNoteType(e.target.value)}
              className="w-full mb-2 text-sm border rounded px-2 py-1"
            >
              <option value="note">Notat</option>
              <option value="correction">Korrigering (feil i dokument)</option>
              <option value="important">Viktig merknad</option>
              <option value="question">Spørsmål</option>
            </select>
            <textarea
              value={newNote}
              onChange={(e) => setNewNote(e.target.value)}
              placeholder="Skriv et notat..."
              className="w-full border rounded p-2 text-sm resize-none h-20"
            />
            <button
              onClick={() => addAnnotation.mutate()}
              disabled={!newNote.trim()}
              className="mt-2 w-full bg-blue-600 text-white py-1.5 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-1"
            >
              <Plus size={14} /> Legg til notat
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
