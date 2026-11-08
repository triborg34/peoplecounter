import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { MobileTabBar } from './MobileTabBar';
import { useState } from 'react';

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <TopBar onMenuClick={() => setSidebarOpen(true)} />

      <main
        className={`main-content ${sidebarOpen ? '' : 'main-content-full'} lg:mr-64 lg:main-content pb-20 lg:pb-0`}
        role="main"
        id="main-content"
      >
        <div className="p-4 sm:p-6 lg:p-8">
          <Outlet />
        </div>
      </main>

      {/* Bottom tab bar: mobile-only quick navigation between pages. */}
      <MobileTabBar />
    </div>
  );
}
