import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from '@/store/auth-store';
import Header from '@/components/layout/header';
import Sidebar from '@/components/layout/sidebar';

// Pages
import LoginPage from '@/pages/auth/login';
import RegisterPage from '@/pages/auth/register';
import DashboardPage from '@/pages/dashboard';
import CollectionsPage from '@/pages/collections';
import CollectionDetailPage from '@/pages/collection-detail';
import DocumentDetailPage from '@/pages/document-detail';
import SearchPage from '@/pages/search';
import SharesPage from '@/pages/shares';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <Header />
      <div className="flex">
        <Sidebar />
        <main className="flex-1 md:ml-64">{children}</main>
      </div>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Private routes */}
          <Route
            path="/"
            element={
              <PrivateRoute>
                <AppLayout>
                  <DashboardPage />
                </AppLayout>
              </PrivateRoute>
            }
          />
          <Route
            path="/collections"
            element={
              <PrivateRoute>
                <AppLayout>
                  <CollectionsPage />
                </AppLayout>
              </PrivateRoute>
            }
          />
          <Route
            path="/collections/:id"
            element={
              <PrivateRoute>
                <AppLayout>
                  <CollectionDetailPage />
                </AppLayout>
              </PrivateRoute>
            }
          />
          <Route
            path="/documents/:id"
            element={
              <PrivateRoute>
                <AppLayout>
                  <DocumentDetailPage />
                </AppLayout>
              </PrivateRoute>
            }
          />
          <Route
            path="/search"
            element={
              <PrivateRoute>
                <AppLayout>
                  <SearchPage />
                </AppLayout>
              </PrivateRoute>
            }
          />
          <Route
            path="/shares"
            element={
              <PrivateRoute>
                <AppLayout>
                  <SharesPage />
                </AppLayout>
              </PrivateRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
