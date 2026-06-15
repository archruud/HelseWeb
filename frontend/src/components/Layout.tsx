import { Routes, Route } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import Dashboard from '../pages/Dashboard';
import DocumentView from '../pages/DocumentView';
import Search from '../pages/Search';
import Timeline from '../pages/Timeline';
import AIAssistant from '../pages/AIAssistant';
import Admin from '../pages/Admin';
import PrivateFiles from '../pages/PrivateFiles';

export default function Layout() {
  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar with tree view */}
      <Sidebar />
      
      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-auto p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/document/:id" element={<DocumentView />} />
            <Route path="/search" element={<Search />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/ai" element={<AIAssistant />} />
            <Route path="/private" element={<PrivateFiles />} />
            <Route path="/admin" element={<Admin />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
