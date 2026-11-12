import { useCallback, useEffect, useState } from 'react';
import { Pencil, Plus, ShieldCheck, Trash2, UserRound } from 'lucide-react';
import api from '@/api/client';
import { type User } from '@/api/types';
import { faDateTime, faNumber } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Alert } from '@/components/ui/alert';
import { Field, Input } from '@/components/ui/input';

const ROLES = [
  { value: 'admin', label: 'مدیر سیستم' },
  { value: 'operator', label: 'اپراتور' },
  { value: 'viewer', label: 'بیننده' },
];

const roleLabel = (r: string) => ROLES.find((x) => x.value === r)?.label ?? r;
const roleVariant = (r: string): 'brand' | 'success' | 'secondary' => (r === 'admin' ? 'brand' : r === 'operator' ? 'success' : 'secondary');

interface UserForm {
  username: string;
  password: string;
  full_name: string;
  email: string;
  role: string;
}

const emptyForm = (): UserForm => ({ username: '', password: '', full_name: '', email: '', role: 'viewer' });

export function UsersPage() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [form, setForm] = useState<UserForm>(emptyForm());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [u, a] = await Promise.all([api.getUsers({ size: 100 }), api.getAuditLog({ limit: 50 })]);
      setUsers(u.items);
      setAudit(a as AuditRow[]);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در بارگذاری کاربران');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm());
    setErrors({});
    setModal(true);
  }

  function openEdit(u: User) {
    setEditing(u);
    setForm({ username: u.username, password: '', full_name: u.full_name || '', email: u.email || '', role: u.role });
    setErrors({});
    setModal(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.username.trim()) errs.username = 'نام کاربری الزامی است';
    if (!editing && form.password.length < 6) errs.password = 'رمز عبور حداقل ۶ نویسه باشد';
    setErrors(errs);
    if (Object.keys(errs).length) return;

    setSaving(true);
    try {
      if (editing) {
        await api.updateUser(editing.id, {
          full_name: form.full_name,
          email: form.email || undefined,
          role: form.role as User['role'],
          ...(form.password ? { password: form.password } : {}),
        });
      } else {
        await api.createUser({
          username: form.username.trim(),
          password: form.password,
          full_name: form.full_name,
          email: form.email || undefined,
          role: form.role as User['role'],
        });
      }
      setModal(false);
      fetchAll();
    } catch (err: any) {
      setErrors({ submit: err.response?.data?.detail || 'خطا در ذخیره کاربر' });
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(u: User) {
    try {
      await api.toggleUserStatus(u.id, !u.is_active);
      setUsers((prev) => prev.map((x) => (x.id === u.id ? { ...x, is_active: !u.is_active } : x)));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در تغییر وضعیت');
    }
  }

  async function handleDelete(u: User) {
    if (u.id === me?.id) {
      setError('حساب خودتان را نمی‌توانید حذف کنید');
      return;
    }
    if (!window.confirm(`کاربر «${u.username}» حذف شود؟`)) return;
    try {
      await api.deleteUser(u.id);
      setUsers((prev) => prev.filter((x) => x.id !== u.id));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در حذف کاربر');
    }
  }

  if (me?.role !== 'admin') {
    return (
      <EmptyState
        icon={ShieldCheck}
        title="دسترسی مجاز نیست"
        description="مدیریت کاربران فقط برای مدیر سیستم فعال است."
      />
    );
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-lg font-bold">کاربران و دسترسی‌ها</h1>
          <p className="text-sm text-muted-foreground">{faNumber(users.length)} کاربر ثبت شده</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="size-4" />
          کاربر جدید
        </Button>
      </div>

      {error && <Alert variant="destructive">{error}</Alert>}

      <Card>
        {loading ? (
          <CardContent className="space-y-3 pt-5">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-12 animate-pulse rounded-field bg-secondary/60" />
            ))}
          </CardContent>
        ) : users.length === 0 ? (
          <CardContent className="pt-5">
            <EmptyState icon={UserRound} title="کاربری یافت نشد" />
          </CardContent>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-line border-b border-border text-xs text-muted-foreground">
                  <th className="px-4 py-3 text-start font-medium">کاربر</th>
                  <th className="px-4 py-3 text-start font-medium">نقش</th>
                  <th className="hidden px-4 py-3 text-start font-medium md:table-cell">آخرین ورود</th>
                  <th className="px-4 py-3 text-start font-medium">وضعیت</th>
                  <th className="px-4 py-3 text-start font-medium">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-line border-b border-border/60 last:border-0 hover:bg-accent/40">
                    <td className="px-4 py-3">
                      <p className="font-medium">
                        {u.full_name || u.username}
                        {u.id === me?.id && <span className="ms-1.5 text-[11px] text-muted-foreground">(شما)</span>}
                      </p>
                      <p className="ltr-nums text-xs text-muted-foreground">{u.username}</p>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={roleVariant(u.role)}>{roleLabel(u.role)}</Badge>
                    </td>
                    <td className="hidden px-4 py-3 text-xs text-muted-foreground md:table-cell">
                      {u.last_login_at ? faDateTime(u.last_login_at) : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={u.is_active ? 'success' : 'destructive'}>{u.is_active ? 'فعال' : 'غیرفعال'}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" className="size-8" aria-label="ویرایش" onClick={() => openEdit(u)}>
                          <Pencil className="size-4" strokeWidth={1.75} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-8"
                          aria-label={u.is_active ? 'غیرفعال کردن' : 'فعال کردن'}
                          onClick={() => toggleActive(u)}
                        >
                          <span className="text-xs font-semibold">{u.is_active ? 'غیر' : 'فعال'}</span>
                        </Button>
                        {u.id !== me?.id && (
                          <Button variant="ghost" size="icon" className="size-8 text-destructive hover:text-destructive" aria-label="حذف" onClick={() => handleDelete(u)}>
                            <Trash2 className="size-4" strokeWidth={1.75} />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>گزارش رخدادها (Audit)</CardTitle>
        </CardHeader>
        <CardContent>
          {audit.length === 0 ? (
            <p className="py-2 text-xs text-muted-foreground">رخدادی ثبت نشده است</p>
          ) : (
            <ul className="divide-y divide-border text-sm">
              {audit.map((a) => (
                <li key={a.id ?? `${a.ts}-${a.username}`} className="flex flex-wrap items-baseline gap-x-2 py-2 text-xs">
                  <span className="text-muted-foreground">{faDateTime(a.ts)}</span>
                  <span className="font-medium">{a.username}</span>
                  <span className="text-brand">{a.action}</span>
                  {a.details && <span className="text-muted-foreground">{a.details}</span>}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={modal}
        onOpenChange={setModal}
        title={editing ? 'ویرایش کاربر' : 'افزودن کاربر'}
        description="نقش «بیننده» فقط مشاهده دارد؛ «اپراتور» می‌تواند دوربین و خطوط را مدیریت کند."
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          {errors.submit && <Alert variant="destructive">{errors.submit}</Alert>}

          <Field label="نام کاربری" htmlFor="u-username">
            <Input id="u-username" dir="ltr" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} error={errors.username} disabled={!!editing} data-autofocus />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="نام و نام خانوادگی" htmlFor="u-fullname">
              <Input id="u-fullname" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </Field>
            <Field label="نقش" htmlFor="u-role">
              <select
                id="u-role"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                className="h-10 w-full rounded-field border-line-field border-input bg-field px-3 text-sm shadow-field focus-visible:border-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="ایمیل" htmlFor="u-email" hint="اختیاری">
            <Input id="u-email" type="email" dir="ltr" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Field>

          <Field label={editing ? 'رمز عبور جدید' : 'رمز عبور'} htmlFor="u-pass" hint={editing ? 'خالی بگذارید تا تغییر نکند' : 'حداقل ۶ نویسه'}>
            <Input id="u-pass" type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} error={errors.password} />
          </Field>

          <div className="flex gap-2 border-line border-t border-border pt-4">
            <Button type="submit" disabled={saving}>
              {saving ? 'در حال ذخیره…' : editing ? 'به‌روزرسانی' : 'افزودن'}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setModal(false)}>
              انصراف
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}

interface AuditRow {
  id?: number;
  ts: string;
  username: string;
  action: string;
  details?: string;
}
