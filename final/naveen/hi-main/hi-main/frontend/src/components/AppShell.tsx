import { Outlet } from 'react-router-dom';

export default function AppShell() {
  return (
    <div className="page-container">
      <div className="page-content">
        <Outlet />
      </div>
    </div>
  );
}