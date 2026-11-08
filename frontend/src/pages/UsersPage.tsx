import React, { useState, useEffect, useCallback } from 'react';
import api from '../api/client';
import { type User } from '../api/types';
import {
  PlusIcon,
  MagnifyingGlassIcon,
  PencilIcon,
  TrashIcon,
  UserCircleIcon,
  ShieldCheckIcon,
  XMarkIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    role: 'operator' as 'admin' | 'operator' | 'viewer',
    password: '',
    confirm_password: '',
    is_active: true,
  });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getUsers({ page, size: 20, search: search || undefined });
      setUsers(res.items);
      setTotalPages(res.pages);
      setTotalItems(res.total);
    } catch (err) {
      console.error('Failed to fetch users:', err);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleSearch = (value: string) => {
    setSearch(value);
    setPage(1);
  };

  const openCreateModal = () => {
    setEditingUser(null);
    setFormData({
      username: '',
      email: '',
      full_name: '',
      role: 'operator',
      password: '',
      confirm_password: '',
      is_active: true,
    });
    setFormErrors({});
    setShowModal(true);
  };

  const openEditModal = (user: User) => {
    setEditingUser(user);
    setFormData({
      username: user.username,
      email: user.email || '',
      full_name: user.full_name || '',
      role: user.role,
      password: '',
      confirm_password: '',
      is_active: user.is_active,
    });
    setFormErrors({});
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditingUser(null);
    setFormErrors({});
  };

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};
    if (!formData.username.trim()) errors.username = 'نام کاربری الزامی است';
    if (!editingUser && !formData.password.trim()) errors.password = 'رمز عبور الزامی است';
    if (formData.password && formData.password.length < 6) errors.password = 'رمز عبور باید حداقل ۶ کاراکتر باشد';
    if (formData.password !== formData.confirm_password) errors.confirm_password = 'رمزهای عبور مطابقت ندارند';
    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      errors.email = 'فرمت ایمیل نامعتبر است';
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setSubmitting(true);
    try {
      const submitData = {
        username: formData.username,
        email: formData.email || null,
        full_name: formData.full_name || null,
        role: formData.role,
        is_active: formData.is_active,
      } as any;

      if (formData.password) {
        submitData.password = formData.password;
      }

      if (editingUser) {
        await api.updateUser(editingUser.id, submitData);
      } else {
        await api.createUser(submitData);
      }
      closeModal();
      fetchUsers();
    } catch (err: any) {
      if (err.response?.data?.detail) {
        setFormErrors({ submit: err.response.data.detail });
      } else {
        setFormErrors({ submit: 'خطا در ذخیره کاربر' });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (user: User) => {
    try {
      await api.toggleUserStatus(user.id, !user.is_active);
      setUsers((prev) =>
        prev.map((u) => (u.id === user.id ? { ...u, is_active: !user.is_active } : u))
      );
    } catch (err) {
      console.error('Failed to toggle user status:', err);
    }
  };

  const handleDelete = async (user: User) => {
    if (!window.confirm(`آیا از حذف کاربر "${user.username}" مطمئن هستید؟`)) return;
    try {
      await api.deleteUser(user.id);
      setUsers((prev) => prev.filter((u) => u.id !== user.id));
      setTotalItems((prev) => prev - 1);
    } catch (err) {
      console.error('Failed to delete user:', err);
    }
  };

  const roles = [
    { value: 'admin', label: 'مدیر سیستم', description: 'دسترسی کامل به همه بخش‌ها' },
    { value: 'operator', label: 'اپراتور', description: 'مدیریت دوربین‌ها، منطقه‌ها و گزارش‌ها' },
    { value: 'viewer', label: 'مشاهده‌کننده', description: 'فقط مشاهده داشبورد و گزارش‌ها' },
  ];

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('fa-IR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">مدیریت کاربران</h1>
          <p className="text-gray-500 mt-1">افزودن، ویرایش و مدیریت دسترسی کاربران</p>
        </div>
        <button onClick={openCreateModal} className="btn-primary">
          <PlusIcon className="w-5 h-5 ml-2" />
          افزودن کاربر
        </button>
      </div>

      {/* Search */}
      <div className="card">
        <div className="card-body">
          <div className="flex gap-4">
            <div className="relative flex-1">
              <MagnifyingGlassIcon className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="search"
                placeholder="جستجو در نام کاربری، نام، ایمیل..."
                value={search}
                onChange={(e) => handleSearch(e.target.value)}
                className="input-field pr-10"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Users Table */}
      <div className="card">
        <div className="card-body p-0">
          {loading && users.length === 0 ? (
            <div className="flex items-center justify-center h-64">
              <svg className="spinner-lg" />
            </div>
          ) : users.length === 0 ? (
            <div className="empty-state h-64">
              <UserCircleIcon className="empty-state-icon w-16 h-16" />
              <h3 className="empty-state-title">هیچ کاربری یافت نشد</h3>
              <p className="empty-state-description">
                {search ? 'تلاش کنید با کلمات کلیدی دیگر جستجو کنید' : 'برای شروع، اولین کاربر را اضافه کنید'}
              </p>
              {!search && (
                <button onClick={openCreateModal} className="btn-primary mt-4">
                  <PlusIcon className="w-5 h-5 ml-2" />
                  افزودن کاربر
                </button>
              )}
            </div>
          ) : (
            <>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>کاربر</th>
                      <th>نقش</th>
                      <th>ایمیل</th>
                      <th>وضعیت</th>
                      <th>آخرین ورود</th>
                      <th>تاریخ ایجاد</th>
                      <th className="text-left">عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => (
                      <tr key={user.id} className="hover:bg-gray-50">
                        <td>
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                              <span className="text-sm font-medium text-blue-700">
                                {user.full_name?.charAt(0) || user.username.charAt(0)}
                              </span>
                            </div>
                            <div>
                              <p className="font-medium text-gray-900">{user.username}</p>
                              {user.full_name && (
                                <p className="text-xs text-gray-500">{user.full_name}</p>
                              )}
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className={`badge ${
                            user.role === 'admin' ? 'badge-danger' :
                            user.role === 'operator' ? 'badge-warning' : 'badge-info'
                          }`}>
                            {roles.find((r) => r.value === user.role)?.label || user.role}
                          </span>
                        </td>
                        <td>{user.email || <span className="text-gray-400">—</span>}</td>
                        <td>
                          <span className={user.is_active ? 'badge badge-success' : 'badge badge-gray'}>
                            {user.is_active ? 'فعال' : 'غیرفعال'}
                          </span>
                        </td>
                        <td className="text-sm text-gray-500">
                          {user.last_login ? formatDate(user.last_login) : 'هرگز'}
                        </td>
                        <td className="text-sm text-gray-500">{formatDate(user.created_at)}</td>
                        <td>
                          <div className="flex items-center gap-2 text-left">
                            <button
                              onClick={() => openEditModal(user)}
                              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                              aria-label="ویرایش"
                            >
                              <PencilIcon className="w-5 h-5" />
                            </button>
                            <button
                              onClick={() => handleToggleStatus(user)}
                              className={`p-2 rounded-lg transition-colors ${
                                user.is_active
                                  ? 'text-orange-500 hover:text-orange-700 hover:bg-orange-100'
                                  : 'text-green-500 hover:text-green-700 hover:bg-green-100'
                              }`}
                              aria-label={user.is_active ? 'غیرفعال کردن' : 'فعال کردن'}
                            >
                              {user.is_active ? (
                                <ShieldCheckIcon className="w-5 h-5" />
                              ) : (
                                <UserCircleIcon className="w-5 h-5" />
                              )}
                            </button>
                            <button
                              onClick={() => handleDelete(user)}
                              className="p-2 text-red-500 hover:text-red-700 hover:bg-red-100 rounded-lg transition-colors"
                              aria-label="حذف"
                            >
                              <TrashIcon className="w-5 h-5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100">
                  <p className="text-sm text-gray-500">
                    نمایش {((page - 1) * 20) + 1} تا {Math.min(page * 20, totalItems)} از {totalItems}
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="btn-outline btn-sm"
                    >
                      قبلی
                    </button>
                    <button
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                      className="btn-outline btn-sm"
                    >
                      بعدی
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal} role="dialog" aria-modal="true" aria-labelledby="user-modal-title">
          <div className="modal-content max-w-xl" onClick={(e) => e.stopPropagation()}>
            <div className="card-header flex items-center justify-between">
              <h2 id="user-modal-title" className="text-lg font-semibold text-gray-900">
                {editingUser ? 'ویرایش کاربر' : 'افزودن کاربر جدید'}
              </h2>
              <button onClick={closeModal} className="p-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100">
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="card-body space-y-5">
              {formErrors.submit && (
                <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm flex items-center gap-2">
                  <XMarkIcon className="w-5 h-5" />
                  {formErrors.submit}
                </div>
              )}

              <div>
                <label htmlFor="username" className="label-field">نام کاربری <span className="text-red-500">*</span></label>
                <input
                  id="username"
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  className={`input-field ${formErrors.username ? 'border-red-500 focus:ring-red-500' : ''}`}
                  placeholder="مثال: ali_rezaei"
                  disabled={!!editingUser}
                />
                {formErrors.username && <p className="text-red-500 text-sm mt-1">{formErrors.username}</p>}
              </div>

              <div>
                <label htmlFor="full_name" className="label-field">نام کامل</label>
                <input
                  id="full_name"
                  type="text"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  className="input-field"
                  placeholder="مثال: علی رضایی"
                />
              </div>

              <div>
                <label htmlFor="email" className="label-field">ایمیل</label>
                <input
                  id="email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className={`input-field ${formErrors.email ? 'border-red-500 focus:ring-red-500' : ''}`}
                  placeholder="مثال: ali@example.com"
                />
                {formErrors.email && <p className="text-red-500 text-sm mt-1">{formErrors.email}</p>}
              </div>

              <div>
                <label htmlFor="role" className="label-field">نقش <span className="text-red-500">*</span></label>
                <select
                  id="role"
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value as any })}
                  className="input-field"
                >
                  {roles.map((role) => (
                    <option key={role.value} value={role.value}>{role.label}</option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  {roles.find((r) => r.value === formData.role)?.description}
                </p>
              </div>

              <div>
                <label htmlFor="password" className="label-field">
                  رمز عبور {editingUser ? '(خالی بگذارید تا تغییر نکند)' : <span className="text-red-500">*</span>}
                </label>
                <input
                  id="password"
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className={`input-field ${formErrors.password ? 'border-red-500 focus:ring-red-500' : ''}`}
                  placeholder={editingUser ? '••••••••' : 'حداقل ۶ کاراکتر'}
                  autoComplete={editingUser ? 'off' : 'new-password'}
                />
                {formErrors.password && <p className="text-red-500 text-sm mt-1">{formErrors.password}</p>}
              </div>

              <div>
                <label htmlFor="confirm_password" className="label-field">تایید رمز عبور</label>
                <input
                  id="confirm_password"
                  type="password"
                  value={formData.confirm_password}
                  onChange={(e) => setFormData({ ...formData, confirm_password: e.target.value })}
                  className={`input-field ${formErrors.confirm_password ? 'border-red-500 focus:ring-red-500' : ''}`}
                  placeholder="تکرار رمز عبور"
                  autoComplete={editingUser ? 'off' : 'new-password'}
                />
                {formErrors.confirm_password && <p className="text-red-500 text-sm mt-1">{formErrors.confirm_password}</p>}
              </div>

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">کاربر فعال است</span>
                </label>
              </div>

              <div className="flex justify-end gap-3 border-t border-gray-100 pt-5">
                <button type="button" onClick={closeModal} className="btn-secondary">
                  انصراف
                </button>
                <button type="submit" disabled={submitting} className="btn-primary">
                  {submitting ? (
                    <span className="flex items-center gap-2">
                      <svg className="spinner" />
                      در حال ذخیره...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <CheckIcon className="w-5 h-5" />
                      {editingUser ? 'به‌روزرسانی' : 'افزودن'}
                    </span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}