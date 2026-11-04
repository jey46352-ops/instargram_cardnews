# Claude Code 설정 지시서

이 파일은 Claude Code가 읽고 저장소 `jey46352-ops/instargram_cardnews`를 실행 가능한 상태로 만드는 순서입니다.
사용자는 개발 경험이 많지 않으니, 한 단계씩 진행하면서 쉬운 한국어로 설명해 주세요.

## 원칙
- **키와 토큰 값은 절대 대화창에 입력받지 마세요.** 쿠팡 키나 인스타 토큰을 화면에 붙여 넣게 하지 말고, 사용자가 **별도의 터미널 창**에서 `gh secret set` 명령을 직접 실행하게 안내합니다. 이 명령은 값을 숨긴 채 입력받습니다.
- 명령을 실행하기 전에 무엇을 하는 명령인지 한 줄로 설명합니다.
- 실패하면 오류를 읽고 원인을 고친 뒤 다시 시도합니다. 같은 명령을 무작정 반복하지 마세요.
- 쿠팡 검색 API는 호출 한도가 작습니다. 워크플로 수동 실행은 성공할 때까지 연달아 돌리지 말고, 실패 원인을 고친 뒤에 한 번씩만 실행합니다.

## 0. 준비 확인
1. `gh --version`으로 GitHub CLI가 설치되어 있는지 확인합니다.
   - 없으면 OS에 맞게 설치를 안내합니다. Windows는 `winget install GitHub.cli`, Mac은 `brew install gh`입니다.
2. `gh auth status`로 로그인 상태를 확인합니다.
   - 로그인이 안 되어 있으면 사용자가 터미널에서 `gh auth login`을 직접 실행하게 안내합니다. 선택지는 GitHub.com, HTTPS, 브라우저 로그인입니다.
3. 저장소를 클론합니다: `gh repo clone jey46352-ops/instargram_cardnews`

## 1. Actions와 Pages 켜기
1. 워크플로를 활성화합니다: `gh workflow enable daily-cardnews -R jey46352-ops/instargram_cardnews`
2. Pages를 GitHub Actions 방식으로 켭니다:
   `gh api -X POST repos/jey46352-ops/instargram_cardnews/pages -f build_type=workflow`
   - 이미 켜져 있다는 오류가 나면 아래 명령으로 방식을 바꿉니다:
     `gh api -X PUT repos/jey46352-ops/instargram_cardnews/pages -f build_type=workflow`

## 2. Variables 넣기 (값이 비밀이 아니므로 Claude Code가 직접 실행)
1. 사용자에게 인스타그램 계정 아이디를 물어보고 `IG_HANDLE`에 넣습니다:
   `gh variable set IG_HANDLE -R jey46352-ops/instargram_cardnews --body "@계정아이디"`
2. 실적 구분용 `COUPANG_SUB_ID`를 넣습니다:
   `gh variable set COUPANG_SUB_ID -R jey46352-ops/instargram_cardnews --body "insta"`

## 3. 쿠팡 키 넣기 (사용자가 직접 실행)
사용자에게 **새 터미널 창**을 열고 아래 두 명령을 하나씩 실행하게 안내합니다. 각 명령을 실행하면 값을 붙여 넣으라는 칸이 나오고, 붙여 넣은 값은 화면에 보이지 않습니다.
```
gh secret set COUPANG_ACCESS_KEY -R jey46352-ops/instargram_cardnews
gh secret set COUPANG_SECRET_KEY -R jey46352-ops/instargram_cardnews
```
키는 쿠팡파트너스 사이트 → 추가기능 → 파트너스 API에서 확인할 수 있다고 알려 줍니다.
사용자가 완료했다고 하면 `gh secret list -R jey46352-ops/instargram_cardnews`로 이름이 등록됐는지만 확인합니다. 값은 보이지 않는 것이 정상입니다.

## 4. 인스타 자동 게시는 나중에 켜기
인스타 토큰을 발급하는 과정(Meta 개발자 앱 생성)이 가장 어렵기 때문에, 먼저 **카드 생성과 링크 페이지만** 돌아가게 합니다.
1. 이 설정은 워크플로에 **이미 적용되어 있습니다.** `publish` 작업의 조건은 `vars.AUTO_PUBLISH == 'true'`입니다. 따로 고칠 필요가 없고, 확인만 합니다.
   - 이렇게 하면 `AUTO_PUBLISH` 변수가 `true`가 아닌 동안에는 게시 단계를 건너뜁니다.
   - 그 대신 매일 카드 이미지가 `docs/cards/vol-NN/`에 만들어집니다. 사용자는 그 이미지와 `caption.txt`를 내려받아 직접 올리면 됩니다.

## 5. 첫 실행과 확인
1. `gh workflow run daily-cardnews -R jey46352-ops/instargram_cardnews -f publish=false`
2. `gh run watch -R jey46352-ops/instargram_cardnews`로 끝날 때까지 지켜봅니다.
3. 실패하면 `gh run view --log-failed -R jey46352-ops/instargram_cardnews`로 오류를 읽고 원인을 고칩니다. 자주 나오는 원인은 아래와 같습니다.
   - 쿠팡 키 오류(401/403): 키를 다시 넣게 안내합니다. 연속 실행은 하지 않습니다.
   - "상품을 3개 이상 찾지 못해": `data/topics.json`의 해당 주제 키워드를 더 일반적인 단어로 바꿉니다.
   - Pages 배포 실패: 1-2단계를 다시 확인합니다.
4. 성공하면 다음을 확인합니다.
   - `git pull` 후 `docs/cards/vol-01/` 이미지 7장이 있는지 보고, 사용자에게 이미지를 열어 보라고 안내합니다.
   - 링크 페이지 https://jey46352-ops.github.io/instargram_cardnews/ 가 열리는지 확인합니다.
5. 사용자에게 인스타 프로필 링크에 위 주소를 등록하라고 안내합니다.

## 6. (나중에) 인스타 자동 게시 켜기
사용자가 원할 때 아래 순서로 안내합니다.
1. 인스타 계정을 프로페셔널(비즈니스 또는 크리에이터) 계정으로 전환합니다.
2. developers.facebook.com에서 앱을 만들고 Instagram API 제품을 추가합니다. 사용 사례는 "Instagram에서 메시지 및 콘텐츠 관리"입니다.
3. 인스타 계정을 연결하고 장기 액세스 토큰과 Instagram 사용자 ID를 발급받습니다.
4. 사용자가 새 터미널 창에서 직접 아래 명령을 실행합니다:
   `gh secret set IG_ACCESS_TOKEN -R jey46352-ops/instargram_cardnews`
   `gh secret set IG_USER_ID -R jey46352-ops/instargram_cardnews`
5. Instagram 로그인 방식으로 받은 토큰이라면 아래 변수도 넣습니다:
   `gh variable set IG_GRAPH_BASE -R jey46352-ops/instargram_cardnews --body "https://graph.instagram.com/v21.0"`
6. 자동 게시를 켭니다: `gh variable set AUTO_PUBLISH -R jey46352-ops/instargram_cardnews --body "true"`
7. 토큰은 약 60일마다 갱신해야 한다고 알려 줍니다.
