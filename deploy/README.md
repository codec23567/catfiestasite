# 새 서버(VM) 구축 가이드

구글시트 자동화를 처리하는 웹훅 서버를 새 VM 에 만드는 방법입니다.
`01_bootstrap.sh` 가 자동으로 하는 것과, 사람이 직접 해야 하는 것을 나눴습니다.

| 파일 | 역할 |
|---|---|
| `01_bootstrap.sh` | 초기 세팅 전체 (root 로 실행) |
| `02_harden_ssh.sh` | SSH 비밀번호/root 로그인 차단 (키 접속 확인 후 실행) |
| `requirements-server.txt` | 서버용 Python 패키지 목록 (버전 고정) |
| `CLAUDE.md` | 서버에서 Claude Code 로 진행할 때의 규칙과 배경 (아래 "Claude Code 로 진행하기") |

> 비밀 값(`.env`, `credentials.json`)은 이 저장소에 없습니다. 아래 3단계에서 따로 만들거나 옮깁니다.
> GitHub 웹에서 만든 파일은 실행 권한이 없으므로 **항상 `bash 파일명`** 으로 실행하세요.

## 전체 순서

```
준비 → 1. 초기 세팅(자동) → 2. SSH 강화 → 3. 비밀 파일(.env, credentials.json)
→ 4. 직접 실행해서 확인 후 서비스 시작 → 5. Apps Script 연결 → 6. (선택) catfiestasite 배포 키
→ 7. 전환 테스트 → 8. 이후 개선
```

## 자동으로 설치·설정되는 것 (`01_bootstrap.sh`)

| 구분 | 내용 |
|---|---|
| 시스템 패키지 (apt) | `python3`, `python3-venv`, `python3-pip`, `python3-dev`, `build-essential`, `git`, `curl`, `ca-certificates`, `gnupg`, `ufw`, `fail2ban`, `tzdata`, `unattended-upgrades`, `logrotate` |
| Google Chrome | 공식 `.deb` 설치 (amd64 만 지원). `modify_*` 스크립트의 selenium 이 사용 |
| Python 패키지 | `requirements-server.txt` 37개: `selenium`, `requests`, `beautifulsoup4`, `gspread`, `google-auth`, `Flask` 등 |
| 설정 | 관리자 계정+SSH 키, 방화벽(22·5000), fail2ban, 스왑(RAM 3GB 미만일 때), venv, 저장소 clone, `webhook.service`(부팅 시 자동 시작), 로그 회전 |

- **chromedriver 는 따로 설치하지 않습니다.** selenium 이 처음 실행할 때 알아서 받으므로, **서버가 인터넷에 연결되어 있어야** 하고 첫 실행은 조금 느릴 수 있습니다.
- `python3-dev`, `build-essential` 은 pip 가 C 확장 패키지를 직접 컴파일해야 할 때(예: `gcc failed`, `Python.h: No such file` 오류) 필요해서 미리 넣어 둔 것입니다.

## 준비 (VM 만들기 전)

- [ ] 새 VM 사양: 2 vCPU / RAM 4GB / 디스크 40GB 이상, **Ubuntu 26.04 amd64** (Chrome 이 amd64 만 지원)
- [ ] 내 PC 에 SSH 키가 있는지 확인. 없으면 만들기: `ssh-keygen -t ed25519`
- [ ] 업체가 **제자리 플랜 업그레이드**를 지원하면 새 VM 대신 그것을 먼저 고려 (IP·설정 유지)
- [ ] 옛 서버의 `.env`, `credentials.json` 을 **서버 밖에 백업**해 두었는지 확인 (없어도 3단계 B 로 새로 만들 수 있음)

## 1. 초기 세팅 (자동)

새 서버에 **root** 로 접속해서 (VM 을 만들면 업체가 알려주는 접속 정보):

