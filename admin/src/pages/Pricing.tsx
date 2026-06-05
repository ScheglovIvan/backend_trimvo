import { Card, Form, InputNumber, Button, Table, Typography, message, Spin } from "antd";
import { useEffect, useState } from "react";
import api from "../api/client";

const { Title } = Typography;

interface PricingData {
  gems_base_per_10s: number;
  gems_base_per_5s: number;
  gems_multiplier_standard: number;
  gems_multiplier_hd: number;
  gems_multiplier_ultra_hd: number;
  image_job_cost: number;
}

interface PreviewRow {
  key: string;
  duration: string;
  quality: string;
  gems: number;
  svip_gems: number;
}

function buildPreview(d: PricingData): PreviewRow[] {
  const rows: PreviewRow[] = [];
  const qualities = [
    { key: "standard", label: "Standard", mult: d.gems_multiplier_standard },
    { key: "hd",       label: "HD",       mult: d.gems_multiplier_hd },
    { key: "ultra_hd", label: "Ultra HD", mult: d.gems_multiplier_ultra_hd },
  ];
  const durations = [
    { seconds: 5,  label: "5s",  base: d.gems_base_per_5s },
    { seconds: 10, label: "10s", base: d.gems_base_per_10s },
  ];
  for (const dur of durations) {
    for (const q of qualities) {
      const gems = (dur.base || 0) * (q.mult || 1);
      rows.push({
        key: `${dur.seconds}-${q.key}`,
        duration: dur.label,
        quality: q.label,
        gems,
        svip_gems: Math.max(1, Math.floor(gems / 2)),
      });
    }
  }
  return rows;
}

export default function Pricing() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState<PreviewRow[]>([]);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/pricing");
      form.setFieldsValue(res.data);
      setPreview(buildPreview(res.data));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const onValuesChange = (_: any, all: PricingData) => {
    if (
      all.gems_base_per_10s &&
      all.gems_base_per_5s &&
      all.gems_multiplier_standard &&
      all.gems_multiplier_hd &&
      all.gems_multiplier_ultra_hd
    ) {
      setPreview(buildPreview(all));
    }
  };

  const onSave = async (values: PricingData) => {
    setSaving(true);
    try {
      await api.put("/admin/pricing", values);
      message.success("Pricing updated");
    } catch {
      message.error("Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const columns = [
    { title: "Duration", dataIndex: "duration", key: "duration", width: 90 },
    { title: "Quality", dataIndex: "quality", key: "quality", width: 110 },
    { title: "Gems", dataIndex: "gems", key: "gems", width: 100 },
    { title: "SVIP (50% off)", dataIndex: "svip_gems", key: "svip_gems", width: 130 },
  ];

  return (
    <Spin spinning={loading}>
      <Title level={4} style={{ marginBottom: 24 }}>Generation Pricing</Title>
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        <Card title="Pricing Settings" style={{ minWidth: 340 }}>
          <Form form={form} layout="vertical" onFinish={onSave} onValuesChange={onValuesChange}>
            <Form.Item name="gems_base_per_5s" label="Base price per 5s (gems)" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="gems_base_per_10s" label="Base price per 10s (gems)" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="gems_multiplier_standard" label="Standard quality multiplier" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="gems_multiplier_hd" label="HD quality multiplier" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="gems_multiplier_ultra_hd" label="Ultra HD quality multiplier" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="image_job_cost" label="Create Image — cost per image (gems)" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" block loading={saving}>Save</Button>
            </Form.Item>
          </Form>
        </Card>

        <Card title="Preview (gems cost)" style={{ flex: 1, minWidth: 380 }}>
          <Table
            rowKey="key"
            dataSource={preview}
            columns={columns}
            pagination={false}
            size="small"
          />
          <div style={{ marginTop: 8, color: "#888", fontSize: 12 }}>
            SVIP subscribers get 50% discount on all generations.
          </div>
        </Card>
      </div>
    </Spin>
  );
}
