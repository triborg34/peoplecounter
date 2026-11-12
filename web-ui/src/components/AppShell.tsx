import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Video,
  ScanLine,
  BarChart3,
  Users,
  Settings,
  LogOut,
  Menu,
  X,
  Eye,
} from 'lucide-react';
import { cn, fa } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';

const NAV = [
  { to: '/', label: 'داشبورد', icon: LayoutDashboard, permission: null },
  { to: '/cameras', label: 'دوربین‌ها', icon: Video, permission: null },
  { to: '/zones', label: 'خطوط و مناطق', icon: ScanLine, permission: 'manage_cameras' },
  { to: '/reports', label: 'گزارش‌ها', icon: BarChart3, permission: null },
  { to: '/users', label: 'کاربران', icon: Users, permission: 'manage_users' },
  { to: '/settings', label: 'تنظیمات', icon: Settings, permission: null },
];

const ROLE_LABEL: Record<string, string> = {
  admin: 'مدیر سیستم',
  operator: 'اپراتور',
  viewer: 'بیننده',
};

/** پوسته برنامه: نوار کنار در سمت راست (RTL)، نوار بالا و تب موبایل. */
export function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);

  // Close the drawer on navigation.
  useEffect(() => setOpen(false), [location.pathname]);

  const items = NAV.filter((n) => !n.permission || (user && n.permission === 'manage_users' ? user.role === 'admin' : user?.role !== 'viewer' || n.to === '/' || n.to === '/cameras' || n.to === '/reports'));

  async function handleLogout() {
    await logout();
    navigate('/login');
  }

  return (
    <div className="min-h-screen bg-background">
      {/* نوار کنار - دسکتاپ */}
      <aside className="fixed inset-y-0 start-0 z-40 hidden w-60 border-line border-border bg-card lg:flex lg:flex-col">
        <div className="flex items-center gap-2.5 border-line border-b border-border px-5 py-4">
          <span className="flex size-9 items-center justify-center rounded-control bg-brand text-brand-foreground">
            <Eye className="size-5" strokeWidth={2} />
          </span>
          <div className="leading-tight">
            <p className="font-display text-sm font-bold">شمارش‌گر افراد</p>
            <p className="text-[11px] text-muted-foreground">نسخه وب</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="ناوبری اصلی">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium transition-colors duration-(--motion) ease-motion',
                  isActive
                    ? 'bg-accent text-foreground'
                    : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
                )
              }
            >
              <item.icon className="size-4.5 shrink-0" strokeWidth={1.75} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-line border-t border-border p-3">
          <div className="flex items-center gap-3 rounded-control px-2 py-2">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-secondary text-sm font-bold">
              {(user?.full_name || user?.username || '؟').trim().charAt(0)}
            </span>
            <div className="min-w-0 flex-1 leading-tight">
              <p className="truncate text-sm font-medium">{user?.full_name || user?.username}</p>
              <p className="text-[11px] text-muted-foreground">{ROLE_LABEL[user?.role ?? ''] ?? user?.role}</p>
            </div>
            <Button variant="ghost" size="icon" className="size-8" aria-label="خروج از حساب" onClick={handleLogout}>
              <LogOut className="size-4" strokeWidth={1.75} />
            </Button>
          </div>
        </div>
      </aside>

      {/* نوار کنار - موبایل (کشویی) */}
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 start-0 flex w-64 flex-col border-line border-border bg-card shadow-overlay animate-fade-up">
            <div className="flex items-center justify-between border-line border-b border-border px-4 py-3">
              <span className="font-display text-sm font-bold">شمارش‌گر افراد</span>
              <Button variant="ghost" size="icon" className="size-8" aria-label="بستن منو" onClick={() => setOpen(false)}>
                <X className="size-4" />
              </Button>
            </div>
            <nav className="flex-1 space-y-1 overflow-y-auto p-3">
              {items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium',
                      isActive ? 'bg-accent text-foreground' : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
                    )
                  }
                >
                  <item.icon className="size-4.5" strokeWidth={1.75} />
                  {item.label}
                </NavLink>
              ))}
            </nav>
            <div className="border-line border-t border-border p-3">
              <Button variant="outline" className="w-full" onClick={handleLogout}>
                <LogOut className="size-4" />
                خروج از حساب
              </Button>
            </div>
          </aside>
        </div>
      )}

      {/* نوار بالا */}
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-line border-b border-border bg-card/90 px-4 backdrop-blur-sm lg:ps-8">
        <Button variant="ghost" size="icon" className="size-9 lg:hidden" aria-label="باز کردن منو" onClick={() => setOpen(true)}>
          <Menu className="size-5" />
        </Button>
        <p className="font-display text-sm font-semibold lg:hidden">شمارش‌گر افراد</p>
        <div className="ms-auto hidden items-center gap-2 text-xs text-muted-foreground sm:flex">
          <span className="inline-flex size-2 rounded-full bg-success" aria-hidden />
          متصل
        </div>
      </header>

      {/* محتوای اصلی */}
      <main className="px-4 py-6 pb-20 lg:ps-64 lg:pe-8 lg:pb-8">
        <Outlet />
      </main>

      {/* تب‌بار موبایل */}
      <nav className="fixed inset-x-0 bottom-0 z-40 flex border-line border-t border-border bg-card lg:hidden" aria-label="ناوبری موبایل">
        {items.slice(0, 4).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] font-medium',
                isActive ? 'text-brand' : 'text-muted-foreground',
              )
            }
          >
            <item.icon className="size-5" strokeWidth={1.75} />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

/** نشان وضعیت دوربین */
export function StatusDot({ status }: { status: string }) {
  const map: Record<string, { cls: string; label: string }> = {
    online: { cls: 'bg-success', label: 'آنلاین' },
    offline: { cls: 'bg-muted-foreground/40', label: 'آفلاین' },
    reconnecting: { cls: 'bg-warning animate-pulse', label: 'در حال اتصال' },
    error: { cls: 'bg-destructive', label: 'خطا' },
  };
  const s = map[status] ?? map.offline;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <span className={cn('size-2 rounded-full', s.cls)} aria-hidden />
      {s.label}
    </span>
  );
}

export { fa };
