import { Card, Form, Input, Button, message, Typography, Spin } from "antd";
import { useEffect, useState } from "react";
import api from "../api/client";

const { Title } = Typography;

export default function Models() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/admin/config/models").then((r) => {
      form.setFieldsValue({ ai_endpoint: r.data.ai_endpoint, ai_token: r.data.ai_token });
    }).finally(() => setLoading(false));
  }, []);

  const handleSave = async (values: any) => {
    try {
      await api.put("/admin/config/models", values);
      message.success("Model config saved");
    } catch {
      message.error("Save failed");
    }
  };

  const handleTest = async () => {
    const endpoint = form.getFieldValue("ai_endpoint");
    if (!endpoint) { message.warning("No endpoint set"); return; }
    try {
      await api.get(endpoint);
      message.success("Connection OK");
    } catch (e: any) {
      message.error(`Connection failed: ${e.message}`);
    }
  };

  if (loading) return <Spin />;

  return (
    <>
      <Title level={4}>AI Models Config</Title>
      <Card style={{ maxWidth: 600 }}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="ai_endpoint" label="AI Endpoint">
            <Input placeholder="https://api.example.com/v1/generate" />
          </Form.Item>
          <Form.Item name="ai_token" label="API Token">
            <Input.Password placeholder="sk-..." />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" style={{ marginRight: 8 }}>Save</Button>
            <Button onClick={handleTest}>Test Connection</Button>
          </Form.Item>
        </Form>
      </Card>
    </>
  );
}
