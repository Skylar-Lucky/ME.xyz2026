import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { MemoryMapPage } from "./features/memory-map";
const authHeaders=():Record<string,string>=>{const token=localStorage.getItem("mexyz_token");return token?{Authorization:`Bearer ${token}`}:{ };};
createRoot(document.getElementById("root")!).render(<StrictMode><BrowserRouter basename="/memory-map"><Routes>
  <Route path="/" element={<MemoryMapPage apiBaseUrl={window.location.origin} getAuthHeaders={authHeaders}/>}/><Route path="*" element={<Navigate to="/"/>}/>
</Routes></BrowserRouter></StrictMode>);
