import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, KeyRound, User, AlertCircle } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Field, Input } from '@/components/ui/input';

export function LoginPage() {
  const navigate = useNavigate();
  const { login, loading } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (!username.trim() || !password.trim()) {
      setError('نام کاربری و رمز عبور را وارد کنید');
      return;
    }
    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch (err: any) {
      if (err.response?.status === 401) setError('نام کاربری یا رمز عبور اشتباه است');
      else if (err.response?.data?.detail) setError(String(err.response.data.detail));
      else setError('خطا در اتصال به سرور؛ دوباره تلاش کنید');
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm animate-fade-up">
        {/* نشان و عنوان */}
        <div className="mb-8 text-center">
          <span className="mx-auto mb-4 flex size-14 items-center justify-center rounded-surface border-line border-border bg-card shadow-surface">
            <Eye className="size-7 text-brand" strokeWidth={1.75} />
          </span>
          <h1 className="font-display text-xl font-bold">شمارش‌گر افراد</h1>
          <p className="mt-1 text-sm text-muted-foreground">ورود به سامانه پایش و شمارش</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-surface border-line border-border bg-card p-6 shadow-surface"
        >
          {error && (
            <div role="alert" className="flex items-start gap-2 rounded-field border-line border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
              <AlertCircle className="mt-0.5 size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <Field label="نام کاربری" htmlFor="username">
            <div className="relative">
              <User className="pointer-events-none absolute inset-y-0 start-3 my-auto size-4 text-muted-foreground" aria-hidden />
              <Input
                id="username"
                autoComplete="username"
                className="ps-9"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="مثلاً admin"
                autoFocus
              />
            </div>
          </Field>

          <Field label="رمز عبور" htmlFor="password">
            <div className="relative">
              <KeyRound className="pointer-events-none absolute inset-y-0 start-3 my-auto size-4 text-muted-foreground" aria-hidden />
              <Input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                className="ps-9 pe-10"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? 'پنهان کردن رمز' : 'نمایش رمز'}
                className="absolute inset-y-0 end-2 my-auto flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground"
              >
                <Eye className="size-4" />
              </button>
            </div>
          </Field>

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? 'در حال ورود…' : 'ورود'}
          </Button>

          <p className="text-center text-[11px] leading-5 text-muted-foreground">
            اولین ورود با حساب پیش‌فرض «admin» است؛ سامانه تغییر رمز را الزامی می‌کند.
          </p>
        </form>
      </div>
    </div>
  );
}
