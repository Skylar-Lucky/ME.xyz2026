import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  base:"/memory-map/",
  plugins:[react()],
  build:{
    outDir:"../../../MExyz-feature/ME_xyz/memory-map",
    emptyOutDir:true,
  },
  server:{port:5173},
});
