import { NavLink } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import {
  HomeIcon,
  VideoCameraIcon,
  Squares2X2Icon,
  ChartBarIcon,
  UsersIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline';

export const navigation = [
  { name: 'داشبورد', href: '/', icon: HomeIcon, permission: 'cameras:read' },
  { name: 'دوربین‌ها', href: '/cameras', icon: VideoCameraIcon, permission: 'cameras:read' },
  { name: 'منطقه‌ها', href: '/zones', icon: Squares2X2Icon, permission: 'zones:read' },
  { name: 'گزارش‌ها', href: '/reports', icon: ChartBarIcon, permission: 'reports:read' },
  { name: 'کاربران', href: '/users', icon: UsersIcon, permission: 'users:read' },
  { name: 'تنظیمات', href: '/settings', icon: Cog6ToothIcon, permission: 'settings:read' },
];

/**
 * Bottom tab bar shown only on small screens (lg:hidden).
 * Gives touch users direct navigation between pages, which the
 * desktop sidebar hides behind the hamburger menu on mobile.
 */
export function MobileTabBar() {
  const { hasPermission } = useAuth();
  const items = navigation.filter((item) => hasPermission(item.permission));

  return (
    <nav
      className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-white/95 dark:bg-gray-900/95 backdrop-blur border-t border-gray-200 dark:border-gray-700"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      aria-label="ناوبری پایین"
    >
      <ul className="flex items-stretch justify-around px-1" role="list">
        {items.map((item) => (
          <li key={item.href} className="flex-1">
            <NavLink
              to={item.href}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium transition-colors ${
                  isActive
                    ? 'text-blue-600 dark:text-blue-400'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon className={`w-6 h-6 ${isActive ? 'stroke-[2.2]' : ''}`} aria-hidden="true" />
                  <span className="truncate max-w-[4.5rem]">{item.name}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
