import { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { MagnifyingGlassIcon, BellIcon, MoonIcon, SunIcon } from '@heroicons/react/24/outline';

interface TopBarProps {
  onMenuClick: () => void;
}

export function TopBar({ onMenuClick }: TopBarProps) {
  const { user } = useAuth();
  const [darkMode, setDarkMode] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const saved = localStorage.getItem('darkMode');
    if (saved) {
      setDarkMode(JSON.parse(saved));
      document.documentElement.classList.toggle('dark', JSON.parse(saved));
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      setDarkMode(true);
      document.documentElement.classList.add('dark');
    }
  }, []);

  const toggleDarkMode = () => {
    const newMode = !darkMode;
    setDarkMode(newMode);
    localStorage.setItem('darkMode', JSON.stringify(newMode));
    document.documentElement.classList.toggle('dark', newMode);
  };

  return (
    <header className="top-bar" role="banner">
      <div className="flex items-center gap-4">
        <button
          className="lg:hidden p-2 rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          onClick={onMenuClick}
          aria-label="باز کردن منو"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <div className="hidden sm:block w-64 sm:w-80">
          <div className="relative">
            <MagnifyingGlassIcon className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" aria-hidden="true" />
            <input
              type="search"
              placeholder="جستجو در دوربین‌ها، منطقه‌ها..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field pr-10 pl-4 py-2 text-sm"
              aria-label="جستجو"
            />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Notifications */}
        <div className="relative">
          <button
            className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors relative"
            onClick={() => setNotificationsOpen(!notificationsOpen)}
            aria-label="اعلان‌ها"
            aria-expanded={notificationsOpen}
          >
            <BellIcon className="w-5 h-5" aria-hidden="true" />
            <span className="absolute top-1 left-1 w-2 h-2 bg-red-500 rounded-full" aria-hidden="true" />
          </button>

          {notificationsOpen && (
            <div className="absolute left-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50 animate-fade-in">
              <div className="px-4 py-3 border-b border-gray-100">
                <h3 className="font-medium text-gray-900">اعلان‌ها</h3>
              </div>
              <div className="max-h-64 overflow-y-auto">
                <div className="px-4 py-3 text-center text-gray-500 text-sm">
                  هیچ اعلانی وجود ندارد
                </div>
              </div>
              <div className="px-4 py-2 border-t border-gray-100">
                <button className="text-sm text-blue-600 hover:text-blue-700 w-full text-right">
                  مشاهده همه
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Dark mode toggle */}
        <button
          onClick={toggleDarkMode}
          className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
          aria-label={darkMode ? 'حالت روز' : 'حالت شب'}
        >
          {darkMode ? <SunIcon className="w-5 h-5" /> : <MoonIcon className="w-5 h-5" />}
        </button>

        {/* User menu */}
        <div className="relative">
          <button
            className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            aria-label="منوی کاربر"
            aria-expanded="false"
          >
            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
              <span className="text-sm font-medium text-blue-700">
                {user?.full_name?.charAt(0) || user?.username?.charAt(0) || '؟'}
              </span>
            </div>
            <span className="hidden md:block text-sm font-medium text-gray-700">
              {user?.full_name || user?.username}
            </span>
          </button>
        </div>
      </div>
    </header>
  );
}