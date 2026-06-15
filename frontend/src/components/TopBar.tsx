import { useAuthStore } from '../stores/authStore';
import { LogOut, User } from 'lucide-react';

export default function TopBar() {
  const { user, logout } = useAuthStore();
  
  const roleLabels: Record<string, string> = {
    admin: 'Administrator',
    doctor: 'Lege',
    specialist: 'Spesialist',
    psychologist: 'Psykolog',
    lawyer: 'Advokat',
    guest: 'Gjest',
  };
  
  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm">
          <User size={16} className="text-gray-500" />
          <span className="font-medium">{user?.full_name}</span>
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
            {roleLabels[user?.role || 'guest']}
          </span>
        </div>
        <button
          onClick={logout}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-red-600"
        >
          <LogOut size={16} />
          Logg ut
        </button>
      </div>
    </header>
  );
}
