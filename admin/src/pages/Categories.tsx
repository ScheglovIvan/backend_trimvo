import {
  Table, Button, Modal, Form, Input, InputNumber, message, Space,
  Typography, Empty, Image, Select, Spin, Tag, Tooltip,
} from "antd";
import { PlusOutlined, ArrowLeftOutlined, SearchOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import api from "../api/client";

const { Title } = Typography;

export default function Categories() {
  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState<any>(null);
  const [form] = Form.useForm();

  // Manage templates режим
  const [activeCategory, setActiveCategory] = useState<any>(null);
  const [catTemplates, setCatTemplates] = useState<any[]>([]);
  const [catLoading, setCatLoading] = useState(false);

  // Добавление шаблона в категорию
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [allTemplates, setAllTemplates] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [addForm] = Form.useForm();

  const loadCategories = () => {
    setLoading(true);
    api.get("/admin/categories")
      .then((r) => setCategories(r.data ?? []))
      .catch((e) => message.error("Failed to load: " + (e.response?.data?.detail ?? e.message)))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadCategories(); }, []);

  // ── Загрузить шаблоны категории ──────────────────────────────────────────
  const loadCatTemplates = (categoryId: string) => {
    setCatLoading(true);
    api.get(`/admin/categories/${categoryId}/templates`)
      .then((r) => setCatTemplates(r.data ?? []))
      .catch((e) => message.error("Failed: " + (e.response?.data?.detail ?? e.message)))
      .finally(() => setCatLoading(false));
  };

  const openManage = (cat: any) => {
    setActiveCategory(cat);
    loadCatTemplates(cat.id);
  };

  const closeManage = () => {
    setActiveCategory(null);
    setCatTemplates([]);
  };

  // ── Поиск шаблонов для добавления ───────────────────────────────────────
  const searchTemplates = (q: string) => {
    setSearchLoading(true);
    api.get("/admin/templates", { params: { page: 1, per_page: 50, search: q || "" } })
      .then((r) => {
        const existingIds = new Set(catTemplates.map((t) => t.id));
        setAllTemplates((r.data?.items ?? []).filter((t: any) => !existingIds.has(t.id)));
      })
      .catch(() => {})
      .finally(() => setSearchLoading(false));
  };

  const handleAddToCategory = async (values: any) => {
    try {
      await api.post(`/admin/categories/${activeCategory.id}/templates`, {
        template_ids: [values.template_id],
      });
      message.success("Template added to category");
      setAddModalOpen(false);
      addForm.resetFields();
      loadCatTemplates(activeCategory.id);
    } catch (e: any) {
      message.error("Failed to add template: " + (e.response?.data?.detail ?? e.message));
    }
  };

  const handleRemoveFromCategory = async (templateId: string) => {
    try {
      await api.delete(`/admin/categories/${activeCategory.id}/templates/${templateId}`);
      message.success("Removed from category");
      loadCatTemplates(activeCategory.id);
    } catch (e: any) {
      message.error("Failed: " + (e.response?.data?.detail ?? e.message));
    }
  };

  const handleUpdateOrder = async (templateId: string, newOrder: number) => {
    try {
      await api.patch(
        `/admin/categories/${activeCategory.id}/templates/${templateId}/order`,
        { order: newOrder }
      );
      message.success("Order updated");
      loadCatTemplates(activeCategory.id);
    } catch (e: any) {
      message.error("Failed: " + (e.response?.data?.detail ?? e.message));
    }
  };

  // ── Edit/Delete категории ────────────────────────────────────────────────
  const openCreate = () => { setEditItem(null); form.resetFields(); setModalOpen(true); };
  const openEdit = (item: any) => { setEditItem(item); form.setFieldsValue({ name: item.name, order: item.order }); setModalOpen(true); };
  const handleDelete = async (id: string) => {
    await api.delete(`/admin/categories/${id}`);
    message.success("Deleted");
    loadCategories();
  };
  const handleSave = async (values: any) => {
    try {
      if (editItem) {
        await api.put(`/admin/categories/${editItem.id}`, values);
      } else {
        await api.post("/admin/categories", values);
      }
      message.success(editItem ? "Updated" : "Created");
      setModalOpen(false);
      loadCategories();
    } catch {
      message.error("Save failed");
    }
  };

  // ── Категории таблица ────────────────────────────────────────────────────
  const catColumns = [
    { title: "Name", dataIndex: "name", key: "name" },
    { title: "Order", dataIndex: "order", key: "order", width: 80 },
    {
      title: "Actions",
      key: "actions",
      render: (_: any, r: any) => (
        <Space>
          <Button size="small" type="primary" ghost onClick={() => openManage(r)}>Manage Templates</Button>
          <Button size="small" onClick={() => openEdit(r)}>Edit</Button>
          <Button size="small" danger onClick={() => handleDelete(r.id)}>Delete</Button>
        </Space>
      ),
    },
  ];

  // ── Шаблоны категории таблица ────────────────────────────────────────────
  const tmplColumns = [
    {
      title: "Thumb",
      key: "thumb",
      width: 70,
      render: (_: any, r: any) =>
        r.thumb_url
          ? <Image src={r.thumb_url} width={50} height={65} style={{ objectFit: "cover", borderRadius: 4 }} />
          : <div style={{ width: 50, height: 65, background: "#333", borderRadius: 4 }} />,
    },
    { title: "Title", dataIndex: "title", key: "title" },
    { title: "Plays", dataIndex: "plays", key: "plays", width: 80 },
    {
      title: "Order",
      key: "order_in_category",
      width: 120,
      render: (_: any, r: any) => (
        <InputNumber
          size="small"
          defaultValue={r.order_in_category ?? 0}
          style={{ width: 80 }}
          onBlur={(e) => handleUpdateOrder(r.id, parseInt(e.target.value) || 0)}
        />
      ),
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: any, r: any) => (
        <Button size="small" danger onClick={() => handleRemoveFromCategory(r.id)}>
          Remove
        </Button>
      ),
    },
  ];

  // ── RENDER ───────────────────────────────────────────────────────────────

  // Режим управления шаблонами категории
  if (activeCategory) {
    return (
      <>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={closeManage}>Back</Button>
          <Title level={4} style={{ margin: 0 }}>
            Category: {activeCategory.name} — Templates
          </Title>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            style={{ marginLeft: "auto" }}
            onClick={() => { searchTemplates(""); setAddModalOpen(true); }}
          >
            Add Template
          </Button>
        </div>

        <Table
          rowKey="id"
          dataSource={[...catTemplates].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))}
          columns={tmplColumns}
          loading={catLoading}
          locale={{ emptyText: <Empty description="No templates in this category" /> }}
          pagination={{ pageSize: 20 }}
        />

        {/* Модал добавления шаблона в категорию */}
        <Modal
          open={addModalOpen}
          title={`Add template to "${activeCategory.name}"`}
          onCancel={() => { setAddModalOpen(false); addForm.resetFields(); }}
          footer={null}
        >
          <Form form={addForm} layout="vertical" onFinish={handleAddToCategory}>
            <Form.Item name="template_id" label="Search template" rules={[{ required: true }]}>
              <Select
                showSearch
                filterOption={false}
                onSearch={searchTemplates}
                loading={searchLoading}
                placeholder="Type to search by name..."
                notFoundContent={searchLoading ? <Spin size="small" /> : "Not found"}
                optionLabelProp="label"
                options={allTemplates.map((t) => ({
                  value: t.id,
                  label: t.title,
                  thumb: t.thumb_url,
                }))}
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
            <Form.Item name="order_in_category" label="Order in category" initialValue={0}>
              <InputNumber style={{ width: "100%" }} min={0} />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" block>Add to Category</Button>
            </Form.Item>
          </Form>
        </Modal>
      </>
    );
  }

  // Режим списка категорий
  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Categories</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>New Category</Button>
      </div>
      <Table
        rowKey="id"
        dataSource={categories}
        columns={catColumns}
        loading={loading}
        locale={{ emptyText: <Empty description="No data" /> }}
        pagination={{ pageSize: 20 }}
      />
      <Modal
        open={modalOpen}
        title={editItem ? "Edit Category" : "New Category"}
        onCancel={() => setModalOpen(false)}
        footer={null}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="order" label="Order" initialValue={0}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>Save</Button>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
