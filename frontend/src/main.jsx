import React, { lazy, Suspense } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

const archiveRoute = window.location.pathname.startsWith("/archive");
const ArchiveApp = archiveRoute ? lazy(() => import("./ArchiveApp")) : null;
const root = createRoot(document.getElementById("root"));

root.render(
  archiveRoute ? (
    <Suspense fallback={<main>일자별 리포트를 불러오는 중입니다.</main>}>
      <ArchiveApp />
    </Suspense>
  ) : (
    <App />
  ),
);
