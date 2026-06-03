import { Card, Col, Row, Statistic, Typography } from "antd";
import { useEffect, useState } from "react";
import api from "../api/client";

const { Title } = Typography;

export default function Dashboard() {
  const [stats, setStats] = useState({ total: 0, queued: 0, processing: 0, done: 0, failed: 0 });

  useEffect(() => {
    api.get("/admin/jobs?per_page=200").then((res) => {
      const jobs = res.data.items;
      setStats({
        total: res.data.total,
        queued: jobs.filter((j: any) => j.status === "queued").length,
        processing: jobs.filter((j: any) => j.status === "processing").length,
        done: jobs.filter((j: any) => j.status === "done").length,
        failed: jobs.filter((j: any) => j.status === "failed").length,
      });
    });
  }, []);

  return (
    <>
      <Title level={4}>Dashboard</Title>
      <Row gutter={16}>
        <Col span={6}><Card><Statistic title="Total Jobs" value={stats.total} /></Card></Col>
        <Col span={6}><Card><Statistic title="Queued" value={stats.queued} /></Card></Col>
        <Col span={6}><Card><Statistic title="Processing" value={stats.processing} /></Card></Col>
        <Col span={6}><Card><Statistic title="Done" value={stats.done} valueStyle={{ color: "#52c41a" }} /></Card></Col>
      </Row>
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={6}><Card><Statistic title="Failed" value={stats.failed} valueStyle={{ color: "#ff4d4f" }} /></Card></Col>
      </Row>
    </>
  );
}