```bash
apt-get update && apt-get install -y git
git clone https://github.com/codec23567/catfiestasite.git /root/catfiestasite
cd /root/catfiestasite/deploy

# 먼저 할 일만 미리 보기 (아무것도 안 바뀜)
DRY_RUN=1 ADMIN_USER=내이름 ADMIN_SSH_PUBKEY="ssh-ed25519 AAAA... me@pc" bash 01_bootstrap.sh

# 실제 실행 (ADMIN_SSH_PUBKEY 에는 내 PC 의 .pub 파일 내용 한 줄을 그대로 넣기)
ADMIN_USER=내이름 ADMIN_SSH_PUBKEY="ssh-ed25519 AAAA... me@pc" bash 01_bootstrap.sh
```

- 이 폴더는 `catfiestasite` 저장소에 있습니다. 웹훅 서버가 실제로 쓰는 `catfiestagitsheet235` 저장소는 `01_bootstrap.sh` 가 `/root/catfiestagitsheet235` 에 알아서 clone 합니다.
- [ ] 실행이 끝까지 됐는지 확인 (`[오류]` 가 없어야 함)
- [ ] `.env`, `credentials.json` 이 아직 없어서 webhook 은 시작되지 않은 것이 정상

## 2. SSH 강화 (반드시 이 순서)

- [ ] **새 터미널**에서 `ssh 내이름@<새IP>` 로 키 접속 확인
- [ ] 그 터미널에서 `sudo -n true && echo OK` 확인
- [ ] 원래 터미널은 닫지 말고 그대로 둔 채:
      `ADMIN_USER=내이름 CONFIRM_KEY_LOGIN_TESTED=yes bash /root/catfiestasite/deploy/02_harden_ssh.sh`
- [ ] 새 터미널을 하나 더 열어서 다시 접속되는지 확인
- [ ] 잠겼을 때: 업체 웹 콘솔에서 `rm /etc/ssh/sshd_config.d/00-hardening.conf && systemctl reload ssh`

이후 작업은 관리자 계정으로 접속해 `sudo -i` 로 root 가 되어 진행합니다 (root 로그인은 막혀 있음).

## 3. 비밀 파일 (`.env`, `credentials.json`)

두 파일은 **git 으로 옮기지 마세요.** 위치는 `/root/catfiestagitsheet235/` 입니다.

### A. 옛 서버에서 복사

```bash
# 옛 서버에서: 2단계로 root 로그인을 막았다면 관리자 계정의 홈으로 보낸다
scp /root/catfiestagitsheet235/.env /root/catfiestagitsheet235/credentials.json 내이름@<새IP>:~/

# 새 서버에서 (sudo -i 로 root 가 된 뒤): 제자리로 옮긴다
mv /home/내이름/.env /home/내이름/credentials.json /root/catfiestagitsheet235/
```

### B. 새로 만들기 (옛 서버가 없거나 원본이 없을 때)

```bash
cd /root/catfiestagitsheet235

# 임의의 긴 토큰 만들기 → 이 값을 아래 .env 와 5단계 Apps Script 두 곳에 똑같이 넣는다
openssl rand -base64 32

nano .env
```

`.env` 내용:

```
CAT_ID=카페아이디
CAT_PW=카페비밀번호
WEBHOOK_SECRET=위에서_만든_토큰
```

- 한 줄에 `키=값`. **따옴표를 넣지 마세요.** 파서가 따옴표를 벗기지 않아 값에 그대로 포함됩니다.
- **`WEBHOOK_SECRET` 은 반드시 설정하세요.** 없으면 기본값 `changeme` 로 동작해서 누구나 알 수 있는 토큰이 됩니다.

```bash
nano credentials.json     # 구글 서비스 계정 키(JSON) 전체를 붙여넣기
```

- 키 발급: Google Cloud 콘솔 → IAM 및 관리자 → 서비스 계정 → 해당 계정 → 키 → 키 추가 → JSON.
- 시트가 그 서비스 계정 이메일(`client_email`)에 **편집자로 공유**되어 있어야 합니다 (기존 계정이면 이미 되어 있음).
- GitHub Actions 는 같은 내용을 `GOOGLE_CREDENTIALS` 시크릿으로 씁니다. 옛 키를 삭제하고 새 키로 바꿨다면 그 시크릿도 함께 바꿔야 합니다.

### 공통

