# NewsDeliver 프론트엔드

React + TypeScript + Vite로 만든 NewsDeliver 사용자 화면입니다. FastAPI 백엔드의 `/api/v1/*` JSON API를 사용합니다.

```bash
npm install
cp .env.example .env   # VITE_API_URL=백엔드 주소
npm run dev
```

Vercel에 배포할 때는 Root Directory를 `frontend`로 지정하고 환경변수 `VITE_API_URL`에 Render 백엔드 주소를 넣습니다.
