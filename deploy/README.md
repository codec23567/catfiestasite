# 새 VM 이전 체크리스트

이 폴더(`deploy/`)의 스크립트로 새 서버를 만드는 방법입니다.
`01_bootstrap.sh` 가 자동으로 하는 것 / 사람이 직접 해야 하는 것을 나눴습니다.

| 파일 | 역할 |
|---|---|
| `01_bootstrap.sh` | 초기 세팅 전체 (root 로 실행) |
| `02_harden_ssh.sh` | SSH 비밀번호/root 로그인 차단 (키 접속 확인 후 실행) |
| `requirements-server.txt` | 서버용 Python 패키지 목록 (Flask, selenium 등) |

> 비밀 값(`.env`, `credentials.json`)은 이 저장소에 없습니다. 아래 3번처럼 따로 옮깁니다.
> GitHub 웹에서 만든 파일은 실행 권한이 없으므로 **항상 `bash 파일명`** 으로 실행하세요.

## 준비 (VM 만들기 전)

- [ ] 새 VM 사양: 2 vCPU / RAM 4GB / 디스크 40GB 이상, **Ubuntu 26.04 amd64** (Chrome 이 amd64 만 지원)
- [ ] 내 PC 에 SSH 키가 있는지 확인. 없으면 만들기: `ssh-keygen -t ed25519`
- [ ] 업체가 **제자리 플랜 업그레이드**를 지원하면 새 VM 대신 그것을 먼저 고려 (IP·설정 유지)

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
- [ ] `.env`, `credentials.json` 이 없어서 webhook 은 아직 시작되지 않은 것이 정상

## 2. SSH 강화 (반드시 이 순서)

- [ ] **새 터미널**에서 `ssh 내이름@<새IP>` 로 키 접속 확인
- [ ] 그 터미널에서 `sudo -n true && echo OK` 확인
- [ ] 원래 터미널은 닫지 말고 그대로 둔 채:
      `ADMIN_USER=내이름 CONFIRM_KEY_LOGIN_TESTED=yes bash /root/catfiestasite/deploy/02_harden_ssh.sh`
- [ ] 새 터미널을 하나 더 열어서 다시 접속되는지 확인
- [ ] 잠겼을 때: 업체 웹 콘솔에서 `rm /etc/ssh/sshd_config.d/00-hardening.conf && systemctl reload ssh`

## 3. 비밀 파일 옮기기 (수동, git 으로 옮기지 말 것)

옛 서버에서 (내 PC 를 거치거나, 서버끼리 직접):

```bash
scp /root/catfiestagitsheet235/.env /root/catfiestagitsheet235/credentials.json <새IP 접속정보>:/root/catfiestagitsheet235/
# 새 서버에서
chmod 600 /root/catfiestagitsheet235/.env /root/catfiestagitsheet235/credentials.json
systemctl start webhook
```

- [ ] **`WEBHOOK_SECRET` 을 새 값으로 교체** 권장 (옛 서버는 비밀번호 로그인이 열려 있었음). 교체하면 Apps Script 의 값도 함께 바꿔야 함
- [ ] (선택) 서비스 계정 키 / 카페 비밀번호 교체
- [ ] `systemctl status webhook` 이 `active` 인지 확인

## 4. catfiestasite 저장소 (이 서버에서 쓴다면)

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

## 5. 전환 테스트

- [ ] 방화벽/웹훅 확인: 내 PC 에서 잘못된 토큰으로 호출하면 401 이 와야 정상 (안전한 테스트)
      `curl -sS -X POST http://<새IP>:5000/run -H 'Content-Type: application/json' -d '{"secret":"wrong","workflow":"image","sheet_name":"x"}'`
- [ ] 진짜 토큰으로 호출할 때는 **테스트용 시트 탭**으로 (실제 탭이면 J열이 실제로 덮어써짐)
- [ ] Apps Script 의 웹훅 주소를 새 서버로 변경
- [ ] 실제 시트에서 한 번 실행해서 성공 확인, `/root/catfiestagitsheet235/logs/*.log` 확인
- [ ] 하루쯤 옛 서버를 켜 둔 채 관찰 → 이상 없으면 `systemctl disable --now webhook` 후 옛 서버 삭제

## 6. 이후 개선 (선택)

- [ ] **HTTPS**: 도메인 → 새 IP 연결 후 nginx + certbot. 이때 5000 포트는 외부에서 닫고 443 만 열기 (`ufw delete allow 5000/tcp`, `ufw allow 443/tcp`)
- [ ] **gunicorn**: `pip install gunicorn` 후 서비스 `ExecStart` 를
      `.../venv/bin/gunicorn --workers 1 --threads 8 --timeout 180 --bind 0.0.0.0:5000 webhook:app`
      워커는 반드시 **1개**여야 함 (`running_jobs` 중복 실행 방지가 프로세스 메모리에 있음)
- [ ] 웹훅을 root 가 아닌 전용 계정으로 실행 (`webhook.py` 97행의 `/root/myproject/venv/bin/python3` 경로를 `sys.executable` 등으로 바꿔야 함)
- [ ] 완료 후 VM **스냅샷** 만들어 두기

## 참고: 현재 서버와 다른 점 / 주의

- 타임존은 현재 서버처럼 **UTC** 그대로 둡니다 (`zoneinfo` 를 쓰는 스크립트가 있으니, 필요하면 확인 후 변경)
- Python 은 현재 서버 3.14.4 기준으로 만든 `requirements-server.txt` 를 씁니다. 새 서버의 기본 Python 버전이 다르면 일부 패키지가 안 깔릴 수 있음 (그때는 `pip freeze` 대신 최상위 패키지만 쓰기)
- GitHub Actions 는 GitHub 에서 돌기 때문에 이전과 무관합니다
