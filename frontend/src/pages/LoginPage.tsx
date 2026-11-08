import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { VideoCameraIcon } from '@heroicons/react/24/outline';

export function LoginPage() {
  const navigate = useNavigate();
  const { login, loading } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [rememberMe, setRememberMe] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!username.trim() || !password.trim()) {
      setError('نام کاربری و رمز عبور الزامی است');
      return;
    }

    try {
      await login(username, password);
      navigate('/');
    } catch (err: any) {
      if (err.response?.status === 401) {
        setError('نام کاربری یا رمز عبور اشتباه است');
      } else if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError('خطا در اتصال به سرور. لطفاً مجدداً تلاش کنید.');
      }
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <div className="w-20 h-20 rounded-2xl bg-blue-600 flex items-center justify-center">
            <VideoCameraIcon className="w-12 h-12 text-white" />
          </div>
        </div>

        {/* Title */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">شمارش‌گر افراد</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-2">ورود به پنل مدیریت</p>
        </div>

        {/* Login Form */}
        <div className="card">
          <div className="card-body">
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm flex items-center gap-2" role="alert">
                  <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  {error}
                </div>
              )}

              <div>
                <label htmlFor="username" className="label-field">نام کاربری</label>
                <input
                  id="username"
                  type="text"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="input-field"
                  placeholder="نام کاربری خود را وارد کنید"
                  disabled={loading}
                  autoFocus
                />
              </div>

              <div>
                <label htmlFor="password" className="label-field">رمز عبور</label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field"
                  placeholder="رمز عبور خود را وارد کنید"
                  disabled={loading}
                />
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-600 dark:text-gray-400">مرا به خاطر بسپار</span>
                </label>
                <a href="#" className="text-sm text-blue-600 hover:text-blue-700">فراموشی رمز عبور؟</a>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn-primary w-full btn-lg"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="spinner" aria-hidden="true" />
                    در حال ورود...
                  </span>
                ) : (
                  'ورود'
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Footer info */}
        <div className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
          <p>پنل مدیریت سیستم شمارش افراد</p>
          <p className="mt-1">ورژن ۲.۰.۰</p>
        </div>
      </div>
    </div>
  );
}