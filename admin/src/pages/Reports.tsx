import { Table, Button, Modal, Select, message, Space, Typography, Tag, Image } from "antd";
import { useEffect, useState } from "react";
import api from "../api/client";

const { Title, Text } = Typography;
const { Option } = Select;

const STATUS_COLORS: Record<string, string> = {
  pending: "orange",
  reviewed: "green",
  dismissed: "default",
};

export default function Reports() {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [detail, setDetail] = useState<any>(null);

  const load = () => {
    setLoading(true);
    const params: any = { page: 1, per_page: 100 };
    if (statusFilter) params.status = statusFilter;
    api.get("/admin/reports", { params }).then((r) => setReports(r.data.items)).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [statusFilter]);

  const updateStatus = async (id: string, status: string) => {
    try {
      await api.put(`/admin/reports/${id}`, { status });
      message.success("Status updated");
      load();
      setDetail(null);
    } catch {
      message.error("Update failed");
    }
  };

  const columns = [
    {
      title: "Thumb",
      key: "thumb",
      width: 70,
      render: (_: any, r: any) =>
        r.template_thumb_url ? (
          <Image src={r.template_thumb_url} width={50} height={65} style={{ objectFit: "cover" }} />
        ) : (
          <div style={{ width: 50, height: 65, background: "#333", borderRadius: 4 }} />
        ),
    },
    { title: "Template", dataIndex: "template_title", key: "template_title" },
    { title: "Reason", dataIndex: "reason", key: "reason" },
    { title: "User", dataIndex: "user_email", key: "user_email", render: (v: any) => v || <Text type="secondary">Anonymous</Text> },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (v: string) => <Tag color={STATUS_COLORS[v] || "default"}>{v}</Tag>,
    },
    { title: "Date", dataIndex: "created_at", key: "created_at", render: (v: string) => new Date(v).toLocaleDateString() },
    {
      title: "Actions",
      key: "actions",
      render: (_: any, r: any) => (
        <Space>
          <Button size="small" onClick={() => setDetail(r)}>View</Button>
          {r.status === "pending" && (
            <>
              <Button size="small" type="primary" onClick={() => updateStatus(r.id, "reviewed")}>Reviewed</Button>
              <Button size="small" danger onClick={() => updateStatus(r.id, "dismissed")}>Dismiss</Button>
            </>
          )}
        </Space>
      ),
    },
  ];

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Reports</Title>
        <Select
          placeholder="Filter by status"
          allowClear
          style={{ width: 180 }}
          value={statusFilter}
          onChange={setStatusFilter}
        >
          <Option value="pending">Pending</Option>
          <Option value="reviewed">Reviewed</Option>
          <Option value="dismissed">Dismissed</Option>
        </Select>
      </div>
      <Table rowKey="id" dataSource={reports} columns={columns} loading={loading} onRow={(r) => ({ onClick: () => setDetail(r) })} />

      <Modal open={!!detail} onCancel={() => setDetail(null)} footer={null} title="Report Details" width={520}>
        {detail && (
          <Space direction="vertical" style={{ width: "100%" }}>
            <div><Text strong>Template:</Text> {detail.template_title}</div>
            <div><Text strong>Reason:</Text> {detail.reason}</div>
            <div><Text strong>Description:</Text> {detail.description || "—"}</div>
            <div><Text strong>User:</Text> {detail.user_email || "Anonymous"}</div>
            <div><Text strong>Status:</Text> <Tag color={STATUS_COLORS[detail.status]}>{detail.status}</Tag></div>
            <div><Text strong>Date:</Text> {new Date(detail.created_at).toLocaleString()}</div>
            {detail.status === "pending" && (
              <Space style={{ marginTop: 8 }}>
                <Button type="primary" onClick={() => updateStatus(detail.id, "reviewed")}>Mark Reviewed</Button>
                <Button danger onClick={() => updateStatus(detail.id, "dismissed")}>Dismiss</Button>
              </Space>
            )}
          </Space>
        )}
      </Modal>
    </>
  );
}
