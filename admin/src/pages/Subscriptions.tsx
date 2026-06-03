import { Table, Button, Modal, Form, Input, InputNumber, Select, Switch, message, Space, Typography, Tag } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import api from "../api/client";

const { Title } = Typography;
const { Option } = Select;

const TIER_COLORS: Record<string, string> = { vip: "purple", svip: "gold" };

export default function Subscriptions() {
  const [plans, setPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState<any>(null);
  const [form] = Form.useForm();

  const load = () => {
    setLoading(true);
    api.get("/admin/subscription-plans").then((r) => setPlans(r.data.items)).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditItem(null);
    form.resetFields();
    form.setFieldsValue({ currency: "UAH", bonus_gems: 0, discount_percent: 0, is_active: true, order: 0 });
    setModalOpen(true);
  };

  const openEdit = (item: any) => {
    setEditItem(item);
    form.setFieldsValue(item);
    setModalOpen(true);
  };

  const handleDelete = async (id: string) => {
    await api.delete(`/admin/subscription-plans/${id}`);
    message.success("Deleted");
    load();
  };

  const handleSave = async (values: any) => {
    try {
      if (editItem) {
        await api.put(`/admin/subscription-plans/${editItem.id}`, values);
        message.success("Updated");
      } else {
        await api.post("/admin/subscription-plans", values);
        message.success("Created");
      }
      setModalOpen(false);
      load();
    } catch {
      message.error("Save failed");
    }
  };

  const columns = [
    { title: "Order", dataIndex: "order", key: "order", width: 70 },
    { title: "Name", dataIndex: "name", key: "name" },
    {
      title: "Tier",
      dataIndex: "tier",
      key: "tier",
      render: (v: string) => <Tag color={TIER_COLORS[v] || "default"}>{v?.toUpperCase()}</Tag>,
    },
    { title: "Period", dataIndex: "period", key: "period" },
    { title: "Price", key: "price", render: (_: any, r: any) => `${r.price} ${r.currency}` },
    { title: "Bonus Gems", dataIndex: "bonus_gems", key: "bonus_gems" },
    { title: "Discount", dataIndex: "discount_percent", key: "discount_percent", render: (v: number) => v ? `${v}%` : "—" },
    {
      title: "Active",
      dataIndex: "is_active",
      key: "is_active",
      render: (v: boolean) => <Tag color={v ? "green" : "red"}>{v ? "Yes" : "No"}</Tag>,
    },
    { title: "Apple ID", dataIndex: "apple_product_id", key: "apple_product_id", render: (v: any) => v || "—" },
    { title: "Google ID", dataIndex: "google_product_id", key: "google_product_id", render: (v: any) => v || "—" },
    {
      title: "Actions",
      key: "actions",
      render: (_: any, r: any) => (
        <Space>
          <Button size="small" onClick={() => openEdit(r)}>Edit</Button>
          <Button size="small" danger onClick={() => handleDelete(r.id)}>Delete</Button>
        </Space>
      ),
    },
  ];

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Subscription Plans</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>New Plan</Button>
      </div>
      <Table rowKey="id" dataSource={plans} columns={columns} loading={loading} />

      <Modal open={modalOpen} title={editItem ? "Edit Plan" : "New Plan"} onCancel={() => setModalOpen(false)} footer={null} width={560}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input placeholder="e.g. Weekly VIP" />
          </Form.Item>
          <Space style={{ width: "100%" }} align="start">
            <Form.Item name="tier" label="Tier" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select placeholder="Select tier">
                <Option value="vip">VIP</Option>
                <Option value="svip">SVIP</Option>
              </Select>
            </Form.Item>
            <Form.Item name="period" label="Period" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select placeholder="Select period">
                <Option value="weekly">Weekly</Option>
                <Option value="monthly">Monthly</Option>
                <Option value="yearly">Yearly</Option>
                <Option value="lifetime">Lifetime</Option>
              </Select>
            </Form.Item>
          </Space>
          <Space style={{ width: "100%" }} align="start">
            <Form.Item name="price" label="Price" rules={[{ required: true }]} style={{ flex: 1 }}>
              <InputNumber min={0} step={0.01} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="currency" label="Currency" initialValue="UAH" style={{ flex: 1 }}>
              <Input />
            </Form.Item>
          </Space>
          <Space style={{ width: "100%" }} align="start">
            <Form.Item name="bonus_gems" label="Bonus Gems" initialValue={0} style={{ flex: 1 }}>
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="discount_percent" label="Discount %" initialValue={0} style={{ flex: 1 }}>
              <InputNumber min={0} max={100} style={{ width: "100%" }} />
            </Form.Item>
          </Space>
          <Space style={{ width: "100%" }} align="start">
            <Form.Item name="apple_product_id" label="Apple Product ID" style={{ flex: 1 }}>
              <Input />
            </Form.Item>
            <Form.Item name="google_product_id" label="Google Product ID" style={{ flex: 1 }}>
              <Input />
            </Form.Item>
          </Space>
          <Space style={{ width: "100%" }} align="start">
            <Form.Item name="order" label="Order" initialValue={0} style={{ flex: 1 }}>
              <InputNumber style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="is_active" label="Active" valuePropName="checked" style={{ flex: 1 }}>
              <Switch defaultChecked />
            </Form.Item>
          </Space>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>Save</Button>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
