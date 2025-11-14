# 解决前后端数据类型不一致问题
## 使用 openapi-typescript + openapi-fetch（推荐）
cd frontend
npm install openapi-fetch
npm install -D openapi-typescript
// frontend/package.json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "generate-api": "openapi-typescript http://localhost:8000/api/openapi.json -o src/types/api.d.ts",
    "dev:all": "npm run generate-api && npm run dev"
  }
}