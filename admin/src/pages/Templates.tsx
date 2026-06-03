import {
  Table, Button, Modal, Form, Input, InputNumber, Upload, Switch, message, Space, Typography, Tag, Image, Spin, Empty, Select, Popconfirm,
} from "antd";
import { UploadOutlined, PlusOutlined, PlayCircleOutlined, LoadingOutlined } from "@ant-design/icons";
import { useEffect, useRef, useState } from "react";
import api from "../api/client";

const { Title } = Typography;

export default function Templates() {
  const [templates, setTemplates] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState<any>(null);
  const [previewVideo, setPreviewVideo] = useState<string | null>(null);
  const [trendIds, setTrendIds] = useState<Set<string>>(new Set());
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [form] = Form.useForm();
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startPollingIfNeeded = (items: any[], currentPage: number) => {
    const hasProcessing = items.some((t) => t.status === "processing" || t.status === "queued");
    if (hasProcessing && !pollRef.current) {
      pollRef.current = setInterval(() => {
        api.get("/admin/templates", { params: { page: currentPage, per_page: 20 } }).then((r) => {
          setTemplates(r.data?.items ?? []);
          const stillProcessing = (r.data?.items ?? []).some(
            (t: any) => t.status === "processing" || t.status === "queued"
          );
          if (!stillProcessing && pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        });
      }, 4000);
    } else if (!hasProcessing && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const loadTrends = () => {
    api.get("/admin/trends").then((r) => {
      const ids = new Set<string>((r.data ?? []).map((t: any) => t.template_id as string));
      setTrendIds(ids);
    }).catch(() => {});
  };

  const load = (currentPage = page) => {
    setLoading(true);
    api.get("/admin/templates", { params: { page: currentPage, per_page: 20 } })
      .then((r) => {
        setTemplates(r.data?.items ?? []);
        setTotal(r.data?.total ?? 0);
        startPollingIfNeeded(r.data?.items ?? [], currentPage);
      })
      .catch((e) => {
        console.error("Templates load error:", e);
        message.error("Failed to load templates: " + (e.response?.data?.detail ?? e.message));
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load(page);
    loadTrends();
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [page]);

  const openCreate = () => {
    setEditItem(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (item: any) => {
    setEditItem(item);
    form.setFieldsValue({
      title: item.title,
      description: item.description,
      is_active: item.is_active,
      likes: item.likes,
      plays: item.plays,
      gems_cost: item.gems_cost ?? 200,
      photo_slots: item.photo_slots ?? 1,
    });
    setModalOpen(true);
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await api.delete(`/admin/templates/${id}`);
      message.success("Deleted");
      load();
    } catch (e: any) {
      message.error("Delete failed: " + (e.response?.data?.detail ?? e.message));
    } finally {
      setDeletingId(null);
    }
  };

  const handleSave = async (values: any) => {
    try {
      const fd = new FormData();
      fd.append("title", values.title);
      if (values.description) fd.append("description", values.description);
      fd.append("likes", String(values.likes ?? 0));
      fd.append("plays", String(values.plays ?? 0));
      fd.append("gems_cost", String(values.gems_cost ?? 200));
      const photoSlots = values.photo_slots ?? 1;
      fd.append("photo_slots", String(photoSlots));
      fd.append("has_male_slot", String(photoSlots === 2));
      fd.append("has_female_slot", String(photoSlots === 2));
      if (editItem) {
        fd.append("is_active", String(values.is_active ?? true));
        if (values.video?.fileList?.[0]?.originFileObj)
          fd.append("video", values.video.fileList[0].originFileObj);
        if (values.thumb?.fileList?.[0]?.originFileObj)
          fd.append("thumb", values.thumb.fileList[0].originFileObj);
        await api.put(`/admin/templates/${editItem.id}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
        message.success("Updated");
      } else {
        if (values.video?.fileList?.[0]?.originFileObj)
          fd.append("video", values.video.fileList[0].originFileObj);
        if (values.thumb?.fileList?.[0]?.originFileObj)
          fd.append("thumb", values.thumb.fileList[0].originFileObj);
        await api.post("/admin/templates", fd, { headers: { "Content-Type": "multipart/form-data" } });
        message.success("Created — thumbnail is being generated");
      }
      setModalOpen(false);
      load();
    } catch {
      message.error("Save failed");
    }
  };

  const isProcessing = (r: any) => r.status === "processing" || r.status === "queued";

  const columns = [
    {
      title: "Thumb",
      key: "thumb",
      width: 80,
      render: (_: any, r: any) => {
        if (isProcessing(r)) {
          return (
            <div style={{ width: 60, height: 80, background: "#1a1a1a", borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Spin indicator={<LoadingOutlined style={{ fontSize: 20 }} spin />} />
            </div>
          );
        }
        return r.thumb_url ? (
          <Image src={r.thumb_url} width={60} height={80} style={{ objectFit: "cover" }} />
        ) : (
          <div style={{ width: 60, height: 80, background: "#333", borderRadius: 4 }} />
        );
      },
    },
    { title: "Title", dataIndex: "title", key: "title" },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (v: string) => {
        const colors: Record<string, string> = { ready: "green", processing: "blue", queued: "orange", failed: "red" };
        return <Tag color={colors[v] ?? "default"}>{v ?? "ready"}</Tag>;
      },
    },
    { title: "Likes", dataIndex: "likes", key: "likes" },
    { title: "Plays", dataIndex: "plays", key: "plays" },
    { title: "Gems", dataIndex: "gems_cost", key: "gems_cost", width: 80, render: (v: number) => `💎 ${v ?? 200}` },
    { title: "Photos", dataIndex: "photo_slots", key: "photo_slots", width: 80, render: (v: number) => v === 2 ? "2 (M+F)" : "1" },
    {
      title: "Trending",
      key: "trending",
      width: 90,
      render: (_: any, r: any) => {
        if (isProcessing(r)) return null;
        const isTrend = trendIds.has(r.id);
        return (
          <Button
            size="small"
            type={isTrend ? "primary" : "default"}
            danger={false}
            style={isTrend ? { background: "#ff6b00", borderColor: "#ff6b00", color: "#fff" } : {}}
            icon={<span style={{ fontSize: 14 }}>🔥</span>}
            onClick={async () => {
              try {
                if (isTrend) {
                  const res = await api.get("/admin/trends");
                  const trend = (res.data ?? []).find((t: any) => t.template_id === r.id);
                  if (trend) {
                    await api.delete(`/admin/trends/${trend.id}`);
                    message.success(`${r.title} removed from trends`);
                  }
                } else {
                  await api.post("/admin/trends", { template_id: r.id, order: 0 });
                  message.success(`${r.title} added to trends`);
                }
                loadTrends();
              } catch {
                message.error("Failed to update trends");
              }
            }}
          >
            {isTrend ? "In Trends" : "Add"}
          </Button>
        );
      },
    },
    {
      title: "Preview",
      key: "preview",
      render: (_: any, r: any) => {
        if (isProcessing(r)) {
          return <Spin size="small" />;
        }
        return r.preview_url ? (
          <Button size="small" icon={<PlayCircleOutlined />} onClick={() => setPreviewVideo(r.preview_url)}>
            Play
          </Button>
        ) : null;
      },
    },
    {
      title: "Active",
      dataIndex: "is_active",
      key: "is_active",
      render: (v: boolean) => <Tag color={v ? "green" : "red"}>{v ? "Yes" : "No"}</Tag>,
    },
    { title: "Created", dataIndex: "created_at", key: "created_at", render: (v: string) => new Date(v).toLocaleDateString() },
    {
      title: "Actions",
      key: "actions",
      render: (_: any, r: any) => (
        <Space>
          <Button size="small" onClick={() => openEdit(r)}>Edit</Button>
          <Button
            size="small"
            disabled={!r.video_url || isProcessing(r)}
            onClick={async () => {
              try {
                await api.post(`/admin/templates/${r.id}/reprocess`);
                message.success("Reprocessing started");
                setTimeout(() => load(), 2000);
              } catch {
                message.error("Reprocess failed");
              }
            }}
          >
            ↻ Reprocess
          </Button>
          <Popconfirm
              title="Delete template?"
              description="This will also delete all reports and category assignments."
              onConfirm={() => handleDelete(r.id)}
              okText="Delete"
              cancelText="Cancel"
              okButtonProps={{ danger: true }}
            >
              <Button
                size="small"
                danger
                loading={deletingId === r.id}
              >
                Delete
              </Button>
            </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Templates</Title>
        <Space>
          <Button
            onClick={async () => {
              try {
                const res = await api.post("/admin/templates/reprocess-all");
                message.success(`Queued ${res.data.queued} templates`);
                setTimeout(() => load(), 3000);
              } catch {
                message.error("Reprocess all failed");
              }
            }}
          >
            ↻ Reprocess All
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>New Template</Button>
        </Space>
      </div>
      <Table
        rowKey="id"
        dataSource={templates}
        columns={columns}
        loading={loading}
        locale={{ emptyText: <Empty description="No data" /> }}
        pagination={{
          total,
          pageSize: 20,
          current: page,
          onChange: (p) => setPage(p),
        }}
      />

      <Modal open={modalOpen} title={editItem ? "Edit Template" : "New Template"} onCancel={() => setModalOpen(false)} footer={null} width={560}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="title" label="Title" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Space style={{ width: "100%" }}>
            <Form.Item name="likes" label="Likes" initialValue={0} style={{ flex: 1 }}>
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="plays" label="Plays" initialValue={0} style={{ flex: 1 }}>
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>
          </Space>
          <Space style={{ width: "100%" }}>
            <Form.Item name="gems_cost" label="Gems cost (base)" initialValue={200} style={{ flex: 1 }}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="photo_slots" label="Photo slots" initialValue={1} style={{ flex: 1 }}>
              <Select style={{ width: "100%" }}>
                <Select.Option value={1}>1 Photo</Select.Option>
                <Select.Option value={2}>2 Photos (Male + Female)</Select.Option>
              </Select>
            </Form.Item>
          </Space>
          {editItem && (
            <Form.Item name="is_active" label="Active" valuePropName="checked">
              <Switch />
            </Form.Item>
          )}
          {editItem?.thumb_url && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, color: "#999", marginBottom: 4 }}>Current Thumb</div>
              <Image src={editItem.thumb_url} width={80} height={100} style={{ objectFit: "cover" }} />
            </div>
          )}
          <Form.Item name="video" label={editItem ? "Replace Video (mp4)" : "Video File (mp4)"}>
            <Upload beforeUpload={() => false} maxCount={1} accept="video/mp4,video/*">
              <Button icon={<UploadOutlined />}>Select Video</Button>
            </Upload>
          </Form.Item>
          <Form.Item name="thumb" label={editItem ? "Replace Thumb (jpg)" : "Thumb File (jpg, optional)"}>
            <Upload beforeUpload={() => false} maxCount={1} accept="image/*">
              <Button icon={<UploadOutlined />}>Select Thumb</Button>
            </Upload>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>Save</Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={!!previewVideo}
        onCancel={() => setPreviewVideo(null)}
        footer={null}
        title="Preview"
        width={400}
        centered
        styles={{ body: { padding: 0, display: 'flex', justifyContent: 'center', background: '#000' } }}
      >
        {previewVideo && (
          <video
            src={previewVideo}
            controls
            autoPlay
            style={{
              width: '100%',
              maxWidth: 360,
              maxHeight: '80vh',
              display: 'block',
              margin: '0 auto',
            }}
          />
        )}
      </Modal>
    </>
  );
}
