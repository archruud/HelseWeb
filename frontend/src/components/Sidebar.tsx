import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ChevronRight, ChevronDown, FileText, Calendar, Building2, Search, Brain, Clock, Shield, FolderOpen, Users } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import api from '../api/client';
import { useAuthStore } from '../stores/authStore';

interface TreeNode {
  id: string;
  label: string;
  type: string;
  children?: TreeNode[];
  document_id?: string;
  count?: number;
}

function TreeItem({ node, level = 0 }: { node: TreeNode; level?: number }) {
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();
  
  const hasChildren = node.children && node.children.length > 0;
  const isDocument = node.type === 'document';
  
  const icons: Record<string, any> = {
    year: Calendar,
    month: FolderOpen,
    hospital: Building2,
    document: FileText,
  };
  const Icon = icons[node.type] || FileText;
  
  return (
    <div>
      <div
        className={`flex items-center gap-1 py-1 px-2 rounded cursor-pointer hover:bg-blue-50 text-sm ${
          isDocument ? 'text-gray-700' : 'text-gray-900 font-medium'
        }`}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={() => {
          if (isDocument && node.document_id) {
            navigate(`/document/${node.document_id}`);
          } else if (hasChildren) {
            setExpanded(!expanded);
          }
        }}
      >
        {hasChildren && (
          expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
        )}
        {!hasChildren && !isDocument && <span className="w-3.5" />}
        <Icon size={14} className={isDocument ? 'text-blue-500' : 'text-gray-500'} />
        <span className="truncate flex-1">{node.label}</span>
        {node.count && (
          <span className="text-xs text-gray-400 bg-gray-100 px-1.5 rounded">
            {node.count}
          </span>
        )}
      </div>
      {expanded && hasChildren && (
        <div>
          {node.children!.map((child) => (
            <TreeItem key={child.id} node={child} level={level + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuthStore();
  
  const { data: tree, isLoading } = useQuery({
    queryKey: ['document-tree'],
    queryFn: async () => {
      const res = await api.get('/documents/tree');
      return res.data as TreeNode[];
    },
  });
  
  const navItems = [
    { path: '/', label: 'Oversikt', icon: FileText },
    { path: '/search', label: 'Søk', icon: Search },
    { path: '/timeline', label: 'Tidslinje', icon: Clock },
  ];

  if (user?.permissions?.includes('ai_query')) {
    navItems.push({ path: '/ai', label: 'AI Assistent', icon: Brain });
  }
  if (user?.permissions?.includes('view_private')) {
    navItems.push({ path: '/private', label: 'Mine filer', icon: Shield });
  }
  if (user?.role === 'admin') {
    navItems.push({ path: '/admin', label: 'Administrasjon', icon: Users });
  }
  
  return (
    <aside className="w-80 bg-white border-r border-gray-200 flex flex-col h-full">
      {/* Logo */}
      <div className="p-4 border-b border-gray-200">
        <h1 className="text-lg font-bold text-blue-900">Helsejournal</h1>
        <p className="text-xs text-gray-500">Personlig helsearkiv</p>
      </div>
      
      {/* Navigation */}
      <nav className="p-2 border-b border-gray-200">
        {navItems.map((item) => (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded text-sm ${
              location.pathname === item.path
                ? 'bg-blue-50 text-blue-700 font-medium'
                : 'text-gray-600 hover:bg-gray-50'
            }`}
          >
            <item.icon size={16} />
            {item.label}
          </button>
        ))}
      </nav>
      
      {/* Tree View */}
      <div className="flex-1 overflow-auto p-2">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-2 py-2">
          Dokumenter
        </h3>
        {isLoading ? (
          <div className="text-center text-gray-400 py-4 text-sm">Laster...</div>
        ) : tree && tree.length > 0 ? (
          tree.map((node) => <TreeItem key={node.id} node={node} />)
        ) : (
          <div className="text-center text-gray-400 py-4 text-sm">
            Ingen dokumenter lastet opp ennå
          </div>
        )}
      </div>
    </aside>
  );
}
