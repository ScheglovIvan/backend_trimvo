import { Table, Typography } from "antd";
import { useEffect, useState } from "react";
import api from "../api/client";

const { Title } = Typography;

export default function AuditLog() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.get("/admin/audit-log").then((r) => setLogs(r.data)).finally(() => setLoading(false));
  }, []);

  const columns = [
    { title: "User ID", dataIndex: "user_id", key: "user_id", render: (v: string) => v ? v.slice(0, 8) + "..." : "-" },
    { title: "Action", dataIndex: "action", key: "action" },
    { title: "Entity", dataIndex: "entity", key: "entity" },
    { title: "Entity ID", dataIndex: "entity_id", key: "entity_id" },
    { title: "Details", dataIndex: "details", key: "details", render: (v: any) => v ? JSON.stringify(v).slice(0, 60) : "-" },
    { title: "Created", dataIndex: "created_at", key: "created_at", render: (v: string) => new Date(v).toLocaleString() },
  ];

  return (
    <>
      <Title level={4}>Audit Log</Title>
      <Table rowKey="id" dataSource={logs} columns={columns} loading={loading} />
    </>
  );
}
