import { Button, Card, Typography, Upload, message, Spin } from "antd";
import { UploadOutlined, DeleteOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import api from "../api/client";

const { Title, Text } = Typography;

export default function OnboardingVideo() {
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/config/onboarding-video");
      setVideoUrl(res.data.url ?? null);
    } catch {
      message.error("Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const form = new FormData();
      form.append("video", file);
      const res = await api.post("/admin/config/onboarding-video", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setVideoUrl(res.data.url);
      message.success("Video uploaded!");
    } catch {
      message.error("Upload failed");
    } finally {
      setUploading(false);
    }
    return false; // prevent default upload
  };

  const handleDelete = async () => {
    try {
      await api.delete("/admin/config/onboarding-video");
      setVideoUrl(null);
      message.success("Video deleted");
    } catch {
      message.error("Failed");
    }
  };

  return (
    <Spin spinning={loading}>
      <Title level={4} style={{ marginBottom: 24 }}>Onboarding Background Video</Title>
      <Text type="secondary" style={{ display: "block", marginBottom: 16 }}>
        This video plays fullscreen in the background on the onboarding and paywall screens.
        Upload a vertical video (9:16) for best results. Supports MP4 and GIF.
      </Text>

      <Card style={{ maxWidth: 420 }}>
        {videoUrl ? (
          <>
            <video
              src={videoUrl}
              autoPlay
              loop
              muted
              playsInline
              style={{
                width: "100%",
                borderRadius: 8,
                marginBottom: 16,
                maxHeight: 500,
                objectFit: "cover",
              }}
            />
            <div style={{ display: "flex", gap: 8 }}>
              <Upload
                accept="video/mp4,image/gif"
                showUploadList={false}
                beforeUpload={handleUpload}
              >
                <Button icon={<UploadOutlined />} loading={uploading}>
                  Replace Video
                </Button>
              </Upload>
              <Button
                danger
                icon={<DeleteOutlined />}
                onClick={handleDelete}
              >
                Delete
              </Button>
            </div>
          </>
        ) : (
          <Upload
            accept="video/mp4,image/gif"
            showUploadList={false}
            beforeUpload={handleUpload}
            style={{ display: "block" }}
          >
            <Button
              type="primary"
              icon={<UploadOutlined />}
              loading={uploading}
              size="large"
              block
            >
              Upload Background Video
            </Button>
          </Upload>
        )}
      </Card>

      <div style={{ marginTop: 16, color: "#888", fontSize: 12 }}>
        Recommended: vertical MP4, 9:16 ratio, under 20MB for fast loading.
      </div>
    </Spin>
  );
}