```bash
chmod 600 /root/catfiestagitsheet235/.env /root/catfiestagitsheet235/credentials.json
```

- [ ] **`WEBHOOK_SECRET` 을 새 값으로 교체** 권장 (옛 서버는 비밀번호 로그인이 열려 있었음). 교체하면 Apps Script 의 값도 함께 바꿔야 함
- [ ] (선택) 서비스 계정 키 / 카페 비밀번호 교체

## 4. 직접 실행해서 확인한 뒤 서비스 시작

서비스로 등록하기 전에 먼저 눈으로 확인하면, 문제가 생겼을 때 원인을 좁히기 쉽습니다.

```bash
cd /root/catfiestagitsheet235
/root/myproject/venv/bin/python3 webhook.py
```

`Running on http://127.0.0.1:5000` 같은 줄이 보이면 정상입니다. **새 터미널**을 열어서:

```bash
curl -sS -X POST http://localhost:5000/run -H 'Content-Type: application/json' \
  -d '{"secret":"wrong","workflow":"image","sheet_name":"x"}'
# → {"error":"unauthorized"}  가 나와야 정상 (잘못된 토큰이라 아무 작업도 실행되지 않음)
```

확인이 끝나면 원래 터미널에서 `Ctrl+C` 로 종료하고 서비스로 시작합니다.

```bash
systemctl start webhook
systemctl status webhook              # active (running) 이어야 함
journalctl -u webhook -n 30 --no-pager   # 로그 확인
```

| 증상 | 원인 |
|---|---|
| `FileNotFoundError: ... .env` / `credentials.json` | 3단계를 안 했음 |
| 시작하자마자 종료를 반복 | 위 로그에서 오류 메시지 확인 |
| `Address already in use` | 직접 실행한 `webhook.py` 를 아직 종료하지 않았음 |

## 5. 구글 Apps Script 연결

구글시트 → 확장 프로그램 → Apps Script → 프로젝트 설정 → **스크립트 속성**:

| 속성 | 값 |
|---|---|
| `WEBHOOK_SECRET` | 서버 `.env` 의 값과 **똑같이** |
| `GITHUB_PAT` | GitHub Actions 백업용 토큰 (기존 값 그대로) |

서버를 호출하는 함수 (기존에 있다면 **`SERVER_URL` 만** 새 서버로 바꾸면 됩니다):

```javascript
const SERVER_URL = "http://새서버IP:5000/run";

function callServer(workflow, sheetName) {
  const secret = PropertiesService.getScriptProperties().getProperty("WEBHOOK_SECRET");
  const response = UrlFetchApp.fetch(SERVER_URL, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({ secret: secret, workflow: workflow, sheet_name: sheetName }),
    muteHttpExceptions: true   // 오류 응답(401/500 등)에서도 예외 없이 코드를 받는다
  });
  const code = response.getResponseCode();
  Logger.log(workflow + " / " + sheetName + " → " + code + " " + response.getContentText());
  return code;
}
```

**작업 이름(`workflow`)** 은 서버의 `webhook.py` 에 정의된 값만 쓸 수 있습니다.

| `workflow` | 실행하는 스크립트 | 카페 로그인 | 로그 파일 |
|---|---|---|---|
| `nickdate` | `nickdate/select_organize_nickdate.py` | 아니오 | `logs/nickdate.log` |
| `image` | `image/select_organize_image.py` | 아니오 | `logs/image.log` |
| `m_html_one` | `modify_html_unity_ver/read_host_html_unity.py` | 예 | `logs/modify_html_unity_ver.log` |
| `m_html_two` | `modify_html_unity_ver/read_host_html_unity.py` | 예 | `logs/modify_html_unity_ver.log` |
| `m_normal_bl` | `modify_normal_bl_ver/read_host_normal_bl.py` | 예 | `logs/modify_normal_bl_ver.log` |

**서버의 응답 코드** (서버는 작업이 **끝날 때까지 기다렸다가** 응답합니다. 최대 120초):

