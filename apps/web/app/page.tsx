"use client";

import { useEffect, useState } from "react";
import { BookOpen, ChevronRight, CircleAlert, Headphones, MessageCircle, RefreshCw, Sparkles } from "lucide-react";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

type ApiState = "loading" | "ready" | "unavailable";

const routes = [
  { label: "Học theo giáo trình", icon: BookOpen, detail: "Chờ PDF được import và kiểm duyệt" },
  { label: "Ôn tập hôm nay", icon: RefreshCw, detail: "Lịch ôn sẽ xuất hiện sau khi có dữ liệu học" },
  { label: "Luyện nghe", icon: Headphones, detail: "Đang chờ thiết lập nguồn audio" },
  { label: "Gia sư AI", icon: MessageCircle, detail: "Cần cấu hình nhà cung cấp AI ở máy chủ" },
];

export default function DashboardPage() {
  const [apiState, setApiState] = useState<ApiState>("loading");
  const [selectedRoute, setSelectedRoute] = useState(0);

  async function checkApi() {
    setApiState("loading");
    try {
      const response = await fetch(`${apiBaseUrl}/health`, { cache: "no-store" });
      setApiState(response.ok ? "ready" : "unavailable");
    } catch {
      setApiState("unavailable");
    }
  }

  useEffect(() => {
    void checkApi();
  }, []);

  return (
    <main className="app-shell">
      <section className="side-panel" aria-label="Điều hướng học tập">
        <a className="brand" href="#overview" aria-label="Korean Learning Platform, về tổng quan">
          <span className="brand-mark" aria-hidden="true">ㄱ</span>
          <span>Korean<br />Learning Platform</span>
        </a>
        <nav>
          {routes.map(({ label, icon: Icon }, index) => (
            <button
              className={selectedRoute === index ? "nav-item is-active" : "nav-item"}
              key={label}
              onClick={() => setSelectedRoute(index)}
              type="button"
            >
              <Icon aria-hidden="true" size={18} strokeWidth={1.8} />
              {label}
            </button>
          ))}
        </nav>
        <p className="source-note">Mọi nội dung giáo trình sẽ hiển thị nguồn theo quyển, bài và trang.</p>
      </section>

      <section className="workspace" id="overview">
        <header className="topbar">
          <p>Không gian học cá nhân</p>
          <button className="quiet-button" onClick={() => void checkApi()} type="button">
            <RefreshCw aria-hidden="true" size={16} /> Kiểm tra kết nối
          </button>
        </header>

        <div className="intro-grid">
          <div>
            <h1>Học có căn cứ.<br /><span>Tiến bộ có chủ đích.</span></h1>
            <p className="lede">Bắt đầu bằng cách import giáo trình. Khi nguồn học được kiểm duyệt, bài học và lịch ôn sẽ được tạo từ dữ liệu có xuất xứ rõ ràng.</p>
          </div>
          <div className="hanja-card" aria-label="Câu chào tiếng Hàn">
            <p>오늘의 첫걸음</p>
            <strong>Bước đầu hôm nay</strong>
          </div>
        </div>

        <section className="connection-card" aria-live="polite">
          <div>
            <span className={`status-dot ${apiState}`} aria-hidden="true" />
            <p><strong>{apiState === "ready" ? "API đã sẵn sàng" : apiState === "loading" ? "Đang kiểm tra API" : "Chưa thể kết nối API"}</strong><br />{apiState === "unavailable" ? "Hãy chạy FastAPI tại cổng 8000 hoặc kiểm tra biến NEXT_PUBLIC_API_BASE_URL." : "Trạng thái kết nối được kiểm tra trực tiếp từ máy chủ."}</p>
          </div>
          {apiState === "unavailable" && <CircleAlert aria-label="Cần kiểm tra máy chủ" size={22} />}
        </section>

        <section className="study-grid" aria-label="Lối tắt học tập">
          {routes.map(({ label, icon: Icon, detail }, index) => (
            <button className={selectedRoute === index ? "study-path selected" : "study-path"} key={label} type="button" onClick={() => setSelectedRoute(index)}>
              <Icon aria-hidden="true" size={22} strokeWidth={1.6} />
              <span><strong>{label}</strong><small>{detail}</small></span>
              <ChevronRight aria-hidden="true" size={18} />
            </button>
          ))}
        </section>

        <section className="next-step">
          <Sparkles aria-hidden="true" size={20} />
          <div><h2>Bước tiếp theo: đăng ký PDF nguồn</h2><p>Phase 1 đã chuẩn bị API import idempotent. Giao diện quản trị import và pipeline trích xuất/kiểm duyệt sẽ thuộc Phase 2.</p></div>
        </section>
      </section>
    </main>
  );
}
