import {
  Table, Button, Input, Select, Space, Tag, Typography, Modal, Form,
  InputNumber, DatePicker, Drawer, message, Tooltip,
} from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import dayjs from "dayjs";
import api from "../api/client";

const { Title, Text } = Typography;
const { Option } = Select;

interface UserRecord {
  id: string;
  email: string;
  name?: string;
  gems: number;
  subscription_status: string;
  subscription_expires_at?: string;
  is_banned: boolean;
  role: string;
  created_at: string;
}

interface Transaction {
  id: string;
  amount: number;
  balance_after: number;
  type: string;
  description?: string;
  reference_id?: string;
  created_at: string;
}

export default function Users() {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [subFilter, setSubFilter] = useState<string | undefined>(undefined);
  const [bannedFilter, setBannedFilter] = useState<boolean | undefined>(undefined);

  const [gemsModal, setGemsModal] = useState<UserRecord | null>(null);
  const [subModal, setSubModal] = useState<UserRecord | null>(null);
  const [txDrawer, setTxDrawer] = useState<UserRecord | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [txLoading, setTxLoading] = useState(false);

  const [gemsForm] = Form.useForm();
  const [subForm] = Form.useForm();

  const load = async (p = page) => {
    setLoading(true);
    try {
      const params: any = { page: p, per_page: 20 };
      if (search) params.search = search;
      if (subFilter) params.subscription = subFilter;
      if (bannedFilter !== undefined) params.is_banned = bannedFilter;
      const res = await api.get("/admin/users", { params });
      setUsers(res.data.items);
      setTotal(res.data.total);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page, subFilter, bannedFilter]);

  const handleSearch = () => { setPage(1); load(1); };

  const openTxDrawer = async (user: UserRecord) => {
    setTxDrawer(user);
    setTxLoading(true);
    try {
      const res = await api.get(`/admin/users/${user.id}/transactions`);
      setTransactions(res.data.items);
    } finally {
      setTxLoading(false);
    }
  };

  const handleAdjustGems = async (values: any) => {
    if (!gemsModal) return;
    try {
      await api.post(`/admin/users/${gemsModal.id}/gems`, values);
      message.success("Gems adjusted");
      setGemsModal(null);
      gemsForm.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "Failed");
    }
  };

  const handleSetSubscription = async (values: any) => {
    if (!subModal) return;
    try {
      const payload = {
        subscription_status: values.subscription_status,
        subscription_expires_at: values.subscription_expires_at
          ? values.subscription_expires_at.toISOString()
          : null,
      };
      await api.put(`/admin/users/${subModal.id}/subscription`, payload);
      message.success("Subscription updated");
      setSubModal(null);
      subForm.resetFields();
      load();
    } catch {
      message.error("Failed");
    }
  };

  const handleBan = async (user: UserRecord, ban: boolean) => {
    try {
      await api.post(`/admin/users/${user.id}/${ban ? "ban" : "unban"}`);
      message.success(ban ? "User banned" : "User unbanned");
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "Failed");
    }
  };

  const subscriptionBadge = (status: string, expires?: string) => {
    const colors: Record<string, string> = { free: "default", vip: "blue", svip: "gold" };
    return (
      <Space size={4}>
        <Tag color={colors[status] || "default"}>{status.toUpperCase()}</Tag>
        {expires && <Text type="secondary" style={{ fontSize: 11 }}>{dayjs(expires).format("DD.MM.YY")}</Text>}
      </Space>
    );
  };

  const columns = [
    {
      title: "Email",
      dataIndex: "email",
      key: "email",
      render: (v: string, r: UserRecord) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => openTxDrawer(r)}>{v}</Button>
      ),
    },
    { title: "Name", dataIndex: "name", key: "name", render: (v: any) => v || "—" },
    {
      title: "Gems",
      dataIndex: "gems",
      key: "gems",
      width: 90,
      render: (v: number) => <Text strong>{v}</Text>,
    },
    {
      title: "Subscription",
      key: "subscription",
      render: (_: any, r: UserRecord) => subscriptionBadge(r.subscription_status, r.subscription_expires_at),
    },
    {
      title: "Registered",
      dataIndex: "created_at",
      key: "created_at",
      width: 110,
      render: (v: string) => dayjs(v).format("DD.MM.YY"),
    },
    {
      title: "Status",
      dataIndex: "is_banned",
      key: "is_banned",
      width: 90,
      render: (v: boolean) => <Tag color={v ? "red" : "green"}>{v ? "Banned" : "Active"}</Tag>,
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: any, r: UserRecord) => (
        <Space wrap>
          <Button size="small" onClick={() => { setGemsModal(r); gemsForm.resetFields(); }}>Adjust Gems</Button>
          <Button size="small" onClick={() => {
            setSubModal(r);
            subForm.setFieldsValue({
              subscription_status: r.subscription_status,
              subscription_expires_at: r.subscription_expires_at ? dayjs(r.subscription_expires_at) : null,
            });
          }}>Set Subscription</Button>
          {r.role !== "admin" && (
            r.is_banned
              ? <Button size="small" onClick={() => handleBan(r, false)}>Unban</Button>
              : <Button size="small" danger onClick={() => handleBan(r, true)}>Ban</Button>
          )}
        </Space>
      ),
    },
  ];

  const txColumns = [
    { title: "Date", dataIndex: "created_at", key: "created_at", width: 140, render: (v: string) => dayjs(v).format("DD.MM.YY HH:mm") },
    {
      title: "Type",
      dataIndex: "type",
      key: "type",
      width: 130,
      render: (v: string) => {
        const colors: Record<string, string> = { purchase: "green", generation: "red", refund: "blue", admin_adjustment: "orange", bonus: "purple" };
        return <Tag color={colors[v] || "default"}>{v}</Tag>;
      },
    },
    {
      title: "Amount",
      dataIndex: "amount",
      key: "amount",
      width: 90,
      render: (v: number) => <Text style={{ color: v >= 0 ? "#52c41a" : "#ff4d4f" }}>{v >= 0 ? `+${v}` : v}</Text>,
    },
    { title: "Balance After", dataIndex: "balance_after", key: "balance_after", width: 110 },
    { title: "Description", dataIndex: "description", key: "description" },
  ];

  return (
    <>
      <Title level={4} style={{ marginBottom: 16 }}>Users</Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="Search by email"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onPressEnter={handleSearch}
          suffix={<SearchOutlined onClick={handleSearch} style={{ cursor: "pointer" }} />}
          style={{ width: 260 }}
        />
        <Select
          placeholder="Subscription"
          allowClear
          style={{ width: 160 }}
          onChange={(v) => { setSubFilter(v); setPage(1); }}
        >
          <Option value="free">Free</Option>
          <Option value="vip">VIP</Option>
          <Option value="svip">SVIP</Option>
        </Select>
        <Select
          placeholder="Status"
          allowClear
          style={{ width: 140 }}
          onChange={(v) => { setBannedFilter(v); setPage(1); }}
        >
          <Option value={false}>Active</Option>
          <Option value={true}>Banned</Option>
        </Select>
      </Space>

      <Table
        rowKey="id"
        dataSource={users}
        columns={columns}
        loading={loading}
        pagination={{ current: page, pageSize: 20, total, onChange: (p) => setPage(p) }}
        size="middle"
      />

      {/* Adjust Gems Modal */}
      <Modal
        open={!!gemsModal}
        title={`Adjust Gems — ${gemsModal?.email}`}
        onCancel={() => setGemsModal(null)}
        footer={null}
      >
        <Form form={gemsForm} layout="vertical" onFinish={handleAdjustGems}>
          <Form.Item name="amount" label="Amount (positive = add, negative = remove)" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="description" label="Description" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>Apply</Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* Set Subscription Modal */}
      <Modal
        open={!!subModal}
        title={`Set Subscription — ${subModal?.email}`}
        onCancel={() => setSubModal(null)}
        footer={null}
      >
        <Form form={subForm} layout="vertical" onFinish={handleSetSubscription}>
          <Form.Item name="subscription_status" label="Status" rules={[{ required: true }]}>
            <Select>
              <Option value="free">Free</Option>
              <Option value="vip">VIP</Option>
              <Option value="svip">SVIP</Option>
            </Select>
          </Form.Item>
          <Form.Item name="subscription_expires_at" label="Expires At (leave empty = no expiry)">
            <DatePicker showTime style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>Save</Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* Transaction History Drawer */}
      <Drawer
        title={`Transactions — ${txDrawer?.email}`}
        open={!!txDrawer}
        onClose={() => setTxDrawer(null)}
        width={700}
      >
        <Table
          rowKey="id"
          dataSource={transactions}
          columns={txColumns}
          loading={txLoading}
          pagination={false}
          size="small"
        />
      </Drawer>
    </>
  );
}
