# 여행·숙소·캠핑 카드뉴스 자동 생성 + 쿠팡파트너스

매일 19시경 GitHub Actions가 아래 과정을 자동으로 실행합니다.

1. **주제 선정**: 여행 → 숙소 → 캠핑 순서로 돌아가며 `data/topics.json`에서 하나를 고릅니다 (카테고리별 7개, 총 21개).
2. **상품 검색**: 쿠팡파트너스 검색 API로 상품 5개를 찾습니다. 로켓배송 상품을 우선으로 고르고, 응답에 들어 있는 수익 링크를 그대로 씁니다.
3. **카드 렌더링**: 표지, 상품 5장, 마무리 장으로 된 1080×1350 JPEG 7장을 만듭니다.
4. **링크 페이지 갱신**: GitHub Pages에 링크인바이오 페이지를 올립니다. 게시물의 No. 번호 순서대로 쿠팡 링크가 정리됩니다.
5. **인스타 게시**: Instagram Graph API로 캐러셀을 올립니다. 캡션에는 팁, 해시태그, 대가성 문구가 자동으로 들어갑니다.

주제 21개를 다 쓰면 동작이 둘로 나뉩니다.
- `ANTHROPIC_API_KEY`가 있으면 Claude가 새 주제를 만듭니다.
- 키가 없으면 같은 주제를 처음부터 다시 씁니다. 상품은 그날 검색 결과로 새로 바뀝니다.

## 설정 (처음 한 번)

### 1. 저장소 만들기
1. GitHub에서 **Public** 저장소를 새로 만들고, 이 폴더의 파일을 모두 올립니다.
   - 무료 플랜의 GitHub Pages는 공개 저장소에서만 쓸 수 있습니다.
   - 키는 아래의 Secrets에만 넣으므로 저장소가 공개되어도 노출되지 않습니다.
2. **Settings → Pages → Source**를 `GitHub Actions`로 설정합니다.

### 2. Secrets 넣기
**Settings → Secrets and variables → Actions → Secrets**에 아래 값을 넣습니다.

| 이름 | 값 |
|---|---|
| `COUPANG_ACCESS_KEY` | 쿠팡파트너스 Access Key |
| `COUPANG_SECRET_KEY` | 쿠팡파트너스 Secret Key |
| `IG_USER_ID` | 인스타그램 비즈니스 계정 ID (숫자) |
| `IG_ACCESS_TOKEN` | 장기 액세스 토큰 (`instagram_content_publish` 권한 포함) |
| `ANTHROPIC_API_KEY` | 선택 사항. 주제 자동 생성에 씁니다 |

### 3. Variables 넣기
같은 화면의 **Variables** 탭에 아래 값을 넣습니다.

| 이름 | 예시 |
|---|---|
| `IG_HANDLE` | `@trip_camp_pick` (카드 하단과 링크 페이지에 표시) |
| `COUPANG_SUB_ID` | 선택 사항. 채널별 실적 구분용 (예: `insta`) |
| `CARD_ACCENT` | 선택 사항. 포인트 컬러 (기본 `#FFD43B`) |
| `IG_GRAPH_BASE` | 선택 사항. 기본은 `https://graph.facebook.com/v21.0`. Instagram 로그인 방식의 토큰이라면 `https://graph.instagram.com/v21.0` |

### 4. 인스타그램 준비
1. 계정을 **프로페셔널(비즈니스 또는 크리에이터)** 계정으로 전환합니다.
2. Meta for Developers에서 앱을 만들고 콘텐츠 게시 권한을 받습니다.
3. 액세스 토큰은 장기 토큰도 약 60일 뒤에 만료됩니다. 만료 전에 갱신해서 `IG_ACCESS_TOKEN`을 바꿔 주세요.
4. 인스타 **프로필 링크**에 `https://<GitHub아이디>.github.io/<저장소이름>/`을 등록합니다.

### 5. 첫 실행
1. **Actions → daily-cardnews → Run workflow**에서 `publish` 체크를 해제하고 실행합니다.
2. 생성된 `docs/cards/vol-01/`의 이미지와 링크 페이지를 확인합니다.
3. 문제가 없으면 다음 날부터 매일 자동으로 게시됩니다.

## 주의할 점
- **쿠팡 검색 API는 호출 한도가 작습니다.** 수동 실행을 연달아 여러 번 하지 마세요. 1회 실행에 5번을 호출합니다. 한도 초과 오류가 나면 즉시 멈추도록 되어 있습니다.
- 상품을 3개 이상 찾지 못한 날은 게시하지 않고 건너뜁니다.
- 대가성 문구("이 포스팅은 쿠팡 파트너스 활동의 일환으로…")는 마무리 카드, 캡션, 링크 페이지에 모두 자동으로 들어갑니다. 지우지 마세요.
- 키워드, 문구, 순서는 `data/topics.json`에서 바로 고칠 수 있습니다.
- 진행 상태는 `data/state.json`에 저장됩니다. 지우면 Vol.01부터 다시 시작합니다.

## 로컬에서 디자인 확인
```bash
pip install -r requirements.txt && python -m playwright install chromium
python -m src.main generate --mock   # 쿠팡 API 없이 docs/cards/ 에 카드 생성
```
