# 🛡️ HedgeMate

AI 기반의 리스크 관리 및 포트폴리오 추천 플랫폼입니다. 사용자의 투자 데이터를 분석하여 최적의 헤지 전략을 제안합니다.

## ✨ 주요 기능
- **포트폴리오 OCR 등록**: `Tesseract.js`를 이용해 스크린샷에서 투자 내역을 자동으로 추출합니다.
- **리스크 분석 및 스트레스 테스트**: `Recharts`를 활용한 데이터 시각화로 투자 리스크를 진단합니다.
- **AI 규칙 기반 추천**: 사용자 성향에 맞는 리스크 관리 규칙 및 종목을 추천합니다.
- **반응형 디자인**: 다양한 기기에서 최적화된 UX를 제공합니다.

## 🛠 기술 스택
- **Framework**: React 19, Vite
- **Routing**: React Router 7
- **Visualization**: Recharts
- **OCR**: Tesseract.js
- **Icons**: Lucide React

## 💻 개발 환경 설정

이 프로젝트를 로컬 환경에서 실행하려면 아래 과정을 따라주세요.

### 사전 요구 사항
- [Node.js](https://nodejs.org/) (v18.0.0 이상 권장)
- npm (또는 yarn)

### 설치 (Installation)
```bash
# 저장소 복제
git clone https://github.com/hedgemate2026/hedge.git

# 프로젝트 폴더로 이동
cd hedge

# 의존성 패키지 설치
npm install
```

### 실행 (Usage)
```bash
# 개발 서버 시작
npm run dev
```
브라우저에서 `http://localhost:5173` 접속 시 확인 가능합니다.

### 빌드 (Build)
```bash
# 배포용 파일 생성
npm run build
```

## 📂 주요 프로젝트 구조
- `src/components`: 재사용 가능한 UI 컴포넌트
- `src/pages`: 각 페이지 구성 요소
- `src/utils`: OCR 파싱 등 공통 유틸리티 함수
- `public`: 이미지 및 정적 자산
