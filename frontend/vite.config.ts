import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({plugins:[react()],server:{proxy:{"/api":{target:"http://localhost:8000",changeOrigin:true},"/health":{target:"http://localhost:8000"},"/ready":{target:"http://localhost:8000"}}},test:{globals:true,environment:"jsdom",setupFiles:["./src/test.ts"],exclude:["e2e/**","node_modules/**"]}});
