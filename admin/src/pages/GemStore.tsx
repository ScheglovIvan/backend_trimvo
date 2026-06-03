import { Table, Button, Modal, Form, Input, InputNumber, Switch, message, Space, Typography, Tag } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import api from "../api/client";

const { Title } = Typography;

export default function GemStore() {
  const [packages, setPackages] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState<any>(null);
  const [form] = Form.useForm();

  const load = () => {
    setLoading(true);
    api.get("/admin/gem-packages").then((r) => setPackages(r.data.items)).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditItem(null);
    form.resetFields();
    form.setFieldsValue({ currency: "UAH", bonus_gems: 0, is_popular: false, is_active: true, order: 0 });
    setModalOpen(true);
  };

  const openEdit = (item: any) => {
    setEditItem(item);
    form.setFieldsValue(item);
    setModalOpen(true);
  };

  const handleDelete = async (id: string) => {
    await api.delete(`/admin/gem-packages/${id}`);
    message.success("Deleted");
    load();
  };

  const handleSave = async (values: any) => {
    try {
      if (editItem) {
        await api.put(`/admin/gem-packages/${editItem.id}`, values);
        message.success("Updated");
      } else {
        await api.post("/admin/gem-packages", values);
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
    { title: "Label", dataIndex: "label", key: "label", render: (v: any) => v || "—" },
    { title: "Gems", dataIndex: "gems_amount", key: "gems_amount" },
    { title: "Bonus", dataIndex: "bonus_gems", key: "bonus_gems" },
    { title: "Price", key: "price", render: (_: any, r: any) => `${r.price} ${r.currency}` },
    {
      title: "Popular",
      dataIndex: "is_popular",
      key: "is_popular",
      render: (v: boolean) => v ? <Tag color="gold">Popular</Tag> : null,
    },
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
        <Title level={4} style={{ margin: 0 }}>Gem Store</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>New Package</Button>
      </div>
      <Table rowKey="id" dataSource={packages} columns={columns} loading={loading} />

      <Modal open={modalOpen} title={editItem ? "Edit Package" : "New Package"} onCancel={() => setModalOpen(false)} footer={null} width={520}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Space style={{ width: "100%" }} align="start">
            <Form.Item name="gems_amount" label="Gems Amount" rules={[{ required: true }]} style={{ flex: 1 }}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="bonus_gems" label="Bonus Gems" initialValue={0} style={{ flex: 1 }}>
              <InputNumber min={0} style={{ width: "100%" }} />
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
          <Form.Item name="label" label="Label (e.g. Starter, Most Popular)">
            <Input />
          </Form.Item>
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
            <Form.Item name="is_popular" label="Popular" valuePropName="checked" style={{ flex: 1 }}>
              <Switch />
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
