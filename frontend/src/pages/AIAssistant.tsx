import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Brain, Send, FileText } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';

export default function AIAssistant() {
  const [question, setQuestion] = useState('');
  const [conversation, setConversation] = useState<any[]>([]);
  const navigate = useNavigate();

  const { data: aiStatus } = useQuery({
    queryKey: ['ai-status'],
    queryFn: async () => { const res = await api.get('/ai/status'); return res.data; },
  });

  const askAI = useMutation({
    mutationFn: async (q: string) => {
      const res = await api.post('/ai/query', { question: q });
      return res.data;
    },
    onSuccess: (data, variables) => {
      setConversation(prev => [...prev, { question: variables, answer: data.answer, sources: data.source_documents }]);
      setQuestion('');
    },
  });

  return (
    <div className="space-y-6 h-full flex flex-col">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Brain className="text-purple-600" /> AI Assistent
        </h2>
        <span className={`text-xs px-2 py-1 rounded ${aiStatus?.status === 'online' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
          {aiStatus?.status === 'online' ? 'AI Online' : 'AI Offline'}
        </span>
      </div>
      
      <div className="bg-white rounded-lg shadow flex-1 flex flex-col">
        {/* Conversation */}
        <div className="flex-1 overflow-auto p-6 space-y-4">
          {conversation.length === 0 && (
            <div className="text-center text-gray-400 py-12">
              <Brain size={48} className="mx-auto mb-4 opacity-50" />
              <p>Still et spørsmål om journalene dine.</p>
              <p className="text-sm mt-2">Eksempler:</p>
              <div className="mt-3 space-y-2 text-sm">
                <p className="bg-gray-50 p-2 rounded">"Oppsummer alle innleggelser med magesmerter"</p>
                <p className="bg-gray-50 p-2 rounded">"Hvilke medisiner har jeg brukt mot smerter?"</p>
                <p className="bg-gray-50 p-2 rounded">"Finn alle episoder med intravenøs ernæring"</p>
              </div>
            </div>
          )}
          {conversation.map((item, i) => (
            <div key={i} className="space-y-3">
              <div className="bg-blue-50 p-3 rounded-lg ml-12">
                <p className="text-sm font-medium">{item.question}</p>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg mr-12">
                <p className="text-sm whitespace-pre-wrap">{item.answer}</p>
                {item.sources?.length > 0 && (
                  <div className="mt-3 border-t pt-2">
                    <p className="text-xs font-medium text-gray-500">Kilder:</p>
                    {item.sources.map((src: any) => (
                      <button
                        key={src.id}
                        onClick={() => navigate(`/document/${src.id}`)}
                        className="flex items-center gap-1 text-xs text-blue-600 hover:underline mt-1"
                      >
                        <FileText size={12} /> {src.title} ({src.date})
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {askAI.isPending && (
            <div className="bg-gray-50 p-4 rounded-lg mr-12 animate-pulse">
              <p className="text-sm text-gray-400">Tenker...</p>
            </div>
          )}
        </div>
        
        {/* Input */}
        <div className="p-4 border-t flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && question.trim() && askAI.mutate(question)}
            placeholder="Still et spørsmål om journalene..."
            className="flex-1 border rounded-lg px-4 py-2"
            disabled={aiStatus?.status !== 'online'}
          />
          <button
            onClick={() => question.trim() && askAI.mutate(question)}
            disabled={!question.trim() || askAI.isPending}
            className="bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
