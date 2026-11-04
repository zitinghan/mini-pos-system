import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { useAuth } from '../stores/auth';
import type { User } from '../services/types';
import { ErrorBox, Loading } from '../components/Common';

export default function Login() {
  const client = useQueryClient();
  const [name, setName] = useState('');
  const [pin, setPin] = useState('');
  const [token, setToken] = useState('');
  const status = useQuery({
    queryKey: ['setup'],
    queryFn: () => api<{ setup_required: boolean }>('/auth/setup-status'),
    retry: false,
  });
  const setup = status.data?.setup_required;
  const mutation = useMutation({
    mutationFn: async () => {
      if (setup) await api('/auth/setup', 'POST', { name, pin, setup_token: token });
      return api<{ token: string; user: User }>('/auth/login', 'POST', { name, pin });
    },
    onSuccess: (data) => {
      client.clear();
      useAuth.getState().signIn(data.token, data.user);
    },
  });

  return (
    <main className="login">
      <div className="brand-mark">可可</div>
      <p className="eyebrow">KEKE WANTAN MEE</p>
      <h1>{setup ? '首次设置管理员' : '欢迎回来'}</h1>
      <p className="muted">可可云吞面 · 店内点餐系统</p>
      {status.isPending ? <Loading /> : (
        <form className="card stack" onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}>
          <label>
            员工名称
            <input value={name} maxLength={80} required autoComplete="username"
              onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            {setup ? '设置 6–12 位数字 PIN' : 'PIN 码'}
            <input type="password" inputMode="numeric" pattern="[0-9]{6,12}"
              minLength={6} maxLength={12} required value={pin}
              autoComplete={setup ? 'new-password' : 'current-password'}
              onChange={(event) => setPin(event.target.value)} />
          </label>
          {setup && (
            <label>
              服务器设置令牌
              <input type="password" required value={token}
                onChange={(event) => setToken(event.target.value)} />
              <small>由部署人员从服务器配置中提供。</small>
            </label>
          )}
          <ErrorBox error={status.error || mutation.error} />
          <button className="primary" disabled={mutation.isPending || !status.data}>
            {mutation.isPending ? '请稍候…' : setup ? '创建管理员并登录' : '登录'}
          </button>
        </form>
      )}
    </main>
  );
}
