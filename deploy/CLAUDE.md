# 새 서버 구축 작업 지침 (Claude Code 용)

이 폴더(`deploy/`)는 새 VM 에 구글시트 웹훅 서버를 만드는 스크립트와 가이드입니다.
**작업 순서는 `README.md` 를 그대로 따르세요.** 이 파일은 그 작업의 규칙과 배경입니다.
접속은 SSH 키 없이 root 비밀번호를 쓰는 단순한 방식이며, `01_bootstrap.sh` 는 `ADMIN_USER`/`ADMIN_SSH_PUBKEY` 없이 실행합니다.

> 이 저장소는 공개이고 GitHub Pages 로 서비스됩니다. **이 파일과 저장소에는 비밀 값, IP, 비밀번호를 적지 마세요.**

## 시스템 구조 (배경)

- 구글시트(Apps Script)가 `POST http://서버:5000/run` 으로 호출 → 서버의 `webhook.py` 가 스크립트를 실행 → 시트 갱신.
- 실패하면 서버가 **500** 을 돌려주고, Apps Script 가 **GitHub Actions 백업**으로 전환합니다.
- 웹훅 서버 코드는 별도 저장소 `catfiestagitsheet235` 에 있고 `01_bootstrap.sh` 가 `/root/catfiestagitsheet235` 에 clone 합니다.
- 서비스: `webhook.service`(systemd, 포트 5000, 부팅 시 자동 시작), venv `/root/myproject/venv`.
- `modify_*` 스크립트는 Chrome + selenium 을 씁니다 (chromedriver 는 selenium 이 자동으로 받음, 인터넷 필요).
- 작업 이름: `nickdate`, `image`, `m_html_one`, `m_html_two`, `m_normal_bl`.

## 절대 하지 말 것

1. **`.env`, `credentials.json` 의 내용을 읽거나 출력하지 마세요.** 존재 여부, 키 이름, 파일 권한(`600`)만 확인합니다. 로그에도, 커밋에도 넣지 마세요.
2. **방화벽(`ufw`)과 SSH 설정을 바꾸기 전에** 무엇을 바꾸는지 설명하고 승인을 받으세요. `ufw enable` 전에 `22/tcp` 가 허용되어 있는지 반드시 확인합니다 (root 비밀번호 접속이 끊기면 업체 웹 콘솔로만 들어갈 수 있음). `02_harden_ssh.sh` 는 평소 쓰지 않는 스크립트이므로 사용자가 요청하지 않으면 실행하지 마세요. 보안 관련 정보는 그 파일 상단 주석에 모아 두었습니다.
3. **실제 시트를 대상으로 작업을 실행하지 마세요.** `image` 는 J열, `nickdate` 는 F/G열을 덮어쓰고, `m_*` 는 카페 글을 수정합니다. 웹훅 테스트는 **잘못된 토큰으로 401 이 오는지**까지만 하고, 진짜 토큰 호출은 사용자가 테스트용 탭을 지정했을 때만 합니다.
4. **`git push` 를 하지 마세요.** `catfiestagitsheet235` 는 push 를 일부러 막아 둔 저장소입니다. `catfiestasite` 는 사용자가 요청할 때만 push 합니다.
5. **커밋 기록에는 사용자 본인만 남기세요.** 커밋 전에 `git config user.name`/`user.email` 을 확인하고(비어 있으면 서버 기본 이메일이 기록되어 무관한 GitHub 계정이 작성자로 표시됨), `Co-Authored-By` 를 넣지 마세요.
6. **비밀 값을 채팅에 붙여넣으라고 요청하지 마세요.** 파일은 사용자가 `scp` 나 `nano` 로 직접 넣습니다.
7. `rm -rf`, 서비스 삭제, 서버 재부팅/종료처럼 **되돌리기 어려운 작업**은 실행 전에 확인을 받으세요.

## 작업 방식

- 각 단계를 시작하기 전에 무엇을 할지 짧게 알리고, 스크립트는 **`DRY_RUN=1` 로 먼저** 실행하세요.
- 단계가 끝나면 결과를 명령으로 확인하고 보고하세요.
  `systemctl is-active webhook` / `ss -ltn | grep 5000` / `ufw status` / `fail2ban-client status sshd`
- 오류가 나면 추측하지 말고 로그부터 보세요. `journalctl -u webhook -n 50 --no-pager`
- **확인하지 못한 것은 못 했다고 말하세요.** 실행하지 않은 것을 됐다고 하지 마세요.

## 알려진 함정 (이전 서버에서 실제로 겪은 것)

| 상황 | 내용 |
|---|---|
| `fail2ban` 이 공격을 못 잡음 | OpenSSH 9.8+ 는 로그인 실패를 `sshd-session` 프로세스가 기록합니다. `journalmatch = _SYSTEMD_UNIT=ssh.service` 로 넓혀야 합니다 (스크립트에 반영됨) |
| 차단 목록이 안 보임 | `fail2ban` 은 nftables 로 차단해서 `iptables -S` 에 안 나옵니다. `nft list ruleset` 로 확인 |
| 웹훅이 다시 살아남 | `Restart=always` 라서 `kill` 해도 다시 뜹니다. **`systemctl stop webhook`** 을 쓰세요 |
| 웹훅이 시작 직후 죽음 | `.env` 또는 `credentials.json` 이 없을 때. 시작할 때 읽습니다 |
| 인증이 약함 | `WEBHOOK_SECRET` 이 없으면 기본값 `changeme` 로 동작합니다. `.env` 값에 **따옴표를 넣으면 그대로 값에 포함**됩니다 |
| venv 경로 | `webhook.py` 97행에 `/root/myproject/venv/bin/python3` 가 고정되어 있습니다 |
| 웹훅 응답 | 200 성공 / 500 실패(→ GitHub 백업) / 409 이미 진행 중 / 401 토큰 불일치 / 400 잘못된 요청 |

## 완료 기준

- [ ] `webhook` 이 `active` 이고 `enabled`, 5000 포트 listen, 잘못된 토큰에 **401**
- [ ] `ufw` active (22, 5000 허용), `fail2ban` active
- [ ] 사용자에게 **남은 수동 작업**을 안내: Apps Script 의 `SERVER_URL` 과 `WEBHOOK_SECRET`, 옛 서버 정리 (push 를 쓴다면 GitHub 배포 키 등록)
