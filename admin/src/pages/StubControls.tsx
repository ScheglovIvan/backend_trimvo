import { Card, Form, Slider, Switch, Button, message, Typography, Spin, Descriptions, Tag } from "antd";
import { useEffect, useState } from "react";
import api from "../api/client";

const { Title } = Typography;

export default function StubControls() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [testResult, setTestResult] = useState<any>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    api.get("/admin/config/stub").then((r) => {
      form.setFieldsValue({
        stub_mode: r.data.stub_mode === "true",
        stub_latency_ms: parseInt(r.data.stub_latency_ms) || 10000,
        stub_success_rate: Math.round(parseFloat(r.data.stub_success_rate) * 100) || 80,
      });
    }).finally(() => setLoading(false));
  }, []);

  const handleSave = async (values: any) => {
    try {
      await api.put("/admin/config/stub", {
        stub_mode: values.stub_mode,
        stub_latency_ms: values.stub_latency_ms,
        stub_success_rate: values.stub_success_rate / 100,
      });
      message.success("Stub config saved");
    } catch {
      message.error("Save failed");
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.post("/admin/stub/test-job");
      setTestResult(res.data);
    } catch {
      message.error("Test job failed");
    } finally {
      setTesting(false);
    }
  };

  if (loading) return <Spin />;

  return (
    <>
      <Title level={4}>Stub Controls</Title>
      <Card style={{ maxWidth: 600 }}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="stub_mode" label="Stub Mode" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="stub_latency_ms" label="Latency (ms)">
            <Slider min={1000} max={30000} step={500} tooltip={{ formatter: (v) => `${v}ms` }} />
          </Form.Item>
          <Form.Item name="stub_success_rate" label="Success Rate (%)">
            <Slider min={0} max={100} tooltip={{ formatter: (v) => `${v}%` }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit">Save Config</Button>
          </Form.Item>
        </Form>
      </Card>

      <Card style={{ maxWidth: 600, marginTop: 16 }} title="Test Job">
        <Button onClick={handleTest} loading={testing} type="default">
          Create Test Job
        </Button>
        {testResult && (
          <Descriptions style={{ marginTop: 16 }} bordered size="small" column={1}>
            <Descriptions.Item label="Job ID">{testResult.job_id}</Descriptions.Item>
            <Descriptions.Item label="Status">
              <Tag color={testResult.status === "queued" ? "blue" : "red"}>{testResult.status}</Tag>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Card>
    </>
  );
}
