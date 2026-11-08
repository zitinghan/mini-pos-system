import { useEffect } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './services/api';
import type { User } from './services/types';
import { useAuth } from './stores/auth';
import { useUI } from './stores/ui';
import { Loading, ErrorBox } from './components/Common';
import Login from './pages/Login';
import Tables from './pages/Tables';
import Session from './pages/Session';
import Checkout from './pages/Checkout';
import Orders from './pages/Orders';
import History from './pages/History';
import Settings from './pages/Settings';
import Receipt from './pages/Receipt';

export default function App() {
  const { token, user, signIn, signOut } = useAuth();
  const notice = useUI((state) => state.notice);
  const client = useQueryClient();
  const me = useQuery({
    queryKey: ['me', token],
    queryFn: () => api<User>('/auth/me'),
    enabled: !!token,
    retry: false,
    refetchInterval: 60000,
  });
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => api('/health'),
    refetchInterval: 4000,
    retry: false,
  });

  useEffect(() => {
    if (me.data && token) signIn(token, me.data);
  }, [me.data, token, signIn]);

  if (!token) return <Login />;
  if (!user) {
    return <main className="container"><Loading /><ErrorBox error={me.error} /></main>;
  }
  const admin = user.role === 'ADMIN';
  const logout = () => {
    void api('/auth/logout', 'POST').catch(() => undefined).finally(() => {
      signOut();
      client.clear();
    });
  };

  return (
    <>
      <header>
        <div><strong>可可·南洋咖啡店</strong><small>KE KE / KOPITIAM</small></div>
        <div className="row">
          <span>{user.name}</span>
          <button className="header-button" onClick={logout}>退出</button>
        </div>
      </header>
      <main className="container">
        {health.isError && (
          <div className="error" role="alert">
            服务器连接中断。请检查店内 WiFi；未确认订单请使用原草稿重试。
          </div>
        )}
        {notice && (
          <div className="notice" role="status">
            <p>{notice}</p>
            <button onClick={() => useUI.getState().setNotice('')}>知道了</button>
          </div>
        )}
        <Routes>
          <Route path="/" element={<Tables />} />
          <Route path="/session/:id" element={<Session />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/checkout/:id" element={<Checkout />} />
          <Route path="/history" element={admin ? <History /> : <Navigate to="/" replace />} />
          <Route path="/settings" element={admin ? <Settings /> : <Navigate to="/" replace />} />
          <Route path="/receipts/:paymentId" element={<Receipt />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <nav aria-label="主导航">
        <NavLink to="/" end><span>▦</span>桌台</NavLink>
        <NavLink to="/orders"><span>☷</span>订单</NavLink>
        {admin && <>
          <NavLink to="/history"><span>◷</span>营业记录</NavLink>
          <NavLink to="/settings"><span>⚙</span>设置</NavLink>
        </>}
      </nav>
    </>
  );
}