| 코드 | 의미 | Apps Script 가 할 일 |
|---|---|---|
| 200 | 작업 성공 | 없음 |
| 500 | 작업 실패 또는 시간초과 | **GitHub Actions 백업으로 전환** |
| 409 | 같은 시트의 같은 작업이 이미 진행 중 | 잠시 후 다시 시도 |
| 401 | `secret` 불일치 | 스크립트 속성 값 확인 |
| 400 | 모르는 `workflow` 이거나 `sheet_name` 없음 | 요청 내용 확인 |

- GitHub 백업 호출 코드는 **기존 Apps Script 의 것을 그대로 유지**하세요. 서버 응답이 200 이 아닐 때 그쪽으로 넘어가는 구조입니다.
- 방화벽에서 **5000 포트가 열려 있어야** 합니다. 구글 서버 IP 는 특정할 수 없어서 IP 로 제한하기 어렵습니다.
- 주소가 `http://` 라서 토큰이 평문으로 오갑니다. 신경 쓰인다면 8단계의 HTTPS 를 적용하세요.

## 6. catfiestasite 저장소 (이 서버에서 쓴다면)

옛 서버는 `~/.ssh/config` 의 `github-catfiestasite` 별칭 + `~/.ssh/catfiestasite_deploy` 배포 키로 push 합니다.
**개인 키를 복사하지 말고 새 서버에서 새로 만드세요.**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/catfiestasite_deploy -N ""
cat ~/.ssh/catfiestasite_deploy.pub     # GitHub > catfiestasite > Settings > Deploy keys 에 등록 (Write 권한)
printf 'Host github-catfiestasite\n    HostName github.com\n    IdentityFile ~/.ssh/catfiestasite_deploy\n' >> ~/.ssh/config
# 1단계에서 이미 /root/catfiestasite 로 clone 했으므로, push 주소만 배포 키 별칭으로 바꾼다
git -C /root/catfiestasite remote set-url --push origin git@github-catfiestasite:codec23567/catfiestasite.git
```

- [ ] 등록 후 이전 서버의 배포 키를 GitHub 에서 삭제

## 7. 전환 테스트

- [ ] Apps Script 의 `SERVER_URL` 을 새 서버로 변경
- [ ] 진짜 토큰으로 호출할 때는 **테스트용 시트 탭**으로 (실제 탭이면 J열, F/G열이 실제로 덮어써짐)
- [ ] 구글시트에서 체크박스를 눌러 한 번 실행하고, 서버 로그에서 정상 완료 확인:
      `tail -n 40 /root/catfiestagitsheet235/logs/image.log` (작업에 맞는 로그 파일, 5단계 표 참고)
- [ ] 하루쯤 옛 서버를 켜 둔 채 관찰 → 이상 없으면 `systemctl disable --now webhook` 후 옛 서버 삭제

## 8. 이후 개선 (선택)

- [ ] **HTTPS**: 도메인 → 새 IP 연결 후 nginx + certbot. 이때 5000 포트는 외부에서 닫고 443 만 열기 (`ufw delete allow 5000/tcp`, `ufw allow 443/tcp`)
- [ ] **gunicorn**: `pip install gunicorn` 후 서비스 `ExecStart` 를
      `.../venv/bin/gunicorn --workers 1 --threads 8 --timeout 180 --bind 0.0.0.0:5000 webhook:app`
      워커는 반드시 **1개**여야 함 (`running_jobs` 중복 실행 방지가 프로세스 메모리에 있음)
- [ ] 웹훅을 root 가 아닌 전용 계정으로 실행 (`webhook.py` 97행의 `/root/myproject/venv/bin/python3` 경로를 `sys.executable` 등으로 바꿔야 함)
- [ ] 완료 후 VM **스냅샷** 만들어 두기

## 직접 만들 때 자주 틀리는 곳

이 스크립트 대신 손으로 구축하거나 옛 요약 가이드를 따라 할 때 조심할 점입니다.

1. **`webhook.py` 를 새로 작성하지 마세요. 저장소에 있는 것을 쓰세요.** 간단한 뼈대(스레드로 던지고 `started` 만 응답)로 만들면 다음이 빠집니다.
   - 실패 시 **500 응답 → GitHub 백업 전환**이 동작하지 않음
   - 같은 시트·작업의 **중복 실행 방지**, **120초 시간초과**
   - 인자를 받는 스크립트 실행 (`m_html_one`, `m_html_two`)
2. **venv 경로**: `python3 -m venv /root/myproject/venv` 로 만드세요. `~/myproject` 로 만들면 `venv` 폴더가 없어서 `source .../venv/bin/activate` 가 실패합니다. `webhook.py` 97행과 서비스 파일이 이 경로를 씁니다.
3. **`WEBHOOK_SECRET` 이 비어 있으면 인증이 뚫립니다.** 직접 짤 때 `os.environ.get(...)` 결과가 `None` 인 채로 `data.get("secret") != SECRET` 을 비교하면, 요청에 `secret` 을 빼고 보내도 `None != None` 이 거짓이라 통과합니다. 값이 없으면 서버가 시작되지 않게 하세요.
4. **`.env` 값에 따옴표를 넣지 마세요** (3단계 참고).
5. **`chmod 600`** 을 `.env` 와 `credentials.json` **둘 다** 적용하세요.

## 참고: 현재 서버와 다른 점 / 주의

- 타임존은 현재 서버처럼 **UTC** 그대로 둡니다 (`zoneinfo` 를 쓰는 스크립트가 있으니, 필요하면 확인 후 변경)
- Python 은 현재 서버 3.14.4 기준으로 만든 `requirements-server.txt` 를 씁니다. 새 서버의 기본 Python 버전이 다르면 일부 패키지가 안 깔릴 수 있음 (그때는 `pip freeze` 대신 최상위 패키지만 쓰기)
- GitHub Actions 는 GitHub 에서 돌기 때문에 이전과 무관합니다 (`GOOGLE_CREDENTIALS` 시크릿만 서비스 계정 키와 맞춰 두면 됩니다)

## Claude Code 로 진행하기 (선택)

새 서버에 Claude Code 를 설치해서 이 가이드를 대신 실행하게 할 수 있습니다.
같은 폴더의 `CLAUDE.md` 가 규칙(하면 안 되는 일)과 배경(시스템 구조, 알려진 함정)을 알려 줍니다.
설치와 로그인 방법은 Claude Code 공식 문서를 확인하세요.

```bash
cd /root/catfiestasite/deploy
claude
```

예시 요청:

```
이 서버는 새로 만든 Ubuntu VM 입니다. deploy/README.md 를 읽고 1~4단계를 진행해 주세요.
- 각 단계를 실행하기 전에 무엇을 할지 먼저 알려 주세요.
- 01_bootstrap.sh 는 DRY_RUN=1 로 먼저 확인한 뒤 실제로 실행해 주세요.
- 02_harden_ssh.sh 는 제가 새 터미널에서 키 접속을 확인했다고 말하기 전에는 절대 실행하지 마세요.
- .env 와 credentials.json 은 제가 직접 넣을 테니 내용을 읽거나 출력하지 마세요.
- 웹훅은 잘못된 토큰으로 401 이 오는지까지만 테스트해 주세요 (실제 작업은 실행 금지).
```

**주의**

- 서버 안에서 실행되므로 **그 서버의 셸 권한을 갖습니다.** 관리자 계정으로 실행하고 필요한 명령만 `sudo` 로 하세요. 권한 요청을 **자동 승인하지 말고**, 방화벽과 SSH 설정은 내용을 확인한 뒤 승인하세요.
- **비밀 값을 대화에 붙여넣지 마세요.** 대화는 기록으로 남습니다. `nano` 나 `scp` 로 직접 넣으세요.
- 작업이 끝나면 **로그아웃하거나 API 키를 삭제**하세요.
- 새 Claude Code 는 이전 대화를 기억하지 못합니다. 이 폴더의 파일이 유일한 정보입니다.
- 사람이 직접 해야 하는 일: VM 생성, 서비스 계정 키 발급, GitHub 배포 키 등록, Apps Script 수정, **새 터미널에서 키 접속 확인**.
