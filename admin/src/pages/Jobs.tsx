import { Table, Tag, Progress, Select, Typography } from "antd";
import { useEffect, useState, useRef } from "react";
import api from "../api/client";

const { Title } = Typography;

const statusColors: Record<string, string> = {
  queued: "blue",
  processing: "orange",
  done: "green",
  failed: "red",
};

export default function Jobs() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = (status?: string) => {
    setLoading(true);
    const params = new URLSearchParams({ per_page: "100" });
    if (status) params.append("status", status);
    api.get(`/admin/jobs?${params}`).then((r) => {
      setJobs(r.data.items);
    }).finally(() => setLoading(false));
  };

  useEffect(() => {
    load(statusFilter);
    intervalRef.current = setInterval(() => load(statusFilter), 5000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [statusFilter]);

  const columns = [
    { title: "ID", dataIndex: "id", key: "id", render: (v: string) => v.slice(0, 8) + "..." },
    { title: "Template", dataIndex: "template_id", key: "template_id", render: (v: string) => v?.slice(0, 8) + "..." },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (v: string) => <Tag color={statusColors[v] || "default"}>{v}</Tag>,
    },
    {
      title: "Progress",
      dataIndex: "progress",
      key: "progress",
      render: (v: number) => <Progress percent={v} size="small" />,
    },
    { title: "Created", dataIndex: "created_at", key: "created_at", render: (v: string) => new Date(v).toLocaleString() },
  ];

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Jobs</Title>
        <Select
          allowClear
          placeholder="Filter by status"
          style={{ width: 180 }}
          options={["queued", "processing", "done", "failed"].map((s) => ({ value: s, label: s }))}
          onChange={(v) => setStatusFilter(v)}
        />
      </div>
      <Table rowKey="id" dataSource={jobs} columns={columns} loading={loading} />
    </>
  );
}
