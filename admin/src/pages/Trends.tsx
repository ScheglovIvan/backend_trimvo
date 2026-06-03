import { Table, Button, Modal, Form, Select, InputNumber, message, Space, Typography, Spin, Empty, Image } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import api from "../api/client";

const { Title } = Typography;

export default function Trends() {
  const [trends, setTrends] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const searchTemplates = (search: string) => {
    setTemplatesLoading(true);
    api.get("/admin/templates", { params: { page: 1, per_page: 50, search: search || "" } })
      .then((r) => setTemplates(r.data?.items ?? []))
      .catch((e) => console.error(e))
      .finally(() => setTemplatesLoading(false));
  };

  const load = () => {
    setLoading(true);
    Promise.all([
      api.get("/admin/trends"),
      api.get("/admin/templates", { params: { page: 1, per_page: 50 } }),
    ]).then(([t, tmpl]) => {
      setTrends(t.data ?? []);
      setTemplates(tmpl.data?.items ?? []);
    })
    .catch((e) => {
      console.error(e);
      message.error("Load failed");
    })
    .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (id: string) => {
    await api.delete(`/admin/trends/${id}`);
    message.success("Removed from trends");
    load();
  };

  const handleSave = async (values: any) => {
    try {
      await api.post("/admin/trends", values);
      message.success("Added to trends");
      setModalOpen(false);
      load();
    } catch {
      message.error("Failed");
    }
  };

  const handleUpdateOrder = async (trend: any, newOrder: number) => {
    try {
      await api.put(`/admin/trends/${trend.id}`, {
        template_id: trend.template_id,
        order: newOrder,
      });
      message.success("Order updated");
      load();
    } catch {
      message.error("Failed to update order");
    }
  };

  const templateMap = Object.fromEntries(templates.map((t) => [t.id, t.title]));

  const columns = [
    {
      title: "Thumb",
      key: "thumb",
      width: 70,
      render: (_: any, r: any) => {
        const tmpl = templates.find((t) => t.id === r.template_id);
        return tmpl?.thumb_url
          ? <Image src={tmpl.thumb_url} width={50} height={65} style={{ objectFit: "cover", borderRadius: 4 }} />
          : <div style={{ width: 50, height: 65, background: "#333", borderRadius: 4 }} />;
      },
    },
    {
      title: "Template",
      dataIndex: "template_id",
      key: "template_id",
      render: (id: string) => templateMap[id] || id,
    },
    {
      title: "Order",
      key: "order",
      width: 120,
      render: (_: any, r: any) => (
        <InputNumber
          size="small"
          defaultValue={r.order}
          style={{ width: 80 }}
          onBlur={(e) => handleUpdateOrder(r, parseInt(e.target.value) || 0)}
        />
      ),
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: any, r: any) => (
        <Button size="small" danger onClick={() => handleDelete(r.id)}>Remove</Button>
      ),
    },
  ];

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Trends</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); searchTemplates(""); setModalOpen(true); }}>Add Trend</Button>
      </div>
      <Table
        rowKey="id"
        dataSource={[...trends].sort((a, b) => a.order - b.order)}
        columns={columns}
        loading={loading}
        locale={{ emptyText: <Empty description="No data" /> }}
        pagination={{ pageSize: 20 }}
      />
      <Modal open={modalOpen} title="Add Trend" onCancel={() => setModalOpen(false)} footer={null}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="template_id" label="Template" rules={[{ required: true }]}>
            <Select
              showSearch
              filterOption={false}
              onSearch={searchTemplates}
              loading={templatesLoading}
              placeholder="Type to search by name..."
              notFoundContent={templatesLoading ? <Spin size="small" /> : "Not found"}
              optionLabelProp="label"
              options={templates
                .filter((t) => !new Set(trends.map((tr) => tr.template_id)).has(t.id))
                .map((t) => ({
                  value: t.id,
                  label: t.title,
                  thumb: t.thumb_url,
                }))
              }
              optionRender={(opt: any) => (
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  {opt.data.thumb
                    ? <img src={opt.data.thumb} style={{ width: 36, height: 48, objectFit: "cover", borderRadius: 4 }} />
                    : <div style={{ width: 36, height: 48, background: "#333", borderRadius: 4 }} />
                  }
                  <span>{opt.data.label}</span>
                </div>
              )}
            />
          </Form.Item>
          <Form.Item name="order" label="Order" initialValue={0}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>Add</Button>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
