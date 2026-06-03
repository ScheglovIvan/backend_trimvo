import { ConfigProvider, theme, Layout, Menu } from "antd";
import {
  DashboardOutlined,
  AppstoreOutlined,
  TagsOutlined,
  FireOutlined,
  BarsOutlined,
  ControlOutlined,
  RobotOutlined,
  AuditOutlined,
  WarningOutlined,
  GiftOutlined,
  CrownOutlined,
  DollarOutlined,
  TeamOutlined,
  VideoCameraOutlined,
} from "@ant-design/icons";
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Templates from "./pages/Templates";
import Categories from "./pages/Categories";
import Trends from "./pages/Trends";
import Jobs from "./pages/Jobs";
import StubControls from "./pages/StubControls";
import Models from "./pages/Models";
import AuditLog from "./pages/AuditLog";
import Reports from "./pages/Reports";
import GemStore from "./pages/GemStore";
import Subscriptions from "./pages/Subscriptions";
import Pricing from "./pages/Pricing";
import Users from "./pages/Users";
import OnboardingVideos from "./pages/OnboardingVideos";

const { Sider, Content, Header } = Layout;

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("access_token");
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

const menuItems = [
  { key: "/dashboard", icon: <DashboardOutlined />, label: "Dashboard" },
  { key: "/users", icon: <TeamOutlined />, label: "Users" },
  { key: "/templates", icon: <AppstoreOutlined />, label: "Templates" },
  { key: "/categories", icon: <TagsOutlined />, label: "Categories" },
  { key: "/trends", icon: <FireOutlined />, label: "Trends" },
  { key: "/jobs", icon: <BarsOutlined />, label: "Jobs" },
  { key: "/reports", icon: <WarningOutlined />, label: "Reports" },
  { key: "/gem-store", icon: <GiftOutlined />, label: "Gem Store" },
  { key: "/pricing", icon: <DollarOutlined />, label: "Pricing" },
  { key: "/subscriptions", icon: <CrownOutlined />, label: "Subscriptions" },
  { key: "/stub", icon: <ControlOutlined />, label: "Stub Controls" },
  { key: "/models", icon: <RobotOutlined />, label: "Models" },
  { key: "/audit", icon: <AuditOutlined />, label: "Audit Log" },
  { key: "/onboarding-videos", icon: <VideoCameraOutlined />, label: "Onboarding Videos" },
];

function AppLayout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider collapsible>
        <div style={{ color: "#fff", padding: "16px", fontWeight: "bold", fontSize: 18 }}>
          Trimvo
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: "0 16px", background: "#141414", display: "flex", alignItems: "center", justifyContent: "flex-end" }}>
          <span
            style={{ color: "#999", cursor: "pointer" }}
            onClick={() => {
              localStorage.removeItem("access_token");
              navigate("/login");
            }}
          >
            Logout
          </span>
        </Header>
        <Content style={{ margin: "16px", padding: "16px", background: "#1f1f1f", borderRadius: 8, minHeight: 280 }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  return (
    <ConfigProvider theme={{ algorithm: theme.darkAlgorithm }}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/*"
            element={
              <RequireAuth>
                <AppLayout>
                  <Routes>
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/users" element={<Users />} />
                    <Route path="/templates" element={<Templates />} />
                    <Route path="/categories" element={<Categories />} />
                    <Route path="/trends" element={<Trends />} />
                    <Route path="/jobs" element={<Jobs />} />
                    <Route path="/reports" element={<Reports />} />
                    <Route path="/gem-store" element={<GemStore />} />
                    <Route path="/pricing" element={<Pricing />} />
                    <Route path="/subscriptions" element={<Subscriptions />} />
                    <Route path="/stub" element={<StubControls />} />
                    <Route path="/models" element={<Models />} />
                    <Route path="/audit" element={<AuditLog />} />
                    <Route path="/onboarding-videos" element={<OnboardingVideos />} />
                    <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  </Routes>
                </AppLayout>
              </RequireAuth>
            }
          />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
