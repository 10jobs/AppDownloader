# Internal APK Hub

사내망에서 APK 업로드/다운로드와 공지 조회를 제공하는 FastAPI 웹앱입니다.

## 주요 기능
- 일반 사용자: 앱 목록/버전 조회, APK 다운로드, 공지 조회
- 관리자 1계정: 앱 종류 관리, APK 업로드/덮어쓰기/버전 삭제, 공지 등록/수정/노출 전환
- 로그: 관리자 감사 로그 + 다운로드 로그 DB 저장

## 기술 스택
- FastAPI + Jinja2 + SQLite + SQLAlchemy + Alembic
- 인증: 세션 기반 관리자 로그인, Argon2 해시
- 패키지/실행: uv 프로젝트(`pyproject.toml`, `uv.lock`)

## 빠른 시작 (uv)
1. 의존성 동기화
```bash
uv sync
```

2. 환경변수 파일 준비
```bash
cp .env.example .env
```

3. DB 마이그레이션
```bash
uv run alembic upgrade head
```

4. 관리자 계정 생성(선택)
```bash
uv run python scripts/create_admin.py
```

5. 실행
```bash
uv run uvicorn appdownloader.main:app --host 0.0.0.0 --port 8080
```

또는 프로젝트 스크립트 실행:
```bash
uv run appdownloader
```

Windows에서 8080 포트 바인딩 오류(`WinError 10013`)가 발생하면 포트를 5000으로 변경:
```bash
uv run uvicorn appdownloader.main:app --host 0.0.0.0 --port 5000
```

## 테스트
```bash
uv run pytest -q
```

## 다른 PC 설치 체크리스트
### 1) 기존 데이터까지 그대로 이전(권장)
1. 기존 서버에서 프로젝트 폴더 전체를 복사
- `C:\Python\Projects\AppDownloader\`
2. 대상 PC에 동일 경로로 배치
3. 대상 PC에서 아래 명령 실행
```bash
cd /d C:\Python\Projects\AppDownloader
uv sync
uv run alembic upgrade head
uv run uvicorn appdownloader.main:app --host 0.0.0.0 --port 5000
```
4. 접속 확인
- `http://localhost:5000`

### 2) 코드만 배포하고 새로 시작
1. 대상 PC에 Python + uv 설치
2. 저장소 clone 또는 프로젝트 코드 복사
3. `.env` 준비
```bash
copy .env.example .env
```
4. 초기화 및 실행
```bash
uv sync
uv run alembic upgrade head
uv run python scripts/create_admin.py
uv run uvicorn appdownloader.main:app --host 0.0.0.0 --port 5000
```

### 3) 운영 전 점검
1. Windows 방화벽 인바운드에 서비스 포트(예: 5000) 허용
2. 관리자 계정 비밀번호 변경
3. `scripts/backup.ps1` 주기 실행(작업 스케줄러) 설정
4. 사용자 단말에서 `http://서버IP:5000` 접속 테스트

## 운영(Windows)
- NSSM 서비스 등록: `scripts/install_service.ps1`
- 백업 스크립트: `scripts/backup.ps1`

## 기본 URL
- 사용자 홈: `/`
- 관리자 로그인: `/admin/login`
- 관리자 대시보드: `/admin`
- APK 업로드/버전 삭제: `/admin/apks/upload`

## 주의사항
- 1차 배포 기준 HTTP-only(사내망 전용)
- 방화벽/IP 제한은 서버에서 별도 설정 필요
- 기본 관리자 비밀번호는 반드시 변경
- 로그 저장 위치(DB): `data/app.db` (`audit_logs`, `download_logs`)
